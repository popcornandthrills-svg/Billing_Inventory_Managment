import tkinter as tk
from tkinter import ttk
from purchase_entry import PurchaseEntry
from stock_summary_ui import StockSummaryUI
from supplier_due_report import SupplierDueReport  # later

class PurchaseUI(tk.Toplevel):
    def __init__(self, parent):
        super().__init__(parent)
        self.title("Purchase Menu")
        self.geometry("500x400")

        ttk.Label(
            self, text="Purchase",
            font=("Arial", 14, "bold")
        ).pack(pady=20)

        ttk.Button(
            self, text="New Purchase",
            width=30,
            command=lambda: PurchaseEntry(self)
        ).pack(pady=8)

        ttk.Button(
            self, text="Supplier Due Report",
            width=30,
            command=lambda: SupplierDueReport(self)
        ).pack(pady=8)

        ttk.Button(
            self, text="Total Stock Summary",
            width=30,
            command=lambda: StockSummaryUI(self)
        ).pack(pady=8)
