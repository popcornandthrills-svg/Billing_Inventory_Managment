from typing import Optional, List
import os
import json
from datetime import datetime

from fastapi import FastAPI, Header, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel

from data_consistency import ensure_data_consistency
from item_summary_report import get_item_summary_report
from inventory import get_total_stock_value, add_stock, get_item_stock
from purchase import load_purchases, create_purchase
from sales import load_sales, save_sales, create_sale
from cash_ledger import add_cash_entry
from audit_log import write_audit_log
from item_summary_report import adjust_item_summary_available_qty, set_item_summary_override
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


def _safe_float(value):
    try:
        return float(value)
    except Exception:
        return 0.0


def _normalize_mode(value: str) -> str:
    text = str(value or "").strip()
    return text if text else "Cash"


def _parse_date(date_text: str) -> datetime:
    raw = str(date_text or "").strip()
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d", "%d-%m-%Y %H:%M:%S", "%d-%m-%Y"):
        try:
            return datetime.strptime(raw, fmt)
        except Exception:
            continue
    return datetime.min


def _sort_rows(rows, key_name="date"):
    return sorted(rows, key=lambda r: _parse_date(str(r.get(key_name, ""))), reverse=True)


def _require_role(x_user_role: Optional[str], allowed: List[str]):
    role = (x_user_role or "").strip().lower()
    if role not in [a.lower() for a in allowed]:
        raise HTTPException(status_code=403, detail="Access denied for this role.")


