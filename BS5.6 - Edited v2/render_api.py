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
    h3 { margin:0 0 8px 0; font-size:15px; }
    .row { display:flex; gap:10px; flex-wrap:wrap; align-items:center; justify-content:space-between; }
    input, button { padding:10px; border-radius:8px; border:1px solid var(--line); }
    input { min-width:260px; }
    button { background:#0f3359; color:#fff; cursor:pointer; border:0; }
    button.secondary { background:#fff; color:#123; border:1px solid var(--line); }
    table { width:100%; border-collapse:collapse; font-size:13px; }
    th, td { border:1px solid var(--line); padding:7px; text-align:left; }
    th { background:#eef4fc; }
    .muted { color:var(--muted); font-size:12px; }
    .kpi { min-width:200px; }
    .hidden { display:none; }
    .scroll { max-height:320px; overflow:auto; }
    .tabs { display:flex; gap:8px; flex-wrap:wrap; margin-bottom:10px; }
    .tabbtn { background:#dfe9f7; color:#103a67; border:1px solid #c8d7ec; padding:8px 12px; border-radius:8px; cursor:pointer; }
    .tabbtn.active { background:#0f3359; color:#fff; border-color:#0f3359; }
    .tab { display:none; }
    .tab.active { display:block; }
    .tools { display:flex; gap:8px; flex-wrap:wrap; align-items:center; margin-bottom:8px; }
    .tools input { min-width:240px; }
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

      <div class="card">
        <div class="tabs">
          <button class="tabbtn active" data-tab="summaryTab">Summary</button>
          <button class="tabbtn" data-tab="itemsTab">Items</button>
          <button class="tabbtn" data-tab="salesTab">Sales</button>
          <button class="tabbtn" data-tab="purchaseTab">Purchase</button>
          <button class="tabbtn" data-tab="dueTab">Due</button>
        </div>

        <div id="summaryTab" class="tab active">
          <div class="row">
            <div class="card kpi"><h3>Sales Count</h3><div id="k_sales_count">-</div></div>
            <div class="card kpi"><h3>Sales Total</h3><div id="k_sales_total">-</div></div>
            <div class="card kpi"><h3>Sales Due</h3><div id="k_sales_due">-</div></div>
            <div class="card kpi"><h3>Purchase Total</h3><div id="k_purchase_total">-</div></div>
            <div class="card kpi"><h3>Purchase Due</h3><div id="k_purchase_due">-</div></div>
            <div class="card kpi"><h3>Stock Value</h3><div id="k_stock_value">-</div></div>
          </div>
        </div>

        <div id="itemsTab" class="tab">
          <div class="tools">
            <input id="itemsSearch" placeholder="Search item...">
            <button class="secondary" id="itemsExportBtn">Export CSV</button>
          </div>
          <div class="scroll">
            <table id="itemsTbl">
              <thead><tr><th>Item</th><th>Available Qty</th><th>Purchase Price</th><th>Selling Price</th></tr></thead>
              <tbody></tbody>
            </table>
          </div>
        </div>

        <div id="salesTab" class="tab">
          <div class="tools">
            <input id="salesSearch" placeholder="Search invoice/customer/phone...">
            <button class="secondary" id="salesExportBtn">Export CSV</button>
          </div>
          <div class="scroll">
            <table id="salesTbl">
              <thead><tr><th>Date</th><th>Invoice</th><th>Customer</th><th>Phone</th><th>Total</th><th>Paid</th><th>Due</th></tr></thead>
              <tbody></tbody>
            </table>
          </div>
        </div>

        <div id="purchaseTab" class="tab">
          <div class="tools">
            <input id="purchaseSearch" placeholder="Search purchase/supplier...">
            <button class="secondary" id="purchaseExportBtn">Export CSV</button>
          </div>
          <div class="scroll">
            <table id="purchaseTbl">
              <thead><tr><th>Date</th><th>Purchase ID</th><th>Supplier</th><th>Total</th><th>Paid</th><th>Due</th><th>Pay Mode</th></tr></thead>
              <tbody></tbody>
            </table>
          </div>
        </div>

        <div id="dueTab" class="tab">
          <div class="tools">
            <input id="dueSearch" placeholder="Search due invoice/customer/phone...">
            <button class="secondary" id="dueExportBtn">Export CSV</button>
          </div>
          <div class="scroll">
            <table id="dueTbl">
              <thead><tr><th>Date</th><th>Invoice</th><th>Customer</th><th>Phone</th><th>Total</th><th>Paid</th><th>Due</th></tr></thead>
              <tbody></tbody>
            </table>
          </div>
        </div>
      </div>
    </div>
  </div>

  <script>
    const $ = (id) => document.getElementById(id);
    const state = { summary:null, items:[], sales:[], purchases:[], due:[] };
    function money(v){ return Number(v||0).toFixed(2); }

    function setActiveTab(tabId){
      document.querySelectorAll('.tabbtn').forEach(b => b.classList.toggle('active', b.dataset.tab===tabId));
      document.querySelectorAll('.tab').forEach(t => t.classList.toggle('active', t.id===tabId));
    }

    function toRowText(r){ return Object.values(r||{}).join(' ').toLowerCase(); }
    function csvEscape(v){ const s=String(v??''); return `"${s.replaceAll('"','""')}"`; }
    function exportRowsToCsv(filename, headers, rows){
      const lines = [headers.map(csvEscape).join(',')];
      rows.forEach(r => lines.push(headers.map(h => csvEscape(r[h])).join(',')));
      const blob = new Blob([lines.join('\\n')], {type:'text/csv;charset=utf-8;'});
      const a = document.createElement('a');
      a.href = URL.createObjectURL(blob);
      a.download = filename;
      a.click();
      URL.revokeObjectURL(a.href);
    }

    function renderItems(){
      const q = ($('itemsSearch').value || '').trim().toLowerCase();
      const rows = state.items.filter(r => toRowText(r).includes(q));
      const body = $('itemsTbl').querySelector('tbody');
      body.innerHTML = '';
      rows.forEach(r => {
        const tr = document.createElement('tr');
        tr.innerHTML = `<td>${r.item||''}</td><td>${money(r.available_qty)}</td><td>${money(r.purchase_price)}</td><td>${money(r.selling_price)}</td>`;
        body.appendChild(tr);
      });
      return rows;
    }

    function renderSales(){
      const q = ($('salesSearch').value || '').trim().toLowerCase();
      const rows = state.sales.filter(r => toRowText(r).includes(q));
      const body = $('salesTbl').querySelector('tbody');
      body.innerHTML = '';
      rows.forEach(r => {
        const tr = document.createElement('tr');
        tr.innerHTML = `<td>${r.date||''}</td><td>${r.invoice_no||''}</td><td>${r.customer_name||''}</td><td>${r.phone||''}</td><td>${money(r.grand_total)}</td><td>${money(r.paid||r.paid_amount)}</td><td>${money(r.due)}</td>`;
        body.appendChild(tr);
      });
      return rows;
    }

    function renderPurchases(){
      const q = ($('purchaseSearch').value || '').trim().toLowerCase();
      const rows = state.purchases.filter(r => toRowText(r).includes(q));
      const body = $('purchaseTbl').querySelector('tbody');
      body.innerHTML = '';
      rows.forEach(r => {
        const total = Number(r.grand_total ?? r.total_amount ?? 0);
        const paid = Number(r.paid_amount ?? r.paid ?? 0);
        const due = Number(r.due ?? r.due_amount ?? Math.max(total-paid,0));
        const tr = document.createElement('tr');
        tr.innerHTML = `<td>${r.date||r.created_on||''}</td><td>${r.purchase_id||''}</td><td>${r.supplier_name||r.supplier||''}</td><td>${money(total)}</td><td>${money(paid)}</td><td>${money(due)}</td><td>${r.payment_mode||r.payment_type||''}</td>`;
        body.appendChild(tr);
      });
      return rows;
    }

    function renderDue(){
      const q = ($('dueSearch').value || '').trim().toLowerCase();
      const rows = state.due.filter(r => toRowText(r).includes(q));
      const body = $('dueTbl').querySelector('tbody');
      body.innerHTML = '';
      rows.forEach(r => {
        const tr = document.createElement('tr');
        tr.innerHTML = `<td>${r.date||''}</td><td>${r.invoice_no||''}</td><td>${r.customer_name||''}</td><td>${r.phone||''}</td><td>${money(r.grand_total)}</td><td>${money(r.paid||r.paid_amount)}</td><td>${money(r.due)}</td>`;
        body.appendChild(tr);
      });
      return rows;
    }

    async function loadDashboard() {
      const [summaryR, itemsR, salesR, purchaseR] = await Promise.all([
        fetch('/dashboard/summary'),
        fetch('/items/summary'),
        fetch('/sales?limit=1000'),
        fetch('/purchases?limit=1000')
      ]);
      if(!summaryR.ok || !itemsR.ok || !salesR.ok || !purchaseR.ok){ throw new Error('Failed to load data'); }
      state.summary = await summaryR.json();
      state.items = (await itemsR.json()).items || [];
      state.sales = (await salesR.json()).rows || [];
      state.purchases = (await purchaseR.json()).rows || [];
      state.due = state.sales.filter(r => Number(r.due||0) > 0);

      $('k_sales_count').textContent = state.summary.sales.count;
      $('k_sales_total').textContent = money(state.summary.sales.total);
      $('k_sales_due').textContent = money(state.summary.sales.due);
      $('k_purchase_total').textContent = money(state.summary.purchase.total);
      $('k_purchase_due').textContent = money(state.summary.purchase.due);
      $('k_stock_value').textContent = money(state.summary.stock_value);

      renderItems(); renderSales(); renderPurchases(); renderDue();
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

    document.querySelectorAll('.tabbtn').forEach(btn => btn.addEventListener('click', () => setActiveTab(btn.dataset.tab)));
    $('itemsSearch').addEventListener('input', renderItems);
    $('salesSearch').addEventListener('input', renderSales);
    $('purchaseSearch').addEventListener('input', renderPurchases);
    $('dueSearch').addEventListener('input', renderDue);

    $('itemsExportBtn').addEventListener('click', () => {
      const rows = renderItems().map(r => ({Item:r.item, AvailableQty:r.available_qty, PurchasePrice:r.purchase_price, SellingPrice:r.selling_price}));
      exportRowsToCsv('items_summary.csv', ['Item','AvailableQty','PurchasePrice','SellingPrice'], rows);
    });
    $('salesExportBtn').addEventListener('click', () => {
      const rows = renderSales().map(r => ({Date:r.date, Invoice:r.invoice_no, Customer:r.customer_name, Phone:r.phone, Total:r.grand_total, Paid:(r.paid||r.paid_amount), Due:r.due}));
      exportRowsToCsv('sales_report.csv', ['Date','Invoice','Customer','Phone','Total','Paid','Due'], rows);
    });
    $('purchaseExportBtn').addEventListener('click', () => {
      const rows = renderPurchases().map(r => ({Date:(r.date||r.created_on), PurchaseID:r.purchase_id, Supplier:(r.supplier_name||r.supplier), Total:(r.grand_total??r.total_amount??0), Paid:(r.paid_amount??r.paid??0), Due:(r.due??r.due_amount??0), PaymentMode:(r.payment_mode||r.payment_type||'')}));
      exportRowsToCsv('purchase_report.csv', ['Date','PurchaseID','Supplier','Total','Paid','Due','PaymentMode'], rows);
    });
    $('dueExportBtn').addEventListener('click', () => {
      const rows = renderDue().map(r => ({Date:r.date, Invoice:r.invoice_no, Customer:r.customer_name, Phone:r.phone, Total:r.grand_total, Paid:(r.paid||r.paid_amount), Due:r.due}));
      exportRowsToCsv('due_report.csv', ['Date','Invoice','Customer','Phone','Total','Paid','Due'], rows);
    });

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
