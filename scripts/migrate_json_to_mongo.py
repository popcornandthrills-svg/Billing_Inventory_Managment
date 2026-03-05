import json
import os
from datetime import datetime

from mongo_api import collection, is_configured
from utils import app_dir


DATA_DIR = os.path.join(app_dir(), "data")
FILES = {
    "sales": "sales.json",
    "purchases": "purchase.json",
    "inventory": "inventory.json",
    "customers": "customers.json",
    "suppliers": "suppliers.json",
    "audit_log": "audit_log.json",
    "cash_ledger": "cash_ledger.json",
    "shop_managers": "shop_manager_users.json",
}


def _load_json(path, default):
    if not os.path.exists(path):
        return default
    with open(path, "r", encoding="utf-8") as f:
        try:
            return json.load(f)
        except Exception:
            return default


def _ensure_list(name, data):
    if isinstance(data, list):
        return data
    if isinstance(data, dict):
        if name == "inventory":
            rows = []
            for item_name, rec in data.items():
                if not isinstance(rec, dict):
                    continue
                rows.append(
                    {
                        "item": item_name,
                        "stock": float(rec.get("stock", 0) or 0),
                        "rate": float(rec.get("rate", 0) or 0),
                    }
                )
            return rows
    return []


def migrate(overwrite=False):
    if not is_configured():
        raise RuntimeError("Configure MONGODB_URI and MONGODB_DB_NAME before migration")

    result = {}
    for coll_name, file_name in FILES.items():
        path = os.path.join(DATA_DIR, file_name)
        default = {} if coll_name == "inventory" else []
        data = _load_json(path, default)
        rows = _ensure_list(coll_name, data)

        col = collection(coll_name)
        if overwrite:
            col.delete_many({})
        if rows:
            for r in rows:
                if isinstance(r, dict):
                    r.setdefault("_migrated_at", datetime.utcnow().isoformat())
            col.insert_many(rows)

        result[coll_name] = len(rows)

    return result


if __name__ == "__main__":
    out = migrate(overwrite=True)
    print("Migration complete")
    for k, v in out.items():
        print(f"{k}: {v}")
