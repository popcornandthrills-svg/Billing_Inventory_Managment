import json
import os
from datetime import datetime

from utils import app_dir


BASE_DIR = app_dir()
DATA_DIR = os.path.join(BASE_DIR, "data")
SUPPLIER_PAYMENTS_FILE = os.path.join(DATA_DIR, "supplier_payments.json")


def load_supplier_payments():
    if not os.path.exists(SUPPLIER_PAYMENTS_FILE):
        return []
    with open(SUPPLIER_PAYMENTS_FILE, "r", encoding="utf-8") as f:
        try:
            return json.load(f)
        except Exception:
            return []


def save_supplier_payments(rows):
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(SUPPLIER_PAYMENTS_FILE, "w", encoding="utf-8") as f:
        json.dump(rows, f, indent=4)


def add_supplier_payment(supplier_name, amount, payment_mode, reference="", note="", due_before=0.0, due_after=0.0):
    rows = load_supplier_payments()
    record = {
        "payment_id": f"SP{len(rows) + 1:05d}",
        "date": datetime.now().strftime("%Y-%m-%d"),
        "supplier_name": supplier_name,
        "amount": float(amount),
        "payment_mode": payment_mode,
        "reference": reference,
        "note": note,
        "due_before": float(due_before),
        "due_after": float(due_after),
    }
    rows.append(record)
    save_supplier_payments(rows)
    return record


def get_supplier_payments(supplier_name):
    target = str(supplier_name or "").strip().lower()
    return [
        p for p in load_supplier_payments()
        if str(p.get("supplier_name", "")).strip().lower() == target
    ]
