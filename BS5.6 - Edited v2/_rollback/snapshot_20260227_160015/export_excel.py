# export_excel.py
import os
import pandas as pd
from datetime import datetime
from tkinter import messagebox
from sales import load_sales
from utils import app_dir
from purchase import load_purchases
from inventory import get_stock_valuation_summary


# ---------- PATH ----------
BASE_DIR = app_dir()
DATA_DIR = os.path.join(BASE_DIR, "data")
REPORT_DIR = os.path.join(DATA_DIR, "reports")
os.makedirs(REPORT_DIR, exist_ok=True)


def parse_date(d):
    try:
        return datetime.strptime(d, "%Y-%m-%d")
    except Exception:
        return None


def export_purchase_date_filtered(from_date, to_date):
    purchases = load_purchases()
    rows = []

    f_date = parse_date(from_date)
    t_date = parse_date(to_date)

    if not f_date or not t_date:
        messagebox.showerror(
            "Invalid Date",
            "Date format must be YYYY-MM-DD"
        )
        return None

    for p in purchases:
        p_date = parse_date(p.get("date", ""))
        if not p_date or not (f_date <= p_date <= t_date):
            continue

        total = p.get("grand_total", 0)
        paid = p.get("paid_amount", 0)
        due = round(total - paid, 2)
        if due <0:
            due = 0

        for i in p.get("items", []):
            amount = i["qty"] * i["rate"] * (1 + i.get("gst", 0) / 100)

            rows.append({
                "Date": p.get("date"),
                "Supplier": p.get("supplier_name", ""),
                "Item": i.get("item", ""),
                "Qty": i.get("qty", 0),
                "Rate": i.get("rate", 0),
                "GST %": i.get("gst", 0),
                "Amount": round(amount, 2),
                "Purchase Total": total,
                "Paid": paid,
                "Due": due
            })

    if not rows:
        messagebox.showwarning(
            "No Data",
            "No purchases found for selected dates"
        )
        return None

    df = pd.DataFrame(rows)

    file_path = os.path.join(
        REPORT_DIR,
        f"purchase_{from_date}_to_{to_date}.xlsx"
    )

    df.to_excel(file_path, index=False)
    os.startfile(file_path)

    return file_path

def export_purchase_item_date_filtered(item_name, from_date, to_date):
    purchases = load_purchases()
    rows = []

    f_date = parse_date(from_date)
    t_date = parse_date(to_date)

    if not f_date or not t_date:
        messagebox.showerror("Error", "Date format must be YYYY-MM-DD")
        return None

    for p in purchases:
        p_date = parse_date(p.get("date", ""))
        if not p_date or not (f_date <= p_date <= t_date):
            continue

        supplier = p.get("supplier_name", "")
        for i in p.get("items", []):
            if i.get("item") != item_name:
                continue

            amount = i["qty"] * i["rate"] * (1 + i.get("gst", 0) / 100)

            rows.append({
                "Date": p.get("date"),
                "Supplier": supplier,
                "Item": item_name,
                "Qty": i.get("qty", 0),
                "Rate": i.get("rate", 0),
                "GST %": i.get("gst", 0),
                "Amount": round(amount, 2)
            })

    if not rows:
        messagebox.showwarning("No Data", "No records found")
        return None

    file_path = os.path.join(
        REPORT_DIR,
        f"purchase_{item_name}_{from_date}_to_{to_date}.xlsx"
    )

    df = pd.DataFrame(rows)
    df.to_excel(file_path, index=False)
    os.startfile(file_path)
    return file_path


def get_all_purchased_items():
    purchases = load_purchases()
    items = set()

    for p in purchases:
        for i in p.get("items", []):
            if i.get("item"):
                items.add(i["item"])

    return sorted(items)



def export_stock_excel():
    stock_list = get_stock_valuation_summary()

    if not stock_list:
        return None

    rows = []
    for s in stock_list:
        rows.append({
            "Item": s.get("item"),
            "Quantity": s.get("total_qty", 0),
            "Rate": s.get("last_purchase_rate", 0),
            "Value": s.get("total_value", 0)
        })

    df = pd.DataFrame(rows)
    file_path = os.path.join(REPORT_DIR, "stock_report.xlsx")
    df.to_excel(file_path, index=False)
    os.startfile(file_path)
    return file_path


def export_sales_excel():
    sales = load_sales()
    if not sales:
        return None

    df = pd.DataFrame(sales)
    file_path = os.path.join(REPORT_DIR, "sales_report.xlsx")
    df.to_excel(file_path, index=False)
    os.startfile(file_path)
    return file_path

