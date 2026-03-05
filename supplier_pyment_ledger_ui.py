import tkinter as tk
from tkinter import ttk
from datetime import datetime
from purchase import get_supplier_ledger
from suppliers import get_supplier

class SupplierPaymentLedgerUI(tk.Toplevel):
    def __init__(self, parent, supplier_id):
        super().__init__(parent)
        self.title("Supplier Ledger")
        self.geometry("650x400")

        supplier = get_supplier(supplier_id)

        tk.Label(
            self,
            text=f"Supplier Ledger : {supplier['name']}",
            font=("Arial", 12, "bold")
        ).pack(pady=5)

        tree = ttk.Treeview(
            self,
            columns=("date", "pid", "total", "paid", "due"),
            show="headings"
        )
        for c in ("date", "pid", "total", "paid", "due"):
            tree.heading(c, text=c.upper())

        tree.pack(fill="both", expand=True)

        ledger = get_supplier_ledger(supplier_id)
        ledger = sorted(ledger, key=lambda r: self._parse_date(r.get("date")), reverse=True)
        for row in ledger:
            tree.insert("", "end", values=(
                row["date"],
                row["purchase_id"],
                row["total"],
                row["paid"],
                row["due"]
            ))

    def _parse_date(self, value):
        text = str(value or "").strip()
        for fmt in ("%Y-%m-%d", "%d-%m-%Y", "%Y-%m-%d %H:%M:%S", "%d-%m-%Y %H:%M:%S"):
            try:
                return datetime.strptime(text, fmt)
            except Exception:
                continue
        return datetime.min
