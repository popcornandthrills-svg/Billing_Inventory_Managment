import json
import os
from datetime import datetime
from utils import app_dir
from audit_log import write_audit_log

BASE_DIR = app_dir()
DATA_DIR = os.path.join(BASE_DIR, "data")
os.makedirs(DATA_DIR, exist_ok=True)

INVENTORY_FILE = os.path.join(DATA_DIR, "inventory.json")
AUDIT_FILE = os.path.join(DATA_DIR, "audit_log.json")

# -------------------------
# File helpers
# -------------------------
def load_inventory():
    if not os.path.exists(INVENTORY_FILE):
        return {}
    with open(INVENTORY_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def save_inventory(data):
    with open(INVENTORY_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4)


# -------------------------
# STOCK INCREASE
# -------------------------
def add_stock(item_name, qty, rate=0, user="admin", reason="purchase"):
    inv = load_inventory()
    before = inv.get(item_name, {}).copy()

    if item_name in inv:
        inv[item_name]["stock"] += qty
        inv[item_name]["rate"] = rate or inv[item_name]["rate"]
    else:
        inv[item_name] = {
            "stock": qty,
            "rate": rate
        }

    save_inventory(inv)

def write_audit_log(
    user=None,
    module=None,
    action=None,
    reference=None,
    before=None,
    after=None,
    extra=None
):
    log = {
        "user": user,
        "module": module,
        "action": action,
        "reference": reference,
        "before": before,
        "after": after,
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }

    if extra:
        log.update(extra)

    logs = []
    if os.path.exists(AUDIT_FILE):
        try:
            with open(AUDIT_FILE, "r", encoding="utf-8") as f:
                logs = json.load(f)
        except:
            logs = []

    logs.append(log)

    with open(AUDIT_FILE, "w", encoding="utf-8") as f:
        json.dump(logs, f, indent=2)


# -------------------------
# STOCK REDUCE
# -------------------------
def reduce_stock(item_name, qty, user="admin", reason="sale"):
    inv = load_inventory()

    if item_name not in inv:
        raise ValueError(f"Item not found: {item_name}")

    if inv[item_name]["stock"] < qty:
        raise ValueError("Insufficient stock")

    before = inv[item_name].copy()
    inv[item_name]["stock"] -= qty

    save_inventory(inv)

    write_audit_log(
        user=user,
        module="inventory",
        action="stock_reduce",
        reference=item_name,
        before=before,
        after=inv[item_name],
        extra={"reason": reason}
    )


# -------------------------
# STOCK RESTORE (Invoice Cancel)
# -------------------------
def restore_stock(item_name, qty, user="admin", reason="invoice_cancel"):
    inv = load_inventory()
    before = inv.get(item_name, {}).copy()

    if item_name in inv:
        inv[item_name]["stock"] += qty
    else:
        inv[item_name] = {"stock": qty, "rate": 0}

    save_inventory(inv)

    write_audit_log(
        user=user,
        module="inventory",
        action="stock_restore",
        reference=item_name,
        before=before,
        after=inv[item_name],
        extra={"reason": reason}
    )


# -------------------------
# MANUAL ADJUSTMENT
# -------------------------
def adjust_stock(item_name, new_qty, user="admin", note="manual_adjustment"):
    inv = load_inventory()

    before = inv.get(item_name, {}).copy()
    inv[item_name] = {
        "qty": new_qty,
        "rate": before.get("rate", 0)
    }

    save_inventory(inv)
    
   
def get_total_stock_value():
    inv = load_inventory()
    total = 0.0

    for item_name, data in inv.items():
        qty = float(data.get("stock", 0))
        rate = float(data.get("rate", 0))
        total += qty * rate

    return round(total, 2)

def get_stock_valuation_summary():
    """
    Used for stock report / export
    """
    inv = load_inventory()
    summary = []

    for item_name, data in inv.items():
        qty = float(data.get("stock", 0))
        rate = float(data.get("rate", 0))
        total_value = round(qty * rate, 2)

        summary.append({
           "item": item_name,
            "total_qty":qty,
            "last_purchase_rate": rate,
            "total_value": round(total_value)
        })

    return summary

def get_available_items():
    """
    Billing UI item dropdown
    """
    inv = load_inventory()
    return sorted(inv.keys())

def get_item_stock(item_name):
    """
    Used before billing to prevent over-sale
    """
    inv = load_inventory()
    if item_name not in inv:
        return 0
    return float(inv[item_name].get("stock", 0))