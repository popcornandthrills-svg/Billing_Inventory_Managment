import json
import os
from datetime import datetime, timedelta
from inventory import reduce_stock, add_stock, get_item_stock
from utils import app_dir
from audit_log import write_audit_log
from item_summary_report import adjust_item_summary_available_qty, set_item_summary_override



# -------------------------------
# Path setup (EXE safe)
# -------------------------------
BASE_DIR = app_dir()
DATA_DIR = os.path.join(BASE_DIR, "data")
os.makedirs(DATA_DIR, exist_ok=True)

SALES_FILE = os.path.join(DATA_DIR, "sales.json")


# -------------------------------
# File handling
# -------------------------------
def load_sales():
    if not os.path.exists(SALES_FILE):
        return []
    with open(SALES_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def save_sales(data):
    with open(SALES_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4)
        
    
# -------------------------------
# Invoice number
# -------------------------------
def generate_invoice_no(sales):
    if not sales:
        return "INV0001"

    last = sales[-1]["invoice_no"]
    num = int(last.replace("INV", ""))
    return f"INV{num + 1:04d}"


# -------------------------------
# Core sales logic
# -------------------------------
def create_sale(customer_name, phone, items, payment_mode, paid_amount, discount_percent=0.0):
    """
    items = GST-ready items (from gst.py)
    """

    if not customer_name or not phone:
        raise ValueError("Customer name and phone required")

    sales = load_sales()
    invoice_no = generate_invoice_no(sales)

    # ---------------- TOTALS ----------------
    subtotal = sum(i.get("taxable", i["qty"] * i["rate"]) for i in items)
    gst_total = (
        sum(i.get("cgst", 0) for i in items) +
        sum(i.get("sgst", 0) for i in items) +
        sum(i.get("igst", 0) for i in items)
    )
    gross_total = round(sum(i["total"] for i in items), 2)
    try:
        discount_percent = float(discount_percent or 0)
    except (TypeError, ValueError):
        discount_percent = 0.0
    discount_percent = max(0.0, min(discount_percent, 100.0))
    discount_amount = round(gross_total * (discount_percent / 100.0), 2)
    grand_total = round(max(gross_total - discount_amount, 0.0), 2)

    paid = float(paid_amount)
    due = round(grand_total - paid, 2)
    if due < 0:
        due = 0.0
    # ---------------- RECORD ----------------
    record = {
        "invoice_no": invoice_no,
        "date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "customer_name": customer_name,
        "phone": phone,
        "items": items,
        "subtotal": round(subtotal, 2),
        "gst_total": round(gst_total, 2),
        "gross_total": gross_total,
        "discount_percent": round(discount_percent, 2),
        "discount_amount": discount_amount,
        "grand_total": grand_total,
        "paid": paid,
        "paid_amount": paid,
        "due": due,
        "payment_mode": payment_mode
    }

    sales.append(record)
    save_sales(sales)
    
    from cash_ledger import add_cash_entry

    if payment_mode == "Cash" and paid > 0:
        add_cash_entry(
            date=datetime.now().strftime("%Y-%m-%d"),
            particulars=f"Cash Sale {invoice_no}",
            cash_in=paid,
            reference=invoice_no
        )

    # ---------------- STOCK REDUCE ----------------
    for i in items:
        item_name = i.get("item") or i.get("name")
        qty = i["qty"]
        reduce_stock(item_name=item_name, qty=qty)
        # Keep Item Summary available_qty synchronized with sale movement.
        adjust_item_summary_available_qty(item_name, -qty)
        set_item_summary_override(item_name, available_qty=get_item_stock(item_name))

    return invoice_no

def cancel_invoice(invoice_no, reason, user="admin"):
    sales = load_sales()
    target = None

    for s in sales:
        if s["invoice_no"] == invoice_no:
            target = s
            break

    if not target:
        raise ValueError("Invoice not found")

    if target.get("cancelled"):
        raise ValueError("Invoice already cancelled")

    before = {
        "invoice_no": target["invoice_no"],
        "grand_total": target["grand_total"],
        "paid": target["paid"],
        "due": target["due"]
    }

    # STOCK REVERSE
    for item in target.get("items", []):
        item_name = item.get("item") or item.get("name")
        qty = item["qty"]
        add_stock(item_name=item_name, qty=qty, rate=item["rate"])
        # Sync Item Summary quantity on invoice cancellation (stock restore).
        adjust_item_summary_available_qty(item_name, qty)
        set_item_summary_override(item_name, available_qty=get_item_stock(item_name))

    target["cancelled"] = True
    target["cancel_reason"] = reason
    target["cancelled_on"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    save_sales(sales)

    write_audit_log(
        user=user,
        module="sales",
        action="cancel_invoice",
        reference=invoice_no,
        before=before,
        after={
            "cancelled": True,
            "reason": reason
        }
    )

    return True


# -------------------------------
# Customer ledger (date-wise)
# -------------------------------
def get_customer_ledger(phone):
    sales = load_sales()
    ledger = []

    for s in sales:
        if s["phone"] == phone:
            ledger.append({
                "date": s["date"],
                "invoice": s["invoice_no"],
                "total": s["grand_total"],
                "paid": s["paid"],
                "due": s["due"]
            })

    return sorted(ledger, key=lambda x: x["date"], reverse=True)


# -------------------------------
# Due report
# -------------------------------
def get_due_customers():
    sales = load_sales()
    dues = {}

    for s in sales:
        if s["due"] > 0:
            phone = s["phone"]
            dues.setdefault(phone, {
                "customer": s["customer_name"],
                "phone": phone,
                "due": 0.0
            })
            dues[phone]["due"] += s["due"]

    return list(dues.values())


# -------------------------------
# SALES SUMMARY (Dashboard use)
# -------------------------------
def get_sales_summary():
    sales = load_sales()
    total_sales = 0.0
    total_paid = 0.0
    total_due = 0.0

    for s in sales:
        total_sales += s["grand_total"]
        total_paid += s["paid"]
        total_due += s["due"]

    return {
        "total_sales": round(total_sales, 2),
        "total_paid": round(total_paid, 2),
        "total_due": round(total_due, 2),
        "invoice_count": len(sales)
    }


# -------------------------------
# Date-wise sales report
# -------------------------------
def get_sales_by_days(days):
    """
    days = 0 (today), 7, 30, 90, 180, 365
    """
    sales = load_sales()
    cutoff = datetime.now() - timedelta(days=days)

    result = []
    for s in sales:
        sale_date = datetime.strptime(s["date"], "%Y-%m-%d")
        if sale_date >= cutoff:
            result.append(s)

    return result


# -------------------------------
# Flat sales data (Excel friendly)
# -------------------------------
def get_sales_flat_rows():
    rows = []
    for s in load_sales():
        for i in s["items"]:
            rows.append({
                "Invoice": s["invoice_no"],
                "Date": s["date"],
                "Customer": s["customer_name"],
                "Phone": s["phone"],
                "Item": i["item"],
                "Qty": i["qty"],
                "Rate": i["rate"],
                "GST %": i.get("gst", 0),
                "Line Total": i["total"],
                "Invoice Total": s["grand_total"],
                "Paid": s["paid"],
                "Due": s["due"],
                "Payment Mode": s["payment_mode"]
            })
    return rows
