import tkinter as tk
from tkinter import ttk


def setup_style(root: tk.Tk) -> None:
    style = ttk.Style(root)
    try:
        style.theme_use("clam")
    except Exception:
        pass

    bg = "#f4f6f8"
    panel = "#ffffff"
    accent = "#1f5aa6"
    text = "#1f2937"
    muted = "#6b7280"
    border = "#d1d5db"

    root.configure(bg=bg)

    style.configure(".", font=("Segoe UI", 10))
    style.configure("TFrame", background=bg)
    style.configure("Card.TFrame", background=panel)
    style.configure("TLabelframe", background=panel, bordercolor=border, relief="solid")
    style.configure("TLabelframe.Label", background=panel, foreground=text, font=("Segoe UI", 10, "bold"))
    style.configure("TLabel", background=bg, foreground=text)
    style.configure("Card.TLabel", background=panel, foreground=text)
    style.configure("Header.TLabel", background=bg, foreground=accent, font=("Segoe UI Semibold", 20))
    style.configure("Subtle.TLabel", background=bg, foreground=muted, font=("Segoe UI", 10))
    style.configure("Section.TLabel", background=bg, foreground=text, font=("Segoe UI Semibold", 12))

    style.configure("TButton", padding=(10, 6), font=("Segoe UI Semibold", 9))
    style.configure("Nav.TButton", padding=(10, 7), anchor="w")
    style.configure("Danger.TButton", padding=(10, 6))
    style.map(
        "TButton",
        background=[("active", "#e5e7eb")],
    )
    style.map(
        "Danger.TButton",
        background=[("active", "#fee2e2")],
        foreground=[("active", "#991b1b")],
    )

    style.configure("Treeview", rowheight=28, fieldbackground=panel, background=panel)
    style.configure("Treeview.Heading", font=("Segoe UI Semibold", 9), padding=(8, 6))
    style.map("Treeview", background=[("selected", "#dbeafe")], foreground=[("selected", "#111827")])

    style.configure("TEntry", padding=(6, 4))
    style.configure("TCombobox", padding=(6, 4))
