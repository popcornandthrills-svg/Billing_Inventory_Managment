import tkinter as tk
from tkinter import ttk
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
        for row in ledger:
            tree.insert("", "end", values=(
                row["date"],
                row["purchase_id"],
                row["total"],
                row["paid"],
                row["due"]
            ))