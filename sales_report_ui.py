import tkinter as tk
from tkinter import ttk, messagebox
from datetime import datetime

from sales import load_sales
from date_picker import open_date_picker
from report_pdf import generate_sales_report_pdf
from utils_print import print_pdf
from ui_theme import compact_form_grid


class SalesReportUI(ttk.Frame):
    def __init__(self, parent):
        super().__init__(parent)
        self.pack(fill="both", expand=True, padx=10, pady=10)

        self.sales = []
        self.filtered_sales = []
        self.tree_invoice_map = {}
        self.item_values_all = []
        self.customer_values_all = []
        self.item_suggest_win = None
        self.item_suggest_list = None
        self.customer_suggest_win = None
        self.customer_suggest_list = None

        self.build_ui()
        self.load_data()

    def build_ui(self):
        ttk.Label(self, text="Sales Report", font=("Arial", 15, "bold")).pack(pady=(0, 10))

        filter_frame = ttk.LabelFrame(self, text="Filters")
        filter_frame.pack(fill="x", padx=10, pady=(0, 8))

        self.filter_var = tk.StringVar(value="date")
        ttk.Radiobutton(
            filter_frame, text="Date-wise", variable=self.filter_var, value="date", command=self.on_filter_change
        ).grid(row=0, column=0, padx=8, pady=6)
        ttk.Radiobutton(
            filter_frame, text="Item-wise", variable=self.filter_var, value="item", command=self.on_filter_change
        ).grid(row=0, column=1, padx=8, pady=6)
        ttk.Radiobutton(
            filter_frame, text="Customer-wise", variable=self.filter_var, value="customer", command=self.on_filter_change
        ).grid(row=0, column=2, padx=8, pady=6)

        ttk.Label(filter_frame, text="From Date").grid(row=1, column=0, sticky="w")
        self.from_date = ttk.Entry(filter_frame, width=15)
        self.from_date.insert(0, "DD-MM-YYYY")
        self.from_date.grid(row=1, column=1, sticky="w")
        ttk.Button(
            filter_frame, text="📅", width=5, command=lambda: open_date_picker(self, self.from_date)
        ).grid(row=1, column=2, sticky="w", padx=(4, 8))

        ttk.Label(filter_frame, text="To Date").grid(row=1, column=3, sticky="w")
        self.to_date = ttk.Entry(filter_frame, width=15)
        self.to_date.insert(0, "DD-MM-YYYY")
        self.to_date.grid(row=1, column=4, sticky="w")
        ttk.Button(
            filter_frame, text="📅", width=5, command=lambda: open_date_picker(self, self.to_date)
        ).grid(row=1, column=5, sticky="w", padx=(4, 8))

        ttk.Button(filter_frame, text="Load Report", command=self.load_report).grid(row=1, column=6, padx=10)

        ttk.Label(filter_frame, text="Item").grid(row=2, column=0, sticky="w", pady=(6, 4))
        self.item_cb = ttk.Combobox(filter_frame, width=28, state="normal")
        self.item_cb.grid(row=2, column=1, columnspan=3, sticky="w", pady=(6, 4))
        self.item_cb.bind("<KeyRelease>", self.on_item_search)
        self.item_cb.bind("<FocusOut>", self.on_item_focus_out)
        self.item_cb.bind("<Down>", self.on_item_down_key)

        ttk.Label(filter_frame, text="Customer").grid(row=3, column=0, sticky="w", pady=(2, 6))
        self.customer_cb = ttk.Combobox(filter_frame, width=28, state="normal")
        self.customer_cb.grid(row=3, column=1, columnspan=3, sticky="w", pady=(2, 6))
        self.customer_cb.bind("<KeyRelease>", self.on_customer_search)
        self.customer_cb.bind("<FocusOut>", self.on_customer_focus_out)
        self.customer_cb.bind("<Down>", self.on_customer_down_key)

        compact_form_grid(filter_frame)
        self.item_cb.grid_remove()
        self.customer_cb.grid_remove()

        table_frame = ttk.Frame(self)
        table_frame.pack(fill="both", expand=True, padx=10, pady=8)
        table_frame.columnconfigure(0, weight=1)
        table_frame.rowconfigure(0, weight=1)

        cols = ("date", "invoice", "customer", "phone", "total", "paid", "due")
        self.tree = ttk.Treeview(table_frame, columns=cols, show="headings")
        headings = {
            "date": "Date",
            "invoice": "Invoice",
            "customer": "Customer",
            "phone": "Customer Number",
            "total": "Total",
            "paid": "Paid",
            "due": "Due",
        }
        for c in cols:
            anchor = "w" if c in ("date", "invoice", "customer", "phone") else "e"
            width = 170 if c in ("date", "customer") else (140 if c == "phone" else 120)
            self.tree.heading(c, text=headings[c], anchor=anchor)
            self.tree.column(c, width=width, anchor=anchor)

        ysb = ttk.Scrollbar(table_frame, orient="vertical", command=self.tree.yview)
        xsb = ttk.Scrollbar(table_frame, orient="horizontal", command=self.tree.xview)
        self.tree.configure(yscrollcommand=ysb.set, xscrollcommand=xsb.set)
        self.tree.grid(row=0, column=0, sticky="nsew")
        ysb.grid(row=0, column=1, sticky="ns")
        xsb.grid(row=1, column=0, sticky="ew")
        self.tree.bind("<<TreeviewSelect>>", self.on_selection_change)
        self.tree.bind("<Double-1>", self.on_row_double_click)
        self._setup_sorting()

        bottom = ttk.Frame(self)
        bottom.pack(fill="x", padx=10, pady=(0, 4))

        self.summary_var = tk.StringVar(value="")
        ttk.Label(bottom, textvariable=self.summary_var, font=("Arial", 10, "bold"), foreground="green").pack(
            side="left"
        )

        actions = ttk.Frame(bottom)
        actions.pack(side="right")
        ttk.Button(actions, text="Export Excel", command=self.on_export_excel, width=14).pack(side="left", padx=4)
        ttk.Button(actions, text="Export PDF", command=self.on_export_pdf, width=14).pack(side="left", padx=4)
        ttk.Button(actions, text="Print", command=self.on_print, width=12).pack(side="left", padx=4)

        self.selected_summary_var = tk.StringVar(value="Selected: 0 | Total: 0.00 | Paid: 0.00 | Due: 0.00")
        ttk.Label(self, textvariable=self.selected_summary_var, style="Subtle.TLabel").pack(
            anchor="e", padx=12, pady=(2, 0)
        )

    def _to_float(self, value):
        try:
            return float(value)
        except Exception:
            return 0.0

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

    def _show_customer_suggestions(self, values):
        if not values:
            self._hide_customer_suggestions()
            return
        if self.customer_suggest_win is None or not self.customer_suggest_win.winfo_exists():
            self.customer_suggest_win = tk.Toplevel(self)
            self.customer_suggest_win.overrideredirect(True)
            self.customer_suggest_win.attributes("-topmost", True)
            self.customer_suggest_list = tk.Listbox(self.customer_suggest_win, height=7, activestyle="none")
            self.customer_suggest_list.pack(fill="both", expand=True)
            self.customer_suggest_list.bind("<ButtonRelease-1>", self.on_customer_pick_from_list)
            self.customer_suggest_list.bind("<Return>", self.on_customer_pick_from_list)
        self.customer_suggest_list.delete(0, tk.END)
        for v in values:
            self.customer_suggest_list.insert(tk.END, v)
        x = self.customer_cb.winfo_rootx()
        y = self.customer_cb.winfo_rooty() + self.customer_cb.winfo_height() + 1
        w = max(self.customer_cb.winfo_width(), 220)
        self.customer_suggest_win.geometry(f"{w}x160+{x}+{y}")
        self.customer_suggest_win.deiconify()
        self.customer_suggest_win.lift()

    def _hide_customer_suggestions(self):
        if self.customer_suggest_win is not None and self.customer_suggest_win.winfo_exists():
            self.customer_suggest_win.withdraw()

    def on_customer_pick_from_list(self, _event=None):
        if self.customer_suggest_list is None or not self.customer_suggest_list.curselection():
            return
        picked = self.customer_suggest_list.get(self.customer_suggest_list.curselection()[0])
        self.customer_cb.set(picked)
        self._hide_customer_suggestions()
        self.customer_cb.focus_set()
        self.customer_cb.icursor(tk.END)

    def on_customer_focus_out(self, _event=None):
        self.after(120, self._hide_customer_if_focus_lost)

    def _hide_customer_if_focus_lost(self):
        w = self.focus_get()
        if w is self.customer_cb or w is self.customer_suggest_list:
            return
        self._hide_customer_suggestions()

    def on_customer_down_key(self, _event=None):
        if self.customer_suggest_list is None:
            return
        if self.customer_suggest_win is None or not self.customer_suggest_win.winfo_exists():
            return
        if str(self.customer_suggest_win.state()) != "normal":
            return
        if self.customer_suggest_list.size() <= 0:
            return
        self.customer_suggest_list.focus_set()
        self.customer_suggest_list.selection_clear(0, tk.END)
        self.customer_suggest_list.selection_set(0)
        self.customer_suggest_list.activate(0)
        return "break"

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

    def load_data(self):
        self.sales = load_sales()
        items = set()
        customers = set()
        for s in self.sales:
            name = str(s.get("customer_name", "")).strip()
            if name:
                customers.add(name)
            for it in s.get("items", []):
                item_name = str(it.get("item") or it.get("name") or "").strip()
                if item_name:
                    items.add(item_name)
        self.item_values_all = sorted(items, key=str.lower)
        self.customer_values_all = sorted(customers, key=str.lower)
        self.item_cb["values"] = self.item_values_all
        self.customer_cb["values"] = self.customer_values_all
        self.load_report()

    def on_filter_change(self):
        mode = self.filter_var.get()
        self.item_cb.grid_remove()
        self.customer_cb.grid_remove()
        if mode == "item":
            self.item_cb.grid()
        elif mode == "customer":
            self.customer_cb.grid()

    def on_item_search(self, event=None):
        if event and event.keysym in ("Up", "Down", "Left", "Right", "Return", "Escape", "Tab"):
            return
        typed = self.item_cb.get().strip().lower()
        if not typed:
            self._hide_item_suggestions()
            return
        filtered = [v for v in self.item_values_all if typed in v.lower()]
        self._show_item_suggestions(filtered if filtered else self.item_values_all)

    def on_customer_search(self, event=None):
        if event and event.keysym in ("Up", "Down", "Left", "Right", "Return", "Escape", "Tab"):
            return
        typed = self.customer_cb.get().strip().lower()
        if not typed:
            self._hide_customer_suggestions()
            return
        filtered = [v for v in self.customer_values_all if typed in v.lower()]
        self._show_customer_suggestions(filtered if filtered else self.customer_values_all)

    def load_report(self):
        self.tree.delete(*self.tree.get_children())
        self.filtered_sales = []
        self.tree_invoice_map = {}

        mode = self.filter_var.get()
        from_d = self.parse_date(self.from_date.get().strip())
        to_d = self.parse_date(self.to_date.get().strip())
        selected_item = self.item_cb.get().strip()
        selected_customer = self.customer_cb.get().strip().lower()

        rows = []
        for s in self.sales:
            sale_dt = self.parse_date(s.get("date"))
            if from_d and (not sale_dt or sale_dt < from_d):
                continue
            if to_d and (not sale_dt or sale_dt > to_d):
                continue

            if mode == "item" and selected_item:
                if not any((it.get("item") or it.get("name")) == selected_item for it in s.get("items", [])):
                    continue
            if mode == "customer" and selected_customer:
                if selected_customer not in str(s.get("customer_name", "")).strip().lower():
                    continue

            rows.append(s)

        rows = sorted(rows, key=lambda x: self.parse_date(x.get("date")) or datetime.min, reverse=True)
        self.filtered_sales = rows

        total_sales = sum(self._to_float(s.get("grand_total", 0)) for s in rows)
        total_paid = sum(self._to_float(s.get("paid", s.get("paid_amount", 0))) for s in rows)
        total_due = sum(self._to_float(s.get("due", 0)) for s in rows)
        self.summary_var.set(
            f"TOTAL SALES: Rs {total_sales:.2f}   PAID: Rs {total_paid:.2f}   DUE: Rs {total_due:.2f}"
        )

        for s in rows:
            grand_total = self._to_float(s.get("grand_total", 0))
            paid = self._to_float(s.get("paid", s.get("paid_amount", 0)))
            due = self._to_float(s.get("due", max(grand_total - paid, 0)))
            iid = self.tree.insert(
                "",
                "end",
                values=(
                    self.format_date(s.get("date", "")),
                    s.get("invoice_no", ""),
                    s.get("customer_name", ""),
                    s.get("phone", ""),
                    f"{grand_total:.2f}",
                    f"{paid:.2f}",
                    f"{due:.2f}",
                ),
            )
            self.tree_invoice_map[iid] = s

        self.selected_summary_var.set("Selected: 0 | Total: 0.00 | Paid: 0.00 | Due: 0.00")

    def on_selection_change(self, _event=None):
        selected = self.tree.selection()
        if not selected:
            self.selected_summary_var.set("Selected: 0 | Total: 0.00 | Paid: 0.00 | Due: 0.00")
            return
        tot = paid = due = 0.0
        for iid in selected:
            vals = self.tree.item(iid, "values")
            if not vals:
                continue
            tot += self._to_float(vals[4])
            paid += self._to_float(vals[5])
            due += self._to_float(vals[6])
        self.selected_summary_var.set(
            f"Selected: {len(selected)} | Total: {tot:.2f} | Paid: {paid:.2f} | Due: {due:.2f}"
        )

    def on_export_excel(self):
        from export_excel import export_sales_excel

        path = export_sales_excel()
        if not path:
            messagebox.showinfo("Sales Report", "No sales data to export.")

    def on_export_pdf(self):
        path = generate_sales_report_pdf()
        if not path:
            messagebox.showinfo("Sales Report", "No sales data to export.")

    def on_print(self):
        path = generate_sales_report_pdf()
        if not path:
            messagebox.showinfo("Sales Report", "No sales data to print.")
            return
        print_pdf(path)

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
