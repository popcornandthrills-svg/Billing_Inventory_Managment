import tkinter as tk
from tkinter import ttk, messagebox
import os
from datetime import datetime

from audit_log import write_audit_log
from config import COMPANY
from utils_print import print_pdf
from sales import create_sale
from inventory import get_available_items, get_item_stock, load_inventory
from item_summary_report import get_item_summary_report
from customers import load_customers, get_customer_by_name
from customers import (
    save_customer,
    get_customer_by_phone,
    get_customer_by_name
)
from ui_theme import compact_form_grid

ITEM_TYPE_OPTIONS = ["Nos", "Kg", "Litre", "Metre"]


class BillingUI(ttk.Frame):
    def __init__(self, parent):
        super().__init__(parent)
        self.pack(fill="both", expand=True)
        
        #  ADD THESE LINES HERE
        self.columnconfigure(0, weight=1)
        
        #  Row height control (THIS IS FINAL SET)
        self.rowconfigure(0, weight=0)   # Customer section
        self.rowconfigure(1, weight=0)   # Add item section
        self.rowconfigure(2, weight=1)   # Table ONLY expands
        self.rowconfigure(3, weight=0)   # Edit/Delete
        self.rowconfigure(4, weight=0)   # Summary / Payment
        self.rowconfigure(5, weight=0)   # GST summary
        

        # ================= STATE =================
        self.cart = []
        self.edit_index = None
        self.grand_total = 0.0
        self.last_invoice_path = None
        self._saving_invoice = False
        self._quick_action_locked = False
        self._quick_action_job = None
        self._customers_cache = {}
        self._customer_name_values_all = []
        self._customer_phone_values_all = []
        self._customer_address_values_all = []
        self._stock_cache = {}
        self._selling_price_cache = {}
        self._item_values_all = []
        self.name_suggest_win = None
        self.name_suggest_list = None
        self.phone_suggest_win = None
        self.phone_suggest_list = None
        self.address_suggest_win = None
        self.address_suggest_list = None
        self.item_suggest_win = None
        self.item_suggest_list = None

        # ================= GRID =================
        self.columnconfigure(0, weight=1)

        # =================================================
        # ROW 0 : CUSTOMER DETAILS
        # =================================================
        top = ttk.Frame(self)
        top.grid(row=0, column=0, sticky="ew", padx=10, pady=8)

        ttk.Label(top, text="Customer Name").grid(row=0, column=0, sticky="w")
        
        self.cust_name = ttk.Combobox(top, state="normal", width=30)
        self.cust_name.grid(row=0, column=1, sticky="w")

        ttk.Label(top, text="Phone").grid(row=0, column=2, sticky="w")
        self.phone = ttk.Combobox(top, state="normal", width=15)
        self.phone.grid(row=0, column=3, padx=5)
        phone_vcmd = (self.register(self._validate_phone_input), "%P")
        self.phone.configure(validate="key", validatecommand=phone_vcmd)

        ttk.Label(top, text="Address").grid(row=1, column=0, sticky="w")
        self.address = ttk.Combobox(top, state="normal", width=50)
        self.address.grid(row=1, column=1, columnspan=3, padx=5, pady=4, sticky="w")

        self.cust_name.bind("<KeyRelease>", self.show_customer_suggestions)
        self.cust_name.bind("<<ComboboxSelected>>", self.autofill_by_name)
        self.cust_name.bind("<FocusOut>", self.on_name_focus_out)
        self.cust_name.bind("<Down>", self.on_name_down_key)
        self.phone.bind("<KeyRelease>", self.on_phone_change)
        self.phone.bind("<<ComboboxSelected>>", self.autofill_by_phone)
        self.phone.bind("<FocusOut>", self.on_phone_focus_out)
        self.phone.bind("<Down>", self.on_phone_down_key)
        self.address.bind("<KeyRelease>", self.filter_address_suggestions)
        self.address.bind("<FocusOut>", self.on_address_focus_out)
        self.address.bind("<Down>", self.on_address_down_key)
        compact_form_grid(top)

        # =================================================
        # ROW 1 : ADD ITEM SECTION
        # =================================================
        add = ttk.Frame(self)
        add.grid(row=1, column=0, sticky="ew", padx=10, pady=(10, 10))

        ttk.Label(add, text="Item").grid(row=0, column=0)
        ttk.Label(add, text="Unit").grid(row=0, column=2)
        ttk.Label(add, text="Qty").grid(row=0, column=3)
        ttk.Label(add, text="Rate").grid(row=0, column=4)
        ttk.Label(add, text="GST %").grid(row=0, column=5)
        
        self.item_cb = ttk.Combobox(add, state="normal", width=22)
        self.item_cb.grid(row=1, column=0, padx=5)
        self.item_cb.bind("<KeyRelease>", self.filter_items_live)
        self.item_cb.bind("<<ComboboxSelected>>", self.on_item_change)
        self.item_cb.bind("<FocusOut>", self.on_item_focus_out)
        self.item_cb.bind("<Down>", self.on_item_down_key)

        # ðŸ” SEARCH BUTTON
        self.find_btn = ttk.Button(
            add,
            text="Find",
            width=6,
            command=self.open_item_search
        )
        self.find_btn.grid(row=1, column=1, padx=2)

        self.type_cb = ttk.Combobox(add, values=ITEM_TYPE_OPTIONS, state="readonly", width=10)
        self.type_cb.set("Nos")
        self.type_cb.grid(row=1, column=2, padx=5)

        self.qty_e = ttk.Entry(add, width=8)
        self.qty_e.grid(row=1, column=3)
        self.stock_hint_var = tk.StringVar(value="Available: -")
        ttk.Label(add, textvariable=self.stock_hint_var, foreground="#1f4e79").grid(
            row=2, column=3, columnspan=2, sticky="w", padx=5, pady=(2, 0)
        )

        self.rate_e = ttk.Entry(add, width=10)
        self.rate_e.grid(row=1, column=4)

        self.gst_e = ttk.Entry(add, width=6)
        self.gst_e.insert(0, "18")
        self.gst_e.grid(row=1, column=5)
                        
                
        self.add_btn = ttk.Button(
            add, text="Add / Update Item", command=self.add_item
        )
        self.add_btn.grid(row=1, column=6, padx=12)

        self.refresh_items()
        compact_form_grid(add)

        # =================================================
        # ROW 2 : ITEMS TABLE
        # =================================================
        table_frame = ttk.Frame(self)
        table_frame.grid(row=2, column=0, sticky="nsew", padx=10, pady=5)
        table_frame.columnconfigure(0, weight=1)
        table_frame.columnconfigure(1, weight=0)


        self.tree = ttk.Treeview(
            table_frame,
            columns=("item", "type", "qty", "rate", "gst", "total"),
            show="headings",
            height=14
        )
                
        for col, txt, w in [
            ("item", "ITEM", 220),
            ("type", "TYPE", 90),
            ("qty", "QTY", 80),
            ("rate", "RATE", 100),
            ("gst", "GST %", 80),
            ("total", "TOTAL", 120),
        ]:
            self.tree.heading(col, text=txt)
            self.tree.column(col, width=w, anchor="center")
            
        # Vertical Scrollbar
        v_scroll = ttk.Scrollbar(
            table_frame,
            orient="vertical",
            command=self.tree.yview
        )
        self.tree.configure(yscrollcommand=v_scroll.set)

        self.tree.grid(row=0, column=0, sticky="nsew")
        v_scroll.grid(row=0, column=1, sticky="ns")

        # =================================================
        # ROW 3 : TABLE FOOTER (EDIT / DELETE)
        # =================================================
        table_footer = ttk.Frame(self)
        table_footer.grid(row=3, column=0, sticky="w", padx=10, pady=(0, 10))

        self.edit_btn = ttk.Button(
            table_footer, text="Edit Item", command=self.edit_item
        )
        self.edit_btn.pack(side="left", padx=4)

        self.delete_btn = ttk.Button(
            table_footer, text="Delete Item", command=self.delete_item
        )
        self.delete_btn.pack(side="left", padx=4)

        # =================================================
        # ROW 4 : BOTTOM SUMMARY (LEFT ALIGNED)
        # =================================================
        summary = ttk.Frame(self)
        summary.grid(row=4, column=0, sticky="w", padx=10, pady=(12, 10))

        self.taxable_var = tk.StringVar(value="Taxable: Rs0.00")
        self.cgst_var = tk.StringVar(value="CGST: Rs0.00")
        self.sgst_var = tk.StringVar(value="SGST: Rs0.00")
        self.igst_var = tk.StringVar(value="IGST: Rs0.00")
        self.discount_var = tk.StringVar(value="Discount: Rs0.00")
        self.round_off_var = tk.StringVar(value="Round Off: Rs0.00")
        self.grand_total_var = tk.StringVar(value="Grand Total: Rs0.00")
        self.total_var = tk.StringVar(value="Total: Rs0.00")
        self.balance_var = tk.StringVar(value="Due: Rs0.00")
        self.discount_mode = tk.StringVar(value="percent")
        self.discount_label_var = tk.StringVar(value="Discount")

        ttk.Label(summary, textvariable=self.taxable_var).grid(row=0, column=0, columnspan=6, sticky="w")
        ttk.Label(summary, textvariable=self.cgst_var).grid(row=1, column=0, columnspan=2, sticky="w")
        ttk.Label(summary, textvariable=self.sgst_var).grid(row=1, column=2, columnspan=2, sticky="w", padx=(14, 0))

        ttk.Label(summary, textvariable=self.discount_label_var).grid(row=2, column=0, sticky="w", pady=(2, 0))
        self.discount_e = ttk.Entry(summary, width=10)
        self.discount_e.insert(0, "")
        self.discount_e.grid(row=2, column=1, sticky="w", padx=(6, 4), pady=(2, 0))
        self.discount_e.bind("<KeyRelease>", lambda _e: self.refresh_total())
        self.discount_pct_btn = ttk.Button(summary, text="%", width=4, command=lambda: self._set_discount_mode("percent"))
        self.discount_pct_btn.grid(row=2, column=2, sticky="w", padx=(2, 2), pady=(2, 0))
        self.discount_amt_btn = ttk.Button(summary, text="Rs", width=4, command=lambda: self._set_discount_mode("amount"))
        self.discount_amt_btn.grid(row=2, column=3, sticky="w", padx=(2, 10), pady=(2, 0))
        ttk.Label(summary, textvariable=self.discount_var, foreground="#9a3412").grid(row=2, column=4, columnspan=2, sticky="w")

        ttk.Label(summary, textvariable=self.round_off_var, font=("Arial", 10), foreground="#1f4e79").grid(
            row=3, column=0, columnspan=6, sticky="w", pady=(2, 0)
        )

        ttk.Label(summary, textvariable=self.total_var, font=("Arial", 11, "bold"), foreground="green").grid(
            row=4, column=0, columnspan=6, sticky="w", pady=(2, 0)
        )

        ttk.Label(summary, text="Payment Mode").grid(row=5, column=0, sticky="w", pady=(4, 0))
        self.pay_mode = ttk.Combobox(
            summary, values=["Cash", "UPI", "Card", "Due"],
            state="readonly", width=12
        )
        self.pay_mode.current(0)
        self.pay_mode.grid(row=5, column=1, sticky="w", padx=(6, 0), pady=(4, 0))

        ttk.Label(summary, text="Paid Amount").grid(row=6, column=0, sticky="w", pady=(2, 0))
        self.paid_e = ttk.Entry(summary, width=12)
        self.paid_e.grid(row=6, column=1, sticky="w", padx=(6, 0), pady=(2, 0))
        self.paid_e.bind("<KeyRelease>", self.update_balance)
        ttk.Label(summary, textvariable=self.balance_var, font=("Arial", 10, "bold"), foreground="red").grid(
            row=6, column=2, columnspan=3, sticky="w", padx=(14, 0), pady=(2, 0)
        )

        self.generate_btn = ttk.Button(
            summary, text="Generate Invoice",
            command=self.save_sale, width=20
        )
        self.generate_btn.grid(row=7, column=0, columnspan=2, sticky="w", pady=(10, 0))

        self.print_btn = ttk.Button(
            summary, text="Print",
            command=self.print_invoice, width=14
        )
        self.print_btn.grid(row=7, column=2, columnspan=2, sticky="w", padx=(10, 0), pady=(10, 0))
        self.print_btn.config(state="disabled")
        self.status_var = tk.StringVar(value="")
        ttk.Label(summary, textvariable=self.status_var, foreground="#1f4e79").grid(
            row=8, column=0, columnspan=6, sticky="w", pady=(2, 0)
        )
        compact_form_grid(summary)
        self._set_discount_mode("percent")
        self._bind_enter_navigation()
        self.after(1, self._warm_load_customers)

    def _focus_next_widget(self, event):
        event.widget.tk_focusNext().focus_set()
        return "break"

    def _show_combobox_suggestions(self, widget, values):
        typed = widget.get()
        try:
            cursor = widget.index(tk.INSERT)
        except Exception:
            cursor = len(typed)

        widget["values"] = values
        widget.set(typed)
        try:
            widget.icursor(cursor)
        except Exception:
            pass

    def _round_amount_by_rule(self, value):
        # Always round down to the lower whole value.
        amount = float(value or 0)
        if amount <= 0:
            return 0.0
        return float(int(amount))

    def _set_discount_mode(self, mode):
        self.discount_mode.set("amount" if mode == "amount" else "percent")
        if self.discount_mode.get() == "amount":
            self.discount_label_var.set("Discount (Rs)")
        else:
            self.discount_label_var.set("Discount (%)")
        self.refresh_total()
        try:
            self.after(1, lambda: (self.discount_e.focus_set(), self.discount_e.icursor(tk.END)))
        except Exception:
            pass

    def _compute_discount(self, gross_total):
        try:
            raw_discount = float(self.discount_e.get() or 0)
        except ValueError:
            raw_discount = 0.0
        raw_discount = max(0.0, raw_discount)

        if self.discount_mode.get() == "amount":
            discount_amount = min(raw_discount, max(gross_total, 0.0))
            discount_percent = (discount_amount / gross_total * 100.0) if gross_total > 0 else 0.0
        else:
            discount_percent = min(raw_discount, 100.0)
            discount_amount = round(gross_total * (discount_percent / 100.0), 2)

        return round(discount_percent, 2), round(discount_amount, 2)

    def _bind_enter_navigation(self):
        for w in (
            self.cust_name,
            self.phone,
            self.address,
            self.item_cb,
            self.type_cb,
            self.qty_e,
            self.rate_e,
            self.gst_e,
            self.discount_e,
            self.pay_mode,
            self.paid_e,
        ):
            w.bind("<Return>", self._focus_next_widget)
            w.bind("<KP_Enter>", self._focus_next_widget)
        
    def show_customer_suggestions(self, event=None):
        if event and event.keysym in ("Up", "Down", "Left", "Right", "Return", "Escape", "Tab"):
            return
        typed = self.cust_name.get().strip().lower()
        if not typed:
            self.cust_name["values"] = self._customer_name_values_all
            self._hide_name_suggestions()
            return
        matches = [n for n in self._customer_name_values_all if typed in n.lower()]
        shown = matches if matches else self._customer_name_values_all
        self._show_name_suggestions(shown)

    def filter_phone_suggestions(self, event=None):
        if event and event.keysym in ("Up", "Down", "Left", "Right", "Return", "Escape", "Tab"):
            return
        typed = self.phone.get().strip()
        if not typed:
            self.phone["values"] = self._customer_phone_values_all
            self._hide_phone_suggestions()
            return
        matches = [p for p in self._customer_phone_values_all if typed in p]
        shown = matches if matches else self._customer_phone_values_all
        self._show_phone_suggestions(shown)

    def filter_address_suggestions(self, event=None):
        if event and event.keysym in ("Up", "Down", "Left", "Right", "Return", "Escape", "Tab"):
            return
        typed = self.address.get().strip().lower()
        if not typed:
            self.address["values"] = self._customer_address_values_all
            self._hide_address_suggestions()
            return
        matches = [a for a in self._customer_address_values_all if typed in a.lower()]
        shown = matches if matches else self._customer_address_values_all
        self._show_address_suggestions(shown)

    def _show_name_suggestions(self, values):
        if not values:
            self._hide_name_suggestions()
            return
        if self.name_suggest_win is None or not self.name_suggest_win.winfo_exists():
            self.name_suggest_win = tk.Toplevel(self)
            self.name_suggest_win.overrideredirect(True)
            self.name_suggest_win.attributes("-topmost", True)
            self.name_suggest_list = tk.Listbox(self.name_suggest_win, height=7, activestyle="none")
            self.name_suggest_list.pack(fill="both", expand=True)
            self.name_suggest_list.bind("<ButtonRelease-1>", self.on_name_pick_from_list)
            self.name_suggest_list.bind("<Return>", self.on_name_pick_from_list)
        self.name_suggest_list.delete(0, tk.END)
        for v in values:
            self.name_suggest_list.insert(tk.END, v)
        x = self.cust_name.winfo_rootx()
        y = self.cust_name.winfo_rooty() + self.cust_name.winfo_height() + 1
        w = max(self.cust_name.winfo_width(), 220)
        self.name_suggest_win.geometry(f"{w}x160+{x}+{y}")
        self.name_suggest_win.deiconify()
        self.name_suggest_win.lift()

    def _hide_name_suggestions(self):
        if self.name_suggest_win is not None and self.name_suggest_win.winfo_exists():
            self.name_suggest_win.withdraw()

    def on_name_pick_from_list(self, _event=None):
        if self.name_suggest_list is None or not self.name_suggest_list.curselection():
            return
        picked = self.name_suggest_list.get(self.name_suggest_list.curselection()[0])
        self.cust_name.set(picked)
        self._hide_name_suggestions()
        self.autofill_by_name()
        self.cust_name.focus_set()
        self.cust_name.icursor(tk.END)

    def on_name_focus_out(self, _event=None):
        self.after(120, self._hide_name_if_focus_lost)

    def _hide_name_if_focus_lost(self):
        w = self.focus_get()
        if w is self.cust_name or w is self.name_suggest_list:
            return
        self._hide_name_suggestions()

    def on_name_down_key(self, _event=None):
        if self.name_suggest_list is None:
            return
        if self.name_suggest_win is None or not self.name_suggest_win.winfo_exists():
            return
        if str(self.name_suggest_win.state()) != "normal":
            return
        if self.name_suggest_list.size() <= 0:
            return
        self.name_suggest_list.focus_set()
        self.name_suggest_list.selection_clear(0, tk.END)
        self.name_suggest_list.selection_set(0)
        self.name_suggest_list.activate(0)
        return "break"

    def _show_phone_suggestions(self, values):
        if not values:
            self._hide_phone_suggestions()
            return
        if self.phone_suggest_win is None or not self.phone_suggest_win.winfo_exists():
            self.phone_suggest_win = tk.Toplevel(self)
            self.phone_suggest_win.overrideredirect(True)
            self.phone_suggest_win.attributes("-topmost", True)
            self.phone_suggest_list = tk.Listbox(self.phone_suggest_win, height=7, activestyle="none")
            self.phone_suggest_list.pack(fill="both", expand=True)
            self.phone_suggest_list.bind("<ButtonRelease-1>", self.on_phone_pick_from_list)
            self.phone_suggest_list.bind("<Return>", self.on_phone_pick_from_list)
        self.phone_suggest_list.delete(0, tk.END)
        for v in values:
            self.phone_suggest_list.insert(tk.END, v)
        x = self.phone.winfo_rootx()
        y = self.phone.winfo_rooty() + self.phone.winfo_height() + 1
        w = max(self.phone.winfo_width(), 180)
        self.phone_suggest_win.geometry(f"{w}x160+{x}+{y}")
        self.phone_suggest_win.deiconify()
        self.phone_suggest_win.lift()

    def _hide_phone_suggestions(self):
        if self.phone_suggest_win is not None and self.phone_suggest_win.winfo_exists():
            self.phone_suggest_win.withdraw()

    def on_phone_pick_from_list(self, _event=None):
        if self.phone_suggest_list is None or not self.phone_suggest_list.curselection():
            return
        picked = self.phone_suggest_list.get(self.phone_suggest_list.curselection()[0])
        self.phone.set(picked)
        self._hide_phone_suggestions()
        self.autofill_by_phone()
        self.phone.focus_set()
        self.phone.icursor(tk.END)

    def on_phone_focus_out(self, _event=None):
        self.after(120, self._hide_phone_if_focus_lost)

    def _hide_phone_if_focus_lost(self):
        w = self.focus_get()
        if w is self.phone or w is self.phone_suggest_list:
            return
        self._hide_phone_suggestions()

    def on_phone_down_key(self, _event=None):
        if self.phone_suggest_list is None:
            return
        if self.phone_suggest_win is None or not self.phone_suggest_win.winfo_exists():
            return
        if str(self.phone_suggest_win.state()) != "normal":
            return
        if self.phone_suggest_list.size() <= 0:
            return
        self.phone_suggest_list.focus_set()
        self.phone_suggest_list.selection_clear(0, tk.END)
        self.phone_suggest_list.selection_set(0)
        self.phone_suggest_list.activate(0)
        return "break"

    def _show_address_suggestions(self, values):
        if not values:
            self._hide_address_suggestions()
            return
        if self.address_suggest_win is None or not self.address_suggest_win.winfo_exists():
            self.address_suggest_win = tk.Toplevel(self)
            self.address_suggest_win.overrideredirect(True)
            self.address_suggest_win.attributes("-topmost", True)
            self.address_suggest_list = tk.Listbox(self.address_suggest_win, height=7, activestyle="none")
            self.address_suggest_list.pack(fill="both", expand=True)
            self.address_suggest_list.bind("<ButtonRelease-1>", self.on_address_pick_from_list)
            self.address_suggest_list.bind("<Return>", self.on_address_pick_from_list)
        self.address_suggest_list.delete(0, tk.END)
        for v in values:
            self.address_suggest_list.insert(tk.END, v)
        x = self.address.winfo_rootx()
        y = self.address.winfo_rooty() + self.address.winfo_height() + 1
        w = max(self.address.winfo_width(), 300)
        self.address_suggest_win.geometry(f"{w}x160+{x}+{y}")
        self.address_suggest_win.deiconify()
        self.address_suggest_win.lift()

    def _hide_address_suggestions(self):
        if self.address_suggest_win is not None and self.address_suggest_win.winfo_exists():
            self.address_suggest_win.withdraw()

    def on_address_pick_from_list(self, _event=None):
        if self.address_suggest_list is None or not self.address_suggest_list.curselection():
            return
        picked = self.address_suggest_list.get(self.address_suggest_list.curselection()[0])
        self.address.set(picked)
        self._hide_address_suggestions()
        self.address.focus_set()
        self.address.icursor(tk.END)

    def on_address_focus_out(self, _event=None):
        self.after(120, self._hide_address_if_focus_lost)

    def _hide_address_if_focus_lost(self):
        w = self.focus_get()
        if w is self.address or w is self.address_suggest_list:
            return
        self._hide_address_suggestions()

    def on_address_down_key(self, _event=None):
        if self.address_suggest_list is None:
            return
        if self.address_suggest_win is None or not self.address_suggest_win.winfo_exists():
            return
        if str(self.address_suggest_win.state()) != "normal":
            return
        if self.address_suggest_list.size() <= 0:
            return
        self.address_suggest_list.focus_set()
        self.address_suggest_list.selection_clear(0, tk.END)
        self.address_suggest_list.selection_set(0)
        self.address_suggest_list.activate(0)
        return "break"

    def _warm_load_customers(self):
        try:
            self._customers_cache = load_customers()
        except Exception:
            self._customers_cache = {}
        names = []
        phones = []
        addresses = []
        for c in self._customers_cache.values():
            if not isinstance(c, dict):
                continue
            nm = str(c.get("name", "")).strip()
            ph = str(c.get("phone", "")).strip()
            ad = str(c.get("address", "")).strip()
            if nm:
                names.append(nm)
            if ph:
                phones.append(ph)
            if ad:
                addresses.append(ad)
        self._customer_name_values_all = sorted(set(names), key=str.lower)
        self._customer_phone_values_all = sorted(set(phones))
        self._customer_address_values_all = sorted(set(addresses), key=str.lower)
        self.cust_name["values"] = self._customer_name_values_all
        self.phone["values"] = self._customer_phone_values_all
        self.address["values"] = self._customer_address_values_all

    def _find_customer_by_phone(self, phone):
        key = str(phone or "").strip()
        if not key:
            return None
        for c in self._customers_cache.values():
            if str(c.get("phone", "")).strip() == key:
                return c
        return None

    def _find_customer_by_name(self, name):
        key = str(name or "").strip().lower()
        if not key:
            return None
        for c in self._customers_cache.values():
            if str(c.get("name", "")).strip().lower() == key:
                return c
        return None

    def _validate_phone_input(self, proposed):
        if proposed == "":
            return True
        return proposed.isdigit() and len(proposed) <= 10

    def _normalize_phone(self):
        cursor = 0
        try:
            cursor = self.phone.index(tk.INSERT)
        except Exception:
            cursor = 0
        raw = "".join(ch for ch in self.phone.get() if ch.isdigit())[:10]
        if raw != self.phone.get():
            self.phone.delete(0, tk.END)
            self.phone.insert(0, raw)
            try:
                self.phone.icursor(min(cursor, len(raw)))
            except Exception:
                pass
        return raw

    def on_phone_change(self, event=None):
        phone = self._normalize_phone()
        self.filter_phone_suggestions(event)
        if len(phone) == 10:
            self.autofill_by_phone()
        
        # =================================================
        # HELPERS / LOGIC (UNCHANGED)
        # =================================================
    def refresh_items(self):
        inv = load_inventory()
        self._stock_cache = {
            name: float((data or {}).get("stock", 0) or 0)
            for name, data in inv.items()
        }
        try:
            self._selling_price_cache = {
                str(r.get("item", "")).strip(): float(r.get("selling_price", 0) or 0)
                for r in get_item_summary_report()
                if str(r.get("item", "")).strip()
            }
        except Exception:
            self._selling_price_cache = {}
        items = sorted(inv.keys())
        self._item_values_all = items
        current = self.item_cb.get().strip()
        self.item_cb["values"] = items
        if not current or current not in items:
            self.item_cb.set("")
        self.update_qty_dropdown()
        self.update_rate_for_item()

    def filter_items_live(self, event=None):
        if event and event.keysym in ("Up", "Down", "Left", "Right", "Return", "Escape", "Tab"):
            return
        typed = self.item_cb.get().strip().lower()
        if not typed:
            self.item_cb["values"] = self._item_values_all
            self._hide_item_suggestions()
            self.update_qty_dropdown()
            return
        matches = [name for name in self._item_values_all if typed in name.lower()]
        shown = matches if matches else self._item_values_all
        self._show_item_suggestions(shown)
        self.update_qty_dropdown()

    def _show_item_suggestions(self, values):
        if not values:
            self._hide_item_suggestions()
            return
        if self.item_suggest_win is None or not self.item_suggest_win.winfo_exists():
            self.item_suggest_win = tk.Toplevel(self)
            self.item_suggest_win.overrideredirect(True)
            self.item_suggest_win.attributes("-topmost", True)
            self.item_suggest_list = tk.Listbox(self.item_suggest_win, height=7, activestyle="none")
            self.item_suggest_list.pack(fill="both", expand=True)
            self.item_suggest_list.bind("<ButtonRelease-1>", self.on_item_pick_from_list)
            self.item_suggest_list.bind("<Return>", self.on_item_pick_from_list)
        self.item_suggest_list.delete(0, tk.END)
        for v in values:
            self.item_suggest_list.insert(tk.END, v)
        x = self.item_cb.winfo_rootx()
        y = self.item_cb.winfo_rooty() + self.item_cb.winfo_height() + 1
        w = max(self.item_cb.winfo_width(), 220)
        self.item_suggest_win.geometry(f"{w}x160+{x}+{y}")
        self.item_suggest_win.deiconify()
        self.item_suggest_win.lift()

    def _hide_item_suggestions(self):
        if self.item_suggest_win is not None and self.item_suggest_win.winfo_exists():
            self.item_suggest_win.withdraw()

    def on_item_pick_from_list(self, _event=None):
        if self.item_suggest_list is None or not self.item_suggest_list.curselection():
            return
        picked = self.item_suggest_list.get(self.item_suggest_list.curselection()[0])
        self.item_cb.set(picked)
        self._hide_item_suggestions()
        self.on_item_change()
        self.item_cb.focus_set()
        self.item_cb.icursor(tk.END)

    def on_item_focus_out(self, _event=None):
        self.after(120, self._hide_item_if_focus_lost)

    def _hide_item_if_focus_lost(self):
        w = self.focus_get()
        if w is self.item_cb or w is self.item_suggest_list:
            return
        self._hide_item_suggestions()

    def on_item_down_key(self, _event=None):
        if self.item_suggest_list is None:
            return
        if self.item_suggest_win is None or not self.item_suggest_win.winfo_exists():
            return
        if str(self.item_suggest_win.state()) != "normal":
            return
        if self.item_suggest_list.size() <= 0:
            return
        self.item_suggest_list.focus_set()
        self.item_suggest_list.selection_clear(0, tk.END)
        self.item_suggest_list.selection_set(0)
        self.item_suggest_list.activate(0)
        return "break"

    def _available_stock_for_item(self, item_name):
        item = str(item_name or "").strip()
        if not item:
            return None
        stock = self._stock_cache.get(item)
        if stock is None:
            stock = float(get_item_stock(item))
            self._stock_cache[item] = stock
        return max(0.0, float(stock))

    def _selling_price_for_item(self, item_name):
        item = str(item_name or "").strip()
        if not item:
            return None
        if item in self._selling_price_cache:
            return float(self._selling_price_cache[item])
        inv = load_inventory()
        if item in inv:
            return float((inv.get(item) or {}).get("rate", 0) or 0)
        return None

    def update_qty_dropdown(self):
        item = self.item_cb.get().strip()
        stock = self._available_stock_for_item(item)
        if stock is None:
            self.stock_hint_var.set("Available: -")
            return
        max_qty = int(stock)
        self.stock_hint_var.set(f"Available: {max_qty}")

    def update_rate_for_item(self):
        item = self.item_cb.get().strip()
        if not item:
            return
        price = self._selling_price_for_item(item)
        if price is None:
            return
        self.rate_e.delete(0, tk.END)
        self.rate_e.insert(0, f"{price:.2f}".rstrip("0").rstrip("."))

    def on_item_change(self, _event=None):
        self._hide_item_suggestions()
        self.update_qty_dropdown()
        self.update_rate_for_item()

    def autofill_by_phone(self, event=None):
        c = self._find_customer_by_phone(self.phone.get().strip()) or get_customer_by_phone(self.phone.get().strip())
        if c:
            self.cust_name.delete(0, tk.END)
            self.cust_name.insert(0, c["name"])
            self.address.delete(0, tk.END)
            self.address.insert(0, c.get("address", ""))

    def autofill_by_name(self, event=None):
        c = self._find_customer_by_name(self.cust_name.get().strip()) or get_customer_by_name(self.cust_name.get().strip())
        if c:
            self.phone.delete(0, tk.END)
            self.phone.insert(0, c["phone"])
            self._normalize_phone()
            self.address.delete(0, tk.END)
            self.address.insert(0, c.get("address", ""))

    def get_selected_index(self):
        sel = self.tree.selection()
        return self.tree.index(sel[0]) if sel else None

    def _lock_quick_actions(self, ms=220):
        self._quick_action_locked = True
        if self._quick_action_job:
            try:
                self.after_cancel(self._quick_action_job)
            except Exception:
                pass
        self._quick_action_job = self.after(ms, self._unlock_quick_actions)

    def _unlock_quick_actions(self):
        self._quick_action_locked = False
        self._quick_action_job = None

    # ================= ITEMS =================
    def add_item(self):
        if self._saving_invoice or self._quick_action_locked:
            return
        self._lock_quick_actions()
        try:
            item = self.item_cb.get()
            item_type = self.type_cb.get().strip()
            qty = int(self.qty_e.get())
            rate = float(self.rate_e.get())
            gst = float(self.gst_e.get() or 0)

            current_stock = self._stock_cache.get(item)
            if current_stock is None:
                current_stock = float(get_item_stock(item))
                self._stock_cache[item] = current_stock
            if qty > current_stock:
                messagebox.showerror("Stock Error", f"Insufficient stock. Available: {int(current_stock)}")
                return

            total = qty * rate * (1 + gst / 100)
            row = {"item": item, "type": item_type, "qty": qty, "rate": rate, "gst": gst, "total": total}

            if self.edit_index is not None:
                self.cart[self.edit_index] = row
                self.tree.item(self.tree.get_children()[self.edit_index],
                               values=(item, item_type, qty, rate, gst, total))
                self.edit_index = None
            else:
                self.cart.append(row)
                self.tree.insert("", "end", values=(item, item_type, qty, rate, gst, total))

            self.refresh_total()
            self.qty_e.delete(0, tk.END)
            self.rate_e.delete(0, tk.END)
            self.type_cb.set("Nos")

        except Exception:
            messagebox.showerror("Error", "Invalid item data")

    def edit_item(self):
        if self._saving_invoice or self._quick_action_locked:
            return
        self._lock_quick_actions()
        idx = self.get_selected_index()
        if idx is None:
            return
        i = self.cart[idx]
        self.item_cb.set(i["item"])
        self.update_qty_dropdown()
        self.type_cb.set(i.get("type", ""))
        self.qty_e.delete(0, tk.END)
        self.qty_e.insert(0, i["qty"])
        self.rate_e.delete(0, tk.END)
        self.rate_e.insert(0, i["rate"])
        self.gst_e.delete(0, tk.END)
        self.gst_e.insert(0, i["gst"])
        self.edit_index = idx

    def delete_item(self):
        if self._saving_invoice or self._quick_action_locked:
            return
        self._lock_quick_actions()
        idx = self.get_selected_index()
        if idx is None:
            return
        self.cart.pop(idx)
        self.tree.delete(self.tree.get_children()[idx])
        self.refresh_total()

    # ================= TOTALS =================
    def refresh_total(self):
        taxable = cgst = sgst = 0.0
        for i in self.cart:
            base = i["qty"] * i["rate"]
            tax = base * i["gst"] / 100
            taxable += base
            cgst += tax / 2
            sgst += tax / 2

        gross_total = taxable + cgst + sgst
        discount_percent, discount_amount = self._compute_discount(gross_total)
        calculated_total = max(gross_total - discount_amount, 0.0)
        self.grand_total = self._round_amount_by_rule(calculated_total)
        self.discount_percent = discount_percent
        self.discount_amount = discount_amount
        self.gross_total = gross_total
        round_off = round(self.grand_total - calculated_total, 2)

        self.taxable_var.set(f"Taxable: Rs{taxable:.2f}")
        self.cgst_var.set(f"CGST: Rs{cgst:.2f}")
        self.sgst_var.set(f"SGST: Rs{sgst:.2f}")
        self.igst_var.set("IGST: Rs0.00")
        if self.discount_mode.get() == "amount":
            self.discount_var.set(f"Discount: Rs{discount_amount:.2f} ({discount_percent:.2f}%)")
        else:
            self.discount_var.set(f"Discount: Rs{discount_amount:.2f} ({discount_percent:.2f}%)")
        self.round_off_var.set(f"Round Off: Rs{round_off:.2f}")
        self.grand_total_var.set(f"Grand Total: Rs{self.grand_total:.2f}")
        self.total_var.set(f"Total: Rs{self.grand_total:.2f}")
        self.update_balance()

    def update_balance(self, event=None):
        try:
            paid = float(self.paid_e.get() or 0)
        except ValueError:
            paid = 0
        self.balance_var.set(f"Due: Rs{max(self.grand_total - paid, 0):.2f}")

    # ================= SAVE + PRINT =================
    def save_sale(self):
        if self._saving_invoice:
            return
        if not self.cart:
            messagebox.showerror("Error", "No items added")
            return
        phone = self._normalize_phone().strip()
        if not (phone.isdigit() and len(phone) == 10):
            messagebox.showerror("Error", "Phone must be exactly 10 digits.")
            self.phone.focus_set()
            return

        try:
            paid = float(self.paid_e.get() or 0)
        except ValueError:
            messagebox.showerror("Error", "Invalid paid amount")
            return
        self._saving_invoice = True
        self.generate_btn.config(state="disabled")
        self.find_btn.config(state="disabled")
        self.add_btn.config(state="disabled")
        self.edit_btn.config(state="disabled")
        self.delete_btn.config(state="disabled")
        self.update_idletasks()
        try:
            from gst import calculate_gst_items
            from invoice_pdf import generate_gst_invoice_pdf

            gst_items = [{
                "name": i["item"],
                "qty": i["qty"],
                "rate": i["rate"],
                "gst_percent": i["gst"]
            } for i in self.cart]

            gst_items, summary = calculate_gst_items(
                gst_items, company_state="AP", customer_state="AP"
            )
            gross_total = float(summary.get("grand_total", 0) or 0)
            discount_percent, discount_amount = self._compute_discount(gross_total)
            summary["gross_total"] = round(gross_total, 2)
            summary["discount_percent"] = round(discount_percent, 2)
            summary["discount_amount"] = round(discount_amount, 2)
            summary["grand_total"] = self._round_amount_by_rule(max(gross_total - discount_amount, 0.0))

            invoice_no = create_sale(
                customer_name=self.cust_name.get(),
                phone=phone,
                items=gst_items,
                payment_mode=self.pay_mode.get(),
                paid_amount=paid,
                discount_percent=discount_percent
            )

            write_audit_log(
                user="admin",
                module="invoice",
                action="create",
                reference=invoice_no,
                after={
                    "customer": self.cust_name.get(),
                    "phone": phone,
                    "total": summary.get("grand_total"),
                    "paid": paid,
                    "payment_mode": self.pay_mode.get(),
                    "items_count": len(gst_items)
                }
            )

            save_customer(
                name=self.cust_name.get(),
                phone=phone,
                address=self.address.get()
            )
            self._customers_cache = load_customers()
            self._warm_load_customers()
            for i in gst_items:
                name = i.get("item") or i.get("name")
                sold_qty = float(i.get("qty", 0) or 0)
                if name in self._stock_cache:
                    self._stock_cache[name] = max(self._stock_cache[name] - sold_qty, 0.0)

            pdf_path = f"invoices/{invoice_no}.pdf"
            generate_gst_invoice_pdf(
                filepath=pdf_path,
                company=COMPANY,
                invoice_no=invoice_no,
                invoice_date=datetime.now().strftime("%d-%m-%Y"),
                customer={"name": self.cust_name.get(), "gstin": "", "state": "AP"},
                items=gst_items,
                summary=summary
            )

            self.last_invoice_path = os.path.abspath(pdf_path)
            self.print_btn.config(state="normal")
            os.startfile(self.last_invoice_path)
            self.status_var.set(f"Invoice Created : {invoice_no}")
            self.reset_form_for_next_invoice()
        finally:
            self._saving_invoice = False
            self.generate_btn.config(state="normal")
            self.find_btn.config(state="normal")
            self.add_btn.config(state="normal")
            self.edit_btn.config(state="normal")
            self.delete_btn.config(state="normal")

    def print_invoice(self):
        if self._saving_invoice:
            return
        if not self.last_invoice_path:
            messagebox.showerror("Error", "Generate invoice first")
            return
        print_pdf(self.last_invoice_path)
        
    def open_item_search(self):
        if self._saving_invoice or self._quick_action_locked:
            return
        self._lock_quick_actions()
        self.after(1, self.refresh_items)
        self.after(1, self._warm_load_customers)
        self.item_cb.focus_set()
        self._show_item_suggestions(self._item_values_all)

    def reset_form_for_next_invoice(self):
        self.cart.clear()
        self.edit_index = None
        self.tree.delete(*self.tree.get_children())

        self.cust_name.delete(0, tk.END)
        self.phone.delete(0, tk.END)
        self.address.delete(0, tk.END)

        self.item_cb.set("")
        self._hide_item_suggestions()
        self.type_cb.set("Nos")
        self.qty_e.delete(0, tk.END)
        self.rate_e.delete(0, tk.END)
        self.gst_e.delete(0, tk.END)
        self.gst_e.insert(0, "18")
        self.stock_hint_var.set("Available: -")

        self.pay_mode.current(0)
        self.paid_e.delete(0, tk.END)
        self.paid_e.insert(0, "")
        if hasattr(self, "discount_e"):
            self.discount_e.delete(0, tk.END)
            self.discount_e.insert(0, "")
        if hasattr(self, "_set_discount_mode"):
            self._set_discount_mode("percent")

        self.last_invoice_path = None
        self.print_btn.config(state="disabled")
        # Keep last success text visible until next action.
        self.refresh_total()

        
