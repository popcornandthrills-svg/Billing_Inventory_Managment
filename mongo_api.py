import os
from functools import lru_cache
from pymongo import MongoClient
from pymongo.errors import PyMongoError
from pymongo import ASCENDING, DESCENDING


@lru_cache(maxsize=1)
def _client():
    uri = (os.getenv("MONGODB_URI") or "").strip()
    if not uri:
        raise RuntimeError("MONGODB_URI is not set")
    return MongoClient(uri, serverSelectionTimeoutMS=5000)


def is_configured() -> bool:
    return bool((os.getenv("MONGODB_URI") or "").strip() and (os.getenv("MONGODB_DB_NAME") or "").strip())


def get_db():
    name = (os.getenv("MONGODB_DB_NAME") or "").strip()
    if not name:
        raise RuntimeError("MONGODB_DB_NAME is not set")
    return _client()[name]


def ping() -> bool:
    try:
        _client().admin.command("ping")
        return True
    except PyMongoError:
        return False


def collection(name: str):
    return get_db()[str(name).strip()]


def ensure_indexes() -> dict:
    db = get_db()
    created = {}

    created["sales"] = [
        db["sales"].create_index([("invoice_no", ASCENDING)], unique=True, name="uq_invoice_no"),
        db["sales"].create_index([("date", DESCENDING)], name="ix_sales_date_desc"),
        db["sales"].create_index([("customer_name", ASCENDING)], name="ix_sales_customer"),
        db["sales"].create_index([("phone", ASCENDING)], name="ix_sales_phone"),
    ]

    created["purchases"] = [
        db["purchases"].create_index([("purchase_id", ASCENDING)], unique=True, name="uq_purchase_id"),
        db["purchases"].create_index([("date", DESCENDING)], name="ix_purchase_date_desc"),
        db["purchases"].create_index([("supplier_name", ASCENDING)], name="ix_purchase_supplier"),
    ]

    created["inventory"] = [
        db["inventory"].create_index([("item", ASCENDING)], unique=True, name="uq_inventory_item"),
    ]

    created["audit_log"] = [
        db["audit_log"].create_index([("timestamp", DESCENDING)], name="ix_audit_ts_desc"),
        db["audit_log"].create_index([("user", ASCENDING)], name="ix_audit_user"),
    ]

    created["cash_ledger"] = [
        db["cash_ledger"].create_index([("date", DESCENDING)], name="ix_cash_date_desc"),
        db["cash_ledger"].create_index([("reference", ASCENDING)], name="ix_cash_ref"),
    ]

    return created
