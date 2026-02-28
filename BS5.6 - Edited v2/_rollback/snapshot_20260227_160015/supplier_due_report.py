import tkinter as tk
from tkinter import ttk

from purchase import get_total_supplier_due
from purchase import load_purchases


class SupplierDueReportUI(tk.Toplevel):
    def __init__(self, parent):
        super().__init__(parent)
        self.title("Supplier Due Report")
        self.geometry("650x400")

        tk.Label(
            self,
            text="Supplier Due Summary",
            font=("Arial", 12, "bold")
        ).pack(pady=10)

        self.tree = ttk.Treeview(
            self,
            columns=("supplier", "total", "paid", "due"),
            show="headings"
        )

        for c in ("supplier", "total", "paid", "due"):
            self.tree.heading(c, text=c.upper())

        self.tree.column("supplier", width=220)
        self.tree.column("total", width=120, anchor="e")
        self.tree.column("paid", width=120, anchor="e")
        self.tree.column("due", width=120, anchor="e")

        self.tree.pack(fill="both", expand=True, padx=10, pady=10)

        self.summary_var = tk.StringVar(value="")
        tk.Label(
            self,
            textvariable=self.summary_var,
            font=("Arial", 10, "bold"),
            fg="red"
        ).pack(pady=5)

        self.load_report()

    def load_report(self):
        self.tree.delete(*self.tree.get_children())

        purchases = load_purchases()
        summary = {}

        total_due = 0.0

        for p in purchases:
            sid = p["supplier_id"]
            name = p["supplier_name"]

            if sid not in summary:
                summary[sid] = {
                    "name": name,
                    "total": 0.0,
                    "paid": 0.0,
                    "due": 0.0
                }

            summary[sid]["total"] += p["grand_total"]
            summary[sid]["paid"] += p["paid"]
            summary[sid]["due"] += p["due"]

        for s in summary.values():
            total_due += s["due"]
            self.tree.insert(
                "",
                "end",
                values=(
                    s["name"],
                    f"{s['total']:.2f}",
                    f"{s['paid']:.2f}",
                    f"{s['due']:.2f}"
                )
            )

        self.summary_var.set(f"TOTAL SUPPLIER DUE: ₹{total_due:.2f}")