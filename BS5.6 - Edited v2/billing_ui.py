import tkinter as tk
from tkinter import ttk, messagebox
import os
from datetime import datetime

from audit_log import write_audit_log
from config import COMPANY
from utils_print import print_pdf
from sales import create_sale
from inventory import get_available_items, get_item_stock, load_inventory
from customers import load_customers, get_customer_by_name
from customers import (
    save_customer,
    get_customer_by_phone,
    get_customer_by_name
)
from ui_theme import compact_form_grid

ITEM_TYPE_OPTIONS = ["Nos", "Kg", "Litre", "Metre"]


class BillingUI(ttk.Frame):
    def __init__(self, parent):
        super().__init__(parent)
        self.pack(fill="both", expand=True)
        
        #  ADD THESE LINES HERE
        self.columnconfigure(0, weight=1)
        
        #  Row height control (THIS IS FINAL SET)
        self.rowconfigure(0, weight=0)   # Customer section
        self.rowconfigure(1, weight=0)   # Add item section
        self.rowconfigure(2, weight=1)   # Table ONLY expands
        self.rowconfigure(3, weight=0)   # Edit/Delete
        self.rowconfigure(4, weight=0)   # Summary / Payment
        self.rowconfigure(5, weight=0)   # GST summary
        

        # ================= STATE =================
        self.cart = []
        self.edit_index = None
        self.grand_total = 0.0
        self.last_invoice_path = None
        self._saving_invoice = False
        self._quick_action_locked = False
        self._quick_action_job = None
        self._customers_cache = {}
        self._stock_cache = {}
        self._item_values_all = []

        # ================= GRID =================
        self.columnconfigure(0, weight=1)

        # =================================================
        # ROW 0 : CUSTOMER DETAILS
        # =================================================
        top = ttk.Frame(self)
        top.grid(row=0, column=0, sticky="ew", padx=10, pady=8)

        ttk.Label(top, text="Customer Name").grid(row=0, column=0, sticky="w")
        
        self.cust_name = ttk.Entry(top, width=30)
        self.cust_name.grid(row=0, column=1, sticky="w")
        
       
        self.suggestion_box = tk.Listbox(top, height=5)
        self.suggestion_box.grid(row=2, column=1, sticky="ew")
        
        self.suggestion_box.bind("<<ListboxSelect>>", self.select_customer)

        self.suggestion_box.grid_remove()

        ttk.Label(top, text="Phone").grid(row=0, column=2, sticky="w")
        self.phone = ttk.Entry(top, width=15)
        self.phone.grid(row=0, column=3, padx=5)

        ttk.Label(top, text="Address").grid(row=1, column=0, sticky="w")
        self.address = ttk.Entry(top, width=50)
        self.address.grid(row=1, column=1, columnspan=3, padx=5, pady=4, sticky="w")

        self.cust_name.bind("<KeyRelease>", self.show_customer_suggestions)

         
        self.phone.bind("<KeyRelease>", self.autofill_by_phone)
        compact_form_grid(top)

        # =================================================
        # ROW 1 : ADD ITEM SECTION
        # =================================================
        add = ttk.Frame(self)
        add.grid(row=1, column=0, sticky="ew", padx=10, pady=(10, 10))

        ttk.Label(add, text="Item").grid(row=0, column=0)
        ttk.Label(add, text="Type").grid(row=0, column=2)
        ttk.Label(add, text="Qty").grid(row=0, column=3)
        ttk.Label(add, text="Rate").grid(row=0, column=4)
        ttk.Label(add, text="GST %").grid(row=0, column=5)
        
        self.item_cb = ttk.Combobox(add, state="normal", width=22)
        self.item_cb.grid(row=1, column=0, padx=5)
        self.item_cb.bind("<KeyRelease>", self.filter_items_live)

        # 🔍 SEARCH BUTTON
        self.find_btn = ttk.Button(
            add,
            text="Find",
            width=6,
            command=self.open_item_search
        )
        self.find_btn.grid(row=1, column=1, padx=2)

        self.type_cb = ttk.Combobox(add, values=ITEM_TYPE_OPTIONS, state="readonly", width=10)
        self.type_cb.set("")
        self.type_cb.grid(row=1, column=2, padx=5)

        self.qty_e = ttk.Entry(add, width=8)
        self.qty_e.grid(row=1, column=3)

        self.rate_e = ttk.Entry(add, width=10)
        self.rate_e.grid(row=1, column=4)

        self.gst_e = ttk.Entry(add, width=6)
        self.gst_e.insert(0, "18")
        self.gst_e.grid(row=1, column=5)
                        
                
        self.add_btn = ttk.Button(
            add, text="Add / Update Item", command=self.add_item
        )
        self.add_btn.grid(row=1, column=6, padx=12)

        self.refresh_items()
        compact_form_grid(add)

        # =================================================
        # ROW 2 : ITEMS TABLE
        # =================================================
        table_frame = ttk.Frame(self)
        table_frame.grid(row=2, column=0, sticky="nsew", padx=10, pady=5)
        table_frame.columnconfigure(0, weight=1)
        table_frame.columnconfigure(1, weight=0)


        self.tree = ttk.Treeview(
            table_frame,
            columns=("item", "type", "qty", "rate", "gst", "total"),
            show="headings",
            height=14
        )
                
        for col, txt, w in [
            ("item", "ITEM", 220),
            ("type", "TYPE", 90),
            ("qty", "QTY", 80),
            ("rate", "RATE", 100),
            ("gst", "GST %", 80),
            ("total", "TOTAL", 120),
        ]:
            self.tree.heading(col, text=txt)
            self.tree.column(col, width=w, anchor="center")
            
        # Vertical Scrollbar
        v_scroll = ttk.Scrollbar(
            table_frame,
            orient="vertical",
            command=self.tree.yview
        )
        self.tree.configure(yscrollcommand=v_scroll.set)

        self.tree.grid(row=0, column=0, sticky="nsew")
        v_scroll.grid(row=0, column=1, sticky="ns")

        # =================================================
        # ROW 3 : TABLE FOOTER (EDIT / DELETE)
        # =================================================
        table_footer = ttk.Frame(self)
        table_footer.grid(row=3, column=0, sticky="w", padx=10, pady=(0, 10))

        self.edit_btn = ttk.Button(
            table_footer, text="Edit Item", command=self.edit_item
        )
        self.edit_btn.pack(side="left", padx=4)

        self.delete_btn = ttk.Button(
            table_footer, text="Delete Item", command=self.delete_item
        )
        self.delete_btn.pack(side="left", padx=4)

        # =================================================
        # ROW 4 : PAYMENT + TOTALS + ACTIONS
        # =================================================
        summary = ttk.Frame(self)
        summary.grid(row=4, column=0, sticky="ew", padx=10, pady=(15, 10))

        ttk.Label(summary, text="Payment Mode").grid(row=0, column=0, sticky="w")
        self.pay_mode = ttk.Combobox(
            summary, values=["Cash", "UPI", "Card", "Due"],
            state="readonly", width=12
        )
        self.pay_mode.current(0)
        self.pay_mode.grid(row=0, column=1, padx=5)

        ttk.Label(summary, text="Paid Amount").grid(row=1, column=0, sticky="w")
        self.paid_e = ttk.Entry(summary, width=12)
        self.paid_e.grid(row=1, column=1, padx=5)
        self.paid_e.bind("<KeyRelease>", self.update_balance)

        self.total_var = tk.StringVar(value="Total: ₹0.00")
        self.balance_var = tk.StringVar(value="Balance: ₹0.00")

        ttk.Label(
            summary, textvariable=self.total_var,
            font=("Arial", 11, "bold"), foreground="green"
        ).grid(row=0, column=3, padx=30, sticky="e")

        ttk.Label(
            summary, textvariable=self.balance_var,
            font=("Arial", 11, "bold"), foreground="red"
        ).grid(row=1, column=3, padx=30, sticky="e")

        self.generate_btn = ttk.Button(
            summary, text="Generate Invoice",
            command=self.save_sale, width=20
        )
        self.generate_btn.grid(row=2, column=0, columnspan=2, pady=10)

        self.print_btn = ttk.Button(
            summary, text="Print",
            command=self.print_invoice, width=14
        )
        self.print_btn.grid(row=2, column=3, pady=10)
        self.print_btn.config(state="disabled")
        compact_form_grid(summary)

        # =================================================
        # ROW 5 : GST SUMMARY + GRAND TOTAL
        # =================================================
        gst = ttk.Frame(self)
        gst.grid(row=5, column=0, sticky="e", padx=20, pady=(0, 10))

        self.taxable_var = tk.StringVar(value="Taxable: ₹0.00")
        self.cgst_var = tk.StringVar(value="CGST: ₹0.00")
        self.sgst_var = tk.StringVar(value="SGST: ₹0.00")
        self.igst_var = tk.StringVar(value="IGST: ₹0.00")
        self.discount_var = tk.StringVar(value="Discount: ₹0.00")
        self.grand_total_var = tk.StringVar(value="Grand Total: ₹0.00")

        ttk.Label(gst, textvariable=self.taxable_var).grid(row=0, column=0, sticky="e")
        ttk.Label(gst, textvariable=self.cgst_var).grid(row=1, column=0, sticky="e")
        ttk.Label(gst, textvariable=self.sgst_var).grid(row=2, column=0, sticky="e")
        ttk.Label(gst, textvariable=self.igst_var).grid(row=3, column=0, sticky="e")
        ttk.Label(gst, textvariable=self.discount_var, foreground="#9a3412").grid(row=0, column=1, sticky="e", padx=(30, 0))
        ttk.Label(gst, text="Discount %").grid(row=1, column=1, sticky="e", padx=(30, 0))
        self.discount_e = ttk.Entry(gst, width=8)
        self.discount_e.insert(0, "")
        self.discount_e.grid(row=2, column=1, sticky="e", padx=(30, 0))
        self.discount_e.bind("<KeyRelease>", lambda _e: self.refresh_total())
        ttk.Label(
            gst, textvariable=self.grand_total_var,
            font=("Arial", 11, "bold")
        ).grid(row=4, column=0, sticky="e", pady=(5, 0))
        self._bind_enter_navigation()

    def _focus_next_widget(self, event):
        event.widget.tk_focusNext().focus_set()
        return "break"

    def _bind_enter_navigation(self):
        for w in (
            self.cust_name,
            self.phone,
            self.address,
            self.item_cb,
            self.type_cb,
            self.qty_e,
            self.rate_e,
            self.gst_e,
            self.discount_e,
            self.pay_mode,
            self.paid_e,
        ):
            w.bind("<Return>", self._focus_next_widget)
            w.bind("<KP_Enter>", self._focus_next_widget)
        
    def show_customer_suggestions(self, event=None):
        typed = self.cust_name.get().strip().lower()

        if len(typed) < 3:
            self.suggestion_box.grid_remove()
            return

        matches = [
            c["name"] for c in self._customers_cache.values()
            if typed in c.get("name", "").lower()
        ]

        if not matches:
            self.suggestion_box.grid_remove()
            return

        self.suggestion_box.delete(0, tk.END)

        for m in matches:
            self.suggestion_box.insert(tk.END, m)

        self.suggestion_box.lift()
        self.suggestion_box.grid()

    def _warm_load_customers(self):
        try:
            self._customers_cache = load_customers()
        except Exception:
            self._customers_cache = {}

    def _find_customer_by_phone(self, phone):
        key = str(phone or "").strip()
        if not key:
            return None
        for c in self._customers_cache.values():
            if str(c.get("phone", "")).strip() == key:
                return c
        return None

    def _find_customer_by_name(self, name):
        key = str(name or "").strip().lower()
        if not key:
            return None
        for c in self._customers_cache.values():
            if str(c.get("name", "")).strip().lower() == key:
                return c
        return None

    def select_customer(self, event=None):
        if not self.suggestion_box.curselection():
            return

        selected = self.suggestion_box.get(
            self.suggestion_box.curselection()
        )

        self.cust_name.delete(0, tk.END)
        self.cust_name.insert(0, selected)

        self.suggestion_box.grid_remove()

        c = get_customer_by_name(selected)

        if c:
            self.phone.delete(0, tk.END)
            self.phone.insert(0, c["phone"])

            self.address.delete(0, tk.END)
            self.address.insert(0, c.get("address", ""))

            self.phone.focus()
        
        # =================================================
        # HELPERS / LOGIC (UNCHANGED)
        # =================================================
    def refresh_items(self):
        inv = load_inventory()
        self._stock_cache = {
            name: float((data or {}).get("stock", 0) or 0)
            for name, data in inv.items()
        }
        items = sorted(inv.keys())
        self._item_values_all = items
        current = self.item_cb.get().strip()
        self.item_cb["values"] = items
        if not current or current not in items:
            self.item_cb.set("")

    def filter_items_live(self, event=None):
        if event and event.keysym in ("Up", "Down", "Left", "Right", "Return", "Escape", "Tab"):
            return
        typed = self.item_cb.get().strip().lower()
        if not typed:
            self.item_cb["values"] = self._item_values_all
            return
        matches = [name for name in self._item_values_all if typed in name.lower()]
        self.item_cb["values"] = matches if matches else self._item_values_all

    def autofill_by_phone(self, event=None):
        c = self._find_customer_by_phone(self.phone.get().strip()) or get_customer_by_phone(self.phone.get().strip())
        if c:
            self.cust_name.delete(0, tk.END)
            self.cust_name.insert(0, c["name"])
            self.address.delete(0, tk.END)
            self.address.insert(0, c.get("address", ""))

    def autofill_by_name(self, event=None):
        c = self._find_customer_by_name(self.cust_name.get().strip()) or get_customer_by_name(self.cust_name.get().strip())
        if c:
            self.phone.delete(0, tk.END)
            self.phone.insert(0, c["phone"])
            self.address.delete(0, tk.END)
            self.address.insert(0, c.get("address", ""))

    def get_selected_index(self):
        sel = self.tree.selection()
        return self.tree.index(sel[0]) if sel else None

    def _lock_quick_actions(self, ms=220):
        self._quick_action_locked = True
        if self._quick_action_job:
            try:
                self.after_cancel(self._quick_action_job)
            except Exception:
                pass
        self._quick_action_job = self.after(ms, self._unlock_quick_actions)

    def _unlock_quick_actions(self):
        self._quick_action_locked = False
        self._quick_action_job = None

    # ================= ITEMS =================
    def add_item(self):
        if self._saving_invoice or self._quick_action_locked:
            return
        self._lock_quick_actions()
        try:
            item = self.item_cb.get()
            item_type = self.type_cb.get().strip()
            qty = int(self.qty_e.get())
            rate = float(self.rate_e.get())
            gst = float(self.gst_e.get() or 0)

            current_stock = self._stock_cache.get(item)
            if current_stock is None:
                current_stock = float(get_item_stock(item))
                self._stock_cache[item] = current_stock
            if qty > current_stock:
                messagebox.showerror("Stock Error", "Insufficient stock")
                return

            total = qty * rate * (1 + gst / 100)
            row = {"item": item, "type": item_type, "qty": qty, "rate": rate, "gst": gst, "total": total}

            if self.edit_index is not None:
                self.cart[self.edit_index] = row
                self.tree.item(self.tree.get_children()[self.edit_index],
                               values=(item, item_type, qty, rate, gst, total))
                self.edit_index = None
            else:
                self.cart.append(row)
                self.tree.insert("", "end", values=(item, item_type, qty, rate, gst, total))

            self.refresh_total()
            self.qty_e.delete(0, tk.END)
            self.rate_e.delete(0, tk.END)
            self.type_cb.set("")

        except Exception:
            messagebox.showerror("Error", "Invalid item data")

    def edit_item(self):
        if self._saving_invoice or self._quick_action_locked:
            return
        self._lock_quick_actions()
        idx = self.get_selected_index()
        if idx is None:
            return
        i = self.cart[idx]
        self.item_cb.set(i["item"])
        self.type_cb.set(i.get("type", ""))
        self.qty_e.delete(0, tk.END)
        self.qty_e.insert(0, i["qty"])
        self.rate_e.delete(0, tk.END)
        self.rate_e.insert(0, i["rate"])
        self.gst_e.delete(0, tk.END)
        self.gst_e.insert(0, i["gst"])
        self.edit_index = idx

    def delete_item(self):
        if self._saving_invoice or self._quick_action_locked:
            return
        self._lock_quick_actions()
        idx = self.get_selected_index()
        if idx is None:
            return
        self.cart.pop(idx)
        self.tree.delete(self.tree.get_children()[idx])
        self.refresh_total()

    # ================= TOTALS =================
    def refresh_total(self):
        taxable = cgst = sgst = 0.0
        for i in self.cart:
            base = i["qty"] * i["rate"]
            tax = base * i["gst"] / 100
            taxable += base
            cgst += tax / 2
            sgst += tax / 2

        gross_total = taxable + cgst + sgst
        try:
            discount_percent = float(self.discount_e.get() or 0)
        except ValueError:
            discount_percent = 0.0
        discount_percent = max(0.0, min(discount_percent, 100.0))
        discount_amount = round(gross_total * (discount_percent / 100.0), 2)
        self.grand_total = max(gross_total - discount_amount, 0.0)
        self.discount_percent = discount_percent
        self.discount_amount = discount_amount
        self.gross_total = gross_total

        self.taxable_var.set(f"Taxable: ₹{taxable:.2f}")
        self.cgst_var.set(f"CGST: ₹{cgst:.2f}")
        self.sgst_var.set(f"SGST: ₹{sgst:.2f}")
        self.igst_var.set("IGST: ₹0.00")
        self.discount_var.set(f"Discount: ₹{discount_amount:.2f}")
        self.grand_total_var.set(f"Grand Total: ₹{self.grand_total:.2f}")
        self.total_var.set(f"Total: ₹{self.grand_total:.2f}")
        self.update_balance()

    def update_balance(self, event=None):
        try:
            paid = float(self.paid_e.get() or 0)
        except ValueError:
            paid = 0
        self.balance_var.set(f"Balance: ₹{max(self.grand_total - paid, 0):.2f}")

    # ================= SAVE + PRINT =================
    def save_sale(self):
        if self._saving_invoice:
            return
        if not self.cart:
            messagebox.showerror("Error", "No items added")
            return

        try:
            paid = float(self.paid_e.get() or 0)
        except ValueError:
            messagebox.showerror("Error", "Invalid paid amount")
            return
        self._saving_invoice = True
        self.generate_btn.config(state="disabled")
        self.find_btn.config(state="disabled")
        self.add_btn.config(state="disabled")
        self.edit_btn.config(state="disabled")
        self.delete_btn.config(state="disabled")
        self.update_idletasks()
        try:
            from gst import calculate_gst_items
            from invoice_pdf import generate_gst_invoice_pdf
            try:
                discount_percent = float(self.discount_e.get() or 0)
            except ValueError:
                discount_percent = 0.0
            discount_percent = max(0.0, min(discount_percent, 100.0))

            gst_items = [{
                "name": i["item"],
                "qty": i["qty"],
                "rate": i["rate"],
                "gst_percent": i["gst"]
            } for i in self.cart]

            gst_items, summary = calculate_gst_items(
                gst_items, company_state="AP", customer_state="AP"
            )
            gross_total = float(summary.get("grand_total", 0) or 0)
            discount_amount = round(gross_total * (discount_percent / 100.0), 2)
            summary["gross_total"] = round(gross_total, 2)
            summary["discount_percent"] = round(discount_percent, 2)
            summary["discount_amount"] = round(discount_amount, 2)
            summary["grand_total"] = round(max(gross_total - discount_amount, 0.0), 2)

            invoice_no = create_sale(
                customer_name=self.cust_name.get(),
                phone=self.phone.get(),
                items=gst_items,
                payment_mode=self.pay_mode.get(),
                paid_amount=paid,
                discount_percent=discount_percent
            )

            write_audit_log(
                user="admin",
                module="invoice",
                action="create",
                reference=invoice_no,
                after={
                    "customer": self.cust_name.get(),
                    "phone": self.phone.get(),
                    "total": summary.get("grand_total"),
                    "paid": paid,
                    "payment_mode": self.pay_mode.get(),
                    "items_count": len(gst_items)
                }
            )

            save_customer(
                name=self.cust_name.get(),
                phone=self.phone.get(),
                address=self.address.get()
            )
            self._customers_cache = load_customers()
            for i in gst_items:
                name = i.get("item") or i.get("name")
                sold_qty = float(i.get("qty", 0) or 0)
                if name in self._stock_cache:
                    self._stock_cache[name] = max(self._stock_cache[name] - sold_qty, 0.0)

            pdf_path = f"invoices/{invoice_no}.pdf"
            generate_gst_invoice_pdf(
                filepath=pdf_path,
                company=COMPANY,
                invoice_no=invoice_no,
                invoice_date=datetime.now().strftime("%d-%m-%Y"),
                customer={"name": self.cust_name.get(), "gstin": "", "state": "AP"},
                items=gst_items,
                summary=summary
            )

            self.last_invoice_path = os.path.abspath(pdf_path)
            self.print_btn.config(state="normal")
            os.startfile(self.last_invoice_path)
            messagebox.showinfo("Success", f"Invoice Created : {invoice_no}")
            self.reset_form_for_next_invoice()
        finally:
            self._saving_invoice = False
            self.generate_btn.config(state="normal")
            self.find_btn.config(state="normal")
            self.add_btn.config(state="normal")
            self.edit_btn.config(state="normal")
            self.delete_btn.config(state="normal")

    def print_invoice(self):
        if self._saving_invoice:
            return
        if not self.last_invoice_path:
            messagebox.showerror("Error", "Generate invoice first")
            return
        print_pdf(self.last_invoice_path)
        
    def open_item_search(self):
        if self._saving_invoice or self._quick_action_locked:
            return
        self._lock_quick_actions()
        # Open native combobox dropdown instead of popup search window.
        self.after(1, self.refresh_items)
        self.after(1, self._warm_load_customers)
        self.item_cb.focus_set()
        self.item_cb.event_generate("<Down>")

    def reset_form_for_next_invoice(self):
        self.cart.clear()
        self.edit_index = None
        self.tree.delete(*self.tree.get_children())

        self.cust_name.delete(0, tk.END)
        self.phone.delete(0, tk.END)
        self.address.delete(0, tk.END)

        self.item_cb.set("")
        self.type_cb.set("")
        self.qty_e.delete(0, tk.END)
        self.rate_e.delete(0, tk.END)
        self.gst_e.delete(0, tk.END)
        self.gst_e.insert(0, "18")

        self.pay_mode.current(0)
        self.paid_e.delete(0, tk.END)
        self.paid_e.insert(0, "0")
        if hasattr(self, "discount_e"):
            self.discount_e.delete(0, tk.END)
            self.discount_e.insert(0, "")

        self.last_invoice_path = None
        self.print_btn.config(state="disabled")
        self.refresh_total()

        