def _normalize_items(raw_items: List[TxnItem], for_sale: bool):
    items = []
    for rec in raw_items:
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
        if for_sale:
            taxable = round(qty * rate, 2)
            gst_total = round(taxable * gst / 100.0, 2)
            half = round(gst_total / 2.0, 2)
            total = round(taxable + gst_total, 2)
            items.append(
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
        else:
            items.append({"item": item, "qty": qty, "rate": rate, "gst": gst})
    return items


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
    data = _sort_rows(load_sales(), key_name="date")
    return {"count": len(data), "rows": data[: max(1, min(limit, 1000))]}


@app.get("/purchases")
def purchases(limit: int = 100):
    data = _sort_rows(load_purchases(), key_name="date")
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


@app.post("/sales/create")
def sales_create(
    payload: SaleCreateRequest,
    x_user_role: Optional[str] = Header(default=None),
    x_user_name: Optional[str] = Header(default=None),
):
    _require_role(x_user_role, ["admin", "shop_manager"])
    items = _normalize_items(payload.items, for_sale=True)
    discount = max(0.0, min(_safe_float(payload.discount_percent), 100.0))
    paid = max(0.0, _safe_float(payload.paid_amount))
    invoice_no = create_sale(
        customer_name=(payload.customer_name or "").strip(),
        phone=(payload.phone or "").strip(),
        items=items,
        payment_mode=_normalize_mode(payload.payment_mode),
        paid_amount=paid,
        discount_percent=discount,
    )
    write_audit_log(
        user=(x_user_name or "web_user"),
        module="sales",
        action="create",
        reference=invoice_no,
    )
    return {"ok": True, "invoice_no": invoice_no}


@app.post("/purchases/create")
def purchases_create(
    payload: PurchaseCreateRequest,
    x_user_role: Optional[str] = Header(default=None),
    x_user_name: Optional[str] = Header(default=None),
):
    _require_role(x_user_role, ["admin"])
    items = _normalize_items(payload.items, for_sale=False)
    paid = max(0.0, _safe_float(payload.paid_amount))
    purchase = create_purchase(
        supplier_id=(payload.supplier_id or "").strip(),
        supplier_name=(payload.supplier_name or "").strip(),
        items=items,
        payment_type=_normalize_mode(payload.payment_mode),
        paid_amount=paid,
    )
    for i in items:
        add_stock(item_name=i["item"], qty=i["qty"], rate=i["rate"])
        adjust_item_summary_available_qty(i["item"], i["qty"])
        set_item_summary_override(i["item"], available_qty=get_item_stock(i["item"]))
    write_audit_log(
        user=(x_user_name or "web_user"),
        module="purchase",
        action="create",
        reference=purchase.get("purchase_id", ""),
    )
    return {"ok": True, "purchase_id": purchase.get("purchase_id", "")}


@app.post("/sales/pay-due")
def sales_pay_due(
    payload: DuePaymentRequest,
    x_user_role: Optional[str] = Header(default=None),
    x_user_name: Optional[str] = Header(default=None),
):
    _require_role(x_user_role, ["admin", "shop_manager"])
    invoice_no = str(payload.invoice_no or "").strip()
    pay = _safe_float(payload.pay_amount)
    mode = _normalize_mode(payload.payment_mode)
    if not invoice_no:
        raise HTTPException(status_code=400, detail="Invoice number is required.")
    if pay <= 0:
        raise HTTPException(status_code=400, detail="Pay amount must be greater than 0.")

    sales_rows = load_sales()
    target = None
    for s in sales_rows:
        if str(s.get("invoice_no", "")) == invoice_no:
            target = s
            break
    if not target:
        raise HTTPException(status_code=404, detail="Invoice not found.")

    due_before = _safe_float(target.get("due", 0))
    paid_before = _safe_float(target.get("paid", target.get("paid_amount", 0)))
    if due_before <= 0:
        raise HTTPException(status_code=400, detail="No due available for this invoice.")
    if pay > due_before:
        raise HTTPException(status_code=400, detail=f"Pay amount cannot exceed due ({due_before:.2f}).")

    target["paid"] = round(paid_before + pay, 2)
    target["paid_amount"] = target["paid"]
    target["due"] = round(max(due_before - pay, 0.0), 2)
    target["last_payment_mode"] = mode
    save_sales(sales_rows)

    if mode.lower() == "cash":
        add_cash_entry(
            date=datetime.now().strftime("%Y-%m-%d"),
            particulars=f"Customer Payment {invoice_no}",
            cash_in=pay,
            reference=invoice_no,
        )

    write_audit_log(
        user=(x_user_name or "web_user"),
        module="due_payment",
        action="receive",
        reference=invoice_no,
        before={"paid": paid_before, "due": due_before},
        after={"paid": target["paid"], "due": target["due"], "payment_mode": mode},
    )
    return {"ok": True, "invoice_no": invoice_no, "paid": target["paid"], "due": target["due"]}


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
            <input id="saleCustomer" placeholder="Customer">
            <input id="salePhone" placeholder="Phone">
            <input id="saleItem" placeholder="Item">
            <input id="saleQty" type="number" min="0.01" step="0.01" placeholder="Qty">
            <input id="saleRate" type="number" min="0" step="0.01" placeholder="Rate">
            <input id="saleGst" type="number" min="0" max="100" step="0.01" placeholder="GST%" value="18">
            <input id="saleDiscount" type="number" min="0" max="100" step="0.01" placeholder="Discount %">
            <input id="salePaid" type="number" min="0" step="0.01" placeholder="Paid">
            <select id="salePayMode"><option>Cash</option><option>UPI</option><option>Card</option><option>Bank</option><option>Other</option></select>
            <button class="secondary" id="saleAddItemBtn">Add Item</button>
            <button class="secondary" id="saleClearItemsBtn">Clear</button>
            <button id="saleSaveBtn">Save Invoice</button>
          </div>
          <div class="scroll" style="max-height:120px">
            <table id="saleDraftTbl">
              <thead><tr><th>Item</th><th>Qty</th><th>Rate</th><th>GST</th></tr></thead>
              <tbody></tbody>
            </table>
          </div>
          <div class="muted" id="saleMsg"></div>
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
            <input id="purSupplier" placeholder="Supplier">
            <input id="purItem" placeholder="Item">
            <input id="purQty" type="number" min="0.01" step="0.01" placeholder="Qty">
            <input id="purRate" type="number" min="0" step="0.01" placeholder="Rate">
            <input id="purGst" type="number" min="0" max="100" step="0.01" placeholder="GST%" value="18">
            <input id="purPaid" type="number" min="0" step="0.01" placeholder="Paid">
            <select id="purPayMode"><option>Cash</option><option>UPI</option><option>Card</option><option>Bank</option><option>Other</option></select>
            <button class="secondary" id="purAddItemBtn">Add Item</button>
            <button class="secondary" id="purClearItemsBtn">Clear</button>
            <button id="purSaveBtn">Save Purchase</button>
          </div>
          <div class="scroll" style="max-height:120px">
            <table id="purDraftTbl">
              <thead><tr><th>Item</th><th>Qty</th><th>Rate</th><th>GST</th></tr></thead>
              <tbody></tbody>
            </table>
          </div>
          <div class="muted" id="purMsg"></div>
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
            <input id="dueInvoice" placeholder="Invoice no (or click row)">
            <input id="duePayAmount" type="number" min="0.01" step="0.01" placeholder="Pay amount">
            <select id="duePayMode"><option>Cash</option><option>UPI</option><option>Card</option><option>Bank</option><option>Other</option></select>
            <button id="duePayBtn">Save Payment</button>
            <span class="muted" id="dueMsg"></span>
          </div>
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
    const state = { user:null, summary:null, items:[], sales:[], purchases:[], due:[], saleDraft:[], purchaseDraft:[] };
    function money(v){ return Number(v||0).toFixed(2); }
    function setActiveTab(tabId){ document.querySelectorAll('.tabbtn').forEach(b => b.classList.toggle('active', b.dataset.tab===tabId)); document.querySelectorAll('.tab').forEach(t => t.classList.toggle('active', t.id===tabId)); }
    function toRowText(r){ return Object.values(r||{}).join(' ').toLowerCase(); }
    function debounce(fn, ms){ let t; return (...a)=>{ clearTimeout(t); t=setTimeout(()=>fn(...a), ms); }; }
    function csvEscape(v){ const s=String(v??''); return `"${s.replaceAll('"','""')}"`; }
    function exportRowsToCsv(filename, headers, rows){ const lines=[headers.map(csvEscape).join(',')]; rows.forEach(r => lines.push(headers.map(h => csvEscape(r[h])).join(','))); const blob=new Blob([lines.join('\\n')],{type:'text/csv;charset=utf-8;'}); const a=document.createElement('a'); a.href=URL.createObjectURL(blob); a.download=filename; a.click(); URL.revokeObjectURL(a.href); }
    function setMsg(id, text, isErr=false){ const el=$(id); if(!el) return; el.textContent=text||''; el.style.color=isErr ? '#b00020' : ''; }
    async function api(path, opts={}){ const headers=Object.assign({'Content-Type':'application/json'}, opts.headers||{}); if(state.user){ headers['x-user-role']=state.user.role; headers['x-user-name']=state.user.user; } const res=await fetch(path, Object.assign({}, opts, {headers})); if(!res.ok){ let msg='Request failed'; try{ const j=await res.json(); msg=j.detail||msg; }catch(_){ } throw new Error(msg); } return res.json(); }
    async function withLock(btnId, fn){ const btn=$(btnId); if(btn && btn.disabled) return; if(btn) btn.disabled=true; try{ await fn(); } finally { if(btn) btn.disabled=false; } }
    function applyRoleUi(){ const isAdmin = state.user && state.user.role === 'admin'; const tabBtn=document.querySelector('[data-tab=\"purchaseTab\"]'); if(tabBtn) tabBtn.style.display = isAdmin ? '' : 'none'; $('purchaseTab').style.display = isAdmin ? '' : 'none'; }
    function drawDraft(tblId, rows){ const body=$(tblId).querySelector('tbody'); body.innerHTML=''; rows.forEach(r=>{ const tr=document.createElement('tr'); tr.innerHTML=`<td>${r.item}</td><td>${money(r.qty)}</td><td>${money(r.rate)}</td><td>${money(r.gst)}</td>`; body.appendChild(tr); }); }
    function addDraft(prefix, key){ const item=$(prefix+'Item').value.trim(); const qty=Number($(prefix+'Qty').value||0); const rate=Number($(prefix+'Rate').value||0); const gst=Number($(prefix+'Gst').value||18); const msgId=(prefix==='sale')?'saleMsg':'purMsg'; if(!item || qty<=0 || rate<0 || gst<0 || gst>100){ setMsg(msgId, 'Enter valid item/qty/rate/gst.', true); return; } state[key].push({item,qty,rate,gst}); drawDraft(prefix==='sale'?'saleDraftTbl':'purDraftTbl', state[key]); $(prefix+'Item').value=''; $(prefix+'Qty').value=''; $(prefix+'Rate').value=''; $(prefix+'Gst').value='18'; setMsg(msgId, state[key].length + ' item(s) ready.'); }
    function renderItems(){ const q=($('itemsSearch').value||'').trim().toLowerCase(); const rows=state.items.filter(r => toRowText(r).includes(q)); const isAdmin = state.user && state.user.role === 'admin'; const head=$('itemsTbl').querySelector('thead tr'); head.innerHTML = isAdmin ? '<th>Item</th><th>Available Qty</th><th>Purchase Price</th><th>Selling Price</th>' : '<th>Item</th><th>Available Qty</th><th>Selling Price</th>'; const body=$('itemsTbl').querySelector('tbody'); body.innerHTML=''; rows.forEach(r=>{ const tr=document.createElement('tr'); tr.innerHTML = isAdmin ? `<td>${r.item||''}</td><td>${money(r.available_qty)}</td><td>${money(r.purchase_price)}</td><td>${money(r.selling_price)}</td>` : `<td>${r.item||''}</td><td>${money(r.available_qty)}</td><td>${money(r.selling_price)}</td>`; body.appendChild(tr); }); return rows; }
    function renderSales(){ const q=($('salesSearch').value||'').trim().toLowerCase(); const rows=state.sales.filter(r => toRowText(r).includes(q)); const body=$('salesTbl').querySelector('tbody'); body.innerHTML=''; rows.forEach(r=>{ const tr=document.createElement('tr'); tr.innerHTML=`<td>${r.date||''}</td><td>${r.invoice_no||''}</td><td>${r.customer_name||''}</td><td>${r.phone||''}</td><td>${money(r.grand_total)}</td><td>${money(r.paid||r.paid_amount)}</td><td>${money(r.due)}</td>`; body.appendChild(tr); }); return rows; }
    function renderPurchases(){ const q=($('purchaseSearch').value||'').trim().toLowerCase(); const rows=state.purchases.filter(r => toRowText(r).includes(q)); const body=$('purchaseTbl').querySelector('tbody'); body.innerHTML=''; rows.forEach(r=>{ const total=Number(r.grand_total ?? r.total_amount ?? 0); const paid=Number(r.paid_amount ?? r.paid ?? 0); const due=Number(r.due ?? r.due_amount ?? Math.max(total-paid,0)); const tr=document.createElement('tr'); tr.innerHTML=`<td>${r.date||r.created_on||''}</td><td>${r.purchase_id||''}</td><td>${r.supplier_name||r.supplier||''}</td><td>${money(total)}</td><td>${money(paid)}</td><td>${money(due)}</td><td>${r.payment_mode||r.payment_type||''}</td>`; body.appendChild(tr); }); return rows; }
    function renderDue(){ const q=($('dueSearch').value||'').trim().toLowerCase(); const rows=state.due.filter(r => toRowText(r).includes(q)); const body=$('dueTbl').querySelector('tbody'); body.innerHTML=''; rows.forEach(r=>{ const tr=document.createElement('tr'); tr.innerHTML=`<td>${r.date||''}</td><td>${r.invoice_no||''}</td><td>${r.customer_name||''}</td><td>${r.phone||''}</td><td>${money(r.grand_total)}</td><td>${money(r.paid||r.paid_amount)}</td><td>${money(r.due)}</td>`; tr.addEventListener('click', ()=>{ $('dueInvoice').value=r.invoice_no||''; }); body.appendChild(tr); }); return rows; }
    async function loadDashboard(){ const [summary, items, sales, purchases] = await Promise.all([api('/dashboard/summary'), api('/items/summary'), api('/sales?limit=1000'), api('/purchases?limit=1000')]); state.summary=summary; state.items=items.items||[]; state.sales=sales.rows||[]; state.purchases=purchases.rows||[]; state.due=state.sales.filter(r => Number(r.due||0)>0); $('k_sales_count').textContent=state.summary.sales.count; $('k_sales_total').textContent=money(state.summary.sales.total); $('k_sales_due').textContent=money(state.summary.sales.due); $('k_purchase_total').textContent=money(state.summary.purchase.total); $('k_purchase_due').textContent=money(state.summary.purchase.due); $('k_stock_value').textContent=money(state.summary.stock_value); renderItems(); renderSales(); renderPurchases(); renderDue(); }
    async function login(){ const pwd=$('pwd').value.trim(); if(!pwd){ $('loginMsg').textContent='Enter password.'; return; } $('loginMsg').textContent='Authenticating...'; try{ const data=await api('/auth/login',{method:'POST', body:JSON.stringify({password:pwd})}); state.user=data; localStorage.setItem('im_user', JSON.stringify(data)); $('who').textContent=`${data.user} (${data.role})`; $('loginCard').classList.add('hidden'); $('appCard').classList.remove('hidden'); applyRoleUi(); await loadDashboard(); } catch(e){ $('loginMsg').textContent=e.message||'Invalid credentials.'; } }
    function logout(){ localStorage.removeItem('im_user'); state.user=null; $('appCard').classList.add('hidden'); $('loginCard').classList.remove('hidden'); $('pwd').value=''; $('loginMsg').textContent='Use your existing system password.'; }
    document.querySelectorAll('.tabbtn').forEach(btn => btn.addEventListener('click', () => setActiveTab(btn.dataset.tab)));
    $('itemsSearch').addEventListener('input', debounce(renderItems, 120)); $('salesSearch').addEventListener('input', debounce(renderSales, 120)); $('purchaseSearch').addEventListener('input', debounce(renderPurchases, 120)); $('dueSearch').addEventListener('input', debounce(renderDue, 120));
    $('saleAddItemBtn').addEventListener('click', () => addDraft('sale', 'saleDraft')); $('saleClearItemsBtn').addEventListener('click', () => { state.saleDraft=[]; drawDraft('saleDraftTbl', state.saleDraft); setMsg('saleMsg','Draft cleared.'); });
    $('purAddItemBtn').addEventListener('click', () => addDraft('pur', 'purchaseDraft')); $('purClearItemsBtn').addEventListener('click', () => { state.purchaseDraft=[]; drawDraft('purDraftTbl', state.purchaseDraft); setMsg('purMsg','Draft cleared.'); });
    $('saleSaveBtn').addEventListener('click', () => withLock('saleSaveBtn', async () => { const payload={customer_name:$('saleCustomer').value.trim(), phone:$('salePhone').value.trim(), items:state.saleDraft, payment_mode:$('salePayMode').value, paid_amount:Number($('salePaid').value||0), discount_percent:Number($('saleDiscount').value||0)}; if(!payload.customer_name || !payload.phone || !payload.items.length){ setMsg('saleMsg','Customer, phone and items required.', true); return; } try{ const out=await api('/sales/create',{method:'POST',body:JSON.stringify(payload)}); setMsg('saleMsg','Saved ' + out.invoice_no); state.saleDraft=[]; drawDraft('saleDraftTbl', state.saleDraft); $('saleCustomer').value=''; $('salePhone').value=''; $('salePaid').value=''; $('saleDiscount').value=''; await loadDashboard(); } catch(e){ setMsg('saleMsg', e.message, true); } }));
    $('purSaveBtn').addEventListener('click', () => withLock('purSaveBtn', async () => { const payload={supplier_name:$('purSupplier').value.trim(), items:state.purchaseDraft, payment_mode:$('purPayMode').value, paid_amount:Number($('purPaid').value||0)}; if(!payload.supplier_name || !payload.items.length){ setMsg('purMsg','Supplier and items required.', true); return; } try{ const out=await api('/purchases/create',{method:'POST',body:JSON.stringify(payload)}); setMsg('purMsg','Saved ' + out.purchase_id); state.purchaseDraft=[]; drawDraft('purDraftTbl', state.purchaseDraft); $('purSupplier').value=''; $('purPaid').value=''; await loadDashboard(); } catch(e){ setMsg('purMsg', e.message, true); } }));
    $('duePayBtn').addEventListener('click', () => withLock('duePayBtn', async () => { const payload={invoice_no:$('dueInvoice').value.trim(), pay_amount:Number($('duePayAmount').value||0), payment_mode:$('duePayMode').value}; if(!payload.invoice_no || payload.pay_amount<=0){ setMsg('dueMsg','Invoice and valid pay amount required.', true); return; } try{ const out=await api('/sales/pay-due',{method:'POST',body:JSON.stringify(payload)}); setMsg('dueMsg',`Updated ${out.invoice_no}. Due ${money(out.due)}`); $('duePayAmount').value=''; await loadDashboard(); } catch(e){ setMsg('dueMsg', e.message, true); } }));
    $('itemsExportBtn').addEventListener('click', () => { const isAdmin=state.user && state.user.role==='admin'; const rows=renderItems().map(r => isAdmin ? ({Item:r.item, AvailableQty:r.available_qty, PurchasePrice:r.purchase_price, SellingPrice:r.selling_price}) : ({Item:r.item, AvailableQty:r.available_qty, SellingPrice:r.selling_price})); const headers=isAdmin ? ['Item','AvailableQty','PurchasePrice','SellingPrice'] : ['Item','AvailableQty','SellingPrice']; exportRowsToCsv('items_summary.csv', headers, rows); });
    $('salesExportBtn').addEventListener('click', () => { const rows=renderSales().map(r => ({Date:r.date, Invoice:r.invoice_no, Customer:r.customer_name, Phone:r.phone, Total:r.grand_total, Paid:(r.paid||r.paid_amount), Due:r.due})); exportRowsToCsv('sales_report.csv', ['Date','Invoice','Customer','Phone','Total','Paid','Due'], rows); });
    $('purchaseExportBtn').addEventListener('click', () => { const rows=renderPurchases().map(r => ({Date:(r.date||r.created_on), PurchaseID:r.purchase_id, Supplier:(r.supplier_name||r.supplier), Total:(r.grand_total??r.total_amount??0), Paid:(r.paid_amount??r.paid??0), Due:(r.due??r.due_amount??0), PaymentMode:(r.payment_mode||r.payment_type||'')})); exportRowsToCsv('purchase_report.csv', ['Date','PurchaseID','Supplier','Total','Paid','Due','PaymentMode'], rows); });
    $('dueExportBtn').addEventListener('click', () => { const rows=renderDue().map(r => ({Date:r.date, Invoice:r.invoice_no, Customer:r.customer_name, Phone:r.phone, Total:r.grand_total, Paid:(r.paid||r.paid_amount), Due:r.due})); exportRowsToCsv('due_report.csv', ['Date','Invoice','Customer','Phone','Total','Paid','Due'], rows); });
    $('loginBtn').addEventListener('click', login); $('logoutBtn').addEventListener('click', logout); $('pwd').addEventListener('keydown', (e) => { if(e.key === 'Enter') login(); });
    (async () => { const saved=localStorage.getItem('im_user'); if(!saved) return; try{ const user=JSON.parse(saved); state.user=user; $('who').textContent=`${user.user} (${user.role})`; $('loginCard').classList.add('hidden'); $('appCard').classList.remove('hidden'); applyRoleUi(); await loadDashboard(); } catch (_) {} })();
  </script>
</body>
</html>
"""
    )
