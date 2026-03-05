import tkinter as tk
from tkinter import ttk, messagebox
from datetime import datetime

from sales import load_sales, save_sales
from audit_log import write_audit_log
from cash_ledger import add_cash_entry
from date_picker import open_date_picker
from ui_theme import compact_form_grid


class DueReportUI(ttk.Frame):
    def __init__(self, parent):
        super().__init__(parent)
        self.pack(fill="both", expand=True)

        self.all_sales = []
        self.filtered_rows = []
        self.tree_invoice_map = {}
        self.selected_customer = ""
        self.selected_phone = ""
        self._customer_values_all = []
        self._phone_values_all = []
        self._item_values_all = []
        self.name_suggest_win = None
        self.name_suggest_list = None
        self.phone_suggest_win = None
        self.phone_suggest_list = None
        self.item_suggest_win = None
        self.item_suggest_list = None

        self.total_due_var = tk.StringVar(value="Total Due: Rs0.00")
        self.selected_customer_var = tk.StringVar(value="Selected Customer: -")

        self.build_ui()
        self.load_due_data()

    def build_ui(self):
        ttk.Label(self, text="Sales Due Report", font=("Arial", 15, "bold")).pack(pady=(10, 12))

        filters = ttk.LabelFrame(self, text="Search Filters")
        filters.pack(fill="x", padx=10, pady=(0, 8))

        row1 = ttk.Frame(filters)
        row1.pack(fill="x", padx=4, pady=(4, 2))
        ttk.Label(row1, text="Customer Name").pack(side="left", padx=(0, 3))
        self.name_e = ttk.Combobox(row1, state="normal", width=24)
        self.name_e.pack(side="left", padx=(0, 8))
        self.name_e.bind("<KeyRelease>", self.on_customer_search)
        self.name_e.bind("<FocusOut>", self.on_name_focus_out)
        self.name_e.bind("<Down>", self.on_name_down_key)

        ttk.Label(row1, text="Phone").pack(side="left", padx=(0, 3))
        self.phone_e = ttk.Combobox(row1, state="normal", width=18)
        self.phone_e.pack(side="left", padx=(0, 8))
        phone_vcmd = (self.register(self._validate_phone_input), "%P")
        self.phone_e.configure(validate="key", validatecommand=phone_vcmd)
        self.phone_e.bind("<KeyRelease>", self._on_phone_change)
        self.phone_e.bind("<FocusOut>", self.on_phone_focus_out)
        self.phone_e.bind("<Down>", self.on_phone_down_key)

        ttk.Label(row1, text="Item").pack(side="left", padx=(0, 3))
        self.item_e = ttk.Combobox(row1, state="normal", width=20)
        self.item_e.pack(side="left", padx=(0, 8))
        self.item_e.bind("<KeyRelease>", self.on_item_search)
        self.item_e.bind("<FocusOut>", self.on_item_focus_out)
        self.item_e.bind("<Down>", self.on_item_down_key)

        row2 = ttk.Frame(filters)
        row2.pack(fill="x", padx=4, pady=(2, 4))
        ttk.Label(row2, text="From Date").pack(side="left", padx=(0, 3))
        self.from_date_e = ttk.Entry(row2, width=15)
        self.from_date_e.pack(side="left", padx=(0, 3))
        self.from_date_e.insert(0, "DD-MM-YYYY")
        ttk.Button(row2, text="📅", width=5, command=lambda: open_date_picker(self, self.from_date_e)).pack(
            side="left", padx=(0, 8)
        )

        ttk.Label(row2, text="To Date").pack(side="left", padx=(0, 3))
        self.to_date_e = ttk.Entry(row2, width=15)
        self.to_date_e.pack(side="left", padx=(0, 3))
        self.to_date_e.insert(0, "DD-MM-YYYY")
        ttk.Button(row2, text="📅", width=5, command=lambda: open_date_picker(self, self.to_date_e)).pack(
            side="left", padx=(0, 8)
        )

        ttk.Button(row2, text="Load Sales Due Report", command=self.load_due_data, width=22).pack(side="left", padx=(0, 4))
        compact_form_grid(filters)

        table_frame = ttk.Frame(self)
        table_frame.pack(fill="both", expand=True, padx=10, pady=8)
        table_frame.columnconfigure(0, weight=1)
        table_frame.rowconfigure(0, weight=1)

        cols = ("date", "invoice", "customer", "phone", "total", "paid", "due")
        self.tree = ttk.Treeview(table_frame, columns=cols, show="headings", height=12)
        headings = {
            "date": "Date",
            "invoice": "Invoice No",
            "customer": "Customer",
            "phone": "Phone",
            "total": "Total",
            "paid": "Paid",
            "due": "Due",
        }
        for c in cols:
            anchor = "center" if c not in ("customer",) else "w"
            self.tree.heading(c, text=headings[c])
            self.tree.column(c, anchor=anchor, stretch=True, width=140 if c != "customer" else 220)

        ysb = ttk.Scrollbar(table_frame, orient="vertical", command=self.tree.yview)
        xsb = ttk.Scrollbar(table_frame, orient="horizontal", command=self.tree.xview)
        self.tree.configure(yscrollcommand=ysb.set, xscrollcommand=xsb.set)
        self.tree.grid(row=0, column=0, sticky="nsew")
        ysb.grid(row=0, column=1, sticky="ns")
        xsb.grid(row=1, column=0, sticky="ew")
        self.tree.bind("<<TreeviewSelect>>", self.on_select_row)
        self.tree.bind("<Double-1>", self.on_row_double_click)
        self._setup_sorting()

        bottom = ttk.Frame(self)
        bottom.pack(fill="x", padx=20, pady=(0, 8))
        btns = ttk.Frame(bottom)
        btns.pack(side="left")
        ttk.Button(btns, text="Export Excel", width=15, command=self.export_excel).pack(side="left", padx=5)
        ttk.Button(btns, text="Export PDF", width=15, command=self.export_pdf).pack(side="left", padx=5)

        right_info = ttk.Frame(bottom)
        right_info.pack(side="right")
        ttk.Label(right_info, textvariable=self.selected_customer_var, style="Subtle.TLabel").pack(anchor="e")
        ttk.Label(right_info, textvariable=self.total_due_var, font=("Arial", 12, "bold"), foreground="red").pack(anchor="e")

        payment = ttk.LabelFrame(self, text="Receive Due Payment (Customer-wise)")
        payment.pack(fill="x", padx=20, pady=(0, 12))
        payment.columnconfigure(0, weight=1)
        payment.columnconfigure(1, weight=1)
        payment.columnconfigure(2, weight=1)
        payment.columnconfigure(3, weight=1)

        ttk.Label(payment, text="Pay Amount").grid(row=0, column=0, sticky="w", padx=5, pady=6)
        self.pay_amount_e = ttk.Entry(payment, width=15)
        self.pay_amount_e.grid(row=0, column=1, sticky="w", padx=5, pady=6)

        ttk.Label(payment, text="Payment Type").grid(row=0, column=2, sticky="w", padx=5, pady=6)
        self.pay_mode_cb = ttk.Combobox(
            payment, values=["Cash", "UPI", "Card", "Bank", "Other"], state="readonly", width=14
        )
        self.pay_mode_cb.set("Cash")
        self.pay_mode_cb.grid(row=0, column=3, sticky="w", padx=5, pady=6)

        ttk.Button(payment, text="Save Customer Payment", command=self.save_due_payment).grid(
            row=1, column=0, columnspan=4, padx=12, pady=(6, 8), sticky="e"
        )
        compact_form_grid(payment)

    def _validate_phone_input(self, proposed):
        if proposed == "":
            return True
        return proposed.isdigit() and len(proposed) <= 10

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
        x = self.name_e.winfo_rootx()
        y = self.name_e.winfo_rooty() + self.name_e.winfo_height() + 1
        w = max(self.name_e.winfo_width(), 220)
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
        self.name_e.set(picked)
        self._hide_name_suggestions()
        self.name_e.focus_set()
        self.name_e.icursor(tk.END)

    def on_name_focus_out(self, _event=None):
        self.after(120, self._hide_name_if_focus_lost)

    def _hide_name_if_focus_lost(self):
        w = self.focus_get()
        if w is self.name_e or w is self.name_suggest_list:
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
        x = self.phone_e.winfo_rootx()
        y = self.phone_e.winfo_rooty() + self.phone_e.winfo_height() + 1
        w = max(self.phone_e.winfo_width(), 180)
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
        self.phone_e.set(picked)
        self._hide_phone_suggestions()
        self.phone_e.focus_set()
        self.phone_e.icursor(tk.END)

    def on_phone_focus_out(self, _event=None):
        self.after(120, self._hide_phone_if_focus_lost)

    def _hide_phone_if_focus_lost(self):
        w = self.focus_get()
        if w is self.phone_e or w is self.phone_suggest_list:
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
        x = self.item_e.winfo_rootx()
        y = self.item_e.winfo_rooty() + self.item_e.winfo_height() + 1
        w = max(self.item_e.winfo_width(), 200)
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
        self.item_e.set(picked)
        self._hide_item_suggestions()
        self.item_e.focus_set()
        self.item_e.icursor(tk.END)

    def on_item_focus_out(self, _event=None):
        self.after(120, self._hide_item_if_focus_lost)

    def _hide_item_if_focus_lost(self):
        w = self.focus_get()
        if w is self.item_e or w is self.item_suggest_list:
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

    def _on_phone_change(self, _event=None):
        self.on_phone_search(_event)

    def on_customer_search(self, event=None):
        if event and event.keysym in ("Up", "Down", "Left", "Right", "Return", "Escape", "Tab"):
            return
        typed = self.name_e.get().strip().lower()
        if not typed:
            self._hide_name_suggestions()
            return
        matches = [v for v in self._customer_values_all if typed in v.lower()]
        self._show_name_suggestions(matches if matches else self._customer_values_all)

    def on_phone_search(self, event=None):
        if event and event.keysym in ("Up", "Down", "Left", "Right", "Return", "Escape", "Tab"):
            return
        typed = self.phone_e.get().strip()
        if not typed:
            self._hide_phone_suggestions()
            return
        matches = [v for v in self._phone_values_all if typed in v]
        self._show_phone_suggestions(matches if matches else self._phone_values_all)

    def on_item_search(self, event=None):
        if event and event.keysym in ("Up", "Down", "Left", "Right", "Return", "Escape", "Tab"):
            return
        typed = self.item_e.get().strip().lower()
        if not typed:
            self._hide_item_suggestions()
            return
        matches = [v for v in self._item_values_all if typed in v.lower()]
        self._show_item_suggestions(matches if matches else self._item_values_all)

    def parse_date(self, value):
        text = str(value or "").strip()
        if not text or text in ("DD-MM-YYYY", "YYYY-MM-DD"):
            return None
        for fmt in ("%d-%m-%Y %H:%M:%S", "%Y-%m-%d %H:%M:%S", "%d-%m-%Y", "%Y-%m-%d"):
            try:
                return datetime.strptime(text, fmt)
            except Exception:
                continue
        return None

    def format_date(self, value):
        dt = self.parse_date(value)
        if not dt:
            return str(value or "")
        return dt.strftime("%d-%m-%Y %H:%M:%S")

    def load_due_data(self):
        self.tree.delete(*self.tree.get_children())
        self.filtered_rows = []
        self.tree_invoice_map = {}
        self.selected_customer = ""
        self.selected_phone = ""
        self.selected_customer_var.set("Selected Customer: -")

        self.all_sales = load_sales()
        name = self.name_e.get().strip().lower()
        phone = self.phone_e.get().strip()
        item = self.item_e.get().strip().lower()
        from_date = self.parse_date(self.from_date_e.get().strip())
        to_date = self.parse_date(self.to_date_e.get().strip())

        customer_values = set()
        phone_values = set()
        item_values = set()
        for s in self.all_sales:
            nm = str(s.get("customer_name", "")).strip()
            ph = str(s.get("phone", "")).strip()
            if nm:
                customer_values.add(nm)
            if ph:
                phone_values.add(ph)
            for it in s.get("items", []):
                iname = str(it.get("item") or it.get("name") or "").strip()
                if iname:
                    item_values.add(iname)
        self._customer_values_all = sorted(customer_values, key=str.lower)
        self._phone_values_all = sorted(phone_values)
        self._item_values_all = sorted(item_values, key=str.lower)
        self.name_e["values"] = self._customer_values_all
        self.phone_e["values"] = self._phone_values_all
        self.item_e["values"] = self._item_values_all

        total_due = 0.0
        for s in self.all_sales:
            due = float(s.get("due", 0) or 0)
            if due <= 0:
                continue
            sale_dt = self.parse_date(s.get("date"))
            if from_date and (not sale_dt or sale_dt < from_date):
                continue
            if to_date and (not sale_dt or sale_dt > to_date):
                continue
            if phone and str(s.get("phone", "")).strip() != phone:
                continue
            if name and name not in str(s.get("customer_name", "")).strip().lower():
                continue
            if item:
                found = any(item in str((it.get("item") or it.get("name") or "")).lower() for it in s.get("items", []))
                if not found:
                    continue

            row = (
                self.format_date(s.get("date", "")),
                s.get("invoice_no", ""),
                s.get("customer_name", ""),
                s.get("phone", ""),
                f"{float(s.get('grand_total', 0) or 0):.2f}",
                f"{float(s.get('paid', s.get('paid_amount', 0)) or 0):.2f}",
                f"{due:.2f}",
            )
            self.filtered_rows.append((sale_dt or datetime.min, row, s))
            total_due += due

        self.filtered_rows.sort(key=lambda x: x[0], reverse=True)
        for _dt, row, sale in self.filtered_rows:
            iid = self.tree.insert("", "end", values=row)
            self.tree_invoice_map[iid] = sale

        self.total_due_var.set(f"Total Due: Rs{total_due:,.2f}")

    def on_select_row(self, _event=None):
        sel = self.tree.selection()
        if not sel:
            self.selected_customer = ""
            self.selected_phone = ""
            self.selected_customer_var.set("Selected Customer: -")
            return
        vals = self.tree.item(sel[0], "values")
        if not vals:
            return
        self.selected_customer = str(vals[2]).strip()
        self.selected_phone = str(vals[3]).strip()
        self.selected_customer_var.set(f"Selected Customer: {self.selected_customer} ({self.selected_phone})")

    def save_due_payment(self):
        if not self.selected_customer and not self.selected_phone:
            messagebox.showerror("Error", "Select a customer row first.")
            return
        try:
            pay_amount = float(self.pay_amount_e.get().strip())
        except Exception:
            messagebox.showerror("Error", "Enter a valid pay amount.")
            return
        if pay_amount <= 0:
            messagebox.showerror("Error", "Pay amount must be greater than 0.")
            return

        mode = self.pay_mode_cb.get().strip() or "Cash"
        sales = load_sales()
        targets = []
        for s in sales:
            due = float(s.get("due", 0) or 0)
            if due <= 0:
                continue
            same_phone = self.selected_phone and str(s.get("phone", "")).strip() == self.selected_phone
            same_name = str(s.get("customer_name", "")).strip().lower() == self.selected_customer.lower()
            if same_phone or same_name:
                targets.append(s)

        if not targets:
            messagebox.showerror("Error", "No due invoices found for selected customer.")
            return

        targets.sort(key=lambda x: self.parse_date(x.get("date")) or datetime.min, reverse=True)
        remaining = round(pay_amount, 2)
        changed_invoices = []

        for inv in targets:
            if remaining <= 0:
                break
            due_before = float(inv.get("due", 0) or 0)
            paid_before = float(inv.get("paid", inv.get("paid_amount", 0)) or 0)
            take = min(remaining, due_before)
            if take <= 0:
                continue
            inv["paid"] = round(paid_before + take, 2)
            inv["paid_amount"] = inv["paid"]
            inv["due"] = round(max(due_before - take, 0.0), 2)
            inv["last_payment_mode"] = mode
            changed_invoices.append((inv.get("invoice_no", ""), due_before, inv["due"]))
            remaining = round(remaining - take, 2)

        used_amount = round(pay_amount - remaining, 2)
        if used_amount <= 0:
            messagebox.showinfo("Info", "No due amount available for selected customer.")
            return

        save_sales(sales)
        write_audit_log(
            user="admin",
            module="due_payment",
            action="receive_customer",
            reference=self.selected_phone or self.selected_customer,
            after={
                "customer_name": self.selected_customer,
                "phone": self.selected_phone,
                "payment_mode": mode,
                "paid_amount": used_amount,
                "updated_invoices": [x[0] for x in changed_invoices],
            },
        )

        if mode == "Cash":
            add_cash_entry(
                date=datetime.now().strftime("%Y-%m-%d"),
                particulars=f"Customer Payment {self.selected_customer}",
                cash_in=used_amount,
                reference=self.selected_phone or self.selected_customer,
            )

        msg = f"Payment saved for {self.selected_customer}. Amount adjusted: {used_amount:.2f}"
        if remaining > 0:
            msg += f"\nUnused amount: {remaining:.2f} (no remaining due)."
        messagebox.showinfo("Success", msg)
        self.pay_amount_e.delete(0, tk.END)
        self.load_due_data()

    def export_excel(self):
        from export_excel import export_due_report_excel

        export_due_report_excel()

    def export_pdf(self):
        from report_pdf import generate_due_report_pdf

        generate_due_report_pdf()

    def _setup_sorting(self):
        for col in self.tree["columns"]:
            self.tree.heading(col, command=lambda c=col: self._sort_tree_column(c, False))

    def _sort_tree_column(self, col, reverse):
        def parse_value(v):
            text = str(v or "").strip()
            dt = self.parse_date(text)
            if dt:
                return (0, dt)
            try:
                return (1, float(text.replace(",", "")))
            except Exception:
                return (2, text.lower())

        rows = [(self.tree.set(k, col), k) for k in self.tree.get_children("")]
        rows.sort(key=lambda t: parse_value(t[0]), reverse=reverse)
        for idx, (_, k) in enumerate(rows):
            self.tree.move(k, "", idx)
        self.tree.heading(col, command=lambda c=col: self._sort_tree_column(c, not reverse))

    def on_row_double_click(self, _event=None):
        sel = self.tree.selection()
        if not sel:
            return
        sale = self.tree_invoice_map.get(sel[0])
        if not sale:
            return
        self._show_invoice_details_popup(sale)

    def _to_float(self, value):
        try:
            return float(value)
        except Exception:
            return 0.0

    def _show_invoice_details_popup(self, sale):
        win = tk.Toplevel(self)
        win.title(f"Invoice Details - {sale.get('invoice_no', '')}")
        win.geometry("980x560")
        win.transient(self.winfo_toplevel())

        wrap = ttk.Frame(win, padding=10)
        wrap.pack(fill="both", expand=True)
        wrap.columnconfigure(0, weight=1)
        wrap.rowconfigure(1, weight=1)

        paid = self._to_float(sale.get("paid", sale.get("paid_amount", 0)))
        total = self._to_float(sale.get("grand_total", 0))
        due = self._to_float(sale.get("due", max(total - paid, 0)))
        head = (
            f"Date: {self.format_date(sale.get('date', ''))}    Invoice: {sale.get('invoice_no', '')}\n"
            f"Customer: {sale.get('customer_name', '')}    Phone: {sale.get('phone', '')}    "
            f"Payment Mode: {sale.get('payment_mode', sale.get('last_payment_mode', ''))}"
        )
        ttk.Label(wrap, text=head, justify="left").grid(row=0, column=0, sticky="w", pady=(0, 8))

        cols = ("item", "unit", "qty", "rate", "gst", "line_total")
        tv = ttk.Treeview(wrap, columns=cols, show="headings")
        for c, h, w in (
            ("item", "Item", 280),
            ("unit", "Unit", 90),
            ("qty", "Qty", 90),
            ("rate", "Rate", 100),
            ("gst", "GST %", 90),
            ("line_total", "Line Total", 120),
        ):
            anchor = "w" if c in ("item", "unit") else "e"
            tv.heading(c, text=h, anchor=anchor)
            tv.column(c, anchor=anchor, width=w)

        y = ttk.Scrollbar(wrap, orient="vertical", command=tv.yview)
        x = ttk.Scrollbar(wrap, orient="horizontal", command=tv.xview)
        tv.configure(yscrollcommand=y.set, xscrollcommand=x.set)
        tv.grid(row=1, column=0, sticky="nsew")
        y.grid(row=1, column=1, sticky="ns")
        x.grid(row=2, column=0, sticky="ew")

        for it in sale.get("items", []):
            item_name = it.get("item") or it.get("name") or ""
            unit = it.get("unit", "Nos")
            qty = self._to_float(it.get("qty", 0))
            rate = self._to_float(it.get("rate", 0))
            gst = self._to_float(it.get("gst", it.get("gst_percent", 0)))
            line_total = self._to_float(it.get("total", qty * rate))
            tv.insert("", "end", values=(item_name, unit, f"{qty:.2f}", f"{rate:.2f}", f"{gst:.2f}", f"{line_total:.2f}"))

        ttk.Label(
            wrap,
            text=f"Total: {total:.2f}    Paid: {paid:.2f}    Due: {due:.2f}",
            style="Subtle.TLabel"
        ).grid(row=3, column=0, sticky="w", pady=(8, 0))
