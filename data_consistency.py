import json
import os
import re
from typing import Dict, List, Tuple

from utils import app_dir


BASE_DIR = app_dir()
DATA_DIR = os.path.join(BASE_DIR, "data")
PURCHASE_FILE = os.path.join(DATA_DIR, "purchase.json")
SALES_FILE = os.path.join(DATA_DIR, "sales.json")
INVENTORY_FILE = os.path.join(DATA_DIR, "inventory.json")
STATE_FILE = os.path.join(DATA_DIR, ".consistency_state.json")


def _load_json(path, default):
    if not os.path.exists(path):
        return default
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default


def _save_json(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4)


def _to_float(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _normalize(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", str(name or "").strip().lower())


def _canonical_name(normalized: str, existing_inventory: Dict, name_map: Dict[str, str], fallback: str) -> str:
    if normalized in name_map:
        return name_map[normalized]

    for inv_name in existing_inventory.keys():
        if _normalize(inv_name) == normalized:
            name_map[normalized] = inv_name
            return inv_name

    canonical = str(fallback or "").strip() or normalized
    name_map[normalized] = canonical
    return canonical


def _sanitize_purchase_records(purchases: List[dict], existing_inventory: Dict, name_map: Dict[str, str]):
    changed = False

    for p in purchases:
        if "date" not in p and p.get("created_on"):
            p["date"] = p["created_on"]
            changed = True

        if not p.get("supplier_name") and p.get("supplier"):
            p["supplier_name"] = p["supplier"]
            changed = True

        if not p.get("payment_mode") and p.get("payment_type"):
            p["payment_mode"] = p["payment_type"]
            changed = True

        if "paid_amount" not in p:
            p["paid_amount"] = _to_float(p.get("paid", 0))
            changed = True

        items = p.get("items", [])
        for item in items:
            raw_name = item.get("item") or item.get("name") or ""
            n = _normalize(raw_name)
            if not n:
                continue

            canonical = _canonical_name(n, existing_inventory, name_map, raw_name)
            if item.get("item") != canonical:
                item["item"] = canonical
                changed = True

            qty = _to_float(item.get("qty", 0))
            rate = _to_float(item.get("rate", 0))
            gst = _to_float(item.get("gst", item.get("gst_percent", 0)))
            total = _to_float(item.get("total", qty * rate * (1 + gst / 100)))

            if item.get("qty") != qty:
                item["qty"] = qty
                changed = True
            if item.get("rate") != rate:
                item["rate"] = rate
                changed = True
            if item.get("gst") != gst:
                item["gst"] = gst
                changed = True
            if item.get("total") != total:
                item["total"] = round(total, 2)
                changed = True

        if "grand_total" not in p:
            p["grand_total"] = round(sum(_to_float(i.get("total", 0)) for i in items), 2)
            changed = True
        if "due" not in p and "due_amount" in p:
            p["due"] = _to_float(p.get("due_amount", 0))
            changed = True
        if "due" not in p:
            p["due"] = round(max(_to_float(p.get("grand_total", 0)) - _to_float(p.get("paid_amount", 0)), 0), 2)
            changed = True

    return changed


def _sanitize_sales_records(sales: List[dict], existing_inventory: Dict, name_map: Dict[str, str]):
    changed = False

    for s in sales:
        items = s.get("items", [])
        for item in items:
            raw_name = item.get("item") or item.get("name") or ""
            n = _normalize(raw_name)
            if not n:
                continue

            canonical = _canonical_name(n, existing_inventory, name_map, raw_name)
            if item.get("item") != canonical:
                item["item"] = canonical
                changed = True

            qty = _to_float(item.get("qty", 0))
            rate = _to_float(item.get("rate", 0))
            gst = _to_float(item.get("gst", item.get("gst_percent", 0)))
            total = _to_float(item.get("total", qty * rate * (1 + gst / 100)))

            if item.get("qty") != qty:
                item["qty"] = qty
                changed = True
            if item.get("rate") != rate:
                item["rate"] = rate
                changed = True
            if "gst" not in item or item.get("gst") != gst:
                item["gst"] = gst
                changed = True
            if item.get("total") != total:
                item["total"] = round(total, 2)
                changed = True

        if "paid" not in s:
            s["paid"] = _to_float(s.get("paid_amount", 0))
            changed = True
        if "due" not in s:
            s["due"] = round(max(_to_float(s.get("grand_total", 0)) - _to_float(s.get("paid", 0)), 0), 2)
            changed = True

    return changed


def _rebuild_inventory(purchases: List[dict], sales: List[dict], existing_inventory: Dict, name_map: Dict[str, str]):
    qty_map: Dict[str, float] = {}
    rate_map: Dict[str, float] = {}

    for p in purchases:
        for item in p.get("items", []):
            item_name = item.get("item") or item.get("name") or ""
            n = _normalize(item_name)
            if not n:
                continue
            canonical = _canonical_name(n, existing_inventory, name_map, item_name)
            qty_map[canonical] = qty_map.get(canonical, 0.0) + _to_float(item.get("qty", 0))
            rate_map[canonical] = _to_float(item.get("rate", 0))

    for s in sales:
        if s.get("cancelled"):
            continue
        for item in s.get("items", []):
            item_name = item.get("item") or item.get("name") or ""
            n = _normalize(item_name)
            if not n:
                continue
            canonical = _canonical_name(n, existing_inventory, name_map, item_name)
            qty_map[canonical] = qty_map.get(canonical, 0.0) - _to_float(item.get("qty", 0))
            rate_map.setdefault(canonical, _to_float(item.get("rate", 0)))

    # Preserve inventory-only items that have no matching purchase/sale history.
    for inv_name, data in existing_inventory.items():
        n = _normalize(inv_name)
        canonical = _canonical_name(n, existing_inventory, name_map, inv_name)
        if canonical not in qty_map:
            qty_map[canonical] = _to_float(data.get("stock", 0))
            rate_map[canonical] = _to_float(data.get("rate", 0))

    rebuilt = {
        name: {
            "stock": round(qty_map.get(name, 0.0), 2),
            "rate": round(rate_map.get(name, 0.0), 2),
        }
        for name in sorted(qty_map.keys(), key=lambda x: x.lower())
    }
    return rebuilt


def ensure_data_consistency() -> Dict[str, int]:
    purchases = _load_json(PURCHASE_FILE, [])
    sales = _load_json(SALES_FILE, [])
    inventory = _load_json(INVENTORY_FILE, {})

    if not isinstance(purchases, list):
        purchases = []
    if not isinstance(sales, list):
        sales = []
    if not isinstance(inventory, dict):
        inventory = {}

    name_map: Dict[str, str] = {}
    purchase_changed = _sanitize_purchase_records(purchases, inventory, name_map)
    sales_changed = _sanitize_sales_records(sales, inventory, name_map)
    rebuilt_inventory = _rebuild_inventory(purchases, sales, inventory, name_map)
    inventory_changed = rebuilt_inventory != inventory

    if purchase_changed:
        _save_json(PURCHASE_FILE, purchases)
    if sales_changed:
        _save_json(SALES_FILE, sales)
    if inventory_changed:
        _save_json(INVENTORY_FILE, rebuilt_inventory)

    return {
        "purchase_records": len(purchases),
        "sales_records": len(sales),
        "inventory_items": len(rebuilt_inventory),
        "purchase_changed": int(purchase_changed),
        "sales_changed": int(sales_changed),
        "inventory_changed": int(inventory_changed),
    }


def _file_signature(path: str) -> Dict[str, float]:
    if not os.path.exists(path):
        return {"exists": 0, "size": 0, "mtime": 0}
    try:
        stat = os.stat(path)
        return {
            "exists": 1,
            "size": int(stat.st_size),
            "mtime": float(stat.st_mtime),
        }
    except Exception:
        return {"exists": 1, "size": 0, "mtime": 0}


def _current_signature() -> Dict[str, Dict[str, float]]:
    return {
        "purchase": _file_signature(PURCHASE_FILE),
        "sales": _file_signature(SALES_FILE),
        "inventory": _file_signature(INVENTORY_FILE),
    }


def ensure_data_consistency_if_needed() -> Dict[str, int]:
    current = _current_signature()
    state = _load_json(STATE_FILE, {})
    if isinstance(state, dict) and state.get("signature") == current:
        return {
            "purchase_records": 0,
            "sales_records": 0,
            "inventory_items": 0,
            "purchase_changed": 0,
            "sales_changed": 0,
            "inventory_changed": 0,
            "skipped": 1,
        }

    result = ensure_data_consistency()
    _save_json(STATE_FILE, {"signature": current})
    result["skipped"] = 0
    return result
