import tkinter as tk
from tkinter import ttk

from inventory import get_total_stock_value
from purchase import get_total_supplier_due


class DashboardUI(tk.Toplevel):
    def __init__(self, parent):
        super().__init__(parent)
        self.title("Dashboard Summary")
        self.geometry("420x300")
        self.resizable(False, False)

        self.build_ui()
        self.refresh_data()

    def build_ui(self):
        tk.Label(
            self,
            text="Business Dashboard",
            font=("Arial", 15, "bold")
        ).pack(pady=15)

        frame = tk.Frame(self)
        frame.pack(pady=10)

        self.stock_var = tk.StringVar()
        self.due_var = tk.StringVar()
        self.net_var = tk.StringVar()

        tk.Label(
            frame,
            textvariable=self.stock_var,
            fg="green",
            font=("Arial", 11, "bold")
        ).pack(pady=6)

        tk.Label(
            frame,
            textvariable=self.due_var,
            fg="red",
            font=("Arial", 11, "bold")
        ).pack(pady=6)

        tk.Label(
            frame,
            textvariable=self.net_var,
            fg="blue",
            font=("Arial", 11, "bold")
        ).pack(pady=10)

        ttk.Button(
            self,
            text="Refresh",
            width=15,
            command=self.refresh_data
        ).pack(pady=10)

        ttk.Button(
            self,
            text="Close",
            width=15,
            command=self.destroy
        ).pack(pady=5)

    def refresh_data(self):
        stock = get_total_stock_value()
        due = get_total_supplier_due()
        net = stock - due

        self.stock_var.set(f"Total Stock Value : ₹{stock:,.2f}")
        self.due_var.set(f"Supplier Due : ₹{due:,.2f}")
        self.net_var.set(f"Net Business Value : ₹{net:,.2f}")
