import tkinter as tk
from tkinter import ttk, messagebox
from datetime import datetime
import json
import os

from utils import app_dir
from date_picker import open_date_picker
from ui_theme import compact_form_grid


# ==================================================
# AUDIT VIEWER UI
# ==================================================
class AuditViewerUI(ttk.Frame):
    def __init__(self, parent):
        super().__init__(parent)
        self.pack(fill="both", expand=True)

        self.audit_data = []
        self.filtered = []

        self.load_audit_file()
        self.build_ui()

    # --------------------------------------------------
    # LOAD AUDIT FILE
    # --------------------------------------------------
    def load_audit_file(self):
        base = app_dir()
        data_dir = os.path.join(base, "data")
        self.audit_file = os.path.join(data_dir, "audit_log.json")

        if not os.path.exists(self.audit_file):
            self.audit_data = []
            return

        try:
            with open(self.audit_file, "r", encoding="utf-8") as f:
                self.audit_data = json.load(f)
        except Exception as e:
            messagebox.showerror("Error", f"Failed to load audit log\n{e}")
            self.audit_data = []

    # --------------------------------------------------
    # UI
    # --------------------------------------------------
    def build_ui(self):

        # ---------- TITLE ----------
        ttk.Label(
            self,
            text="Audit Log Viewer",
            font=("Arial", 16, "bold")
        ).pack(pady=(10, 15))

        # ---------- FILTER BAR ----------
        filters = ttk.LabelFrame(self, text="Filters")
        filters.pack(fill="x", padx=10, pady=5)

        ttk.Label(filters, text="From Date").grid(row=0, column=0, sticky="w")
        self.from_date = ttk.Entry(filters, width=14)
        self.from_date.grid(row=0, column=1, padx=5)
        self.from_date.insert(0, "DD-MM-YYYY")
        ttk.Button(
            filters,
            text="📅",
            width=5,
            command=lambda: open_date_picker(self, self.from_date),
        ).grid(row=0, column=2, padx=(0, 8), sticky="w")

        ttk.Label(filters, text="To Date").grid(row=0, column=3, sticky="w")
        self.to_date = ttk.Entry(filters, width=14)
        self.to_date.grid(row=0, column=4, padx=5)
        self.to_date.insert(0, "DD-MM-YYYY")
        ttk.Button(
            filters,
            text="📅",
            width=5,
            command=lambda: open_date_picker(self, self.to_date),
        ).grid(row=0, column=5, padx=(0, 8), sticky="w")

        ttk.Label(filters, text="User").grid(row=0, column=6, sticky="w")
        self.user_e = ttk.Entry(filters, width=14)
        self.user_e.grid(row=0, column=7, padx=5)

        ttk.Label(filters, text="Module").grid(row=0, column=8, sticky="w")
        self.module_e = ttk.Entry(filters, width=14)
        self.module_e.grid(row=0, column=9, padx=5)

        ttk.Button(
            filters,
            text="Apply",
            width=12,
            command=self.apply_filters
        ).grid(row=0, column=10, padx=10)

        ttk.Button(
            filters,
            text="Reset",
            width=10,
            command=self.reset_filters
        ).grid(row=0, column=11, padx=5)
        compact_form_grid(filters)

        # ---------- TABLE ----------
        cols = (
            "timestamp",
            "user",
            "module",
            "action",
            "reference"
        )

        table_frame = ttk.Frame(self)
        table_frame.pack(fill="both", expand=True, padx=10, pady=10)
        table_frame.columnconfigure(0, weight=1)
        table_frame.rowconfigure(0, weight=1)

        self.tree = ttk.Treeview(
            table_frame,
            columns=cols,
            show="headings",
            height=18
        )

        headings = {
            "timestamp": "Timestamp",
            "user": "User",
            "module": "Module",
            "action": "Action",
            "reference": "Reference"
        }

        for c in cols:
            self.tree.heading(c, text=headings[c])
            self.tree.column(c, anchor="center", width=160)

        self.tree.grid(row=0, column=0, sticky="nsew")

        ysb = ttk.Scrollbar(table_frame, orient="vertical", command=self.tree.yview)
        ysb.grid(row=0, column=1, sticky="ns")
        xsb = ttk.Scrollbar(table_frame, orient="horizontal", command=self.tree.xview)
        xsb.grid(row=1, column=0, sticky="ew")
        self.tree.configure(yscrollcommand=ysb.set, xscrollcommand=xsb.set)

        self.load_rows(self.audit_data)

    # --------------------------------------------------
    # LOAD TABLE ROWS
    # --------------------------------------------------
    def load_rows(self, rows):
        self.tree.delete(*self.tree.get_children())

        ordered_rows = sorted(
            rows,
            key=lambda r: self.parse_datetime(r.get("timestamp")) or datetime.min,
            reverse=True
        )

        for r in ordered_rows:
            self.tree.insert(
                "",
                "end",
                values=(
                    self.format_timestamp(r.get("timestamp", "")),
                    self.format_user_label(r.get("user", "")),
                    r.get("module", ""),
                    r.get("action", ""),
                    r.get("reference", "")
                )
            )

    # --------------------------------------------------
    # FILTER LOGIC
    # --------------------------------------------------
    def apply_filters(self):
        self.filtered = []

        from_d = self.parse_date(self.from_date.get())
        to_d = self.parse_date(self.to_date.get())
        user = self.user_e.get().strip().lower()
        module = self.module_e.get().strip().lower()

        for r in self.audit_data:
            ts = self.parse_datetime(r.get("timestamp"))

            if from_d and ts and ts < from_d:
                continue
            if to_d and ts and ts > to_d:
                continue

            display_user = self.format_user_label(r.get("user", "")).lower()
            if user and user not in display_user:
                continue

            if module and module not in r.get("module", "").lower():
                continue

            self.filtered.append(r)

        self.load_rows(self.filtered)

        if not self.filtered:
            messagebox.showinfo("Info", "No audit records found")

    def reset_filters(self):
        self.from_date.delete(0, tk.END)
        self.from_date.insert(0, "DD-MM-YYYY")

        self.to_date.delete(0, tk.END)
        self.to_date.insert(0, "DD-MM-YYYY")

        self.user_e.delete(0, tk.END)
        self.module_e.delete(0, tk.END)

        self.load_rows(self.audit_data)

    # --------------------------------------------------
    # DATE HELPERS
    # --------------------------------------------------
    def parse_date(self, value):
        try:
            if not value or value in ("YYYY-MM-DD", "DD-MM-YYYY"):
                return None
            for fmt in ("%d-%m-%Y", "%Y-%m-%d"):
                try:
                    return datetime.strptime(value, fmt)
                except Exception:
                    continue
            return None
        except Exception:
            return None

    def parse_datetime(self, value):
        try:
            if not value:
                return None
            text = str(value).strip()
            for fmt in ("%d-%m-%Y %H:%M:%S", "%d-%m-%Y", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
                try:
                    return datetime.strptime(text, fmt)
                except Exception:
                    continue
            return None
        except Exception:
            return None

    def format_timestamp(self, value):
        dt = self.parse_datetime(value)
        if not dt:
            return str(value or "")
        return dt.strftime("%d-%m-%Y %H:%M:%S")

    def format_user_label(self, user_value):
        text = str(user_value or "").strip().lower()
        if text in ("admin123", "admin"):
            return "admin"
        return "SM"

