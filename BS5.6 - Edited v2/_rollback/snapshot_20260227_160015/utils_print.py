# utils_print.py
import os
import subprocess
import platform
from tkinter import messagebox


def print_pdf(pdf_path):
    pdf_path = os.path.abspath(pdf_path)

    if not os.path.exists(pdf_path):
        messagebox.showerror("Error", "PDF file not found")
        return

    try:
        if platform.system() == "Windows":
            # Open print dialog instead of silent print
            os.startfile(pdf_path)   # opens PDF viewer
        else:
            messagebox.showinfo(
                "Info",
                "Printing is supported only on Windows"
            )

    except Exception as e:
        messagebox.showerror(
            "Print Error",
            f"Unable to print PDF.\n\n{e}"
        )
