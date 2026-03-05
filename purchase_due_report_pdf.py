# purchase_due_report.py
import tkinter as tk
from tkinter import ttk
from purchase import load_purchases


class PurchaseDueReport(ttk.Frame):
    def __init__(self, parent):
        print("🔥 NEW PurchaseDueReport LOADED")
        super().__init__(parent)
        self.total_due = 0.0
        self.build_ui()
        self.load_data()

    # ================= UI =================
    def build_ui(self):
        # ---------- TITLE ----------
        ttk.Label(
            self,
            text="Purchase Due Report",
            font=("Arial", 14, "bold")
        ).pack(pady=10)

        # ---------- BUTTONS ----------
        btns = ttk.Frame(self)
        btns.pack(pady=5)

        ttk.Button(
            btns,
            text="Export Excel",
            width=16,
            command=self.export_excel
        ).pack(side="left", padx=6)
        
        ttk.Button(
            btns,
            text="Export PDF",
            command=self.export_pdf
        ).pack(pady=5)

        # ---------- TABLE ----------
        table_frame = ttk.Frame(self)
        table_frame.pack(fill="both", expand=True, padx=20, pady=10)

        cols = ("supplier", "invoice", "date", "total", "due")

        self.tree = ttk.Treeview(
            table_frame,
            columns=cols,
            show="headings",
            height=12
        )

        self.tree.heading("supplier", text="Supplier")
        self.tree.heading("invoice", text="Invoice No")
        self.tree.heading("date", text="Date")
        self.tree.heading("total", text="Total")
        self.tree.heading("due", text="Due")

        self.tree.column("supplier", width=200, anchor="w")
        self.tree.column("invoice", width=100, anchor="center")
        self.tree.column("date", width=100, anchor="center")
        self.tree.column("total", width=120, anchor="e")
        self.tree.column("due", width=120, anchor="e")

        self.tree.pack(fill="both", expand=True)

        # ---------- TOTAL ----------
        self.total_lbl = ttk.Label(
            self,
            text="Total Due : ₹ 0.00",
            font=("Arial", 12, "bold"),
            foreground="red"
        )
        self.total_lbl.pack(pady=10)

    # ================= DATA =================
    def load_data(self):
        purchases = load_purchases()
        self.total_due = 0.0

        for p in purchases:
            total = float(p.get("grand_total", 0))
            paid = float(p.get("paid_amount", 0))
            due = round(total - paid, 2)

            if due > 0:
                self.tree.insert(
                    "",
                    "end",
                    values=(
                        p.get("supplier_name", ""),
                        p.get("purchase_id", ""),
                        p.get("date", ""),
                        f"{total:.2f}",
                        f"{due:.2f}"
                    )
                )
                self.total_due += due

        self.total_lbl.config(
            text=f"Total Due : ₹ {self.total_due:,.2f}"
        )

    # ================= EXPORT =================
    def export_excel(self):
        from export_excel import export_purchase_due_excel
        export_purchase_due_excel()
        
    def export_pdf(self):
        from report_pdf import generate_purchase_due_report_pdf

        pdf_path = generate_purchase_due_report_pdf()

        # open pdf
        import os
        os.startfile(pdf_path)
