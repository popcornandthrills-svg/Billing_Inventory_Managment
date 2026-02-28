import tkinter as tk
from tkinter import ttk, messagebox
from datetime import datetime

from sales import load_sales


class SalesReportUI(ttk.Frame):
    def __init__(self, parent):
        super().__init__(parent)
        self.pack(fill="both", expand=True, padx=10, pady=10)
        self._render_job = None
        self._rows_buffer = []

        ttk.Label(
            self,
            text="Sales Report",
            font=("Arial", 14, "bold")
        ).pack(pady=(0, 10))

        cols = ("date", "invoice", "customer", "total", "paid", "due")
        table_frame = ttk.Frame(self)
        table_frame.pack(fill="both", expand=True)
        table_frame.columnconfigure(0, weight=1)
        table_frame.rowconfigure(0, weight=1)

        self.tree = ttk.Treeview(table_frame, columns=cols, show="headings")

        headings = {
            "date": "Date",
            "invoice": "Invoice",
            "customer": "Customer",
            "total": "Total",
            "paid": "Paid",
            "due": "Due",
        }
        for c in cols:
            anchor = "w" if c in ("date", "invoice", "customer") else "e"
            self.tree.heading(c, text=headings[c], anchor=anchor)
            width = 180 if c == "customer" else 120
            self.tree.column(c, width=width, anchor=anchor)

        ysb = ttk.Scrollbar(table_frame, orient="vertical", command=self.tree.yview)
        xsb = ttk.Scrollbar(table_frame, orient="horizontal", command=self.tree.xview)
        self.tree.configure(yscrollcommand=ysb.set, xscrollcommand=xsb.set)

        self.tree.grid(row=0, column=0, sticky="nsew")
        ysb.grid(row=0, column=1, sticky="ns")
        xsb.grid(row=1, column=0, sticky="ew")

        summary = ttk.Frame(self)
        summary.pack(fill="x", pady=(8, 0))

        self.summary_var = tk.StringVar(value="")
        ttk.Label(
            summary,
            textvariable=self.summary_var,
            font=("Arial", 10, "bold"),
            foreground="green"
        ).pack(side="left")

        self.status_var = tk.StringVar(value="")
        ttk.Label(summary, textvariable=self.status_var).pack(side="left", padx=(12, 0))

        ttk.Button(
            summary,
            text="Export Excel",
            command=self.on_export_excel
        ).pack(side="right", padx=(6, 0))

        ttk.Button(
            summary,
            text="Export PDF",
            command=self.on_export_pdf
        ).pack(side="right")

        self.after(1, self.load_report)

    def _to_float(self, value):
        try:
            return float(value)
        except Exception:
            return 0.0

    def _parse_sale_date(self, value):
        text = str(value or "").strip()
        for fmt in ("%Y-%m-%d", "%d-%m-%Y", "%Y-%m-%d %H:%M:%S", "%d-%m-%Y %H:%M:%S"):
            try:
                return datetime.strptime(text, fmt)
            except Exception:
                continue
        return datetime.min

    def _format_sale_date(self, value):
        parsed = self._parse_sale_date(value)
        if parsed == datetime.min:
            return str(value or "")
        return parsed.strftime("%d-%m-%Y %H:%M:%S")

    def load_report(self):
        if self._render_job:
            try:
                self.after_cancel(self._render_job)
            except Exception:
                pass
            self._render_job = None

        self.tree.delete(*self.tree.get_children())

        sales = sorted(load_sales(), key=lambda s: self._parse_sale_date(s.get("date")), reverse=True)
        total_sales = self._to_float(sum(self._to_float(s.get("grand_total", 0)) for s in sales))
        total_paid = self._to_float(sum(self._to_float(s.get("paid", s.get("paid_amount", 0))) for s in sales))
        total_due = self._to_float(sum(self._to_float(s.get("due", 0)) for s in sales))

        self.summary_var.set(
            f"TOTAL SALES: Rs {total_sales:.2f}   "
            f"PAID: Rs {total_paid:.2f}   "
            f"DUE: Rs {total_due:.2f}"
        )

        self._rows_buffer = []
        for s in sales:
            grand_total = self._to_float(s.get("grand_total", 0))
            paid = self._to_float(s.get("paid", s.get("paid_amount", 0)))
            due = self._to_float(s.get("due", max(grand_total - paid, 0)))
            self._rows_buffer.append(
                (
                    self._format_sale_date(s.get("date", "")),
                    s.get("invoice_no", ""),
                    s.get("customer_name", ""),
                    f"{grand_total:.2f}",
                    f"{paid:.2f}",
                    f"{due:.2f}",
                )
            )

        self.status_var.set(f"Loading {len(self._rows_buffer)} rows...")
        self._render_rows_chunk()

    def _render_rows_chunk(self, chunk_size=300):
        if not self._rows_buffer:
            self.status_var.set("")
            self._render_job = None
            return

        batch = self._rows_buffer[:chunk_size]
        self._rows_buffer = self._rows_buffer[chunk_size:]
        for row in batch:
            self.tree.insert("", "end", values=row)

        self.status_var.set(f"Loading... {len(self._rows_buffer)} rows remaining")
        self._render_job = self.after(1, self._render_rows_chunk)

    def on_export_excel(self):
        from export_excel import export_sales_excel
        path = export_sales_excel()
        if not path:
            messagebox.showinfo("Sales Report", "No sales data to export.")

    def on_export_pdf(self):
        from report_pdf import generate_sales_report_pdf
        path = generate_sales_report_pdf()
        if not path:
            messagebox.showinfo("Sales Report", "No sales data to export.")
