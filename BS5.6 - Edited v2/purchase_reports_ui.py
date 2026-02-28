import os
import re
from datetime import datetime
import tkinter as tk
from tkinter import ttk, messagebox

from purchase import load_purchases
from suppliers import get_all_suppliers
from report_pdf import generate_purchase_report_pdf, generate_purchase_items_pdf
from utils_print import print_pdf
from utils import app_dir
from date_picker import open_date_picker
from ui_theme import compact_form_grid


class PurchaseReportsUI(ttk.Frame):
    def __init__(self, parent):
        super().__init__(parent)
        self.pack(fill="both", expand=True)

        self.purchases = load_purchases()
        self.filtered_rows = []
        self.filtered_purchases = []
        self.row_purchase_map = {}
        self.item_values_all = []
        self.supplier_values_all = []
        self.item_suggest_win = None
        self.item_suggest_list = None
        self.supplier_suggest_win = None
        self.supplier_suggest_list = None

        self.build_ui()

    # ==================================================
    # UI
    # ==================================================
    def build_ui(self):
        ttk.Label(
            self,
            text="Purchase Reports",
            font=("Arial", 15, "bold")
        ).pack(pady=10)

        filter_frame = ttk.LabelFrame(self, text="Filters")
        filter_frame.pack(fill="x", padx=30, pady=5)

        self.filter_var = tk.StringVar(value="date")

        ttk.Radiobutton(
            filter_frame, text="Date-wise",
            variable=self.filter_var, value="date",
            command=self.on_filter_change
        ).grid(row=0, column=0, padx=8)

        ttk.Radiobutton(
            filter_frame, text="Item-wise",
            variable=self.filter_var, value="item",
            command=self.on_filter_change
        ).grid(row=0, column=1, padx=8)

        ttk.Radiobutton(
            filter_frame, text="Supplier-wise",
            variable=self.filter_var, value="supplier",
            command=self.on_filter_change
        ).grid(row=0, column=2, padx=8)

        ttk.Label(filter_frame, text="From Date").grid(row=1, column=0, sticky="w", pady=5)
        self.from_date = ttk.Entry(filter_frame, width=15)
        self.from_date.insert(0, "DD-MM-YYYY")
        self.from_date.grid(row=1, column=1, sticky="w")
        ttk.Button(
            filter_frame,
            text="📅",
            width=5,
            command=lambda: open_date_picker(self, self.from_date),
        ).grid(row=1, column=2, sticky="w", padx=(4, 8))

        ttk.Label(filter_frame, text="To Date").grid(row=1, column=3, sticky="w")
        self.to_date = ttk.Entry(filter_frame, width=15)
        self.to_date.insert(0, "DD-MM-YYYY")
        self.to_date.grid(row=1, column=4, sticky="w")
        ttk.Button(
            filter_frame,
            text="📅",
            width=5,
            command=lambda: open_date_picker(self, self.to_date),
        ).grid(row=1, column=5, sticky="w", padx=(4, 8))

        ttk.Button(
            filter_frame, text="Load Report",
            command=self.load_report
        ).grid(row=1, column=6, padx=15)

        ttk.Label(filter_frame, text="Item").grid(row=2, column=0, sticky="w")
        self.item_cb = ttk.Combobox(filter_frame, width=30)
        self.item_cb.grid(row=2, column=1, columnspan=3, sticky="w")
        self.item_cb.bind("<KeyRelease>", self.on_item_search)
        self.item_cb.bind("<FocusOut>", self.on_item_focus_out)
        self.item_cb.bind("<Down>", self.on_item_down_key)

        ttk.Label(filter_frame, text="Supplier").grid(row=3, column=0, sticky="w")
        self.supplier_cb = ttk.Combobox(filter_frame, width=30)
        self.supplier_cb.grid(row=3, column=1, columnspan=3, sticky="w")
        self.supplier_cb.bind("<KeyRelease>", self.on_supplier_search)
        self.supplier_cb.bind("<FocusOut>", self.on_supplier_focus_out)
        self.supplier_cb.bind("<Down>", self.on_supplier_down_key)

        self.item_cb.grid_remove()
        self.supplier_cb.grid_remove()
        compact_form_grid(filter_frame)

        self.load_filter_values()

        table_wrap = ttk.Frame(self)
        table_wrap.pack(fill="both", expand=True, padx=30, pady=10)

        cols = ("invoice", "supplier", "date", "amount")
        self.tree = ttk.Treeview(
            table_wrap,
            columns=cols,
            show="headings",
            height=14
        )

        self.tree.heading("invoice", text="Invoice")
        self.tree.heading("supplier", text="Supplier")
        self.tree.heading("date", text="Date")
        self.tree.heading("amount", text="Amount")

        self.tree.column("invoice", anchor="center", width=120)
        self.tree.column("supplier", anchor="w", width=260)
        self.tree.column("date", anchor="center", width=130)
        self.tree.column("amount", anchor="e", width=140)

        self.tree.pack(fill="both", expand=True)
        self.tree.bind("<Double-1>", self.on_row_double_click)

        action_bar = ttk.Frame(self)
        action_bar.pack(pady=10)

        ttk.Button(
            action_bar, text="Export Excel",
            command=self.export_excel, width=18
        ).pack(side="left", padx=8)

        ttk.Button(
            action_bar, text="Export PDF",
            command=self.export_pdf, width=18
        ).pack(side="left", padx=8)

        ttk.Button(
            action_bar, text="Print",
            command=self.print_report, width=18
        ).pack(side="left", padx=8)

    # ==================================================
    # FILTER CHANGE
    # ==================================================
    def on_filter_change(self):
        mode = self.filter_var.get()
        self.item_cb.grid_remove()
        self.supplier_cb.grid_remove()
        self._hide_item_suggestions()
        self._hide_supplier_suggestions()

        if mode == "item":
            self.item_cb.grid()
        elif mode == "supplier":
            self.supplier_cb.grid()

    # ==================================================
    # LOAD FILTER VALUES
    # ==================================================
    def load_filter_values(self):
        items = set()
        for p in self.purchases:
            for it in p.get("items", []):
                item_name = it.get("item") or it.get("name")
                if item_name:
                    items.add(item_name)

        self.item_values_all = sorted(items)
        self.item_cb["values"] = self.item_values_all

        suppliers = get_all_suppliers()
        supplier_names = []
        for s in suppliers.values():
            if not isinstance(s, dict):
                continue
            raw_name = s.get("name", "")
            if isinstance(raw_name, dict):
                raw_name = raw_name.get("name", "")
            name = str(raw_name or "").strip()
            if name:
                supplier_names.append(name)
        self.supplier_values_all = sorted(set(supplier_names), key=str.lower)
        self.supplier_cb["values"] = self.supplier_values_all

    # ==================================================
    # LOAD REPORT
    # ==================================================
    def load_report(self):
        self.tree.delete(*self.tree.get_children())
        self.filtered_rows.clear()
        self.filtered_purchases.clear()
        self.row_purchase_map.clear()

        mode = self.filter_var.get()
        from_d = self.parse_date(self.from_date.get().strip())
        to_d = self.parse_date(self.to_date.get().strip())

        filtered_with_key = []
        for i, p in enumerate(self.purchases, start=1):
            raw_date = p.get("date", "")
            p_date = self.parse_date(raw_date)

            if from_d and (not p_date or p_date < from_d):
                continue
            if to_d and (not p_date or p_date > to_d):
                continue

            if mode == "supplier":
                if p.get("supplier_name") != self.supplier_cb.get():
                    continue

            if mode == "item":
                selected_item = self.item_cb.get()
                if selected_item:
                    found = any((it.get("item") or it.get("name")) == selected_item for it in p.get("items", []))
                    if not found:
                        continue

            invoice_no = p.get("purchase_id", "").strip() or f"PO-{i:04d}"
            amount = float(p.get("grand_total", p.get("total_amount", 0)))
            row = (
                invoice_no,
                p.get("supplier_name", p.get("supplier", "")),
                self.format_date(raw_date),
                f"{amount:.2f}",
            )
            p.setdefault("purchase_id", invoice_no)
            filtered_with_key.append((p_date or datetime.min, row, p))

        filtered_with_key.sort(key=lambda x: x[0], reverse=True)
        for _sort_date, row, p in filtered_with_key:
            self.filtered_rows.append(row)
            self.filtered_purchases.append(p)
            iid = self.tree.insert("", "end", values=row)
            self.row_purchase_map[iid] = p

        if not self.filtered_rows:
            messagebox.showinfo("Info", "No records found")

    def parse_date(self, value):
        text = str(value or "").strip()
        if not text or text in ("YYYY-MM-DD", "DD-MM-YYYY"):
            return None
        for fmt in ("%d-%m-%Y %H:%M:%S", "%Y-%m-%d %H:%M:%S", "%d-%m-%Y", "%Y-%m-%d"):
            try:
                return datetime.strptime(text, fmt)
            except Exception:
                continue
        return None

    def format_date(self, value):
        parsed = self.parse_date(value)
        if not parsed:
            return str(value or "")
        return parsed.strftime("%d-%m-%Y %H:%M:%S")

    def on_item_search(self, _event=None):
        if _event and _event.keysym in ("Up", "Down", "Left", "Right", "Return", "Escape", "Tab"):
            return

        typed = self.item_cb.get().strip().lower()
        if not typed:
            self.item_cb["values"] = self.item_values_all
            self._hide_item_suggestions()
            return
        filtered = [name for name in self.item_values_all if typed in name.lower()]
        self.item_cb["values"] = filtered
        if self.filter_var.get() != "item":
            return
        if filtered:
            self._show_item_suggestions(filtered)
        else:
            self._hide_item_suggestions()

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

        x = self.item_cb.winfo_rootx()
        y = self.item_cb.winfo_rooty() + self.item_cb.winfo_height() + 1
        w = max(self.item_cb.winfo_width(), 220)
        self.item_suggest_win.geometry(f"{w}x160+{x}+{y}")
        self.item_suggest_win.deiconify()
        self.item_suggest_win.lift()
        self.item_cb.focus_set()
        self.item_cb.icursor(tk.END)

    def _hide_item_suggestions(self):
        if self.item_suggest_win is not None and self.item_suggest_win.winfo_exists():
            self.item_suggest_win.withdraw()

    def on_item_pick_from_list(self, _event=None):
        if self.item_suggest_list is None or not self.item_suggest_list.curselection():
            return
        picked = self.item_suggest_list.get(self.item_suggest_list.curselection()[0])
        self.item_cb.set(picked)
        self._hide_item_suggestions()
        self.item_cb.focus_set()
        self.item_cb.icursor(tk.END)

    def on_item_focus_out(self, _event=None):
        self.after(120, self._hide_if_item_focus_lost)

    def _hide_if_item_focus_lost(self):
        w = self.focus_get()
        if w is self.item_cb or w is self.item_suggest_list:
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

    def on_supplier_search(self, _event=None):
        if _event and _event.keysym in ("Up", "Down", "Left", "Right", "Return", "Escape", "Tab"):
            return

        typed = self.supplier_cb.get().strip().lower()
        if not typed:
            self.supplier_cb["values"] = self.supplier_values_all
            self._hide_supplier_suggestions()
            return

        filtered = [name for name in self.supplier_values_all if typed in name.lower()]
        self.supplier_cb["values"] = filtered
        if self.filter_var.get() != "supplier":
            return
        if filtered:
            self._show_supplier_suggestions(filtered)
        else:
            self._hide_supplier_suggestions()

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
        self._hide_supplier_suggestions()
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

    # ==================================================
    # ROW DETAIL
    # ==================================================
    def on_row_double_click(self, event):
        iid = self.tree.identify_row(event.y)
        if not iid:
            return
        purchase = self.row_purchase_map.get(iid)
        if purchase is None:
            idx = self.tree.index(iid)
            if idx < 0 or idx >= len(self.filtered_purchases):
                return
            purchase = self.filtered_purchases[idx]
        self.open_purchase_items_window(purchase)

    def open_purchase_items_window(self, purchase):
        win = tk.Toplevel(self)
        invoice = purchase.get("purchase_id", "").strip() or "N/A"
        supplier = purchase.get("supplier_name", purchase.get("supplier", ""))
        date = purchase.get("date", purchase.get("created_on", ""))

        win.title(f"Purchase Items - {invoice}")
        win.geometry("760x420")
        win.transient(self.winfo_toplevel())
        win.lift()
        win.focus_force()

        ttk.Label(
            win,
            text=f"Invoice: {invoice}   Supplier: {supplier}   Date: {date}",
            font=("Arial", 11, "bold")
        ).pack(anchor="w", padx=10, pady=(10, 8))

        cols = ("item", "qty", "unit", "rate", "gst", "total")
        items = self._normalize_purchase_items(purchase)
        if not items:
            messagebox.showinfo("Purchase Items", "No item details found for this purchase.", parent=win)
            return

        tools = ttk.Frame(win)
        tools.pack(fill="x", padx=10, pady=(0, 8))
        ttk.Label(tools, text="Search Item").pack(side="left")
        search_var = tk.StringVar()
        search_entry = ttk.Entry(tools, textvariable=search_var, width=28)
        search_entry.pack(side="left", padx=(6, 12))

        shown_rows = {"rows": []}

        def export_items_excel():
            rows = shown_rows["rows"]
            if not rows:
                messagebox.showwarning("No Data", "No item rows to export.", parent=win)
                return

            report_dir = os.path.join(app_dir(), "reports")
            os.makedirs(report_dir, exist_ok=True)
            file_name = f"purchase_items_{self._safe_filename(invoice)}_{self._safe_filename(date)}.xlsx"
            file_path = os.path.join(report_dir, file_name)

            data = []
            total_amount = 0.0
            for row in rows:
                data.append({
                    "Item": row["item"],
                    "Qty": row["qty"],
                    "Unit": row["unit"],
                    "Rate": row["rate"],
                    "GST %": row["gst"],
                    "Total": row["total"],
                })
                total_amount += row["total"]

            data.append({
                "Item": "TOTAL",
                "Qty": "",
                "Unit": "",
                "Rate": "",
                "GST %": "",
                "Total": round(total_amount, 2),
            })

            import pandas as pd
            pd.DataFrame(data).to_excel(file_path, index=False)
            os.startfile(file_path)

        def export_items_pdf():
            rows = shown_rows["rows"]
            if not rows:
                messagebox.showwarning("No Data", "No item rows to export.", parent=win)
                return
            generate_purchase_items_pdf(invoice, supplier, date, rows)

        ttk.Button(tools, text="Export Excel", command=export_items_excel).pack(side="right", padx=(8, 0))
        ttk.Button(tools, text="Export PDF", command=export_items_pdf).pack(side="right")

        frame = ttk.Frame(win)
        frame.pack(fill="both", expand=True, padx=10, pady=(0, 10))
        frame.columnconfigure(0, weight=1)
        frame.rowconfigure(0, weight=1)
        tree = ttk.Treeview(frame, columns=cols, show="headings")
        tree.grid(row=0, column=0, sticky="nsew")

        headers = {
            "item": "Item",
            "qty": "Qty",
            "unit": "Unit",
            "rate": "Rate",
            "gst": "GST %",
            "total": "Total",
        }
        for c in cols:
            anchor = "w" if c in ("item", "unit") else "e"
            tree.heading(c, text=headers[c], anchor=anchor)
            width = 230 if c == "item" else 90
            tree.column(c, width=width, anchor=anchor)

        ysb = ttk.Scrollbar(frame, orient="vertical", command=tree.yview)
        ysb.grid(row=0, column=1, sticky="ns")
        tree.configure(yscrollcommand=ysb.set)

        total_var = tk.StringVar(value="Total Amount (Shown): 0.00")
        ttk.Label(
            win,
            textvariable=total_var,
            font=("Arial", 10, "bold")
        ).pack(anchor="e", padx=12, pady=(0, 10))

        def refresh_rows(*_):
            q = search_var.get().strip().lower()
            tree.delete(*tree.get_children())
            shown_rows["rows"] = []
            shown_total = 0.0

            for row in items:
                if q and q not in row["item"].lower():
                    continue

                shown_rows["rows"].append(row)
                shown_total += row["total"]
                tree.insert(
                    "",
                    "end",
                    values=(
                        row["item"],
                        f"{row['qty']:.2f}",
                        row["unit"],
                        f"{row['rate']:.2f}",
                        f"{row['gst']:.2f}",
                        f"{row['total']:.2f}",
                    )
                )

            total_var.set(f"Total Amount (Shown): {shown_total:.2f}")

        search_var.trace_add("write", refresh_rows)
        refresh_rows()
        search_entry.focus_set()

    def _safe_float(self, value):
        try:
            return float(value or 0)
        except Exception:
            return 0.0

    def _normalize_purchase_items(self, purchase):
        rows = []
        for raw in purchase.get("items", []):
            item_name = str(raw.get("item") or raw.get("name") or raw.get("product") or "").strip()
            qty = self._safe_float(raw.get("qty", raw.get("quantity", 0)))
            rate = self._safe_float(raw.get("rate", raw.get("price", raw.get("unit_price", 0))))
            gst = self._safe_float(raw.get("gst", raw.get("gst_percent", 0)))
            unit = str(raw.get("unit", "") or "")
            total = self._safe_float(raw.get("total", qty * rate * (1 + gst / 100)))
            rows.append({
                "item": item_name,
                "qty": qty,
                "unit": unit,
                "rate": rate,
                "gst": gst,
                "total": total,
            })
        return rows

    def _safe_filename(self, value):
        text = str(value or "").strip()
        if not text:
            return "NA"
        return re.sub(r'[\\/:*?"<>|]+', "_", text)

    # ==================================================
    # EXPORT / PRINT
    # ==================================================
    def export_excel(self):
        from export_excel import export_purchase_report_excel
        export_purchase_report_excel(self.filtered_rows)

    def export_pdf(self):
        generate_purchase_report_pdf(self.filtered_rows)

    def print_report(self):
        path = generate_purchase_report_pdf(self.filtered_rows)
        print_pdf(path)