def export_purchase_supplier_filtered(supplier_name):
    purchases = load_purchases()
    rows = []

    for p in purchases:
        supplier = p.get("supplier_name", "")
        if supplier != supplier_name:
            continue

        total = p.get("grand_total", 0)
        paid = p.get("paid_amount", 0)
        due = round(total - paid, 2)
        if due < 0:
            due = 0

        for i in p.get("items", []):
            amount = i["qty"] * i["rate"] * (1 + i.get("gst", 0) / 100)

            rows.append({
                "Date": p.get("date"),
                "Supplier": supplier,
                "Item": i.get("item"),
                "Qty": i.get("qty"),
                "Rate": i.get("rate"),
                "GST %": i.get("gst", 0),
                "Amount": round(amount, 2),
                "Purchase Total": total,
                "Paid": paid,
                "Due": due
            })

    if not rows:
        messagebox.showwarning("No Data", "No purchases for selected supplier")
        return None

    df = pd.DataFrame(rows)
    file_path = os.path.join(
        REPORT_DIR,
        f"purchase_supplier_{supplier_name}.xlsx"
    )
    df.to_excel(file_path, index=False)
    os.startfile(file_path)
    return file_path

def export_due_report_excel():
    sales = load_sales()
    rows = []
    total_due = 0.0

    for s in sales:
        due = float(s.get("due", 0))
        if due > 0:
            rows.append({
                "Invoice No": s.get("invoice_no"),
                "Date": s.get("date"),
                "Customer": s.get("customer_name"),
                "Phone": s.get("phone"),
                "Total": s.get("grand_total"),
                "Paid": s.get("paid"),
                "Due": due
            })
            total_due += due

    if not rows:
        raise Exception("No due data available")

    df = pd.DataFrame(rows)

    # TOTAL ROW
    total_row = {
        "Invoice No": "",
        "Date": "",
        "Customer": "TOTAL",
        "Phone": "",
        "Total": "",
        "Paid": "",
        "Due": total_due
    }
    df.loc[len(df)] = total_row

    file_path = os.path.join(REPORT_DIR, "Customer_Due_Report.xlsx")
    df.to_excel(file_path, index=False)

    os.startfile(file_path)   #  auto open
    
def export_purchase_due_excel():
    purchases = load_purchases()
    rows = []

    for p in purchases:
        total = float(p.get("grand_total", 0))
        paid = float(p.get("paid_amount", 0))
        due = round(total - paid, 2)

        if due > 0:
            rows.append({
                "Supplier": p.get("supplier_name", ""),
                "Invoice No": p.get("purchase_id", ""),
                "Date": p.get("date", ""),
                "Total": total,
                "Due": due
            })

    if not rows:
        messagebox.showwarning("No Data", "No purchase dues found")
        return

    df = pd.DataFrame(rows)

    file_path = os.path.join(
        REPORT_DIR,
        "purchase_due_report.xlsx"
    )

    df.to_excel(file_path, index=False)
    os.startfile(file_path)


def export_purchase_due_supplier_excel(rows):
    if not rows:
        messagebox.showwarning("No Data", "No supplier due data found")
        return None

    df = pd.DataFrame(rows)
    # Keep column names user-friendly and ordered.
    ordered = [
        "supplier",
        "pending_bills",
        "total_due",
        "oldest_due_date",
        "latest_due_date",
    ]
    for col in ordered:
        if col not in df.columns:
            df[col] = ""
    df = df[ordered]
    df.columns = [
        "Supplier",
        "Pending Bills",
        "Total Due",
        "Oldest Due Date",
        "Latest Due Date",
    ]

    stamp = datetime.now().strftime("%Y-%m-%d")
    file_path = os.path.join(REPORT_DIR, f"purchase_due_supplier_summary_{stamp}.xlsx")
    df.to_excel(file_path, index=False)
    os.startfile(file_path)
    return file_path
    
def export_customer_ledger_excel(rows, customer_name):
    if not rows:
        return None
  
    base = app_dir()
    reports_dir = os.path.join(base, "reports")
    os.makedirs(reports_dir, exist_ok=True)

    df = pd.DataFrame(rows)

    safe_name = customer_name.replace(" ", "_") if customer_name else "customer"
    file_path = os.path.join(
        reports_dir,
        f"{safe_name}_ledger.xlsx"
    )

    df.to_excel(file_path, index=False)
    os.startfile(file_path)
    return file_path
  

def export_purchase_report_excel(rows):
    df = pd.DataFrame(rows)

    out_dir = os.path.join(app_dir(), "reports")
    os.makedirs(out_dir, exist_ok=True)

    path = os.path.join(out_dir, "purchase_report.xlsx")
    df.to_excel(path, index=False)

    os.startfile(path)
    
def export_item_summary_excel():
    from item_summary_report import get_item_summary_report
    import pandas as pd
    import os
    from utils import app_dir

    BASE_DIR = app_dir()
    REPORT_DIR = os.path.join(BASE_DIR, "data", "reports")
    os.makedirs(REPORT_DIR, exist_ok=True)

    data = get_item_summary_report()

    if not data:
        return None

    df = pd.DataFrame(data)

    file_path = os.path.join(REPORT_DIR, "item_summary_report.xlsx")
    df.to_excel(file_path, index=False)

    return file_path
