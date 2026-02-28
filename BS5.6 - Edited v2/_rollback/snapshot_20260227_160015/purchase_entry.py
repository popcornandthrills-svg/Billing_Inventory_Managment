# purchase_entry.py
import tkinter as tk
from tkinter import ttk, messagebox

from audit_log import write_audit_log
from suppliers import get_all_suppliers, add_supplier
from inventory import add_stock, get_available_items
from purchase import create_purchase

UNIT_OPTIONS = ["Nos", "Kg", "Litre", "Metre"]


class PurchaseEntry(ttk.Frame):
    def __init__(self, parent):
        super().__init__(parent)
        self.pack(fill="both", expand=True)

        self.items = []
        self.edit_index = None
        self.suppliers = get_all_suppliers()
        self.supplier_values_all = self._collect_supplier_names()
        self.supplier_suggest_win = None
        self.supplier_suggest_list = None
        self.item_values_all = sorted(set(get_available_items()), key=str.lower)
        self.item_suggest_win = None
        self.item_suggest_list = None

        # ================= LAYOUT CONFIG =================
        self.columnconfigure(0, weight=1)
        self.rowconfigure(1, weight=1)

        # ================= SUPPLIER DETAILS =================
        sup = ttk.LabelFrame(self, text="Supplier Details")
        sup.grid(row=0, column=0, sticky="ew", padx=10, pady=6)

        ttk.Label(sup, text="Supplier").grid(row=0, column=0, sticky="w")

        self.supplier_cb = ttk.Combobox(
            sup,
            values=self.supplier_values_all,
            width=30
        )
        self.supplier_cb.grid(row=0, column=1, padx=5)
        
        self.supplier_cb.bind("<KeyRelease>", self.filter_suppliers)
        self.supplier_cb.bind("<<ComboboxSelected>>", self.autofill_supplier)


        ttk.Label(sup, text="Payment Mode").grid(row=0, column=2, padx=(20, 5))
        self.pay_mode_var = tk.StringVar(value="Cash")
        self.pay_mode = ttk.Combobox(
            sup, values=["Cash", "UPI", "Bank", "Credit", "Other"],
            width=18, state="readonly", textvariable=self.pay_mode_var
        )
        self.pay_mode.grid(row=0, column=3)

        ttk.Label(sup, text="Phone").grid(row=1, column=0, sticky="w")
        self.sup_phone = ttk.Entry(sup, width=25)
        self.sup_phone.grid(row=1, column=1, padx=5)

        ttk.Label(sup, text="Address").grid(row=2, column=0, sticky="w")
        self.sup_address = ttk.Entry(sup, width=50)
        self.sup_address.grid(row=2, column=1, columnspan=3, sticky="w", padx=5)

        # ================= TABLE CONTAINER =================
        table_container = ttk.Frame(self)
        table_container.grid(row=1, column=0, sticky="nsew", padx=10)
        table_container.columnconfigure(0, weight=1)
        table_container.rowconfigure(1, weight=1)
        # ---------- EDIT / DELETE BUTTONS ----------
        btn_frame = ttk.Frame(table_container)
        btn_frame.grid(row=2, column=0, pady=5)

        ttk.Button(btn_frame, text="Edit Selected",
                command=self.edit_item).pack(side="left", padx=5)

        ttk.Button(btn_frame, text="Delete Selected",
                command=self.delete_item).pack(side="left", padx=5)

        # ---------- ADD ITEM ROW ----------
        add = ttk.LabelFrame(table_container, text="Purchased Items")
        add.grid(row=0, column=0, sticky="ew", pady=5)
        
        ttk.Label(add, text="Item").grid(row=0, column=0)

        self.item_entry = ttk.Combobox(add, width=25, values=self.item_values_all)
        self.item_entry.grid(row=0, column=1, padx=5)
        self.item_entry.bind("<KeyRelease>", self.filter_items_live)

        # 🔍 SEARCH BUTTON
        ttk.Button(
            add,
            text="Find",
            width=6,
            command=self.open_item_search
        ).grid(row=0, column=2, padx=3)

        ttk.Label(add, text="HSN").grid(row=0, column=3)
        self.hsn_entry = ttk.Entry(add, width=12)
        self.hsn_entry.grid(row=0, column=4, padx=4)

        ttk.Label(add, text="Qty").grid(row=0, column=5)
        self.qty_entry = ttk.Entry(add, width=8)
        self.qty_entry.grid(row=0, column=6)

        ttk.Label(add, text="Unit").grid(row=0, column=7)
        self.unit_cb = ttk.Combobox(add, values=UNIT_OPTIONS, width=10)
        self.unit_cb.set("Nos")
        self.unit_cb.grid(row=0, column=8)

        ttk.Label(add, text="Rate").grid(row=0, column=9)
        self.rate_entry = ttk.Entry(add, width=10)
        self.rate_entry.grid(row=0, column=10)

        ttk.Label(add, text="GST %").grid(row=0, column=11)
        self.gst_entry = ttk.Entry(add, width=6)
        self.gst_entry.insert(0, "18")
        self.gst_entry.grid(row=0, column=12)

        ttk.Button(
            add,
            text="Add / Update",
            command=self.add_item
        ).grid(row=0, column=13, padx=8)
        
        
        """
        ttk.Label(add, text="Item").grid(row=0, column=0)
        self.item_entry = ttk.Entry(add, width=25)
        self.item_entry.grid(row=0, column=1, padx=5)

        ttk.Label(add, text="Qty").grid(row=0, column=2)
        self.qty_entry = ttk.Entry(add, width=8)
        self.qty_entry.grid(row=0, column=3)

        ttk.Label(add, text="Unit").grid(row=0, column=4)
        self.unit_cb = ttk.Combobox(add, values=UNIT_OPTIONS, width=10)
        self.unit_cb.set("Nos")
        self.unit_cb.grid(row=0, column=5)

        ttk.Label(add, text="Rate").grid(row=0, column=6)
        self.rate_entry = ttk.Entry(add, width=10)
        self.rate_entry.grid(row=0, column=7)

        ttk.Label(add, text="GST %").grid(row=0, column=8)
        self.gst_entry = ttk.Entry(add, width=6)
        self.gst_entry.insert(0, "0")
        self.gst_entry.grid(row=0, column=9)

        ttk.Button(add, text="Add", command=self.add_item)\
            .grid(row=0, column=10, padx=8)
        """

        # ---------- TREEVIEW ----------
        table_frame = ttk.Frame(table_container)
        table_frame.grid(row=1, column=0, sticky="nsew")
        table_frame.columnconfigure(0, weight=1)
        table_frame.rowconfigure(0, weight=1)

        cols = ("Item", "HSN", "Qty", "Unit", "Rate", "GST", "Total")
        self.tree = ttk.Treeview(table_frame, columns=cols, show="headings")

        for c in cols:
            self.tree.heading(c, text=c)
            self.tree.column(c, anchor="center", width=120)

        vsb = ttk.Scrollbar(table_frame, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=vsb.set)

        self.tree.grid(row=0, column=0, sticky="nsew")
        vsb.grid(row=0, column=1, sticky="ns")
        
        
        # ================= SUMMARY =================
        summary = ttk.LabelFrame(self, text="Summary")
        summary.grid(row=2, column=0, sticky="ew", padx=10, pady=6)

        self.total_var = tk.StringVar(value="0.00")
        self.balance_var = tk.StringVar(value="0.00")

        ttk.Label(summary, text="Total").grid(row=0, column=0)
        ttk.Label(summary, textvariable=self.total_var).grid(row=0, column=1)

        ttk.Label(summary, text="Paid").grid(row=1, column=0)
        self.paid_entry = ttk.Entry(summary, width=15)
        self.paid_entry.insert(0, "0")
        self.paid_entry.grid(row=1, column=1)
        self.paid_entry.bind("<KeyRelease>", lambda e: self.update_summary())

        ttk.Label(summary, text="Payment Type").grid(row=1, column=2, padx=(20, 5))
        self.pay_type_summary = ttk.Combobox(
            summary,
            values=["Cash", "UPI", "Bank", "Credit", "Other"],
            width=15,
            state="readonly",
            textvariable=self.pay_mode_var,
        )
        self.pay_type_summary.grid(row=1, column=3)

        ttk.Label(summary, text="Balance").grid(row=2, column=0)
        ttk.Label(summary, textvariable=self.balance_var,
                  foreground="red").grid(row=2, column=1)

        ttk.Button(self, text="Save Purchase",
                   command=self.save_purchase)\
            .grid(row=3, column=0, pady=10)

    # ================= ADD ITEM =================
    
    def add_item(self):
        item = self.item_entry.get().strip()
        hsn = self.hsn_entry.get().strip()
        if not item:
            messagebox.showwarning("Error", "Item required")
            return

        try:
            qty = float(self.qty_entry.get())
            rate = float(self.rate_entry.get())
            gst = float(self.gst_entry.get())
        except ValueError:
            messagebox.showerror("Error", "Invalid numbers")
            return

        total = round(qty * rate * (1 + gst / 100), 2)

        unit = self.unit_cb.get()

        if self.edit_index is not None:
            # UPDATE MODE
            self.items[self.edit_index] = {
                "item": item,
                "hsn": hsn,
                "qty": qty,
                "unit": unit,
                "rate": rate,
                "gst": gst,
                "total": total
            }

            iid = self.tree.get_children()[self.edit_index]
            self.tree.item(iid, values=(item, hsn, qty, unit, rate, gst, total))

            self.edit_index = None
        else:
            # ADD MODE
            self.items.append({
                "item": item,
                "hsn": hsn,
                "qty": qty,
                "unit": unit,
                "rate": rate,
                "gst": gst,
                "total": total
            })

            self.tree.insert("", "end",
                         values=(item, hsn, qty, unit, rate, gst, total))

        self.update_summary()

        # Clear fields after add/update
        self.item_entry.delete(0, tk.END)
        self.hsn_entry.delete(0, tk.END)
        self.qty_entry.delete(0, tk.END)
        self.rate_entry.delete(0, tk.END)
        self.gst_entry.delete(0, tk.END)
        self.gst_entry.insert(0, "18")
        self.unit_cb.set("Nos")
        self._hide_item_suggestions()
        
                    
    def filter_suppliers(self, event=None):
        if event and event.keysym in ("Up", "Down", "Left", "Right", "Return", "Escape", "Tab"):
            return

        typed = self.supplier_cb.get().strip().lower()

        if not typed:
            self.supplier_cb["values"] = self.supplier_values_all
            return

        matches = [n for n in self.supplier_values_all if typed in n.lower()]
        self.supplier_cb["values"] = matches if matches else self.supplier_values_all
        if matches:
            self.supplier_cb.event_generate("<Down>")

    def autofill_supplier(self, event=None):
        name = self.supplier_cb.get().strip().lower()

        for s in self.suppliers.values():
            if not isinstance(s, dict):
                continue
            raw_name = s.get("name", "")
            if isinstance(raw_name, dict):
                raw_name = raw_name.get("name", "")
            if str(raw_name).strip().lower() == name:
                self.sup_phone.delete(0, tk.END)
                self.sup_phone.insert(0, s.get("phone", ""))

                self.sup_address.delete(0, tk.END)
                self.sup_address.insert(0, s.get("address", ""))
                break 
        return

    def _collect_supplier_names(self):
        names = []
        for s in self.suppliers.values():
            if not isinstance(s, dict):
                continue
            raw_name = s.get("name", "")
            if isinstance(raw_name, dict):
                raw_name = raw_name.get("name", "")
            name = str(raw_name or "").strip()
            if name:
                names.append(name)
        return sorted(set(names), key=str.lower)

    def _show_supplier_suggestions(self, values):
        if not values:
            self._hide_supplier_suggestions()
            return

        if self.supplier_suggest_win is None or not self.supplier_suggest_win.winfo_exists():
            self.supplier_suggest_win = tk.Toplevel(self)
            self.supplier_suggest_win.overrideredirect(True)
            self.supplier_suggest_win.attributes("-topmost", True)
            self.supplier_suggest_list = tk.Listbox(self.supplier_suggest_win, height=7, activestyle="none")
            self.supplier_suggest_list.pack(fill="both", expand=True)
            self.supplier_suggest_list.bind("<ButtonRelease-1>", self.on_supplier_pick_from_list)
            self.supplier_suggest_list.bind("<Return>", self.on_supplier_pick_from_list)

        self.supplier_suggest_list.delete(0, tk.END)
        for v in values:
            self.supplier_suggest_list.insert(tk.END, v)

        x = self.supplier_cb.winfo_rootx()
        y = self.supplier_cb.winfo_rooty() + self.supplier_cb.winfo_height() + 1
        w = max(self.supplier_cb.winfo_width(), 220)
        self.supplier_suggest_win.geometry(f"{w}x160+{x}+{y}")
        self.supplier_suggest_win.deiconify()
        self.supplier_suggest_win.lift()
        self.supplier_cb.focus_set()
        self.supplier_cb.icursor(tk.END)

    def _hide_supplier_suggestions(self):
        if self.supplier_suggest_win is not None and self.supplier_suggest_win.winfo_exists():
            self.supplier_suggest_win.withdraw()

    def on_supplier_pick_from_list(self, _event=None):
        if self.supplier_suggest_list is None or not self.supplier_suggest_list.curselection():
            return
        picked = self.supplier_suggest_list.get(self.supplier_suggest_list.curselection()[0])
        self.supplier_cb.set(picked)
        self.autofill_supplier()
        self.supplier_cb.focus_set()
        self.supplier_cb.icursor(tk.END)

    def on_supplier_focus_out(self, _event=None):
        self.after(120, self._hide_if_supplier_focus_lost)

    def _hide_if_supplier_focus_lost(self):
        w = self.focus_get()
        if w is self.supplier_cb or w is self.supplier_suggest_list:
            return
        self._hide_supplier_suggestions()

    def on_supplier_down_key(self, _event=None):
        if self.supplier_suggest_list is None:
            return
        if self.supplier_suggest_win is None or not self.supplier_suggest_win.winfo_exists():
            return
        if str(self.supplier_suggest_win.state()) != "normal":
            return
        if self.supplier_suggest_list.size() <= 0:
            return
        self.supplier_suggest_list.focus_set()
        self.supplier_suggest_list.selection_clear(0, tk.END)
        self.supplier_suggest_list.selection_set(0)
        self.supplier_suggest_list.activate(0)
        return "break"

    def filter_items_live(self, event=None):
        if event and event.keysym in ("Up", "Down", "Left", "Right", "Return", "Escape", "Tab"):
            return

        typed = self.item_entry.get().strip().lower()
        if not typed:
            self.item_entry.configure(values=self.item_values_all)
            return

        matches = [n for n in self.item_values_all if typed in n.lower()]
        self.item_entry.configure(values=matches if matches else self.item_values_all)
        if matches:
            self.item_entry.event_generate("<Down>")

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

        x = self.item_entry.winfo_rootx()
        y = self.item_entry.winfo_rooty() + self.item_entry.winfo_height() + 1
        w = max(self.item_entry.winfo_width(), 220)
        self.item_suggest_win.geometry(f"{w}x160+{x}+{y}")
        self.item_suggest_win.deiconify()
        self.item_suggest_win.lift()
        self.item_entry.focus_set()
        self.item_entry.icursor(tk.END)

    def _hide_item_suggestions(self):
        if self.item_suggest_win is not None and self.item_suggest_win.winfo_exists():
            self.item_suggest_win.withdraw()

    def on_item_pick_from_list(self, _event=None):
        if self.item_suggest_list is None or not self.item_suggest_list.curselection():
            return
        picked = self.item_suggest_list.get(self.item_suggest_list.curselection()[0])
        self.item_entry.delete(0, tk.END)
        self.item_entry.insert(0, picked)
        return
        self.item_entry.focus_set()
        self.item_entry.icursor(tk.END)

    def on_item_focus_out(self, _event=None):
        self.after(120, self._hide_if_item_focus_lost)

    def _hide_if_item_focus_lost(self):
        w = self.focus_get()
        if w is self.item_entry or w is self.item_suggest_list:
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
        
        
    def edit_item(self):
        selected = self.tree.selection()
        if not selected:
            messagebox.showwarning("Select", "Select a row to edit")
            return

        item_index = self.tree.index(selected[0])
        item_data = self.items[item_index]

        self.item_entry.delete(0, tk.END)
        self.item_entry.insert(0, item_data["item"])

        self.hsn_entry.delete(0, tk.END)
        self.hsn_entry.insert(0, item_data.get("hsn", ""))

        self.qty_entry.delete(0, tk.END)
        self.qty_entry.insert(0, item_data["qty"])

        self.unit_cb.set(item_data["unit"])

        self.rate_entry.delete(0, tk.END)
        self.rate_entry.insert(0, item_data["rate"])

        self.gst_entry.delete(0, tk.END)
        self.gst_entry.insert(0, item_data["gst"])

        self.edit_index = item_index


    def delete_item(self):
        selected = self.tree.selection()
        if not selected:
            messagebox.showwarning("Select", "Select a row to delete")
            return

        item_index = self.tree.index(selected[0])

        self.tree.delete(selected[0])
        self.items.pop(item_index)

        self.update_summary()

    # ================= UPDATE SUMMARY =================
    def update_summary(self):
        total = sum(i["total"] for i in self.items)
        self.total_var.set(f"{total:.2f}")

        try:
            paid = float(self.paid_entry.get())
        except:
            paid = 0

        self.balance_var.set(f"{max(total - paid, 0):.2f}")

    # ================= SAVE PURCHASE =================
    def save_purchase(self):
        if not self.items:
            messagebox.showerror("Error", "No items added")
            return

        supplier_name = self.supplier_cb.get().strip()
        if not supplier_name:
            messagebox.showerror("Error", "Supplier name required")
            return

        suppliers = get_all_suppliers()
        supplier_id = None

        for sid, s in suppliers.items():
            if str(s.get("name", "")).lower() == supplier_name.lower():
                supplier_id = sid
                break

        if not supplier_id:
            add_supplier(
                supplier_name,
                self.sup_phone.get().strip(),
                self.sup_address.get().strip()
            )
            suppliers = get_all_suppliers()
            for sid, s in suppliers.items():
                if str(s.get("name", "")).lower() == supplier_name.lower():
                    supplier_id = sid
                    break

        try:
            paid = float(self.paid_entry.get() or 0)
        except ValueError:
            messagebox.showerror("Error", "Invalid paid amount")
            return

        record = create_purchase(
            supplier_id=supplier_id,
            supplier_name=supplier_name,
            items=self.items,
            payment_type=self.pay_mode_var.get().strip() or "Cash",
            paid_amount=paid
        )

        for i in self.items:
            add_stock(
                item_name=i["item"],
                qty=i["qty"],
                rate=i["rate"]
            )

        write_audit_log(
            user="admin",
            module="purchase",
            action="create",
            reference=record["purchase_id"]
        )

        messagebox.showinfo("Saved", "Purchase saved successfully")
        self.reset_form_for_next_purchase()

    def reset_form_for_next_purchase(self):
        self.items.clear()
        self.edit_index = None
        self.tree.delete(*self.tree.get_children())

        self.item_entry.delete(0, tk.END)
        self.hsn_entry.delete(0, tk.END)
        self.qty_entry.delete(0, tk.END)
        self.rate_entry.delete(0, tk.END)
        self.gst_entry.delete(0, tk.END)
        self.gst_entry.insert(0, "18")
        self.unit_cb.set("Nos")
        self.item_entry.configure(values=self.item_values_all)

        self.paid_entry.delete(0, tk.END)
        self.paid_entry.insert(0, "0")
        self.pay_mode_var.set("Cash")
        self.total_var.set("0.00")
        self.balance_var.set("0.00")

        self.supplier_cb.delete(0, tk.END)
        self.sup_phone.delete(0, tk.END)
        self.sup_address.delete(0, tk.END)
        self.supplier_cb["values"] = self.supplier_values_all
        
    def open_item_search(self):
        # Open native combobox dropdown instead of popup search window.
        self.item_values_all = sorted(set(get_available_items()), key=str.lower)
        self.item_entry.configure(values=self.item_values_all)
        self.item_entry.focus_set()
        self.item_entry.event_generate("<Down>")


