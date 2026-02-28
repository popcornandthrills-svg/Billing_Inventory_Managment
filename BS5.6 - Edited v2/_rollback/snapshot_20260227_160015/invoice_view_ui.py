import tkinter as tk
from tkinter import ttk, messagebox

from sales import load_sales


class InvoiceViewUI(tk.Toplevel):
    def __init__(self, parent):
        super().__init__(parent)
        self.title("Invoice Viewer")
        self.geometry("850x500")

        # ---------- LEFT: INVOICE LIST ----------
        left = tk.Frame(self)
        left.pack(side="left", fill="y", padx=10, pady=10)

        tk.Label(
            left,
            text="Invoices",
            font=("Arial", 11, "bold")
        ).pack(pady=5)

        self.listbox = tk.Listbox(left, width=25, height=25)
        self.listbox.pack(fill="y")

        self.listbox.bind("<<ListboxSelect>>", self.show_invoice)

        # ---------- RIGHT: DETAILS ----------
        right = tk.Frame(self)
        right.pack(side="right", fill="both", expand=True, padx=10, pady=10)

        self.info = tk.Label(
            right,
            text="Select invoice to view details",
            justify="left",
            anchor="w"
        )
        self.info.pack(anchor="w")

        self.tree = ttk.Treeview(
            right,
            columns=("item", "qty", "rate", "gst", "total"),
            show="headings",
            height=12
        )

        for c in ("item", "qty", "rate", "gst", "total"):
            self.tree.heading(c, text=c.upper())

        self.tree.column("item", width=180)
        self.tree.column("qty", width=60, anchor="center")
        self.tree.column("rate", width=80, anchor="e")
        self.tree.column("gst", width=60, anchor="e")
        self.tree.column("total", width=90, anchor="e")

        self.tree.pack(fill="both", expand=True, pady=10)

        self.summary = tk.Label(
            right,
            text="",
            font=("Arial", 10, "bold"),
            fg="green"
        )
        self.summary.pack(anchor="e")

        # ---------- LOAD ----------
        self.sales = load_sales()
        for s in self.sales:
            self.listbox.insert(
                tk.END,
                f"{s['invoice_no']} | {s['customer_name']}"
            )

    def show_invoice(self, event=None):
        if not self.listbox.curselection():
            return

        index = self.listbox.curselection()[0]
        sale = self.sales[index]

        self.tree.delete(*self.tree.get_children())

        self.info.config(
            text=(
                f"Invoice: {sale['invoice_no']}\n"
                f"Date: {sale['date']}\n"
                f"Customer: {sale['customer_name']}\n"
                f"Phone: {sale['phone']}\n"
                f"Payment Mode: {sale['payment_mode']}"
            )
        )

        for i in sale["items"]:
            self.tree.insert(
                "",
                "end",
                values=(
                    i["item"],
                    i["qty"],
                    f"{i['rate']:.2f}",
                    f"{i.get('gst', 0):.2f}",
                    f"{i['total']:.2f}"
                )
            )

        self.summary.config(
            text=(
                f"TOTAL: ₹{sale['grand_total']:.2f}   "
                f"PAID: ₹{sale['paid']:.2f}   "
                f"DUE: ₹{sale['due']:.2f}"
            )
        )
