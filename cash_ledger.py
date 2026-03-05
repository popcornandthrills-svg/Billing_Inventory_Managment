import json
import os
from datetime import datetime
from utils import app_dir
from audit_log import write_audit_log

# -------------------------------
# Path setup
# -------------------------------
BASE_DIR = app_dir()
DATA_DIR = os.path.join(BASE_DIR, "data")
os.makedirs(DATA_DIR, exist_ok=True)

CASH_LEDGER_FILE = os.path.join(DATA_DIR, "cash_ledger.json")


# -------------------------------
# Load / Save
# -------------------------------
def load_cash_ledger():
    if not os.path.exists(CASH_LEDGER_FILE):
        return []
    with open(CASH_LEDGER_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def save_cash_ledger(data):
    with open(CASH_LEDGER_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4)


# -------------------------------
# ADD CASH ENTRY (CORE FUNCTION)
# -------------------------------
def add_cash_entry(
    date,
    particulars,
    cash_in=0.0,
    cash_out=0.0,
    reference="",
    user="admin"
):
    ledger = load_cash_ledger()

    entry = {
        "date": date,
        "particulars": particulars,
        "cash_in": round(float(cash_in), 2),
        "cash_out": round(float(cash_out), 2),
        "reference": reference
    }

    ledger.append(entry)
    save_cash_ledger(ledger)

    # ---------- AUDIT ----------
    write_audit_log(
        user=user,
        module="cash_ledger",
        action="cash_in" if cash_in > 0 else "cash_out",
        reference=reference,
        before={},
        after=entry
    )

    return entry
