import tkinter as tk
from tkinter import ttk, messagebox
from sales import load_sales, save_sales
from audit_log import write_audit_log
from cash_ledger import add_cash_entry
from datetime import datetime
from ui_theme import compact_form_grid


class DueReportUI(ttk.Frame):
    def __init__(self, parent):
        super().__init__(parent)
        self.pack(fill="both", expand=True)
        self.all_due_rows = []
        self.selected_invoice = None

        self.total_due_var = tk.StringVar(value="Total Due: Rs0.00")

        title = ttk.Label(
            self,
            text="Customer Due Report",
            font=("Arial", 15, "bold")
        )
        title.pack(pady=(10, 15))

        search_bar = ttk.Frame(self)
        search_bar.pack(fill="x", padx=10, pady=(0, 5))

        ttk.Label(search_bar, text="Search").pack(side="left")
        self.search_var = tk.StringVar()
        self.search_e = ttk.Entry(search_bar, textvariable=self.search_var, width=30)
        self.search_e.pack(side="left", padx=(6, 0))
        self.search_e.bind("<KeyRelease>", self.on_search_change)

        # ================= TABLE =================
        cols = ("invoice", "date", "customer", "phone", "total", "paid", "due")
        table_frame = ttk.Frame(self)
        table_frame.pack(fill="both", expand=True, padx=10, pady=10)
        table_frame.columnconfigure(0, weight=1)
        table_frame.rowconfigure(0, weight=1)

        self.tree = ttk.Treeview(
            table_frame,
            columns=cols,
            show="headings",
            height=12
        )

        headings = {
            "invoice": "Invoice No",
            "date": "Date",
            "customer": "Customer",
            "phone": "Phone",
            "total": "Total",
            "paid": "Paid",
            "due": "Due"
        }

        for c in cols:
            self.tree.heading(c, text=headings[c])
            self.tree.column(c, anchor="center", stretch=True)

        ysb = ttk.Scrollbar(table_frame, orient="vertical", command=self.tree.yview)
        xsb = ttk.Scrollbar(table_frame, orient="horizontal", command=self.tree.xview)
        self.tree.configure(yscrollcommand=ysb.set, xscrollcommand=xsb.set)

        self.tree.grid(row=0, column=0, sticky="nsew")
        ysb.grid(row=0, column=1, sticky="ns")
        xsb.grid(row=1, column=0, sticky="ew")
        self.tree.bind("<<TreeviewSelect>>", self.on_select_row)

        # ---------- BOTTOM BAR ----------
        bottom = ttk.Frame(self)
        bottom.pack(fill="x", padx=20, pady=10)

        # LEFT: Export buttons
        btns = ttk.Frame(bottom)
        btns.pack(side="left")

        ttk.Button(
            btns,
            text="Export Excel",
            width=15,
            command=self.export_excel
        ).pack(side="left", padx=5)

        ttk.Button(
            btns,
            text="Export PDF",
            width=15,
            command=self.export_pdf
        ).pack(side="left", padx=5)

        # RIGHT: Total Due
        ttk.Label(
            bottom,
            textvariable=self.total_due_var,
            font=("Arial", 12, "bold"),
            foreground="red"
        ).pack(side="right")

        # ---------- PAYMENT SECTION ----------
        payment = ttk.LabelFrame(self, text="Receive Due Payment")
        payment.pack(fill="x", padx=20, pady=(0, 12))
        payment.columnconfigure(0, weight=1)
        payment.columnconfigure(1, weight=1)
        payment.columnconfigure(2, weight=1)
        payment.columnconfigure(3, weight=1)

        ttk.Label(payment, text="Selected Invoice").grid(row=0, column=0, sticky="w", padx=5, pady=6)
        self.selected_invoice_var = tk.StringVar(value="-")
        ttk.Label(payment, textvariable=self.selected_invoice_var, font=("Arial", 10, "bold")).grid(
            row=0, column=1, columnspan=3, sticky="w", padx=5, pady=6
        )

        ttk.Label(payment, text="Pay Amount").grid(row=1, column=0, sticky="w", padx=5, pady=6)
        self.pay_amount_e = ttk.Entry(payment, width=15)
        self.pay_amount_e.grid(row=1, column=1, sticky="w", padx=5, pady=6)

        ttk.Label(payment, text="Payment Type").grid(row=1, column=2, sticky="w", padx=5, pady=6)
        self.pay_mode_cb = ttk.Combobox(
            payment,
            values=["Cash", "UPI", "Card", "Bank", "Other"],
            state="readonly",
            width=14
        )
        self.pay_mode_cb.set("Cash")
        self.pay_mode_cb.grid(row=1, column=3, sticky="w", padx=5, pady=6)

        ttk.Button(payment, text="Save Payment", command=self.save_due_payment).grid(
            row=2, column=0, columnspan=4, padx=12, pady=(6, 8), sticky="e"
        )
        compact_form_grid(payment)

        self.load_due_data()

    # ================= LOAD DATA =================
    def _parse_row_date(self, value):
        text = str(value or "").strip()
        for fmt in ("%Y-%m-%d", "%d-%m-%Y", "%Y-%m-%d %H:%M:%S", "%d-%m-%Y %H:%M:%S"):
            try:
                return datetime.strptime(text, fmt)
            except Exception:
                continue
        return datetime.min

    def _format_row_date(self, value):
        parsed = self._parse_row_date(value)
        if parsed == datetime.min:
            return str(value or "")
        return parsed.strftime("%d-%m-%Y %H:%M:%S")

    def load_due_data(self):
        self.all_due_rows = []

        sales = load_sales()
        if not sales:
            self.tree.delete(*self.tree.get_children())
            self.total_due_var.set("Total Due: Rs0.00")
            return

        for s in sales:
            due = float(s.get("due", 0))
            if due <= 0:
                continue

            self.all_due_rows.append(
                (
                    s.get("invoice_no", ""),
                    self._format_row_date(s.get("date", "")),
                    s.get("customer_name", ""),
                    s.get("phone", ""),
                    f"{float(s.get('grand_total', 0)):.2f}",
                    f"{float(s.get('paid', 0)):.2f}",
                    f"{due:.2f}",
                )
            )

        self.all_due_rows.sort(key=lambda r: self._parse_row_date(r[1]), reverse=True)
        self.apply_search_filter()

    def on_search_change(self, _event=None):
        self.apply_search_filter()

    def apply_search_filter(self):
        self.tree.delete(*self.tree.get_children())

        key = self.search_var.get().strip().lower()
        total_due = 0.0

        for row in self.all_due_rows:
            searchable = " ".join(str(x) for x in row[:4]).lower()
            if key and key not in searchable:
                continue
            self.tree.insert("", "end", values=row)
            total_due += float(row[6] or 0)

        self.total_due_var.set(f"Total Due: Rs{total_due:,.2f}")
        self.selected_invoice = None
        self.selected_invoice_var.set("-")

    def on_select_row(self, _event=None):
        sel = self.tree.selection()
        if not sel:
            self.selected_invoice = None
            self.selected_invoice_var.set("-")
            return
        row = self.tree.item(sel[0], "values")
        if not row:
            self.selected_invoice = None
            self.selected_invoice_var.set("-")
            return
        self.selected_invoice = str(row[0])
        self.selected_invoice_var.set(self.selected_invoice)

    def save_due_payment(self):
        if not self.selected_invoice:
            messagebox.showerror("Error", "Select an invoice from due report.")
            return

        try:
            pay = float(self.pay_amount_e.get().strip())
        except Exception:
            messagebox.showerror("Error", "Enter a valid pay amount.")
            return

        if pay <= 0:
            messagebox.showerror("Error", "Pay amount must be greater than 0.")
            return

        mode = self.pay_mode_cb.get().strip() or "Cash"
        sales = load_sales()
        target = None
        for s in sales:
            if str(s.get("invoice_no", "")) == self.selected_invoice:
                target = s
                break

        if not target:
            messagebox.showerror("Error", "Selected invoice not found.")
            return

        due_before = float(target.get("due", 0) or 0)
        paid_before = float(target.get("paid", target.get("paid_amount", 0)) or 0)
        if due_before <= 0:
            messagebox.showinfo("Info", "No due available for selected invoice.")
            return
        if pay > due_before:
            messagebox.showerror("Error", f"Pay amount cannot exceed due ({due_before:.2f}).")
            return

        target["paid"] = round(paid_before + pay, 2)
        target["paid_amount"] = target["paid"]
        target["due"] = round(max(due_before - pay, 0.0), 2)
        target["last_payment_mode"] = mode
        save_sales(sales)

        write_audit_log(
            user="admin",
            module="due_payment",
            action="receive",
            reference=self.selected_invoice,
            before={"paid": paid_before, "due": due_before},
            after={"paid": target["paid"], "due": target["due"], "payment_mode": mode}
        )

        if mode == "Cash":
            add_cash_entry(
                date=datetime.now().strftime("%Y-%m-%d"),
                particulars=f"Customer Payment {self.selected_invoice}",
                cash_in=pay,
                reference=self.selected_invoice
            )

        messagebox.showinfo("Success", "Due payment saved successfully.")
        self.pay_amount_e.delete(0, tk.END)
        self.load_due_data()

    def export_excel(self):
        from export_excel import export_due_report_excel
        export_due_report_excel()

    def export_pdf(self):
        from report_pdf import generate_due_report_pdf
        generate_due_report_pdf()
