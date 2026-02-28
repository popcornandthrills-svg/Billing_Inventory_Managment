# item_summary_report.py

import os
import json
import re
from collections import defaultdict
from utils import app_dir

# ================= PATH =================
BASE_DIR = app_dir()
DATA_DIR = os.path.join(BASE_DIR, "data")

PURCHASE_FILE = os.path.join(DATA_DIR, "purchase.json")
SALES_FILE = os.path.join(DATA_DIR, "sales.json")
INVENTORY_FILE = os.path.join(DATA_DIR, "inventory.json")
OVERRIDES_FILE = os.path.join(DATA_DIR, "item_summary_overrides.json")


# ================= LOAD HELPERS =================
def load_json(path):
    if not os.path.exists(path):
        return {} if path in (INVENTORY_FILE, OVERRIDES_FILE) else []
    with open(path, "r", encoding="utf-8") as f:
        try:
            return json.load(f)
        except Exception:
            return {} if path in (INVENTORY_FILE, OVERRIDES_FILE) else []


def save_json(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


def to_float(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def normalize_item_name(value):
    text = str(value or "").strip().lower()
    return re.sub(r"[^a-z0-9]+", "", text)


def find_existing_key(summary, normalized_name):
    if normalized_name in summary:
        return normalized_name

    for key in summary.keys():
        if normalized_name in key or key in normalized_name:
            return key
    return normalized_name


def set_item_summary_override(item_name, available_qty=None, purchase_price=None, selling_price=None):
    key = normalize_item_name(item_name)
    if not key:
        return

    overrides = load_json(OVERRIDES_FILE)
    if not isinstance(overrides, dict):
        overrides = {}

    rec = overrides.get(key, {})
    rec["item"] = str(item_name).strip()

    if available_qty is not None:
        rec["available_qty"] = round(to_float(available_qty), 2)
    if purchase_price is not None:
        rec["purchase_price"] = round(to_float(purchase_price), 2)
    if selling_price is not None:
        rec["selling_price"] = round(to_float(selling_price), 2)

    overrides[key] = rec
    save_json(OVERRIDES_FILE, overrides)


# ================= MAIN REPORT FUNCTION =================
def get_item_summary_report():
    purchases = load_json(PURCHASE_FILE)
    sales = load_json(SALES_FILE)
    inventory = load_json(INVENTORY_FILE)
    overrides = load_json(OVERRIDES_FILE)
    if not isinstance(overrides, dict):
        overrides = {}

    summary = defaultdict(lambda: {
        "label": "",
        "purchase_qty": 0.0,
        "purchase_value": 0.0,
        "sale_qty": 0.0,
        "sale_value": 0.0,
        "inventory_qty": 0.0
    })

    # ===== PURCHASE CALCULATION =====
    for p in purchases:
        items = p.get("items", [])
        for item in items:
            name = item.get("item") or item.get("name")

            if not name:
                continue
            normalized = normalize_item_name(name)
            key = find_existing_key(summary, normalized)
            if not key:
                continue
            qty = to_float(item.get("qty", 0))
            rate = to_float(item.get("rate", 0))

            if not summary[key]["label"]:
                summary[key]["label"] = str(name).strip()

            summary[key]["purchase_qty"] += qty
            summary[key]["purchase_value"] += qty * rate

    # ===== SALES CALCULATION =====
    for s in sales:
        if s.get("cancelled"):
            continue
        items = s.get("items", [])
        for item in items:
            name = item.get("item") or item.get("name")
            if not name:
                continue
            normalized = normalize_item_name(name)
            key = find_existing_key(summary, normalized)
            if not key:
                continue
            qty = to_float(item.get("qty", 0))
            rate = to_float(item.get("rate", 0))

            if not summary[key]["label"]:
                summary[key]["label"] = str(name).strip()

            summary[key]["sale_qty"] += qty
            summary[key]["sale_value"] += qty * rate

    # ===== INVENTORY QTY (fallback / display label source) =====
    for item_name, data in inventory.items():
        normalized = normalize_item_name(item_name)
        key = find_existing_key(summary, normalized)
        if not key:
            continue
        summary[key]["label"] = str(item_name).strip()
        summary[key]["inventory_qty"] = to_float(data.get("stock", 0))

    # ===== FINAL FORMAT =====
    report_rows = []

    labels = {k: (v["label"] or k) for k, v in summary.items()}
    for key in sorted(summary.keys(), key=lambda k: labels[k].lower()):
        data = summary[key]
        purchase_qty = data["purchase_qty"]
        purchase_value = data["purchase_value"]
        sale_qty = data["sale_qty"]
        sale_value = data["sale_value"]

        weighted_purchase_price = round(purchase_value / purchase_qty, 2) if purchase_qty else 0.0
        selling_price = round(sale_value / sale_qty, 2) if sale_qty else 0.0
        txn_available_qty = purchase_qty - sale_qty

        if purchase_qty == 0 and sale_qty == 0:
            available_qty = data["inventory_qty"]
        else:
            available_qty = txn_available_qty

        row = {
            "item": data["label"] or key,
            "available_qty": round(available_qty, 2),
            "purchase_price": weighted_purchase_price,
            "selling_price": selling_price
        }

        ov = overrides.get(key)
        if isinstance(ov, dict):
            if "available_qty" in ov:
                row["available_qty"] = round(to_float(ov.get("available_qty", row["available_qty"])), 2)
            if "purchase_price" in ov:
                row["purchase_price"] = round(to_float(ov.get("purchase_price", row["purchase_price"])), 2)
            if "selling_price" in ov:
                row["selling_price"] = round(to_float(ov.get("selling_price", row["selling_price"])), 2)

        report_rows.append(row)

    return report_rows
