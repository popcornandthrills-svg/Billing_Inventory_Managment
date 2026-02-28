# purchase_due_report.py
import tkinter as tk
from tkinter import ttk, messagebox
from datetime import datetime

from purchase import load_purchases, save_purchases
from cash_ledger import add_cash_entry, load_cash_ledger
from audit_log import write_audit_log
from export_excel import export_purchase_due_supplier_excel
from supplier_payments import add_supplier_payment, get_supplier_payments


class PurchaseDueReportUI(ttk.Frame):
    def __init__(self, parent):
        super().__init__(parent)

        self.supplier_rows = []
        self.selected_supplier = None
        self.purchase_refs_by_supplier = {}

        self.build_ui()
        self.load_due_report()

    # ==================================================
    # UI
    # ==================================================
    def build_ui(self):
        ttk.Label(
            self,
            text="Purchase Due Report (Supplier-wise)",
            font=("Arial", 16, "bold")
        ).pack(pady=(10, 12))

        top = ttk.Frame(self)
        top.pack(fill="x", padx=10, pady=(0, 8))

        ttk.Button(top, text="Refresh Latest", command=self.load_due_report).pack(side="left", padx=(0, 8))
        ttk.Button(top, text="Export XLSX", command=self.export_xlsx).pack(side="left")

        cols = ("supplier", "pending_bills", "total_due", "oldest_due_date", "latest_due_date")
        self.tree = ttk.Treeview(self, columns=cols, show="headings", height=16)

        headings = {
            "supplier": "Supplier",
            "pending_bills": "Pending Bills",
            "total_due": "Total Due",
            "oldest_due_date": "Oldest Due Date",
            "latest_due_date": "Latest Due Date",
        }
        for c in cols:
            anchor = "w" if c in ("supplier", "oldest_due_date", "latest_due_date") else "e"
            self.tree.heading(c, text=headings[c], anchor=anchor)
            width = 220 if c == "supplier" else 140
            self.tree.column(c, width=width, anchor=anchor)

        self.tree.pack(fill="both", expand=True, padx=12, pady=(5, 8))
        self.tree.bind("<<TreeviewSelect>>", self.on_select)
        self.tree.bind("<Double-1>", self.on_supplier_double_click)
        self.tree.tag_configure("due", background="#ffe6e6")

        self.total_due_var = tk.StringVar(value="Total Due: 0.00")
        ttk.Label(
            self,
            textvariable=self.total_due_var,
            font=("Arial", 12, "bold"),
            foreground="red"
        ).pack(anchor="e", padx=20, pady=(0, 8))

        pay = ttk.LabelFrame(self, text="Pay Supplier Due")
        pay.pack(fill="x", padx=10, pady=8)

        ttk.Label(pay, text="Selected Supplier").grid(row=0, column=0, padx=5, pady=6, sticky="w")
        self.selected_supplier_var = tk.StringVar(value="-")
        ttk.Label(pay, textvariable=self.selected_supplier_var, font=("Arial", 10, "bold")).grid(
            row=0, column=1, padx=5, pady=6, sticky="w"
        )

        ttk.Label(pay, text="Pay Amount").grid(row=1, column=0, padx=5, pady=6, sticky="w")
        self.pay_e = ttk.Entry(pay, width=15)
        self.pay_e.grid(row=1, column=1, padx=5, pady=6, sticky="w")

        ttk.Label(pay, text="Payment Type").grid(row=1, column=2, padx=5, pady=6, sticky="w")
        self.pay_mode_cb = ttk.Combobox(
            pay,
            values=["Cash", "UPI", "Bank", "Card", "Credit"],
            width=12,
            state="readonly"
        )
        self.pay_mode_cb.set("Cash")
        self.pay_mode_cb.grid(row=1, column=3, padx=5, pady=6, sticky="w")

        ttk.Button(pay, text="Save Payment", command=self.save_supplier_payment).grid(
            row=1, column=4, padx=10, pady=6
        )

    # ==================================================
    # HELPERS
    # ==================================================
    def to_float(self, value):
        try:
            return float(value)
        except Exception:
            return 0.0

    def calc_purchase_amounts(self, purchase):
        bill_amount = self.to_float(purchase.get("grand_total", purchase.get("total_amount", 0)))
        paid_amount = self.to_float(purchase.get("paid_amount", purchase.get("paid", 0)))
        if paid_amount < 0:
            paid_amount = 0.0
        due_amount = round(max(bill_amount - paid_amount, 0), 2)
        return round(bill_amount, 2), round(paid_amount, 2), due_amount

    def sync_purchase_due(self, purchase):
        bill_amount, paid_amount, due_amount = self.calc_purchase_amounts(purchase)
        changed = False

        if "grand_total" not in purchase:
            purchase["grand_total"] = bill_amount
            changed = True
        if round(self.to_float(purchase.get("paid_amount", 0)), 2) != paid_amount:
            purchase["paid_amount"] = paid_amount
            changed = True
        if round(self.to_float(purchase.get("due", purchase.get("due_amount", 0))), 2) != due_amount:
            purchase["due"] = due_amount
            changed = True
        if round(self.to_float(purchase.get("due_amount", due_amount)), 2) != due_amount:
            purchase["due_amount"] = due_amount
            changed = True

        return changed

    def parse_purchase_date(self, value):
        text = str(value or "").strip()
        for fmt in ("%Y-%m-%d %H:%M:%S", "%d-%m-%Y %H:%M:%S", "%Y-%m-%d", "%d-%m-%Y"):
            try:
                return datetime.strptime(text, fmt)
            except Exception:
                continue
        return datetime.min

    # ==================================================
    # LOAD REPORT (LATEST SUPPLIER DUES)
    # ==================================================
    def load_due_report(self):
        self.tree.delete(*self.tree.get_children())
        self.supplier_rows = []
        self.selected_supplier = None
        self.selected_supplier_var.set("-")
        self.purchase_refs_by_supplier = {}

        supplier_map = {}
        total_due_all = 0.0

        purchases = load_purchases()
        purchases_changed = False
        for idx, p in enumerate(purchases):
            purchases_changed = self.sync_purchase_due(p) or purchases_changed
            due = self.to_float(p.get("due", p.get("due_amount", 0)))
            if due <= 0:
                continue

            supplier = p.get("supplier_name") or p.get("supplier") or "Unknown Supplier"
            date_text = p.get("date") or p.get("created_on") or ""

            if supplier not in supplier_map:
                supplier_map[supplier] = {
                    "supplier": supplier,
                    "pending_bills": 0,
                    "total_due": 0.0,
                    "oldest_due_date": date_text,
                    "latest_due_date": date_text,
                }
                self.purchase_refs_by_supplier[supplier] = []

            row = supplier_map[supplier]
            row["pending_bills"] += 1
            row["total_due"] += due

            if date_text and (not row["oldest_due_date"] or date_text < row["oldest_due_date"]):
                row["oldest_due_date"] = date_text
            if date_text and (not row["latest_due_date"] or date_text > row["latest_due_date"]):
                row["latest_due_date"] = date_text

            self.purchase_refs_by_supplier[supplier].append((idx, date_text, due))
            total_due_all += due

        if purchases_changed:
            save_purchases(purchases)

        self.supplier_rows = sorted(
            supplier_map.values(),
            key=lambda r: r["total_due"],
            reverse=True
        )

        for row in self.supplier_rows:
            self.tree.insert(
                "",
                "end",
                values=(
                    row["supplier"],
                    row["pending_bills"],
                    f"{row['total_due']:.2f}",
                    row["oldest_due_date"],
                    row["latest_due_date"],
                ),
                tags=("due",)
            )

        self.total_due_var.set(f"Total Due: {total_due_all:,.2f}")

        if not self.supplier_rows:
            messagebox.showinfo("Info", "No supplier dues found")

    # ==================================================
    # EXPORT
    # ==================================================
    def export_xlsx(self):
        if not self.supplier_rows:
            messagebox.showinfo("No Data", "No supplier due data to export")
            return
        path = export_purchase_due_supplier_excel(self.supplier_rows)
        if path:
            messagebox.showinfo("Export", f"Exported successfully:\n{path}")

    # ==================================================
    # SELECT ROW
    # ==================================================
    def on_select(self, _event):
        sel = self.tree.selection()
        if not sel:
            return
        values = self.tree.item(sel[0], "values")
        if not values:
            return
        self.selected_supplier = values[0]
        self.selected_supplier_var.set(self.selected_supplier)

    def on_supplier_double_click(self, event):
        iid = self.tree.identify_row(event.y)
        if not iid:
            return
        supplier = self.tree.set(iid, "supplier")
        if supplier:
            self.open_supplier_purchase_history(supplier)

    def open_supplier_purchase_history(self, supplier_name):
        purchases = []
        for p in load_purchases():
            supplier = p.get("supplier_name") or p.get("supplier") or "Unknown Supplier"
            if supplier != supplier_name:
                continue
            purchases.append(p)

        payment_rows = get_supplier_payments(supplier_name)
        existing_payment_keys = {
            (
                str(p.get("date", "")),
                round(self.to_float(p.get("amount", 0)), 2),
                str(p.get("reference", "")),
            )
            for p in payment_rows
        }
        # Backward compatibility: include older supplier payment entries
        # that were recorded only in cash ledger.
        supplier_lower = supplier_name.strip().lower()
        for row in load_cash_ledger():
            particulars = str(row.get("particulars", ""))
            p_lower = particulars.lower()
            if "supplier payment" not in p_lower:
                continue
            if supplier_lower not in p_lower and str(row.get("reference", "")).strip().lower() != supplier_lower:
                continue

            mode = ""
            if p_lower.startswith("cash "):
                mode = "Cash"
            elif p_lower.startswith("upi "):
                mode = "UPI"
            elif p_lower.startswith("bank "):
                mode = "Bank"
            elif p_lower.startswith("card "):
                mode = "Card"

            key = (
                str(row.get("date", "")),
                round(self.to_float(row.get("cash_out", 0)), 2),
                str(row.get("reference", "")),
            )
            if key in existing_payment_keys:
                continue

            payment_rows.append({
                "payment_id": row.get("reference", ""),
                "date": row.get("date", ""),
                "supplier_name": supplier_name,
                "amount": self.to_float(row.get("cash_out", 0)),
                "payment_mode": mode,
                "reference": row.get("reference", ""),
                "due_after": 0.0,
            })

        win = tk.Toplevel(self)
        win.title(f"Supplier Purchase History - {supplier_name}")
        win.geometry("1180x560")
        win.transient(self.winfo_toplevel())
        win.lift()
        win.focus_force()

        ttk.Label(
            win,
            text=f"Supplier Purchase Report: {supplier_name}",
            font=("Arial", 12, "bold")
        ).pack(anchor="w", padx=10, pady=(10, 6))

        cols = ("date", "type", "reference", "bill_amount", "paid", "due", "payment_mode")
        frame = ttk.Frame(win)
        frame.pack(fill="both", expand=True, padx=10, pady=(0, 8))
        frame.columnconfigure(0, weight=1)
        frame.rowconfigure(0, weight=1)

        tree = ttk.Treeview(frame, columns=cols, show="headings")

        headings = {
            "date": "Date",
            "type": "Type",
            "reference": "Reference",
            "bill_amount": "Bill Amount",
            "paid": "Paid",
            "due": "Due",
            "payment_mode": "Payment Mode",
        }
        for c in cols:
            anchor = "w" if c in ("date", "type", "reference", "payment_mode") else "e"
            width = 140
            if c == "reference":
                width = 230
            elif c == "payment_mode":
                width = 160
            elif c == "type":
                width = 110
            tree.heading(c, text=headings[c], anchor=anchor)
            tree.column(c, width=width, anchor=anchor)

        tree.grid(row=0, column=0, sticky="nsew")
        ysb = ttk.Scrollbar(frame, orient="vertical", command=tree.yview)
        ysb.grid(row=0, column=1, sticky="ns")
        xsb = ttk.Scrollbar(frame, orient="horizontal", command=tree.xview)
        xsb.grid(row=1, column=0, sticky="ew")
        tree.configure(yscrollcommand=ysb.set, xscrollcommand=xsb.set)
        tree.tag_configure("payment", background="#eef7ff")
        tree.tag_configure("purchase", background="#ffffff")

        entries = []
        total_bill = 0.0
        total_paid = 0.0
        current_due_sum = 0.0

        for p in purchases:
            date_text = p.get("date") or p.get("created_on") or ""
            purchase_id = p.get("purchase_id", "")
            bill_amount, paid, due = self.calc_purchase_amounts(p)
            payment_mode = p.get("payment_mode", p.get("payment_type", ""))

            total_bill += bill_amount
            total_paid += paid
            current_due_sum += due

            entries.append({
                "sort_date": self.parse_purchase_date(date_text),
                "type_rank": 1,
                "row": (
                    date_text,
                    "Purchase",
                    purchase_id,
                    f"{bill_amount:,.2f}",
                    f"{paid:,.2f}",
                    f"{due:,.2f}",
                    payment_mode,
                )
            })

        for pay in payment_rows:
            date_text = pay.get("date", "")
            amount = self.to_float(pay.get("amount", 0))
            entries.append({
                "sort_date": self.parse_purchase_date(date_text),
                "type_rank": 0,
                "row": (
                    date_text,
                    "Payment",
                    pay.get("payment_id", pay.get("reference", "")),
                    "",
                    f"{amount:,.2f}",
                    f"{self.to_float(pay.get('due_after', 0)):,.2f}",
                    pay.get("payment_mode", ""),
                )
            })

        # Latest first; on same date show Payment rows before Purchase rows.
        entries.sort(key=lambda e: (e["sort_date"], -e["type_rank"]), reverse=True)
        for e in entries:
            row_type = str(e["row"][1]).lower()
            tree.insert("", "end", values=e["row"], tags=("payment",) if row_type == "payment" else ("purchase",))

        summary = ttk.Frame(win)
        summary.pack(fill="x", padx=10, pady=(0, 10))
        ttk.Label(
            summary,
            text=f"Total Bill: {total_bill:,.2f}    Total Paid (Purchase): {total_paid:,.2f}    Current Due: {current_due_sum:,.2f}",
            font=("Arial", 10, "bold")
        ).pack(anchor="e")

    # ==================================================
    # SAVE PAYMENT (SUPPLIER LEVEL)
    # ==================================================
    def save_supplier_payment(self):
        if not self.selected_supplier:
            messagebox.showerror("Error", "Select a supplier")
            return

        try:
            pay = float(self.pay_e.get())
        except ValueError:
            messagebox.showerror("Error", "Invalid amount")
            return

        if pay <= 0:
            messagebox.showerror("Error", "Pay amount must be greater than 0")
            return
        payment_mode = self.pay_mode_cb.get().strip() or "Cash"

        supplier_rows = [r for r in self.supplier_rows if r["supplier"] == self.selected_supplier]
        if not supplier_rows:
            messagebox.showerror("Error", "Selected supplier due not found")
            return

        supplier_due = supplier_rows[0]["total_due"]
        if pay > supplier_due:
            messagebox.showerror("Error", f"Amount cannot exceed supplier due ({supplier_due:.2f})")
            return
        supplier_due_before = supplier_due

        purchases = load_purchases()
        purchases_changed = False
        for purchase in purchases:
            purchases_changed = self.sync_purchase_due(purchase) or purchases_changed
        refs = self.purchase_refs_by_supplier.get(self.selected_supplier, [])
        refs = sorted(refs, key=lambda x: x[1] or "")  # oldest due first

        remaining = pay
        total_before_due = 0.0
        total_after_due = 0.0

        for idx, _date_text, _due in refs:
            if remaining <= 0:
                break
            if idx >= len(purchases):
                continue

            p = purchases[idx]
            bill_amount, before_paid, current_due = self.calc_purchase_amounts(p)
            if current_due <= 0:
                continue

            apply_amount = min(remaining, current_due)
            before_due = current_due

            p["paid_amount"] = round(before_paid + apply_amount, 2)
            p["due"] = round(max(bill_amount - p["paid_amount"], 0), 2)
            p["due_amount"] = p["due"]
            purchases_changed = True

            total_before_due += before_due
            total_after_due += p["due"]
            remaining -= apply_amount

            write_audit_log(
                user="admin",
                module="purchase_payment",
                action="pay_supplier_due",
                reference=p.get("purchase_id", ""),
                before={"paid": before_paid, "due": before_due},
                after={"paid": p["paid_amount"], "due": p["due"]},
                extra={"supplier": self.selected_supplier, "allocated_payment": round(apply_amount, 2)}
            )

        if remaining > 0.0001:
            messagebox.showerror("Error", "Could not fully allocate payment. Please refresh and retry.")
            return

        if purchases_changed:
            save_purchases(purchases)
        supplier_due_after = round(
            sum(
                self.calc_purchase_amounts(p)[2]
                for p in purchases
                if (p.get("supplier_name") or p.get("supplier") or "Unknown Supplier") == self.selected_supplier
            ),
            2
        )

        add_supplier_payment(
            supplier_name=self.selected_supplier,
            amount=round(pay, 2),
            payment_mode=payment_mode,
            reference=self.selected_supplier,
            note="Supplier due payment",
            due_before=round(supplier_due_before, 2),
            due_after=round(supplier_due_after, 2),
        )

        add_cash_entry(
            date=datetime.now().strftime("%Y-%m-%d"),
            particulars=f"{payment_mode} Supplier Payment - {self.selected_supplier}",
            cash_out=round(pay, 2),
            reference=self.selected_supplier
        )

        write_audit_log(
            user="admin",
            module="purchase_payment",
            action="supplier_bulk_payment",
            reference=self.selected_supplier,
            before={"supplier_due": round(total_before_due, 2)},
            after={"supplier_due": round(total_after_due, 2)},
            extra={"payment": round(pay, 2), "payment_mode": payment_mode}
        )

        messagebox.showinfo("Success", "Supplier payment saved")
        self.pay_e.delete(0, tk.END)
        self.load_due_report()
