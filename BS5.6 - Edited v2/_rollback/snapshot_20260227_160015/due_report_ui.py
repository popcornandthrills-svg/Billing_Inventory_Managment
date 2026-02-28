import tkinter as tk
from tkinter import ttk
from sales import load_sales


class DueReportUI(ttk.Frame):
    def __init__(self, parent):
        super().__init__(parent)
        self.pack(fill="both", expand=True)
        self.all_due_rows = []

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
            height=22
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

        # ---------- BOTTOM BAR ----------
        bottom = ttk.Frame(self)
        bottom.pack(fill="x", padx=20, pady=10)

        # LEFT: Export buttons
        from export_excel import export_due_report_excel
        from report_pdf import generate_due_report_pdf

        btns = ttk.Frame(bottom)
        btns.pack(side="left")

        ttk.Button(
            btns,
            text="Export Excel",
            width=15,
            command=export_due_report_excel
        ).pack(side="left", padx=5)

        ttk.Button(
            btns,
            text="Export PDF",
            width=15,
            command=generate_due_report_pdf
        ).pack(side="left", padx=5)

        # RIGHT: Total Due
        ttk.Label(
            bottom,
            textvariable=self.total_due_var,
            font=("Arial", 12, "bold"),
            foreground="red"
        ).pack(side="right")

        self.load_due_data()

    # ================= LOAD DATA =================
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
                    s.get("date", ""),
                    s.get("customer_name", ""),
                    s.get("phone", ""),
                    f"{float(s.get('grand_total', 0)):.2f}",
                    f"{float(s.get('paid', 0)):.2f}",
                    f"{due:.2f}",
                )
            )

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
