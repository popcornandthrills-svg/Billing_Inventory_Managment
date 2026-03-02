from __future__ import annotations

import os
from datetime import datetime
from typing import Any, Dict, List, Optional

from fastapi import FastAPI, Header, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
from pymongo import DESCENDING, MongoClient
from pymongo.collection import Collection


APP_TITLE = "Inventory Management API (MongoDB)"


class LoginRequest(BaseModel):
    password: str


class TxnItem(BaseModel):
    item: str
    qty: float
    rate: float
    gst: float = 18.0


class SaleCreateRequest(BaseModel):
    customer_name: str
    phone: str
    items: List[TxnItem]
    payment_mode: str = "Cash"
    paid_amount: float = 0.0
    discount_percent: float = 0.0


class PurchaseCreateRequest(BaseModel):
    supplier_name: str
    items: List[TxnItem]
    payment_mode: str = "Cash"
    paid_amount: float = 0.0
    supplier_id: str = ""


class DuePaymentRequest(BaseModel):
    invoice_no: str
    pay_amount: float
    payment_mode: str = "Cash"


def _safe_float(value: Any) -> float:
    try:
        return float(value)
    except Exception:
        return 0.0


def _now_str() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _normalize_mode(value: str) -> str:
    text = str(value or "").strip()
    return text if text else "Cash"


def _mongo_client() -> MongoClient:
    uri = (os.getenv("MONGODB_URI", "") or "").strip()
    if not uri:
        raise HTTPException(status_code=500, detail="MONGODB_URI is not configured.")
    return MongoClient(uri)


def _db_name() -> str:
    return (os.getenv("MONGODB_DB_NAME", "billing_inventory") or "billing_inventory").strip()


def _collection(name: str) -> Collection:
    client = _mongo_client()
    db = client[_db_name()]
    return db[name]


def _role_guard(x_user_role: Optional[str], allowed: List[str]) -> None:
    role = (x_user_role or "").strip().lower()
    allowed_norm = {a.lower() for a in allowed}
    if role not in allowed_norm:
        raise HTTPException(status_code=403, detail="Access denied for this role.")


def _bootstrap_admin() -> None:
    users = _collection("users")
    if users.count_documents({}, limit=1) > 0:
        return
    admin_pwd = (os.getenv("ADMIN_PASSWORD", "admin123") or "admin123").strip()
    users.insert_one(
        {
            "username": "admin",
            "password": admin_pwd,
            "role": "admin",
            "is_active": True,
            "is_deleted": False,
            "created_at": _now_str(),
        }
    )


def _serialize_row(row: Dict[str, Any]) -> Dict[str, Any]:
    out = dict(row)
    out.pop("_id", None)
    return out


def _normalize_sale_items(items: List[TxnItem]) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    for rec in items:
        item = str(rec.item or "").strip()
        qty = _safe_float(rec.qty)
        rate = _safe_float(rec.rate)
        gst = max(0.0, min(_safe_float(rec.gst), 100.0))
        if not item:
            raise HTTPException(status_code=400, detail="Item name is required.")
        if qty <= 0:
            raise HTTPException(status_code=400, detail=f"Quantity must be > 0 for '{item}'.")
        if rate < 0:
            raise HTTPException(status_code=400, detail=f"Rate cannot be negative for '{item}'.")
        taxable = round(qty * rate, 2)
        gst_total = round(taxable * gst / 100.0, 2)
        half = round(gst_total / 2.0, 2)
        total = round(taxable + gst_total, 2)
        rows.append(
            {
                "item": item,
                "qty": qty,
                "rate": rate,
                "gst": gst,
                "taxable": taxable,
                "cgst": half,
                "sgst": round(gst_total - half, 2),
                "igst": 0.0,
                "total": total,
            }
        )
    return rows


def _normalize_purchase_items(items: List[TxnItem]) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    for rec in items:
        item = str(rec.item or "").strip()
        qty = _safe_float(rec.qty)
        rate = _safe_float(rec.rate)
        gst = max(0.0, min(_safe_float(rec.gst), 100.0))
        if not item:
            raise HTTPException(status_code=400, detail="Item name is required.")
        if qty <= 0:
            raise HTTPException(status_code=400, detail=f"Quantity must be > 0 for '{item}'.")
        if rate < 0:
            raise HTTPException(status_code=400, detail=f"Rate cannot be negative for '{item}'.")
        rows.append({"item": item, "qty": qty, "rate": rate, "gst": gst})
    return rows


def _next_series(prefix: str, coll_name: str, field: str) -> str:
    counters = _collection("counters")
    row = counters.find_one_and_update(
        {"_id": f"{coll_name}:{field}"},
        {"$inc": {"value": 1}},
        upsert=True,
        return_document=True,
    )
    number = int((row or {}).get("value", 1))
    return f"{prefix}{number:04d}"


