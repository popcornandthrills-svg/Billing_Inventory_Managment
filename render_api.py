from typing import Optional
import os
import json

from fastapi import FastAPI, Header, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel

from data_consistency import ensure_data_consistency
from item_summary_report import get_item_summary_report
from inventory import get_total_stock_value
from purchase import load_purchases
from sales import load_sales
from utils import app_dir


app = FastAPI(
    title="Inventory Management API",
    version="1.0.0",
    description="Render deployment API for the desktop inventory system backend data.",
)


ADMIN_PASSWORD = "admin123"
SHOP_MANAGER_PASSWORD = "sm123"
SHOP_MANAGER_USERS_FILE = os.path.join(app_dir(), "data", "shop_manager_users.json")


class LoginRequest(BaseModel):
    password: str


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


def _load_shop_manager_accounts():
    if not os.path.exists(SHOP_MANAGER_USERS_FILE):
        return []
    try:
        with open(SHOP_MANAGER_USERS_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception:
        return []
    if not isinstance(data, list):
        return []

    # Backward compatibility: list of plain passwords.
    if data and isinstance(data[0], str):
        rows = []
        for idx, pwd in enumerate(data, start=1):
            text = str(pwd or "").strip()
            if not text:
                continue
            rows.append(
                {
                    "username": f"SM-{idx:03d}",
                    "password": text,
                    "is_active": True,
                    "is_deleted": False,
                }
            )
        return rows

    rows = []
    for rec in data:
        if not isinstance(rec, dict):
            continue
        pwd = str(rec.get("password", "")).strip()
        if not pwd:
            continue
        rows.append(
            {
                "username": str(rec.get("username", "")).strip() or "shop_manager",
                "password": pwd,
                "is_active": bool(rec.get("is_active", True)),
                "is_deleted": bool(rec.get("is_deleted", False)),
            }
        )
    return rows


@app.get("/")
def root():
    return {
        "service": "inventory-management-api",
        "status": "ok",
        "docs": "/docs",
        "app": "/app",
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


@app.post("/auth/login")
def auth_login(payload: LoginRequest):
    pwd = (payload.password or "").strip()
    if not pwd:
        raise HTTPException(status_code=400, detail="Password is required.")

    if pwd == ADMIN_PASSWORD:
        return {"ok": True, "role": "admin", "user": "admin123"}
    if pwd == SHOP_MANAGER_PASSWORD:
        return {"ok": True, "role": "shop_manager", "user": "sm123"}

    for acc in _load_shop_manager_accounts():
        if not acc.get("is_active", True) or acc.get("is_deleted", False):
            continue
        if pwd == str(acc.get("password", "")).strip():
            return {
                "ok": True,
                "role": "shop_manager",
                "user": acc.get("username", "shop_manager"),
            }

    raise HTTPException(status_code=401, detail="Invalid credentials.")


@app.get("/app", response_class=HTMLResponse)
def web_app():
    return HTMLResponse(
        """
<!doctype html>
<html>
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Inventory Management Web</title>
  <style>
    :root { --bg:#f3f6fb; --card:#fff; --ink:#12233d; --muted:#5e6d82; --line:#d8e0ec; --brand:#0b4f8a; }
    * { box-sizing:border-box; font-family:Segoe UI, Tahoma, sans-serif; }
    body { margin:0; background:var(--bg); color:var(--ink); }
    .wrap { max-width:1200px; margin:0 auto; padding:16px; }
    .card { background:var(--card); border:1px solid var(--line); border-radius:10px; padding:14px; margin-bottom:12px; }
    h1 { margin:0 0 12px 0; font-size:22px; }
    h2 { margin:0 0 8px 0; font-size:17px; }
    .row { display:flex; gap:10px; flex-wrap:wrap; align-items:center; }
    input, button { padding:10px; border-radius:8px; border:1px solid var(--line); }
    input { min-width:260px; }
    button { background:#0f3359; color:#fff; cursor:pointer; border:0; }
    table { width:100%; border-collapse:collapse; font-size:13px; }
    th, td { border:1px solid var(--line); padding:7px; text-align:left; }
    th { background:#eef4fc; }
    .muted { color:var(--muted); font-size:12px; }
    .kpi { min-width:200px; }
    .hidden { display:none; }
    .scroll { max-height:320px; overflow:auto; }
  </style>
</head>
<body>
  <div class="wrap">
    <div class="card" id="loginCard">
      <h1>Inventory Management - Web Access</h1>
      <div class="row">
        <input type="password" id="pwd" placeholder="Enter password (admin/sm)">
        <button id="loginBtn">Login</button>
      </div>
      <div class="muted" id="loginMsg">Use your existing system password.</div>
    </div>

    <div id="appCard" class="hidden">
      <div class="card">
        <div class="row" style="justify-content:space-between">
          <h1 style="margin:0">Dashboard</h1>
          <div>
            <span id="who" class="muted"></span>
            <button id="logoutBtn" style="margin-left:8px">Logout</button>
          </div>
        </div>
      </div>

      <div class="row">
        <div class="card kpi"><h2>Sales Count</h2><div id="k_sales_count">-</div></div>
        <div class="card kpi"><h2>Sales Total</h2><div id="k_sales_total">-</div></div>
        <div class="card kpi"><h2>Sales Due</h2><div id="k_sales_due">-</div></div>
        <div class="card kpi"><h2>Stock Value</h2><div id="k_stock_value">-</div></div>
      </div>

      <div class="card">
        <h2>Item Summary</h2>
        <div class="scroll">
          <table id="itemsTbl">
            <thead><tr><th>Item</th><th>Available Qty</th><th>Purchase Price</th><th>Selling Price</th></tr></thead>
            <tbody></tbody>
          </table>
        </div>
      </div>

      <div class="card">
        <h2>Recent Sales</h2>
        <div class="scroll">
          <table id="salesTbl">
            <thead><tr><th>Date</th><th>Invoice</th><th>Customer</th><th>Total</th><th>Paid</th><th>Due</th></tr></thead>
            <tbody></tbody>
          </table>
        </div>
      </div>
    </div>
  </div>

  <script>
    const $ = (id) => document.getElementById(id);
    function money(v){ return Number(v||0).toFixed(2); }

    async function loadDashboard() {
      const [summaryR, itemsR, salesR] = await Promise.all([
        fetch('/dashboard/summary'),
        fetch('/items/summary'),
        fetch('/sales?limit=300')
      ]);
      if(!summaryR.ok || !itemsR.ok || !salesR.ok){ throw new Error('Failed to load data'); }
      const summary = await summaryR.json();
      const items = await itemsR.json();
      const sales = await salesR.json();

      $('k_sales_count').textContent = summary.sales.count;
      $('k_sales_total').textContent = money(summary.sales.total);
      $('k_sales_due').textContent = money(summary.sales.due);
      $('k_stock_value').textContent = money(summary.stock_value);

      const itemBody = $('itemsTbl').querySelector('tbody');
      itemBody.innerHTML = '';
      (items.items || []).forEach(r => {
        const tr = document.createElement('tr');
        tr.innerHTML = `<td>${r.item||''}</td><td>${money(r.available_qty)}</td><td>${money(r.purchase_price)}</td><td>${money(r.selling_price)}</td>`;
        itemBody.appendChild(tr);
      });

      const salesBody = $('salesTbl').querySelector('tbody');
      salesBody.innerHTML = '';
      (sales.rows || []).forEach(r => {
        const tr = document.createElement('tr');
        tr.innerHTML = `<td>${r.date||''}</td><td>${r.invoice_no||''}</td><td>${r.customer_name||''}</td><td>${money(r.grand_total)}</td><td>${money(r.paid||r.paid_amount)}</td><td>${money(r.due)}</td>`;
        salesBody.appendChild(tr);
      });
    }

    async function login() {
      const pwd = $('pwd').value.trim();
      if(!pwd){ $('loginMsg').textContent = 'Enter password.'; return; }
      $('loginMsg').textContent = 'Authenticating...';
      const res = await fetch('/auth/login', {
        method: 'POST',
        headers: {'Content-Type':'application/json'},
        body: JSON.stringify({password: pwd})
      });
      if(!res.ok){ $('loginMsg').textContent = 'Invalid credentials.'; return; }
      const data = await res.json();
      localStorage.setItem('im_user', JSON.stringify(data));
      $('who').textContent = `${data.user} (${data.role})`;
      $('loginCard').classList.add('hidden');
      $('appCard').classList.remove('hidden');
      await loadDashboard();
    }

    function logout() {
      localStorage.removeItem('im_user');
      $('appCard').classList.add('hidden');
      $('loginCard').classList.remove('hidden');
      $('pwd').value = '';
      $('loginMsg').textContent = 'Use your existing system password.';
    }

    $('loginBtn').addEventListener('click', login);
    $('logoutBtn').addEventListener('click', logout);
    $('pwd').addEventListener('keydown', (e) => { if(e.key === 'Enter') login(); });

    (async () => {
      const saved = localStorage.getItem('im_user');
      if(!saved) return;
      try {
        const user = JSON.parse(saved);
        $('who').textContent = `${user.user} (${user.role})`;
        $('loginCard').classList.add('hidden');
        $('appCard').classList.remove('hidden');
        await loadDashboard();
      } catch (_) {}
    })();
  </script>
</body>
</html>
"""
    )
