import tkinter as tk
from tkinter import ttk, messagebox
from datetime import datetime
from export_excel import export_customer_ledger_excel
from sales import load_sales, save_sales
from ledger_pdf import generate_customer_ledger_pdf
from audit_log import write_audit_log
from cash_ledger import add_cash_entry
from date_picker import open_date_picker

class CustomerLedgerUI(ttk.Frame):
    def __init__(self, parent):
        super().__init__(parent)

        self.sales = []
        self.filtered_sales = []
        self.selected_invoice = None

        self.build_ui()
        
        
        
    def export_excel(self):
        if not self.filtered_sales:
            messagebox.showerror("Error", "No data to export")
            return
        
        rows = []
        customer_name = self.filtered_sales[0].get("customer_name", "Customer")
        for s in self.filtered_sales:
            rows.append({
                "Date": s.get("date"),
                "Invoice": s.get("invoice_no"),
                "Total": f"{s.get('grand_total', 0):.2f}",
                "Paid": f"{s.get('paid', 0):.2f}",
                "Due": f"{s.get('due', 0):.2f}"
            })

        export_customer_ledger_excel(
            rows=rows,
            customer_name=customer_name
        )


    def export_pdf(self):
        if not self.filtered_sales:
            messagebox.showerror("Error", "No data to export")
            return
          
        rows = []
        customer_name = self.filtered_sales[0].get("customer_name", "Customer")
        
        for s in self.filtered_sales:
            rows.append({
                "date": s.get("date"),
                "invoice": s.get("invoice_no"),
                "total": f"{s.get('grand_total'):.2f}",
                "paid": f"{s.get('paid'):.2f}",
                "due": f"{s.get('due'):.2f}",
                })

        generate_customer_ledger_pdf(
            rows=rows,
            customer_name=customer_name
        )

    # ==================================================
    # UI
    # ==================================================
    def build_ui(self):

        # ---------- HEADER ----------
        ttk.Label(
            self,
            text="Customer Ledger",
            font=("Arial", 16, "bold")
        ).pack(pady=(10, 15))

        # ---------- SEARCH BAR ----------
        search = ttk.LabelFrame(self, text="Search Filters")
        search.pack(fill="x", padx=10, pady=5)

        ttk.Label(search, text="Customer Name").grid(row=0, column=0, sticky="w")
        self.name_e = ttk.Entry(search, width=22)
        self.name_e.grid(row=0, column=1, padx=5)

        ttk.Label(search, text="Phone").grid(row=0, column=2, sticky="w")
        self.phone_e = ttk.Entry(search, width=18)
        self.phone_e.grid(row=0, column=3, padx=5)

        ttk.Label(search, text="Item").grid(row=0, column=4, sticky="w")
        self.item_e = ttk.Entry(search, width=18)
        self.item_e.grid(row=0, column=5, padx=5)

        ttk.Label(search, text="From Date").grid(row=1, column=0, sticky="w")
        self.from_date_e = ttk.Entry(search, width=15)
        self.from_date_e.grid(row=1, column=1, padx=5)
        self.from_date_e.insert(0, "DD-MM-YYYY")
        ttk.Button(
            search,
            text="📅",
            width=5,
            command=lambda: open_date_picker(self, self.from_date_e),
        ).grid(row=1, column=2, padx=(0, 8), sticky="w")

        ttk.Label(search, text="To Date").grid(row=1, column=3, sticky="w")
        self.to_date_e = ttk.Entry(search, width=15)
        self.to_date_e.grid(row=1, column=4, padx=5)
        self.to_date_e.insert(0, "DD-MM-YYYY")
        ttk.Button(
            search,
            text="📅",
            width=5,
            command=lambda: open_date_picker(self, self.to_date_e),
        ).grid(row=1, column=5, padx=(0, 8), sticky="w")

        ttk.Button(
            search,
            text="Load Ledger",
            width=15,
            command=self.load_ledger
        ).grid(row=1, column=7, padx=10)

        # ---------- CUSTOMER NAME DISPLAY ----------
        self.customer_name_var = tk.StringVar(value="Customer: -")
        ttk.Label(
            self,
            textvariable=self.customer_name_var,
            font=("Arial", 11, "bold"),
            foreground="blue"
        ).pack(anchor="w", padx=15, pady=(5, 0))

        # ---------- TABLE ----------
        cols = ("date", "invoice", "total", "paid", "due")
        self.tree = ttk.Treeview(
            self,
            columns=cols,
            show="headings",
            height=22
        )

        for c in cols:
            self.tree.heading(c, text=c.title())
            self.tree.column(c, width=120, anchor="center")

        self.tree.pack(fill="both", expand=True, padx=15, pady=10)
        self.tree.bind("<<TreeviewSelect>>", self.on_select)

        self.tree.tag_configure("due", background="#ffe6e6")

        # ---------- SUMMARY ----------
        self.total_due_var = tk.StringVar(value="Total Due:0.00")
        ttk.Label(
            self,
            textvariable=self.total_due_var,
            font=("Arial", 12, "bold"),
            foreground="red"
        ).pack(anchor="e", padx=20, pady=(0, 10))

        # ---------- PAYMENT ----------
        pay = ttk.LabelFrame(self, text="Receive Payment")
        pay.pack(fill="x", padx=10, pady=8)

        ttk.Label(pay, text="Pay Amount").grid(row=0, column=0, sticky="w", padx=5)
        self.pay_e = ttk.Entry(pay, width=15)
        self.pay_e.grid(row=0, column=1, padx=5)

        ttk.Button(
            pay,
            text="Save Payment",
            command=self.save_payment
        ).grid(row=0, column=2, padx=10)
        
        # ---------- EXPORT BUTTONS (SAME LINE) ----------
        ttk.Button(
            pay,
            text="Export Excel",
            command=self.export_excel
        ).grid(row=0, column=3, padx=20)

        ttk.Button(
            pay,
            text="Export PDF",
            command=self.export_pdf
        ).grid(row=0, column=4, padx=5)

    # ==================================================
    # LOAD LEDGER (CORE LOGIC)
    # ==================================================
    def load_ledger(self):
        self.tree.delete(*self.tree.get_children())
        self.filtered_sales = []
        self.selected_invoice = None

        name = self.name_e.get().strip().lower()
        phone = self.phone_e.get().strip()
        item = self.item_e.get().strip().lower()

        from_date = self.parse_date(self.from_date_e.get().strip())
        to_date = self.parse_date(self.to_date_e.get().strip())

        total_due = 0.0
        customer_name = None

        for s in load_sales():

            # ---------- FILTERS ----------
            if phone and s.get("phone") != phone:
                continue

            if name and name not in s.get("customer_name", "").lower():
                continue

            if item:
                found = False
                for i in s.get("items", []):
                    if item in i.get("item", i.get("name", "")).lower():
                        found = True
                        break
                if not found:
                    continue

            sale_date = self.parse_date(s.get("date"))
            if from_date and sale_date and sale_date < from_date:
                continue
            if to_date and sale_date and sale_date > to_date:
                continue

            # ---------- PASSED ----------
            self.filtered_sales.append(s)
            customer_name = s.get("customer_name")

            self.tree.insert(
                "",
                "end",
                values=(
                    self.format_date(s.get("date")),
                    s.get("invoice_no"),
                    f"{s.get('grand_total', 0):.2f}",
                    f"{s.get('paid', 0):.2f}",
                    f"{s.get('due', 0):.2f}",
                ),
                tags=("due",) if s.get("due", 0) > 0 else ()
            )

            total_due += float(s.get("due", 0))

        self.customer_name_var.set(
            f"Customer: {customer_name}" if customer_name else "Customer: -"
        )
        self.total_due_var.set(f"Total Due: {total_due:,.2f}")

        if not self.filtered_sales:
            messagebox.showinfo("Info", "No records found")

    # ==================================================
    def parse_date(self, value):
        try:
            if not value or value in ("YYYY-MM-DD", "DD-MM-YYYY"):
                return None
            for fmt in ("%d-%m-%Y", "%Y-%m-%d"):
                try:
                    return datetime.strptime(value, fmt)
                except Exception:
                    continue
            return None
        except Exception:
            return None

    def format_date(self, value):
        d = self.parse_date(value)
        if not d:
            return str(value or "")
        return d.strftime("%d-%m-%Y")

    # ==================================================
    # SELECT ROW
    # ==================================================
    def on_select(self, event):
        sel = self.tree.selection()
        if not sel:
            return
        idx = self.tree.index(sel[0])
        self.selected_invoice = self.filtered_sales[idx]

    # ==================================================
    # SAVE PAYMENT
    # ==================================================
    
    def save_payment(self):
        sel = self.tree.selection()
        if not sel:
            messagebox.showerror("Error", "Select an invoice")
            return

        values = self.tree.item(sel[0], "values")

        try:
            due = float(values[4])   # ✅ row-wise due
        except Exception:
            messagebox.showerror("Error", "Invalid due amount")
            return

        try:
            pay = float(self.pay_e.get())
        except ValueError:
            messagebox.showerror("Error", "Invalid amount")
            return

        if due <= 0:
            messagebox.showinfo("Info", "No due available for this invoice")
            return

        if pay <= 0 or pay > due:
            messagebox.showerror(
                "Error",
                f"Amount must be between 1 and {due:.2f}"
            )
            return

        invoice_no = values[1]

        # ---- update sales data ----
        all_sales = load_sales()
        for s in all_sales:
            if s["invoice_no"] == invoice_no:
                before_paid = s.get("paid", 0)
                before_due = s.get("due", 0)

                s["paid"] = before_paid + pay
                s["due"] = before_due - pay
                break

        save_sales(all_sales)

        write_audit_log(
            user="admin",
            module="payment",
            action="receive",
            reference=invoice_no,
            before={"paid": before_paid, "due": before_due},
            after={"paid": s["paid"], "due": s["due"]}
        )

        add_cash_entry(
            date=datetime.now().strftime("%Y-%m-%d"),
            particulars=f"Customer Payment {invoice_no}",
            cash_in=pay,
            reference=invoice_no
        )

        messagebox.showinfo("Success", "Payment saved")
        self.pay_e.delete(0, tk.END)
        self.load_ledger()

