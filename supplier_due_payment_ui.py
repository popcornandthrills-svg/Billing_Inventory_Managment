import tkinter as tk
from tkinter import ttk, messagebox

from suppliers import get_all_suppliers
from purchase import pay_supplier_due, get_supplier_ledger


class SupplierDuePaymentUI(tk.Toplevel):
    def __init__(self, parent):
        super().__init__(parent)
        self.title("Supplier Due Payment")
        self.geometry("450x300")

        self.suppliers = get_all_suppliers()

        # ---------- Supplier ----------
        tk.Label(self, text="Supplier").pack(pady=5)

        self.supplier_cb = ttk.Combobox(
            self,
            values=[
                f"{sid} - {s['name']}"
                for sid, s in self.suppliers.items()
            ],
            state="readonly",
            width=35
        )
        self.supplier_cb.pack()
        self.supplier_cb.bind("<<ComboboxSelected>>", self.show_due)

        # ---------- Due info ----------
        self.due_var = tk.StringVar(value="Total Due: ₹0.00")
        tk.Label(
            self,
            textvariable=self.due_var,
            font=("Arial", 11, "bold"),
            fg="red"
        ).pack(pady=10)

        # ---------- Payment ----------
        tk.Label(self, text="Payment Amount").pack()
        self.amount_e = tk.Entry(self, width=20)
        self.amount_e.pack(pady=5)

        ttk.Button(
            self,
            text="Save Payment",
            command=self.save_payment
        ).pack(pady=15)

    def show_due(self, event=None):
        sid = self.supplier_cb.get().split(" - ")[0]
        ledger = get_supplier_ledger(sid)
        total_due = sum(l["due"] for l in ledger)
        self.due_var.set(f"Total Due: ₹{total_due:.2f}")

    def save_payment(self):
        if not self.supplier_cb.get():
            messagebox.showerror("Error", "Select supplier")
            return

        try:
            amount = float(self.amount_e.get())
        except:
            messagebox.showerror("Error", "Invalid amount")
            return

        sid = self.supplier_cb.get().split(" - ")[0]

        try:
            pay_supplier_due(sid, amount)
            messagebox.showinfo("Success", "Payment saved successfully")
            self.destroy()
        except Exception as e:
            messagebox.showerror("Error", str(e))