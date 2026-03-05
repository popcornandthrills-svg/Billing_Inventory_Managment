import tkinter as tk
from tkinter import ttk

# These will be created later (or already exist)
from billing_ui import BillingUI
from customer_ledger_ui import CustomerLedgerUI

from due_report_ui import DueReportUI
from sales_report_ui import SalesReportUI
from invoice_view_ui import InvoiceViewUI


class SalesMenuUI(tk.Frame):
    def __init__(self, parent):
        super().__init__(parent)
        
        # ---------- Title ----------
        tk.Label(
            self,
            text="Sales Section",
            font=("Arial", 14, "bold")
        ).pack(pady=15)

        # ---------- Buttons Frame ----------
        btn_frame = tk.Frame(self)
        btn_frame.pack(fill="both", expand=True, padx=30)

        ttk.Button(
            btn_frame,
            text="New Sale / Billing",
            command=lambda: BillingUI(self),
            width=25
        ).pack(pady=8)

        ttk.Button(
            btn_frame,
            text="Customer Ledger",
            command=lambda: CustomerLedgerUI(self),
            width=25
        ).pack(pady=8)

        ttk.Button(
            btn_frame,
            text="Due Report",
            command=lambda: DueReportUI(self),
            width=25
        ).pack(pady=8)

        ttk.Button(
            btn_frame,
            text="Sales Report",
            command=lambda: SalesReportUI(self),
            width=25
        ).pack(pady=8)

        ttk.Button(
            btn_frame,
            text="Invoice Search / Reprint",
            command=lambda: InvoiceViewUI(self),
            width=25
        ).pack(pady=8)

        ttk.Button(
            btn_frame,
            text="Close",
            command=self.destroy,
            width=25
        ).pack(pady=15)
        
        ttk.Button(
            self,
            text="← Back",
            command=lambda: self.master.destroy()
        )
