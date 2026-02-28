import tkinter as tk
from inventory import get_all_items, get_total_stock_value

class StockSummaryUI(tk.Toplevel):
    def __init__(self, parent):
        super().__init__(parent)
        self.title("Stock Summary")
        self.geometry("400x300")

        items = get_all_items()
        total_value = get_total_stock_value()

        tk.Label(
            self, text="Total Stock Summary",
            font=("Arial", 14, "bold")
        ).pack(pady=10)

        tk.Label(
            self, text=f"Total Items : {len(items)}",
            font=("Arial", 11)
        ).pack(pady=5)

        tk.Label(
            self, text=f"Total Stock Value : ₹{total_value:,.2f}",
            font=("Arial", 12, "bold"),
            fg="green"
        ).pack(pady=10)