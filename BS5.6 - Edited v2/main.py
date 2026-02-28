import tkinter as tk
from tkinter import ttk, messagebox
import os
import json
import csv
from datetime import datetime

from inventory import get_total_stock_value
from audit_log import write_audit_log, set_current_audit_user
from data_consistency import ensure_data_consistency_if_needed
from ui_theme import setup_style
from sales import load_sales
from purchase import load_purchases
from inventory import load_inventory
from customers import load_customers
from suppliers import load_suppliers
from utils import app_dir


ADMIN_PASSWORD = "admin123"
SHOP_MANAGER_PASSWORD = "sm123"
REGISTRATION_AUTH_KEY = "12345679"
SHOP_MANAGER_USERS_FILE = os.path.join("data", "shop_manager_users.json")


def _now_text():
    return datetime.now().strftime("%d-%m-%Y %H:%M:%S")


def _parse_ts(value):
    text = str(value or "").strip()
    for fmt in ("%d-%m-%Y %H:%M:%S", "%Y-%m-%d %H:%M:%S", "%d-%m-%Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(text, fmt)
        except Exception:
            continue
    return datetime.min


def load_shop_manager_accounts():
    path = os.path.join(app_dir(), SHOP_MANAGER_USERS_FILE)
    if not os.path.exists(path):
        return []
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception:
        return []

    if not isinstance(data, list):
        return []

    # Backward compatibility: older format was list of passwords.
    if data and isinstance(data[0], str):
        migrated = []
        for idx, raw_pwd in enumerate(data, start=1):
            pwd = str(raw_pwd or "").strip()
            if not pwd:
                continue
            migrated.append(
                {
                    "username": f"SM-{idx:03d}",
                    "password": pwd,
                    "created_on": "",
                    "last_login": "",
                    "is_active": True,
                    "is_deleted": False,
                    "deleted_on": "",
                }
            )
        save_shop_manager_accounts(migrated)
        return migrated

    normalized = []
    for rec in data:
        if not isinstance(rec, dict):
            continue
        username = str(rec.get("username", "")).strip() or f"SM-{len(normalized) + 1:03d}"
        password = str(rec.get("password", "")).strip()
        if not password:
            continue
        normalized.append(
            {
                "username": username,
                "password": password,
                "created_on": str(rec.get("created_on", "")).strip(),
                "last_login": str(rec.get("last_login", "")).strip(),
                "is_active": bool(rec.get("is_active", True)),
                "is_deleted": bool(rec.get("is_deleted", False)),
                "deleted_on": str(rec.get("deleted_on", "")).strip(),
            }
        )
    return normalized


def save_shop_manager_accounts(accounts):
    path = os.path.join(app_dir(), SHOP_MANAGER_USERS_FILE)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    accounts = sorted(accounts, key=lambda a: str(a.get("username", "")).lower())
    with open(path, "w", encoding="utf-8") as f:
        json.dump(accounts, f, indent=2)


def load_registered_shop_manager_passwords():
    return [
        a.get("password", "")
        for a in load_shop_manager_accounts()
        if a.get("password") and a.get("is_active", True) and not a.get("is_deleted", False)
    ]


def create_shop_manager_account(username, password):
    uname = str(username or "").strip()
    pwd = str(password or "").strip()
    if not uname or not pwd:
        raise ValueError("Username and password are required.")

    accounts = load_shop_manager_accounts()
    for a in accounts:
        a_uname = str(a.get("username", "")).strip().lower()
        a_pwd = str(a.get("password", "")).strip()
        if a_uname == uname.lower() and not a.get("is_deleted", False):
            raise ValueError("Username already exists.")
        if a_pwd == pwd and not a.get("is_deleted", False):
            raise ValueError("Password already exists.")

    accounts.append(
        {
            "username": uname,
            "password": pwd,
            "created_on": _now_text(),
            "last_login": "",
            "is_active": True,
            "is_deleted": False,
            "deleted_on": "",
        }
    )
    save_shop_manager_accounts(accounts)


def get_shop_manager_account_by_password(password):
    pwd = str(password or "").strip()
    if not pwd:
        return None
    for a in load_shop_manager_accounts():
        if str(a.get("password", "")).strip() == pwd and a.get("is_active", True) and not a.get("is_deleted", False):
            return a
    return None


def update_shop_manager_last_login(password):
    pwd = str(password or "").strip()
    if not pwd:
        return
    accounts = load_shop_manager_accounts()
    changed = False
    for a in accounts:
        if str(a.get("password", "")).strip() == pwd:
            a["last_login"] = _now_text()
            changed = True
            break
    if changed:
        save_shop_manager_accounts(accounts)


def save_registered_shop_manager_passwords(passwords):
    # compatibility wrapper retained for older call sites
    rebuilt = []
    uniq = []
    for p in passwords:
        text = str(p or "").strip()
        if text and text not in uniq:
            uniq.append(text)
    for idx, pwd in enumerate(uniq, start=1):
        rebuilt.append(
            {
                "username": f"SM-{idx:03d}",
                "password": pwd,
                "created_on": "",
                "last_login": "",
                "is_active": True,
                "is_deleted": False,
                "deleted_on": "",
            }
        )
    save_shop_manager_accounts(rebuilt)


def preload_system_files():
    # Load and normalize core data before UI starts.
    ensure_data_consistency_if_needed()
    load_sales()
    load_purchases()
    load_inventory()
    load_customers()
    load_suppliers()


# ==================================================
# MAIN APP
# ==================================================
class App(tk.Tk):
    def __init__(self):
        super().__init__()

        write_audit_log(
            user="admin",
            module="system",
            action="startup",
            reference="APP_START"
        )

        self.title("Billing & Inventory Management")
        sw = max(self.winfo_screenwidth(), 1024)
        sh = max(self.winfo_screenheight(), 700)
        w = min(int(sw * 0.96), 1600)
        h = min(int(sh * 0.94), 1000)
        self.geometry(f"{w}x{h}+0+0")
        self.minsize(min(1000, w), min(600, h))
        try:
            # Use available screen space so bottom controls don't clip on launch.
            self.state("zoomed")
        except Exception:
            pass
        setup_style(self)

        self.role = None

        container = ttk.Frame(self)
        container.pack(fill="both", expand=True)
        
        container.rowconfigure(0, weight=1)
        container.columnconfigure(0, weight=1)
                
        self.frames = {}
        
        for F in (LoginFrame, DashboardFrame):
            frame = F(container, self)
            self.frames[F.__name__] = frame
            frame.grid(row=0, column=0, sticky="nsew")
        
        self.show_frame("LoginFrame")

    def show_frame(self, name):
        frame = self.frames[name]
        frame.tkraise()


# ==================================================
# LOGIN FRAME
# ==================================================
class LoginFrame(ttk.Frame):
    def __init__(self, parent, app):
        super().__init__(parent)
        self.app = app

        center = ttk.Frame(self)
        center.place(relx=0.5, rely=0.5, anchor="center")

        ttk.Label(
            center,
            text="Billing & Inventory Management",
            style="Header.TLabel"
        ).pack(pady=(0, 25))

        ttk.Label(center, text="Please enter your password", style="Subtle.TLabel").pack()

        self.pwd = ttk.Entry(center, show="*", width=30)
        self.pwd.pack(pady=8)
        self.pwd.focus_set()

        self.pwd.bind("<Return>", lambda e: self.check_login())

        ttk.Button(
            center,
            text="Login",
            width=18,
            command=self.check_login
        ).pack(pady=10)

        ttk.Button(
            center,
            text="Register Shop Manager",
            width=22,
            command=self.open_registration
        ).pack(pady=(2, 0))

        ttk.Label(
            center,
            text="New registration gets Shop Manager access",
            style="Subtle.TLabel"
        ).pack(pady=(8, 0))

    def check_login(self):
        pwd = self.pwd.get().strip()
        registered_passwords = load_registered_shop_manager_passwords()
        audit_identity = None

        if pwd == ADMIN_PASSWORD:
            self.app.role = "admin"
            audit_identity = "admin123"
        elif pwd == SHOP_MANAGER_PASSWORD or pwd in registered_passwords:
            self.app.role = "shop_manager"
            if pwd == SHOP_MANAGER_PASSWORD:
                audit_identity = "sm123"
            else:
                acc = get_shop_manager_account_by_password(pwd)
                audit_identity = (acc or {}).get("username", "shop_manager")
                update_shop_manager_last_login(pwd)
                write_audit_log(
                    user="admin",
                    module="shop_manager_accounts",
                    action="login",
                    reference=audit_identity
                )
        else:
            messagebox.showerror("Login Failed", "Incorrect password. Please try again.")
            return
        set_current_audit_user(audit_identity or self.app.role)

        dashboard = self.app.frames["DashboardFrame"]
        dashboard.refresh()
        self.app.show_frame("DashboardFrame")

    def open_registration(self):
        win = tk.Toplevel(self)
        win.title("Register Shop Manager")
        win.geometry("520x380")
        win.resizable(False, False)
        win.transient(self.winfo_toplevel())
        win.grab_set()

        frm = ttk.Frame(win, padding=14)
        frm.pack(fill="both", expand=True)
        frm.columnconfigure(0, weight=1)

        ttk.Label(frm, text="SM Username").grid(row=0, column=0, sticky="w", pady=(4, 4))
        username_e = ttk.Entry(frm, width=36)
        username_e.grid(row=1, column=0, sticky="w")

        ttk.Label(frm, text="New Shop Manager Password").grid(row=2, column=0, sticky="w", pady=(10, 4))
        pwd1 = ttk.Entry(frm, show="*", width=36)
        pwd1.grid(row=3, column=0, sticky="w")

        ttk.Label(frm, text="Confirm Password").grid(row=4, column=0, sticky="w", pady=(10, 4))
        pwd2 = ttk.Entry(frm, show="*", width=36)
        pwd2.grid(row=5, column=0, sticky="w")

        ttk.Label(frm, text="Authentication Key").grid(row=6, column=0, sticky="w", pady=(10, 4))
        auth_key = ttk.Entry(frm, show="*", width=36)
        auth_key.grid(row=7, column=0, sticky="w")

        ttk.Label(frm, text="Note: This login will have Shop Manager permissions.").grid(
            row=8, column=0, sticky="w", pady=(10, 0)
        )

        ttk.Label(frm, text="Required key: 12345679").grid(
            row=9, column=0, sticky="w", pady=(4, 0)
        )

        def _save():
            username = username_e.get().strip()
            p1 = pwd1.get().strip()
            p2 = pwd2.get().strip()
            key = auth_key.get().strip()

            if not username:
                messagebox.showerror("Invalid", "Username is required.")
                return
            if len(p1) < 4:
                messagebox.showerror("Invalid", "Password must be at least 4 characters.")
                return
            if p1 != p2:
                messagebox.showerror("Mismatch", "Passwords do not match.")
                return
            if key != REGISTRATION_AUTH_KEY:
                messagebox.showerror("Unauthorized", "Invalid authentication key.")
                return
            if p1 in (ADMIN_PASSWORD, SHOP_MANAGER_PASSWORD):
                messagebox.showerror("Invalid", "This password is reserved. Choose another.")
                return

            try:
                create_shop_manager_account(username, p1)
            except ValueError as e:
                messagebox.showerror("Invalid", str(e))
                return

            write_audit_log(
                user="admin",
                module="shop_manager_accounts",
                action="register",
                reference=username
            )
            messagebox.showinfo("Success", "Shop Manager registered successfully.")
            win.destroy()

        btns = ttk.Frame(frm)
        btns.grid(row=10, column=0, sticky="e", pady=(16, 0))
        ttk.Button(btns, text="Cancel", command=win.destroy).pack(side="right", padx=(8, 0))
        ttk.Button(btns, text="Register", command=_save).pack(side="right")


# ==================================================
# DASHBOARD FRAME
# ==================================================
class DashboardFrame(ttk.Frame):
    def __init__(self, parent, app):
        super().__init__(parent)
        self.app = app
        self._nav_locked = False
        self._nav_unlock_job = None
        self._view_cache = {}
        self._nav_buttons = {}
        self._active_nav_key = None

        header = ttk.Frame(self)
        header.pack(fill="x", pady=(10, 5))

        ttk.Label(
            header,
            text="Goldprince Trade Centre PVT LTD",
            style="Header.TLabel"
        ).pack()

        ttk.Label(
            header,
            text="Machilipatnam | GSTIN: 37XXXXXXXXXX",
            style="Subtle.TLabel"
        ).pack()

        main = ttk.Frame(self)
        main.pack(fill="both", expand=True)

        # LEFT
        self.left = ttk.Frame(main, width=260)
        self.left.pack(side="left", fill="y", padx=10)
        self.left.pack_propagate(False)

        # RIGHT
        self.right = ttk.Frame(main)
        self.right.pack(side="right", fill="both", expand=True)

    # ==================================================
    # LEFT MENU
    # ==================================================
    def refresh(self):
        for w in self.left.winfo_children():
            w.destroy()
        self._nav_buttons = {}
        self._active_nav_key = None

        # -------- ITEM SUMMARY (TOP) --------
        if self.app.role in ("admin", "shop_manager"):
            ttk.Label(
                self.left, text="Item Summary",
                style="MenuHeader.TLabel"
            ).pack(pady=(10, 5), padx=(20, 0), anchor="w")

            self._add_nav_button("item_summary_report", "Item Summary Report", self.open_item_summary_report)

        # -------- SALES --------
        ttk.Label(
            self.left, text="Sales",
            style="MenuHeader.TLabel"
        ).pack(pady=(18, 5), padx=(20, 0), anchor="w")

        self._add_nav_button("new_invoice", "New Invoice", self.open_sales)
        self._add_nav_button("sales_report", "Sales Report", self.open_sales_report)
        self._add_nav_button("customer_ledger", "Customer Ledger", self.open_customer_report)
        self._add_nav_button("due_report", "Due Report", self.open_due_report)

        # -------- PURCHASE (ADMIN ONLY) --------
        if self.app.role == "admin":
            ttk.Label(
                self.left, text="Purchase",
                style="MenuHeader.TLabel"
            ).pack(pady=(20, 5), padx=(20, 0), anchor="w")

            self._add_nav_button("new_purchase", "New Purchase", self.open_purchase)
            self._add_nav_button("purchase_report", "Purchase Report", self.open_purchase_report)
            self._add_nav_button("purchase_due_report", "Purchase Due Report", self.open_purchase_due_report)

            # Total stock value after Item Summary, Sales, and Purchase sections.
            stock_value = get_total_stock_value()
            ttk.Label(
                self.left,
                text=f"Total Stock Value : Rs {stock_value:,.2f}",
                font=("Arial", 11, "bold"),
                foreground="green"
            ).pack(pady=(15, 5), padx=(20, 0), anchor="w")

            self._add_nav_button("audit_log", "Audit Log", self.open_audit_viewer, pady=(10, 0))
            self._add_nav_button("manage_sms", "Manage SM's", self.open_manage_sm_accounts, pady=(8, 0))

        ttk.Button(
            self.left, text="Logout",
            width=20, command=self.logout, style="Danger.TButton"
        ).pack(side="bottom", pady=15)

    def _add_nav_button(self, key, text, command, pady=4):
        btn = ttk.Button(
            self.left,
            text=text,
            width=28,
            style="Nav.TButton",
            command=lambda k=key, c=command: self._on_nav_click(k, c),
        )
        btn.pack(pady=pady, padx=(20, 0), anchor="w")
        self._nav_buttons[key] = btn
        return btn

    def _on_nav_click(self, key, command):
        self._set_active_nav(key)
        command()

    def _set_active_nav(self, key):
        self._active_nav_key = key
        for nav_key, btn in self._nav_buttons.items():
            btn.configure(style="ActiveNav.TButton" if nav_key == key else "Nav.TButton")

    # ==================================================
    # REPORT OPEN
    # ==================================================
    def open_sales_report(self):
        def _build():
            from sales_report_ui import SalesReportUI
            SalesReportUI(self.right)
        self._switch_view(_build)

    def open_item_summary_report(self):
        def _build():
            from item_summary_ui import ItemSummaryUI
            ItemSummaryUI(self.right, role=self.app.role)
        self._switch_view(_build)

    # ==================================================
    # RIGHT PANEL FUNCTIONS
    # ==================================================
    def clear_right(self):
        for w in self.right.winfo_children():
            w.destroy()
        self._view_cache.clear()

    def _hide_all_right(self):
        for w in self.right.winfo_children():
            try:
                w.pack_forget()
            except Exception:
                pass

    def _destroy_transient_right(self):
        cached = set(self._view_cache.values())
        for w in self.right.winfo_children():
            if w not in cached:
                w.destroy()

    def _lock_nav(self, ms=250):
        self._nav_locked = True
        if self._nav_unlock_job:
            try:
                self.after_cancel(self._nav_unlock_job)
            except Exception:
                pass
        self._nav_unlock_job = self.after(ms, self._unlock_nav)

    def _unlock_nav(self):
        self._nav_locked = False
        self._nav_unlock_job = None

    def _switch_view(self, builder, cache_key=None):
        if self._nav_locked:
            return
        self._lock_nav()
        if cache_key and cache_key in self._view_cache:
            self._hide_all_right()
            self._view_cache[cache_key].pack(fill="both", expand=True, padx=10, pady=10)
            return

        self._hide_all_right()
        self._destroy_transient_right()

        def _build():
            view = builder()
            if cache_key and view is not None:
                self._view_cache[cache_key] = view
        self.after(1, _build)

    def open_sales(self):
        def _build():
            from billing_ui import BillingUI
            view = BillingUI(self.right)
            view.pack(fill="both", expand=True, padx=10, pady=10)
            return view
        self._switch_view(_build, cache_key="new_invoice")

    def open_customer_report(self):
        def _build():
            from customer_ledger_ui import CustomerLedgerUI
            CustomerLedgerUI(self.right).pack(fill="both", expand=True, padx=10, pady=10)
        self._switch_view(_build)

    def open_due_report(self):
        def _build():
            from due_report_ui import DueReportUI
            DueReportUI(self.right).pack(fill="both", expand=True, padx=10, pady=10)
        self._switch_view(_build)

    def open_purchase_report(self):
        def _build():
            from purchase_reports_ui import PurchaseReportsUI
            PurchaseReportsUI(self.right).pack(fill="both", expand=True, padx=10, pady=10)
        self._switch_view(_build)

    def open_purchase_due_report(self):
        def _build():
            from purchase_due_report import PurchaseDueReportUI
            PurchaseDueReportUI(self.right).pack(fill="both", expand=True, padx=10, pady=10)
        self._switch_view(_build)

    def open_purchase(self):
        def _build():
            from purchase_entry import PurchaseEntry
            view = PurchaseEntry(self.right)
            view.pack(fill="both", expand=True, padx=10, pady=10)
            return view
        self._switch_view(_build, cache_key="new_purchase")

    def open_audit_viewer(self):
        def _build():
            from audit_viewer_ui import AuditViewerUI
            AuditViewerUI(self.right).pack(fill="both", expand=True, padx=10, pady=10)
        self._switch_view(_build)

    def open_manage_sm_accounts(self):
        def _build():
            frame = ttk.Frame(self.right)
            frame.pack(fill="both", expand=True, padx=10, pady=10)
            frame.columnconfigure(0, weight=1)
            frame.rowconfigure(1, weight=1)
            frame.rowconfigure(2, weight=1)

            ttk.Label(frame, text="Manage Shop Manager Accounts", style="Header.TLabel").grid(
                row=0, column=0, sticky="w", pady=(0, 10)
            )

            split = ttk.Panedwindow(frame, orient="horizontal")
            split.grid(row=1, column=0, sticky="nsew")

            table_wrap = ttk.Frame(split)
            table_wrap.columnconfigure(0, weight=1)
            table_wrap.rowconfigure(0, weight=1)
            split.add(table_wrap, weight=3)

            form = ttk.LabelFrame(split, text="Actions")
            form.columnconfigure(1, weight=1)
            split.add(form, weight=2)

            detail_box = ttk.LabelFrame(frame, text="Shop Manager Details & Activity")
            detail_box.grid(row=2, column=0, sticky="nsew", pady=(10, 0))
            detail_box.columnconfigure(0, weight=1)
            detail_box.rowconfigure(1, weight=1)
            detail_box.rowconfigure(3, weight=1)

            detail_header_var = tk.StringVar(value="Select an SM row to view complete details.")
            ttk.Label(detail_box, textvariable=detail_header_var, style="Subtle.TLabel").grid(
                row=0, column=0, sticky="w", padx=8, pady=(6, 4)
            )

            detail_table_wrap = ttk.Frame(detail_box)
            detail_table_wrap.grid(row=1, column=0, sticky="nsew", padx=8, pady=(0, 8))
            detail_table_wrap.columnconfigure(0, weight=1)
            detail_table_wrap.rowconfigure(0, weight=1)

            detail_cols = ("timestamp", "kind", "module", "action", "reference")
            detail_tree = ttk.Treeview(detail_table_wrap, columns=detail_cols, show="headings", height=8)
            for c, title, width in (
                ("timestamp", "Timestamp", 170),
                ("kind", "Category", 140),
                ("module", "Module", 140),
                ("action", "Action", 180),
                ("reference", "Reference", 280),
            ):
                detail_tree.heading(c, text=title)
                detail_tree.column(c, width=width, anchor="center", stretch=True)
            detail_tree.grid(row=0, column=0, sticky="nsew")
            dy = ttk.Scrollbar(detail_table_wrap, orient="vertical", command=detail_tree.yview)
            dy.grid(row=0, column=1, sticky="ns")
            dx = ttk.Scrollbar(detail_table_wrap, orient="horizontal", command=detail_tree.xview)
            dx.grid(row=1, column=0, sticky="ew")
            detail_tree.configure(yscrollcommand=dy.set, xscrollcommand=dx.set)

            sales_summary_var = tk.StringVar(value="Sales Summary: -")
            ttk.Label(detail_box, textvariable=sales_summary_var, style="Subtle.TLabel").grid(
                row=2, column=0, sticky="w", padx=8, pady=(2, 4)
            )

            sales_wrap = ttk.Frame(detail_box)
            sales_wrap.grid(row=3, column=0, sticky="nsew", padx=8, pady=(0, 8))
            sales_wrap.columnconfigure(0, weight=1)
            sales_wrap.rowconfigure(0, weight=1)

            sales_cols = ("invoice", "date", "customer", "total", "paid", "due", "payment_mode")
            sales_tree = ttk.Treeview(sales_wrap, columns=sales_cols, show="headings", height=7)
            for c, t, w in (
                ("invoice", "Invoice", 110),
                ("date", "Date", 160),
                ("customer", "Customer", 170),
                ("total", "Total", 110),
                ("paid", "Paid", 110),
                ("due", "Due", 110),
                ("payment_mode", "Pay Mode", 120),
            ):
                sales_tree.heading(c, text=t)
                sales_tree.column(c, width=w, anchor="center", stretch=True)
            sales_tree.grid(row=0, column=0, sticky="nsew")
            sy = ttk.Scrollbar(sales_wrap, orient="vertical", command=sales_tree.yview)
            sy.grid(row=0, column=1, sticky="ns")
            sx = ttk.Scrollbar(sales_wrap, orient="horizontal", command=sales_tree.xview)
            sx.grid(row=1, column=0, sticky="ew")
            sales_tree.configure(yscrollcommand=sy.set, xscrollcommand=sx.set)

            cols = ("username", "password", "status", "created_on", "last_login")
            tree = ttk.Treeview(table_wrap, columns=cols, show="headings")
            headings = {
                "username": "Username",
                "password": "Password",
                "status": "Status",
                "created_on": "Created On",
                "last_login": "Last Login",
            }
            for c in cols:
                tree.heading(c, text=headings[c])
                tree.column(c, width=140, anchor="center", stretch=True)
            tree.grid(row=0, column=0, sticky="nsew")

            ysb = ttk.Scrollbar(table_wrap, orient="vertical", command=tree.yview)
            ysb.grid(row=0, column=1, sticky="ns")
            xsb = ttk.Scrollbar(table_wrap, orient="horizontal", command=tree.xview)
            xsb.grid(row=1, column=0, sticky="ew")
            tree.configure(yscrollcommand=ysb.set, xscrollcommand=xsb.set)

            ttk.Label(form, text="Username").grid(row=0, column=0, sticky="w", padx=8, pady=(10, 4))
            create_username = ttk.Entry(form)
            create_username.grid(row=0, column=1, sticky="ew", padx=8, pady=(10, 4))

            ttk.Label(form, text="Password").grid(row=1, column=0, sticky="w", padx=8, pady=4)
            create_password = ttk.Entry(form, show="*")
            create_password.grid(row=1, column=1, sticky="ew", padx=8, pady=4)

            ttk.Label(form, text="Reset Password").grid(row=2, column=0, sticky="w", padx=8, pady=(12, 4))
            reset_password = ttk.Entry(form, show="*")
            reset_password.grid(row=2, column=1, sticky="ew", padx=8, pady=(12, 4))

            selected_var = tk.StringVar(value="Selected: -")
            ttk.Label(form, textvariable=selected_var, style="Subtle.TLabel").grid(
                row=3, column=0, columnspan=2, sticky="w", padx=8, pady=(8, 6)
            )
            status_var = tk.StringVar(value="")
            ttk.Label(form, textvariable=status_var, style="Subtle.TLabel").grid(
                row=8, column=0, columnspan=2, sticky="w", padx=8, pady=(8, 10)
            )

            def _selected_username():
                sel = tree.selection()
                if not sel:
                    return ""
                return str(tree.item(sel[0], "values")[0]).strip()

            def _active_accounts():
                return [a for a in load_shop_manager_accounts() if not a.get("is_deleted", False)]

            def _load_accounts():
                tree.delete(*tree.get_children())
                for a in _active_accounts():
                    status = "Active" if a.get("is_active", True) else "Inactive"
                    tree.insert(
                        "",
                        "end",
                        values=(
                            a.get("username", ""),
                            a.get("password", ""),
                            status,
                            a.get("created_on", ""),
                            a.get("last_login", ""),
                        ),
                    )
                selected_var.set("Selected: -")
                detail_header_var.set("Select an SM row to view complete details.")
                detail_tree.delete(*detail_tree.get_children())

            def _load_user_details(username):
                uname = str(username or "").strip()
                if not uname:
                    detail_header_var.set("Select an SM row to view complete details.")
                    detail_tree.delete(*detail_tree.get_children())
                    sales_tree.delete(*sales_tree.get_children())
                    sales_summary_var.set("Sales Summary: -")
                    return

                accounts = _active_accounts()
                account = None
                for a in accounts:
                    if str(a.get("username", "")).strip().lower() == uname.lower():
                        account = a
                        break

                detail_tree.delete(*detail_tree.get_children())
                sales_tree.delete(*sales_tree.get_children())
                path = os.path.join(app_dir(), "data", "audit_log.json")
                logs = []
                if os.path.exists(path):
                    try:
                        with open(path, "r", encoding="utf-8") as f:
                            logs = json.load(f)
                    except Exception:
                        logs = []

                manager_actions = [
                    r for r in logs
                    if str(r.get("user", "")).strip().lower() == uname.lower()
                ]
                admin_changes = [
                    r for r in logs
                    if str(r.get("module", "")).strip() == "shop_manager_accounts"
                    and str(r.get("reference", "")).strip().lower() == uname.lower()
                    and str(r.get("user", "")).strip().lower() in ("admin", "admin123")
                ]

                merged = []
                for r in manager_actions:
                    merged.append(("Performed by SM", r))
                for r in admin_changes:
                    merged.append(("Admin Account Change", r))
                merged = sorted(merged, key=lambda x: _parse_ts(x[1].get("timestamp")), reverse=True)

                for kind, r in merged:
                    detail_tree.insert(
                        "",
                        "end",
                        values=(
                            r.get("timestamp", ""),
                            kind,
                            r.get("module", ""),
                            r.get("action", ""),
                            r.get("reference", ""),
                        ),
                    )

                sales_refs = {
                    str(r.get("reference", "")).strip()
                    for r in logs
                    if str(r.get("user", "")).strip().lower() == uname.lower()
                    and str(r.get("module", "")).strip().lower() == "invoice"
                    and str(r.get("action", "")).strip().lower() == "create"
                    and str(r.get("reference", "")).strip()
                }
                sales_rows = [
                    s for s in load_sales()
                    if str(s.get("invoice_no", "")).strip() in sales_refs
                ]
                sales_rows = sorted(sales_rows, key=lambda s: _parse_ts(s.get("date")), reverse=True)
                sum_total = 0.0
                sum_paid = 0.0
                sum_due = 0.0
                for s in sales_rows:
                    gt = float(s.get("grand_total", 0) or 0)
                    pd = float(s.get("paid", s.get("paid_amount", 0)) or 0)
                    du = float(s.get("due", 0) or 0)
                    sum_total += gt
                    sum_paid += pd
                    sum_due += du
                    sales_tree.insert(
                        "",
                        "end",
                        values=(
                            s.get("invoice_no", ""),
                            s.get("date", ""),
                            s.get("customer_name", ""),
                            f"{gt:.2f}",
                            f"{pd:.2f}",
                            f"{du:.2f}",
                            s.get("payment_mode", ""),
                        ),
                    )
                sales_summary_var.set(
                    f"Sales Summary: Invoices={len(sales_rows)} | Total={sum_total:.2f} | Paid={sum_paid:.2f} | Due={sum_due:.2f}"
                )

                created_on = (account or {}).get("created_on", "")
                last_login = (account or {}).get("last_login", "")
                status = "Active" if (account or {}).get("is_active", True) else "Inactive"
                last_action = merged[0][1].get("timestamp", "") if merged else "-"
                detail_header_var.set(
                    f"SM: {uname} | Status: {status} | Created: {created_on or '-'} | Last Login: {last_login or '-'} | "
                    f"Actions by SM: {len(manager_actions)} | Admin Changes: {len(admin_changes)} | Last Activity: {last_action} | "
                    f"Sales Invoices: {len(sales_rows)}"
                )

            def _create_sm():
                uname = create_username.get().strip()
                pwd = create_password.get().strip()
                if len(uname) < 3:
                    messagebox.showerror("Invalid", "Username must be at least 3 characters.")
                    return
                if len(pwd) < 4:
                    messagebox.showerror("Invalid", "Password must be at least 4 characters.")
                    return
                if pwd in (ADMIN_PASSWORD, SHOP_MANAGER_PASSWORD):
                    messagebox.showerror("Invalid", "This password is reserved.")
                    return
                try:
                    create_shop_manager_account(uname, pwd)
                except ValueError as e:
                    messagebox.showerror("Invalid", str(e))
                    return
                write_audit_log(user="admin", module="shop_manager_accounts", action="create", reference=uname)
                create_username.delete(0, tk.END)
                create_password.delete(0, tk.END)
                status_var.set(f"Created account: {uname}")
                _load_accounts()
                _load_user_details(uname)

            def _reset_password():
                uname = _selected_username()
                if not uname:
                    messagebox.showerror("Select Account", "Select a Shop Manager account.")
                    return
                new_pwd = reset_password.get().strip()
                if len(new_pwd) < 4:
                    messagebox.showerror("Invalid", "New password must be at least 4 characters.")
                    return
                if new_pwd in (ADMIN_PASSWORD, SHOP_MANAGER_PASSWORD):
                    messagebox.showerror("Invalid", "This password is reserved.")
                    return
                accounts = load_shop_manager_accounts()
                target = None
                for a in accounts:
                    if str(a.get("username", "")).strip().lower() == uname.lower() and not a.get("is_deleted", False):
                        target = a
                        break
                if not target:
                    messagebox.showerror("Not Found", "Selected account not found.")
                    return
                target["password"] = new_pwd
                save_shop_manager_accounts(accounts)
                write_audit_log(user="admin", module="shop_manager_accounts", action="reset_password", reference=uname)
                reset_password.delete(0, tk.END)
                status_var.set(f"Password reset for: {uname}")
                _load_accounts()
                _load_user_details(uname)

            def _delete_selected():
                uname = _selected_username()
                if not uname:
                    messagebox.showerror("Select Account", "Select a Shop Manager account.")
                    return
                if not messagebox.askyesno("Confirm Delete", f"Permanently delete account: {uname}?"):
                    return
                accounts = load_shop_manager_accounts()
                new_accounts = [a for a in accounts if str(a.get("username", "")).strip().lower() != uname.lower()]
                if len(new_accounts) == len(accounts):
                    messagebox.showerror("Not Found", "Selected account not found.")
                    return
                save_shop_manager_accounts(new_accounts)
                write_audit_log(user="admin", module="shop_manager_accounts", action="delete", reference=uname)
                status_var.set(f"Deleted account: {uname}")
                _load_accounts()

            def _export_accounts():
                out_dir = os.path.join(app_dir(), "reports")
                os.makedirs(out_dir, exist_ok=True)
                path = os.path.join(out_dir, f"sm_accounts_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv")
                rows = [
                    {
                        "Username": a.get("username", ""),
                        "Password": a.get("password", ""),
                        "Status": "Active" if a.get("is_active", True) else "Inactive",
                        "Created On": a.get("created_on", ""),
                        "Last Login": a.get("last_login", ""),
                    }
                    for a in _active_accounts()
                ]
                with open(path, "w", newline="", encoding="utf-8") as f:
                    writer = csv.DictWriter(
                        f, fieldnames=["Username", "Password", "Status", "Created On", "Last Login"]
                    )
                    writer.writeheader()
                    writer.writerows(rows)
                write_audit_log(user="admin", module="shop_manager_accounts", action="export", reference=path)
                os.startfile(path)
                status_var.set(f"Exported: {path}")

            def _on_select(_event=None):
                uname = _selected_username()
                selected_var.set(f"Selected: {uname or '-'}")
                _load_user_details(uname)

            tree.bind("<<TreeviewSelect>>", _on_select)

            ttk.Button(form, text="Create SM", command=_create_sm).grid(
                row=4, column=0, columnspan=2, sticky="ew", padx=8, pady=(8, 4)
            )
            ttk.Button(form, text="Reset Password", command=_reset_password).grid(
                row=5, column=0, columnspan=2, sticky="ew", padx=8, pady=4
            )
            ttk.Button(form, text="Delete Selected", style="Danger.TButton", command=_delete_selected).grid(
                row=6, column=0, columnspan=2, sticky="ew", padx=8, pady=4
            )
            ttk.Button(form, text="Export List", command=_export_accounts).grid(
                row=7, column=0, columnspan=2, sticky="ew", padx=8, pady=4
            )

            _load_accounts()
            return frame

        self._switch_view(_build, cache_key="manage_sms")

    def logout(self):
        self.clear_right()
        set_current_audit_user(None)
        self.app.role = None
        self.app.show_frame("LoginFrame")


# ==================================================
# START
# ==================================================
if __name__ == "__main__":
    preload_system_files()
    App().mainloop()
