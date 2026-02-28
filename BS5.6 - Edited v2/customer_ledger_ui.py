import tkinter as tk
from tkinter import ttk, messagebox
from datetime import datetime
from sales import load_sales, save_sales
from audit_log import write_audit_log
from cash_ledger import add_cash_entry
from date_picker import open_date_picker
from ui_theme import compact_form_grid

class CustomerLedgerUI(ttk.Frame):
    def __init__(self, parent):
        super().__init__(parent)

        self.sales = []
        self.filtered_sales = []
        self.selected_invoice = None
        self._render_job = None
        self._rows_buffer = []
        self._pending_total_due = 0.0
        self._pending_customer_name = None
        self._customer_name_values_all = []
        self._item_values_all = []
        self.name_suggest_win = None
        self.name_suggest_list = None
        self.item_suggest_win = None
        self.item_suggest_list = None

        self.build_ui()
        self.refresh_filter_recommendations()
        
        
        
    def export_excel(self):
        if not self.filtered_sales:
            messagebox.showerror("Error", "No data to export")
            return
        from export_excel import export_customer_ledger_excel
        
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
        from ledger_pdf import generate_customer_ledger_pdf
          
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

        row1 = ttk.Frame(search)
        row1.pack(fill="x", padx=4, pady=(3, 2))

        ttk.Label(row1, text="Customer Name").pack(side="left", padx=(0, 3))
        self.name_e = ttk.Entry(row1, width=22)
        self.name_e.pack(side="left", padx=(0, 8))
        self.name_e.bind("<KeyRelease>", self.filter_customer_names)
        self.name_e.bind("<FocusOut>", self.on_name_focus_out)
        self.name_e.bind("<Down>", self.on_name_down_key)

        ttk.Label(row1, text="Phone").pack(side="left", padx=(0, 3))
        self.phone_e = ttk.Entry(row1, width=18)
        self.phone_e.pack(side="left", padx=(0, 8))

        ttk.Label(row1, text="Item").pack(side="left", padx=(0, 3))
        self.item_e = ttk.Entry(row1, width=18)
        self.item_e.pack(side="left", padx=(0, 8))
        self.item_e.bind("<KeyRelease>", self.filter_items)
        self.item_e.bind("<FocusOut>", self.on_item_focus_out)
        self.item_e.bind("<Down>", self.on_item_down_key)

        row2 = ttk.Frame(search)
        row2.pack(fill="x", padx=4, pady=(2, 3))

        ttk.Label(row2, text="From Date").pack(side="left", padx=(0, 3))
        self.from_date_e = ttk.Entry(row2, width=15)
        self.from_date_e.pack(side="left", padx=(0, 3))
        self.from_date_e.insert(0, "DD-MM-YYYY")
        ttk.Button(
            row2,
            text="📅",
            width=5,
            command=lambda: open_date_picker(self, self.from_date_e),
        ).pack(side="left", padx=(0, 8))

        ttk.Label(row2, text="To Date").pack(side="left", padx=(0, 3))
        self.to_date_e = ttk.Entry(row2, width=15)
        self.to_date_e.pack(side="left", padx=(0, 3))
        self.to_date_e.insert(0, "DD-MM-YYYY")
        ttk.Button(
            row2,
            text="📅",
            width=5,
            command=lambda: open_date_picker(self, self.to_date_e),
        ).pack(side="left", padx=(0, 8))

        ttk.Button(
            row2,
            text="Load Ledger",
            width=15,
            command=self.load_ledger
        ).pack(side="left", padx=(0, 2))

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
            height=14
        )

        for c in cols:
            self.tree.heading(c, text=c.title())
            self.tree.column(c, width=120, anchor="center")

        self.tree.pack(fill="both", expand=True, padx=15, pady=10)
        self.tree.bind("<<TreeviewSelect>>", self.on_select)

        self.tree.tag_configure("due", background="#ffe6e6")
        self.status_var = tk.StringVar(value="")
        ttk.Label(self, textvariable=self.status_var).pack(anchor="w", padx=15, pady=(0, 4))

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

        ttk.Button(
            pay,
            text="Save Payment",
            command=self.save_payment
        ).grid(row=0, column=0, padx=10)
        
        # ---------- EXPORT BUTTONS (SAME LINE) ----------
        ttk.Button(
            pay,
            text="Export Excel",
            command=self.export_excel
        ).grid(row=0, column=1, padx=20)

        ttk.Button(
            pay,
            text="Export PDF",
            command=self.export_pdf
        ).grid(row=0, column=2, padx=5)
        compact_form_grid(pay)

    # ==================================================
    # LOAD LEDGER (CORE LOGIC)
    # ==================================================
    def load_ledger(self):
        if self._render_job:
            try:
                self.after_cancel(self._render_job)
            except Exception:
                pass
            self._render_job = None
        self.tree.delete(*self.tree.get_children())
        self.filtered_sales = []
        self.selected_invoice = None
        self._rows_buffer = []
        self.refresh_filter_recommendations()

        name = self.name_e.get().strip().lower()
        phone = self.phone_e.get().strip()
        item = self.item_e.get().strip().lower()

        from_date = self.parse_date(self.from_date_e.get().strip())
        to_date = self.parse_date(self.to_date_e.get().strip())

        total_due = 0.0
        customer_name = None
        matched_sales = []

        sales_rows = sorted(
            load_sales(),
            key=lambda x: self.parse_date(x.get("date")) or datetime.min,
            reverse=True
        )
        for s in sales_rows:

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
            matched_sales.append(s)
            customer_name = s.get("customer_name")

            total_due += float(s.get("due", 0))

        self.filtered_sales = matched_sales
        self._pending_customer_name = customer_name
        self._pending_total_due = total_due
        for s in matched_sales:
            self._rows_buffer.append(
                (
                    (
                        self.format_date(s.get("date")),
                        s.get("invoice_no"),
                        f"{s.get('grand_total', 0):.2f}",
                        f"{s.get('paid', 0):.2f}",
                        f"{s.get('due', 0):.2f}",
                    ),
                    ("due",) if s.get("due", 0) > 0 else ()
                )
            )

        if not self.filtered_sales:
            self.customer_name_var.set("Customer: -")
            self.total_due_var.set("Total Due: 0.00")
            self.status_var.set("")
            messagebox.showinfo("Info", "No records found")
            return

        self.status_var.set(f"Loading {len(self._rows_buffer)} rows...")
        self._render_rows_chunk()

    def _render_rows_chunk(self, chunk_size=250):
        if not self._rows_buffer:
            self.customer_name_var.set(
                f"Customer: {self._pending_customer_name}" if self._pending_customer_name else "Customer: -"
            )
            self.total_due_var.set(f"Total Due: {self._pending_total_due:,.2f}")
            self.status_var.set("")
            self._render_job = None
            return

        batch = self._rows_buffer[:chunk_size]
        self._rows_buffer = self._rows_buffer[chunk_size:]
        for values, tags in batch:
            self.tree.insert("", "end", values=values, tags=tags)

        self.status_var.set(f"Loading... {len(self._rows_buffer)} rows remaining")
        self._render_job = self.after(1, self._render_rows_chunk)

    # ==================================================
    def refresh_filter_recommendations(self):
        sales = load_sales()
        customer_names = []
        item_names = []

        for s in sales:
            name = str(s.get("customer_name", "")).strip()
            if name:
                customer_names.append(name)
            for it in s.get("items", []):
                iname = str(it.get("item") or it.get("name") or "").strip()
                if iname:
                    item_names.append(iname)

        self._customer_name_values_all = sorted(set(customer_names), key=str.lower)
        self._item_values_all = sorted(set(item_names), key=str.lower)

    def filter_customer_names(self, event=None):
        if event and event.keysym in ("Up", "Down", "Left", "Right", "Return", "Escape", "Tab"):
            return
        typed = self.name_e.get().strip().lower()
        if not typed:
            self._hide_name_suggestions()
            return
        matches = [n for n in self._customer_name_values_all if typed in n.lower()]
        self._show_name_suggestions(matches)

    def filter_items(self, event=None):
        if event and event.keysym in ("Up", "Down", "Left", "Right", "Return", "Escape", "Tab"):
            return
        typed = self.item_e.get().strip().lower()
        if not typed:
            self._hide_item_suggestions()
            return
        matches = [n for n in self._item_values_all if typed in n.lower()]
        self._show_item_suggestions(matches)

    def _show_name_suggestions(self, values):
        if not values:
            self._hide_name_suggestions()
            return

        if self.name_suggest_win is None or not self.name_suggest_win.winfo_exists():
            self.name_suggest_win = tk.Toplevel(self)
            self.name_suggest_win.overrideredirect(True)
            self.name_suggest_win.attributes("-topmost", True)
            self.name_suggest_list = tk.Listbox(self.name_suggest_win, height=7, activestyle="none")
            self.name_suggest_list.pack(fill="both", expand=True)
            self.name_suggest_list.bind("<ButtonRelease-1>", self.on_name_pick_from_list)
            self.name_suggest_list.bind("<Return>", self.on_name_pick_from_list)

        self.name_suggest_list.delete(0, tk.END)
        for v in values:
            self.name_suggest_list.insert(tk.END, v)

        x = self.name_e.winfo_rootx()
        y = self.name_e.winfo_rooty() + self.name_e.winfo_height() + 1
        w = max(self.name_e.winfo_width(), 220)
        self.name_suggest_win.geometry(f"{w}x160+{x}+{y}")
        self.name_suggest_win.deiconify()
        self.name_suggest_win.lift()
        self.name_e.focus_set()
        self.name_e.icursor(tk.END)

    def _hide_name_suggestions(self):
        if self.name_suggest_win is not None and self.name_suggest_win.winfo_exists():
            self.name_suggest_win.withdraw()

    def on_name_pick_from_list(self, _event=None):
        if self.name_suggest_list is None or not self.name_suggest_list.curselection():
            return
        picked = self.name_suggest_list.get(self.name_suggest_list.curselection()[0])
        self.name_e.delete(0, tk.END)
        self.name_e.insert(0, picked)
        self.name_e.focus_set()
        self.name_e.icursor(tk.END)
        self._hide_name_suggestions()

    def on_name_focus_out(self, _event=None):
        self.after(120, self._hide_if_name_focus_lost)

    def _hide_if_name_focus_lost(self):
        w = self.focus_get()
        if w is self.name_e or w is self.name_suggest_list:
            return
        self._hide_name_suggestions()

    def on_name_down_key(self, _event=None):
        if self.name_suggest_list is None:
            return
        if self.name_suggest_win is None or not self.name_suggest_win.winfo_exists():
            return
        if str(self.name_suggest_win.state()) != "normal":
            return
        if self.name_suggest_list.size() <= 0:
            return
        self.name_suggest_list.focus_set()
        self.name_suggest_list.selection_clear(0, tk.END)
        self.name_suggest_list.selection_set(0)
        self.name_suggest_list.activate(0)
        return "break"

    def _show_item_suggestions(self, values):
        if not values:
            self._hide_item_suggestions()
            return

        if self.item_suggest_win is None or not self.item_suggest_win.winfo_exists():
            self.item_suggest_win = tk.Toplevel(self)
            self.item_suggest_win.overrideredirect(True)
            self.item_suggest_win.attributes("-topmost", True)
            self.item_suggest_list = tk.Listbox(self.item_suggest_win, height=7, activestyle="none")
            self.item_suggest_list.pack(fill="both", expand=True)
            self.item_suggest_list.bind("<ButtonRelease-1>", self.on_item_pick_from_list)
            self.item_suggest_list.bind("<Return>", self.on_item_pick_from_list)

        self.item_suggest_list.delete(0, tk.END)
        for v in values:
            self.item_suggest_list.insert(tk.END, v)

        x = self.item_e.winfo_rootx()
        y = self.item_e.winfo_rooty() + self.item_e.winfo_height() + 1
        w = max(self.item_e.winfo_width(), 220)
        self.item_suggest_win.geometry(f"{w}x160+{x}+{y}")
        self.item_suggest_win.deiconify()
        self.item_suggest_win.lift()
        self.item_e.focus_set()
        self.item_e.icursor(tk.END)

    def _hide_item_suggestions(self):
        if self.item_suggest_win is not None and self.item_suggest_win.winfo_exists():
            self.item_suggest_win.withdraw()

    def on_item_pick_from_list(self, _event=None):
        if self.item_suggest_list is None or not self.item_suggest_list.curselection():
            return
        picked = self.item_suggest_list.get(self.item_suggest_list.curselection()[0])
        self.item_e.delete(0, tk.END)
        self.item_e.insert(0, picked)
        self.item_e.focus_set()
        self.item_e.icursor(tk.END)
        self._hide_item_suggestions()

    def on_item_focus_out(self, _event=None):
        self.after(120, self._hide_if_item_focus_lost)

    def _hide_if_item_focus_lost(self):
        w = self.focus_get()
        if w is self.item_e or w is self.item_suggest_list:
            return
        self._hide_item_suggestions()

    def on_item_down_key(self, _event=None):
        if self.item_suggest_list is None:
            return
        if self.item_suggest_win is None or not self.item_suggest_win.winfo_exists():
            return
        if str(self.item_suggest_win.state()) != "normal":
            return
        if self.item_suggest_list.size() <= 0:
            return
        self.item_suggest_list.focus_set()
        self.item_suggest_list.selection_clear(0, tk.END)
        self.item_suggest_list.selection_set(0)
        self.item_suggest_list.activate(0)
        return "break"

    # ==================================================
    def parse_date(self, value):
        try:
            if not value or value in ("YYYY-MM-DD", "DD-MM-YYYY"):
                return None
            for fmt in ("%d-%m-%Y %H:%M:%S", "%Y-%m-%d %H:%M:%S", "%d-%m-%Y", "%Y-%m-%d"):
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
        return d.strftime("%d-%m-%Y %H:%M:%S")

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

        pay = due

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
        self.load_ledger()

