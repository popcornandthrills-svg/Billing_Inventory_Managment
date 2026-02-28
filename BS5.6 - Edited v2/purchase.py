# purchase.py
import json
import os
from datetime import datetime
from utils import app_dir

# ================= PATH =================
BASE_DIR = app_dir()
DATA_DIR = os.path.join(BASE_DIR, "data")
os.makedirs(DATA_DIR, exist_ok=True)

PURCHASE_FILE = os.path.join(DATA_DIR, "purchase.json")


# ================= FILE HELPERS =================
def load_purchases():
    if not os.path.exists(PURCHASE_FILE):
        return []
    with open(PURCHASE_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def save_purchases(data):
    with open(PURCHASE_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4)


# ================= PURCHASE ID =================
def generate_purchase_id(purchases):
    if not purchases:
        return "P0001"
    last = purchases[-1]["purchase_id"]
    num = int(last.replace("P", ""))
    return f"P{num + 1:04d}"


# ================= CORE SAVE =================
def create_purchase(supplier_id, supplier_name, items, payment_type, paid_amount):
    purchases = load_purchases()

    purchase_id = generate_purchase_id(purchases)

    purchase_date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    subtotal = sum(i["qty"] * i["rate"] for i in items)
    gst_total = sum(i["qty"] * i["rate"] * (i.get("gst", 0) / 100) for i in items)
    grand_total = round(subtotal + gst_total, 2)

    paid = float(paid_amount)
    due = round(grand_total - paid, 2)
    if due < 0:
        due = 0.0

    record = {
        "purchase_id": purchase_id,
        "date": purchase_date,
        "supplier_id": supplier_id,
        "supplier_name": supplier_name,
        "items": items,
        "subtotal": round(subtotal, 2),
        "gst_total": round(gst_total, 2),
        "grand_total": round(grand_total, 2),
        "paid_amount": paid,
        "due": due,
        "payment_mode": payment_type
    }

    purchases.append(record)
    save_purchases(purchases)

    # 🔹 Cash Ledger Entry
    if payment_type == "Cash" and paid > 0:
        from cash_ledger import add_cash_entry
        add_cash_entry(
            date=purchase_date,
            particulars=f"Cash Purchase {purchase_id}",
            cash_out=paid,
            reference=purchase_id
        )

    return record
