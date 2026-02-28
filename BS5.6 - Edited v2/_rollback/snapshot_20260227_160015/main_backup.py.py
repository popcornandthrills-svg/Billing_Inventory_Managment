import tkinter as tk
from tkinter import ttk, messagebox
from purchase_entry import PurchaseEntry
from sales_menu_ui import SalesMenuUI
from backup_restore import backup_data, restore_data

ADMIN_PASSWORD = "admin123"
USER_PASSWORD = "user123"


class App(tk.Tk):
    def __init__(self):
        super().__init__()

        self.title("Billing & Inventory Management")
        self.geometry("800x500")
        self.resizable(False, False)

        self.role = None  # admin / user

        self.show_login()

    # ================= LOGIN SCREEN =================
    def show_login(self):
        self.clear_window()

        tk.Label(
            self,
            text="Billing Software",
            font=("Arial", 18, "bold")
        ).pack(pady=20)

        tk.Label(
            self,
            text="Enter Password",
            font=("Arial", 12)
        ).pack(pady=5)

        self.pwd_entry = tk.Entry(self, show="*", width=25)
        self.pwd_entry.pack(pady=5)
        self.pwd_entry.focus()

        ttk.Button(
            self,
            text="Login",
            width=15,
            command=self.check_password
        ).pack(pady=15)

    def check_password(self):
        pwd = self.pwd_entry.get().strip()

        if pwd == ADMIN_PASSWORD:
            self.role = "admin"
            self.show_dashboard()
        elif pwd == USER_PASSWORD:
            self.role = "user"
            self.show_dashboard()
        else:
            messagebox.showerror("Access Denied", "Invalid password")

    # ================= DASHBOARD =================
    def show_dashboard(self):
        self.clear_window()

        tk.Label(
            self,
            text="Select Operation",
            font=("Arial", 16, "bold")
        ).pack(pady=20)

        main_frame = tk.Frame(self)
        main_frame.pack(pady=15)

        # -------- SALES (both roles) --------
        ttk.Button(
            main_frame,
            text="Sales",
            width=20,
            command=self.open_sales
        ).pack(pady=5)

        # -------- ADMIN ONLY --------
        if self.role == "admin":
            ttk.Button(
                main_frame,
                text="Purchase",
                width=20,
                command=self.open_purchase
            ).pack(pady=5)

            util = tk.Frame(self)
            util.pack(pady=10)

            ttk.Button(
                util,
                text="Backup Data",
                width=18,
                command=backup_data
            ).pack(side="left", padx=10)

            ttk.Button(
                util,
                text="Restore Data",
                width=18,
                command=restore_data
            ).pack(side="left", padx=10)

        ttk.Button(
            self,
            text="Logout",
            width=10,
            command=self.show_login
        ).pack(side="bottom", pady=15)

    # ================= HELPERS =================
    def clear_window(self):
        for w in self.winfo_children():
            w.destroy()

    def open_purchase(self):
        PurchaseEntry(self)

    def open_sales(self):
        SalesMenuUI(self)


if __name__ == "__main__":
    App().mainloop()
