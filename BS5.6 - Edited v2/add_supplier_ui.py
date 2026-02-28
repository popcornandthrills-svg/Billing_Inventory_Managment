import tkinter as tk
from tkinter import messagebox
from suppliers import add_supplier


class AddSupplierWindow(tk.Toplevel):
    def __init__(self, parent, on_save):
        super().__init__(parent)
        self.title("Add New Supplier")
        self.geometry("360x280")
        self.on_save = on_save

        tk.Label(self, text="Supplier Name").pack(pady=5)
        self.name_entry = tk.Entry(self, width=32)
        self.name_entry.pack()

        tk.Label(self, text="Phone").pack(pady=5)
        self.phone_entry = tk.Entry(self, width=32)
        self.phone_entry.pack()

        tk.Label(self, text="Address").pack(pady=5)
        self.addr_entry = tk.Entry(self, width=32)
        self.addr_entry.pack()

        tk.Label(self, text="GST Number").pack(pady=5)
        self.gst_entry = tk.Entry(self, width=32)
        self.gst_entry.pack()

        tk.Button(self, text="Save Supplier", command=self.save)\
            .pack(pady=12)

    def save(self):
        name = self.name_entry.get().strip()
        phone = self.phone_entry.get().strip()
        addr = self.addr_entry.get().strip()
        gst = self.gst_entry.get().strip()

        if not name:
            messagebox.showerror("Error", "Supplier name required")
            return

        supplier = add_supplier(
            name=name,
            phone=phone,
            address=addr,
            gst=gst
        )

        # callback to purchase_entry
        self.on_save(supplier)
        self.destroy()
