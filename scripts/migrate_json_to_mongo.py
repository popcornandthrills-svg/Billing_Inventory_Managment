import json
import os
from pathlib import Path
from typing import Any, Dict, Iterable

from pymongo import MongoClient
from pymongo.collection import Collection


def read_json(path: Path):
    if not path.exists():
        return []
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return []


def to_list(value: Any):
    if isinstance(value, list):
        return value
    if isinstance(value, dict):
        return [value]
    return []


def upsert_many(coll: Collection, rows: Iterable[Dict[str, Any]], key_field: str):
    for row in rows:
        if not isinstance(row, dict):
            continue
        key = str(row.get(key_field, "")).strip()
        if not key:
            coll.insert_one(row)
            continue
        coll.update_one({key_field: key}, {"$set": row}, upsert=True)


def main():
    mongo_uri = (os.getenv("MONGODB_URI", "") or "").strip()
    db_name = (os.getenv("MONGODB_DB_NAME", "billing_inventory") or "billing_inventory").strip()
    if not mongo_uri:
        raise SystemExit("MONGODB_URI is required.")

    repo_root = Path(__file__).resolve().parents[1]
    data_dir = repo_root / "BS5.6 - Edited v2" / "data"
    base_dir = repo_root / "BS5.6 - Edited v2"

    sales = to_list(read_json(data_dir / "sales.json"))
    purchases = to_list(read_json(data_dir / "purchase.json"))
    items = to_list(read_json(data_dir / "item_summary.json"))
    users = to_list(read_json(data_dir / "shop_manager_users.json"))

    if not items:
        items = to_list(read_json(base_dir / "item_summary.json"))
    if not users:
        users = to_list(read_json(base_dir / "shop_manager_users.json"))

    client = MongoClient(mongo_uri)
    db = client[db_name]

    upsert_many(db["sales"], sales, "invoice_no")
    upsert_many(db["purchases"], purchases, "purchase_id")
    upsert_many(db["items"], items, "item")

    normalized_users = []
    for idx, u in enumerate(users, start=1):
        if isinstance(u, str):
            normalized_users.append(
                {
                    "username": f"SM-{idx:03d}",
                    "password": u,
                    "role": "shop_manager",
                    "is_active": True,
                    "is_deleted": False,
                }
            )
        elif isinstance(u, dict):
            normalized_users.append(
                {
                    "username": str(u.get("username", f"SM-{idx:03d}")).strip() or f"SM-{idx:03d}",
                    "password": str(u.get("password", "")).strip(),
                    "role": "shop_manager",
                    "is_active": bool(u.get("is_active", True)),
                    "is_deleted": bool(u.get("is_deleted", False)),
                }
            )

    upsert_many(db["users"], normalized_users, "username")
    if db["users"].count_documents({"username": "admin"}) == 0:
        db["users"].insert_one(
            {
                "username": "admin",
                "password": (os.getenv("ADMIN_PASSWORD", "admin123") or "admin123").strip(),
                "role": "admin",
                "is_active": True,
                "is_deleted": False,
            }
        )

    print("Migration completed.")
    print(f"sales={db['sales'].count_documents({})}")
    print(f"purchases={db['purchases'].count_documents({})}")
    print(f"items={db['items'].count_documents({})}")
    print(f"users={db['users'].count_documents({})}")


if __name__ == "__main__":
    main()

