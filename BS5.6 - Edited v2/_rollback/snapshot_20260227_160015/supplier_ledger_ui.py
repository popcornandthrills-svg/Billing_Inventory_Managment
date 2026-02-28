import tkinter as tk
from tkinter import ttk, messagebox

from export_excel import export_supplier_ledger_excel
from tkinter import messagebox



class SupplierLedgerUI(tk.Toplevel):
    def __init__(self, parent, supplier_id):
        super().__init__(parent)
        self.title("Supplier Ledger")
        self.geometry("650x400")

        # ---------- STORE FOR EXPORT ----------
        self.supplier_id = supplier_id
        self.ledger = get_supplier_ledger(supplier_id)

        # ---------- TABLE ----------
        self.tree = ttk.Treeview(
            self,
            columns=("date", "pid", "total", "paid", "due"),
            show="headings"
        )

        for c in ("date", "pid", "total", "paid", "due"):
            self.tree.heading(c, text=c.upper())

        self.tree.pack(fill="both", expand=True, padx=10, pady=10)

        for row in self.ledger:
            self.tree.insert(
                "",
                "end",
                values=(
                    row["date"],
                    row["purchase_id"],
                    row["total"],
                    row["paid"],
                    row["due"]
                )
            )

        # ---------- EXPORT BUTTON ----------
        ttk.Button(
            self,
            text="Export to Excel",
            command=self.export_excel
        ).pack(pady=5)

    def export_excel(self):
        try:
            file_path = export_supplier_ledger_excel(
                self.ledger,
                self.supplier_id
            )
            messagebox.showinfo(
                "Success",
                f"Excel saved in:\n{file_path}"
            )
        except Exception as e:
            messagebox.showerror("Error", str(e))