from typing import Optional
import os

from fastapi import FastAPI, Header, HTTPException

from data_consistency import ensure_data_consistency
from item_summary_report import get_item_summary_report
from inventory import get_total_stock_value
from purchase import load_purchases
from sales import load_sales


app = FastAPI(
    title="Inventory Management API",
    version="1.0.0",
    description="Render deployment API for the desktop inventory system backend data.",
)


def _safe_float(value):
    try:
        return float(value)
    except Exception:
        return 0.0


def _require_api_key(x_api_key: Optional[str]):
    expected = os.getenv("ADMIN_API_KEY", "").strip()
    # If ADMIN_API_KEY is not configured, allow requests.
    if not expected:
        return
    if (x_api_key or "").strip() != expected:
        raise HTTPException(status_code=401, detail="Invalid API key.")


@app.get("/")
def root():
    return {
        "service": "inventory-management-api",
        "status": "ok",
        "docs": "/docs",
    }


@app.get("/health")
def health():
    return {"status": "healthy"}


@app.post("/admin/reconcile")
def reconcile_data(x_api_key: Optional[str] = Header(default=None)):
    _require_api_key(x_api_key)
    return ensure_data_consistency()


@app.get("/dashboard/summary")
def dashboard_summary():
    sales = load_sales()
    purchases = load_purchases()

    total_sales = sum(_safe_float(s.get("grand_total", 0)) for s in sales if not s.get("cancelled"))
    total_sales_paid = sum(_safe_float(s.get("paid", s.get("paid_amount", 0))) for s in sales if not s.get("cancelled"))
    total_sales_due = sum(_safe_float(s.get("due", 0)) for s in sales if not s.get("cancelled"))

    total_purchase = sum(_safe_float(p.get("grand_total", p.get("total_amount", 0))) for p in purchases)
    total_purchase_paid = sum(_safe_float(p.get("paid_amount", p.get("paid", 0))) for p in purchases)
    total_purchase_due = sum(_safe_float(p.get("due", p.get("due_amount", 0))) for p in purchases)

    return {
        "sales": {
            "count": len([s for s in sales if not s.get("cancelled")]),
            "total": round(total_sales, 2),
            "paid": round(total_sales_paid, 2),
            "due": round(total_sales_due, 2),
        },
        "purchase": {
            "count": len(purchases),
            "total": round(total_purchase, 2),
            "paid": round(total_purchase_paid, 2),
            "due": round(total_purchase_due, 2),
        },
        "stock_value": round(get_total_stock_value(), 2),
    }


@app.get("/items/summary")
def items_summary():
    rows = get_item_summary_report()
    return {"count": len(rows), "items": rows}


@app.get("/sales")
def sales(limit: int = 100):
    data = load_sales()
    return {"count": len(data), "rows": data[: max(1, min(limit, 1000))]}


@app.get("/purchases")
def purchases(limit: int = 100):
    data = load_purchases()
    return {"count": len(data), "rows": data[: max(1, min(limit, 1000))]}