def create_app() -> FastAPI:
    app = FastAPI(title=APP_TITLE, version="1.0.0")

    @app.on_event("startup")
    def startup() -> None:
        _bootstrap_admin()
        _collection("sales").create_index([("date", DESCENDING)])
        _collection("purchases").create_index([("date", DESCENDING)])
        _collection("items").create_index([("item", 1)], unique=True)
        _collection("users").create_index([("username", 1)], unique=True)
        _collection("sales").create_index([("invoice_no", 1)], unique=True)
        _collection("purchases").create_index([("purchase_id", 1)], unique=True)

    @app.get("/")
    def root() -> Dict[str, str]:
        return {"service": "inventory-management-api-mongo", "status": "ok", "docs": "/docs", "app": "/app"}

    @app.get("/health")
    def health() -> Dict[str, str]:
        return {"status": "healthy"}

    @app.post("/auth/login")
    def auth_login(payload: LoginRequest) -> Dict[str, Any]:
        pwd = (payload.password or "").strip()
        if not pwd:
            raise HTTPException(status_code=400, detail="Password is required.")
        user = _collection("users").find_one(
            {"password": pwd, "is_active": {"$ne": False}, "is_deleted": {"$ne": True}}
        )
        if not user:
            raise HTTPException(status_code=401, detail="Invalid credentials.")
        row = _serialize_row(user)
        return {"ok": True, "role": row.get("role", "shop_manager"), "user": row.get("username", "user")}

    @app.get("/dashboard/summary")
    def dashboard_summary() -> Dict[str, Any]:
        sales_rows = list(_collection("sales").find({"cancelled": {"$ne": True}}))
        purchases_rows = list(_collection("purchases").find({}))
        total_sales = sum(_safe_float(s.get("grand_total", 0)) for s in sales_rows)
        total_sales_paid = sum(_safe_float(s.get("paid", s.get("paid_amount", 0))) for s in sales_rows)
        total_sales_due = sum(_safe_float(s.get("due", 0)) for s in sales_rows)
        total_purchase = sum(_safe_float(p.get("grand_total", 0)) for p in purchases_rows)
        total_purchase_paid = sum(_safe_float(p.get("paid_amount", p.get("paid", 0))) for p in purchases_rows)
        total_purchase_due = sum(_safe_float(p.get("due", p.get("due_amount", 0))) for p in purchases_rows)
        stock_value = sum(
            _safe_float(i.get("available_qty", 0)) * _safe_float(i.get("purchase_price", 0))
            for i in _collection("items").find({})
        )
        return {
            "sales": {"count": len(sales_rows), "total": round(total_sales, 2), "paid": round(total_sales_paid, 2), "due": round(total_sales_due, 2)},
            "purchase": {
                "count": len(purchases_rows),
                "total": round(total_purchase, 2),
                "paid": round(total_purchase_paid, 2),
                "due": round(total_purchase_due, 2),
            },
            "stock_value": round(stock_value, 2),
        }

    @app.get("/items/summary")
    def items_summary() -> Dict[str, Any]:
        rows = [_serialize_row(r) for r in _collection("items").find({}).sort("item", 1)]
        return {"count": len(rows), "items": rows}

    @app.get("/sales")
    def sales(limit: int = 1000) -> Dict[str, Any]:
        rows = [_serialize_row(r) for r in _collection("sales").find({}).sort("date", DESCENDING).limit(max(1, min(limit, 5000)))]
        total = _collection("sales").count_documents({})
        return {"count": total, "rows": rows}

    @app.get("/purchases")
    def purchases(limit: int = 1000) -> Dict[str, Any]:
        rows = [_serialize_row(r) for r in _collection("purchases").find({}).sort("date", DESCENDING).limit(max(1, min(limit, 5000)))]
        total = _collection("purchases").count_documents({})
        return {"count": total, "rows": rows}

    @app.post("/sales/create")
    def sales_create(
        payload: SaleCreateRequest,
        x_user_role: Optional[str] = Header(default=None),
        x_user_name: Optional[str] = Header(default=None),
    ) -> Dict[str, Any]:
        _role_guard(x_user_role, ["admin", "shop_manager"])
        if not (payload.customer_name or "").strip() or not (payload.phone or "").strip():
            raise HTTPException(status_code=400, detail="Customer name and phone are required.")
        items = _normalize_sale_items(payload.items)
        gross_total = round(sum(_safe_float(i["total"]) for i in items), 2)
        discount_percent = max(0.0, min(_safe_float(payload.discount_percent), 100.0))
        discount_amount = round(gross_total * discount_percent / 100.0, 2)
        grand_total = round(max(gross_total - discount_amount, 0.0), 2)
        paid = max(0.0, _safe_float(payload.paid_amount))
        due = round(max(grand_total - paid, 0.0), 2)
        invoice_no = _next_series("INV", "sales", "invoice_no")
        row = {
            "invoice_no": invoice_no,
            "date": _now_str(),
            "customer_name": (payload.customer_name or "").strip(),
            "phone": (payload.phone or "").strip(),
            "items": items,
            "gross_total": gross_total,
            "discount_percent": round(discount_percent, 2),
            "discount_amount": discount_amount,
            "grand_total": grand_total,
            "paid": paid,
            "paid_amount": paid,
            "due": due,
            "payment_mode": _normalize_mode(payload.payment_mode),
            "created_by": (x_user_name or "web_user"),
        }
        _collection("sales").insert_one(row)
        items_coll = _collection("items")
        for i in items:
            items_coll.update_one(
                {"item": i["item"]},
                {"$setOnInsert": {"item": i["item"], "purchase_price": 0.0, "selling_price": i["rate"]}, "$inc": {"available_qty": -_safe_float(i["qty"])}},
                upsert=True,
            )
        return {"ok": True, "invoice_no": invoice_no}

    @app.post("/purchases/create")
    def purchases_create(
        payload: PurchaseCreateRequest,
        x_user_role: Optional[str] = Header(default=None),
        x_user_name: Optional[str] = Header(default=None),
    ) -> Dict[str, Any]:
        _role_guard(x_user_role, ["admin"])
        if not (payload.supplier_name or "").strip():
            raise HTTPException(status_code=400, detail="Supplier name is required.")
        items = _normalize_purchase_items(payload.items)
        subtotal = sum(_safe_float(i["qty"]) * _safe_float(i["rate"]) for i in items)
        gst_total = sum((_safe_float(i["qty"]) * _safe_float(i["rate"]) * _safe_float(i.get("gst", 0)) / 100.0) for i in items)
        grand_total = round(subtotal + gst_total, 2)
        paid = max(0.0, _safe_float(payload.paid_amount))
        due = round(max(grand_total - paid, 0.0), 2)
        purchase_id = _next_series("P", "purchases", "purchase_id")
        row = {
            "purchase_id": purchase_id,
            "date": _now_str(),
            "supplier_id": (payload.supplier_id or "").strip(),
            "supplier_name": (payload.supplier_name or "").strip(),
            "items": items,
            "subtotal": round(subtotal, 2),
            "gst_total": round(gst_total, 2),
            "grand_total": round(grand_total, 2),
            "paid_amount": paid,
            "due": due,
            "payment_mode": _normalize_mode(payload.payment_mode),
            "created_by": (x_user_name or "web_user"),
        }
        _collection("purchases").insert_one(row)
        items_coll = _collection("items")
        for i in items:
            items_coll.update_one(
                {"item": i["item"]},
                {
                    "$setOnInsert": {"item": i["item"], "selling_price": _safe_float(i["rate"])},
                    "$set": {"purchase_price": _safe_float(i["rate"])},
                    "$inc": {"available_qty": _safe_float(i["qty"])},
                },
                upsert=True,
            )
        return {"ok": True, "purchase_id": purchase_id}

    @app.post("/sales/pay-due")
    def sales_pay_due(
        payload: DuePaymentRequest,
        x_user_role: Optional[str] = Header(default=None),
        x_user_name: Optional[str] = Header(default=None),
    ) -> Dict[str, Any]:
        _role_guard(x_user_role, ["admin", "shop_manager"])
        invoice_no = (payload.invoice_no or "").strip()
        pay = _safe_float(payload.pay_amount)
        if not invoice_no:
            raise HTTPException(status_code=400, detail="Invoice number is required.")
        if pay <= 0:
            raise HTTPException(status_code=400, detail="Pay amount must be greater than 0.")
        sales_coll = _collection("sales")
        target = sales_coll.find_one({"invoice_no": invoice_no})
        if not target:
            raise HTTPException(status_code=404, detail="Invoice not found.")
        due_before = _safe_float(target.get("due", 0))
        paid_before = _safe_float(target.get("paid", target.get("paid_amount", 0)))
        if due_before <= 0:
            raise HTTPException(status_code=400, detail="No due available for this invoice.")
        if pay > due_before:
            raise HTTPException(status_code=400, detail=f"Pay amount cannot exceed due ({due_before:.2f}).")
        paid_after = round(paid_before + pay, 2)
        due_after = round(max(due_before - pay, 0.0), 2)
        sales_coll.update_one(
            {"invoice_no": invoice_no},
            {
                "$set": {
                    "paid": paid_after,
                    "paid_amount": paid_after,
                    "due": due_after,
                    "last_payment_mode": _normalize_mode(payload.payment_mode),
                    "last_payment_by": (x_user_name or "web_user"),
                }
            },
        )
        return {"ok": True, "invoice_no": invoice_no, "paid": paid_after, "due": due_after}

    @app.get("/app", response_class=HTMLResponse)
    def web_app() -> HTMLResponse:
        return HTMLResponse(
            """
            <!doctype html>
            <html>
            <head>
              <meta charset="utf-8">
              <meta name="viewport" content="width=device-width, initial-scale=1">
              <title>Inventory Management - MongoDB/Vercel</title>
              <style>body{font-family:Segoe UI,Tahoma,sans-serif;padding:20px;background:#f4f7fb} .card{max-width:920px;margin:0 auto;background:#fff;border:1px solid #d8e0ec;border-radius:10px;padding:16px} code{background:#eef4fc;padding:2px 6px;border-radius:6px}</style>
            </head>
            <body>
              <div class="card">
                <h2>Inventory Management API is Live on Vercel</h2>
                <p>Use <code>/docs</code> to test all endpoints.</p>
                <p>This deployment now uses MongoDB via <code>MONGODB_URI</code>.</p>
              </div>
            </body>
            </html>
            """
        )

    return app


app = create_app()

