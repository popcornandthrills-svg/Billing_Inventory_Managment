import tkinter as tk
from tkinter import ttk


def setup_style(root: tk.Tk) -> None:
    style = ttk.Style(root)
    try:
        style.theme_use("clam")
    except Exception:
        pass

    bg = "#f4f7fb"
    panel = "#ffffff"
    accent = "#123f73"
    accent_soft = "#eaf1fd"
    accent_active = "#d4e4ff"
    text = "#10243d"
    muted = "#5f7087"
    border = "#c7d3e3"
    danger = "#b42318"

    root.configure(bg=bg)

    style.configure(".", font=("Segoe UI", 10), background=bg, foreground=text)
    style.configure("TFrame", background=bg)
    style.configure("Card.TFrame", background=panel)
    style.configure("TLabelframe", background=panel, bordercolor=border, relief="solid", padding=10)
    style.configure("TLabelframe.Label", background=panel, foreground=accent, font=("Segoe UI Semibold", 10))
    style.configure("TLabel", background=bg, foreground=text)
    style.configure("Card.TLabel", background=panel, foreground=text)
    style.configure("Header.TLabel", background=bg, foreground=accent, font=("Segoe UI Semibold", 23))
    style.configure("Subtle.TLabel", background=bg, foreground=muted, font=("Segoe UI", 10))
    style.configure("Section.TLabel", background=bg, foreground=accent, font=("Segoe UI Semibold", 12))
    style.configure("MenuHeader.TLabel", background=bg, foreground=accent, font=("Segoe UI Semibold", 13))

    style.configure(
        "TButton",
        padding=(11, 8),
        font=("Segoe UI Semibold", 9),
        background=panel,
        foreground=text,
        bordercolor=border,
        relief="solid"
    )
    style.configure(
        "Nav.TButton",
        padding=(12, 9),
        anchor="w",
        background=accent_soft,
        foreground=accent,
        bordercolor="#b6c7ea"
    )
    style.configure(
        "ActiveNav.TButton",
        padding=(12, 9),
        anchor="w",
        background=accent_active,
        foreground="#0d2f57",
        bordercolor="#7ea0d8"
    )
    style.configure(
        "Danger.TButton",
        padding=(10, 7),
        background="#fdecea",
        foreground=danger,
        bordercolor="#f5c2bf"
    )
    style.map(
        "TButton",
        background=[("active", "#dce8fb"), ("pressed", "#c9dbf8")],
        foreground=[("active", accent)],
    )
    style.map(
        "Nav.TButton",
        background=[("active", "#d5e4fb"), ("pressed", "#c8dbf7")],
        foreground=[("active", "#143d74")]
    )
    style.map(
        "ActiveNav.TButton",
        background=[("active", "#c9ddff"), ("pressed", "#bed4fa")],
        foreground=[("active", "#0d2f57")]
    )
    style.map(
        "Danger.TButton",
        background=[("active", "#fbd5d1"), ("pressed", "#f7c0bb")],
        foreground=[("active", "#8f1d14")],
    )

    style.configure(
        "Treeview",
        rowheight=30,
        fieldbackground=panel,
        background=panel,
        bordercolor=border,
        relief="flat"
    )
    style.configure(
        "Treeview.Heading",
        font=("Segoe UI Semibold", 9),
        padding=(8, 8),
        background=accent_soft,
        foreground=accent,
        bordercolor=border
    )
    style.map("Treeview", background=[("selected", "#dbeafe")], foreground=[("selected", "#111827")])
    style.map("Treeview.Heading", background=[("active", "#d5e4fb")])

    style.configure("TEntry", padding=(8, 6), fieldbackground=panel, bordercolor=border)
    style.configure("TCombobox", padding=(8, 6), fieldbackground=panel, bordercolor=border)
    style.configure("TCheckbutton", background=bg, foreground=text, font=("Segoe UI", 10))
    style.configure("TRadiobutton", background=bg, foreground=text, font=("Segoe UI", 10))

    # If notebook tabs are used in any view, keep selected tab visibly highlighted.
    style.configure("TNotebook", background=bg, borderwidth=0)
    style.configure("TNotebook.Tab", padding=(14, 7), font=("Segoe UI Semibold", 10), background=accent_soft, foreground=accent)
    style.map(
        "TNotebook.Tab",
        background=[("selected", accent_active), ("active", "#dce9ff")],
        foreground=[("selected", "#0d2f57"), ("active", "#123f73")]
    )


def compact_form_grid(frame: tk.Widget) -> None:
    """Reduce horizontal gaps so labels and input widgets stay side-by-side."""
    for widget in frame.grid_slaves():
        try:
            widget_class = widget.winfo_class()
            if widget_class in ("TLabel", "Label"):
                widget.grid_configure(sticky="w", padx=(4, 2), pady=3)
            elif widget_class in ("TEntry", "Entry", "TCombobox", "Combobox", "TSpinbox", "Spinbox"):
                widget.grid_configure(sticky="w", padx=(0, 8), pady=3)
        except Exception:
            continue
