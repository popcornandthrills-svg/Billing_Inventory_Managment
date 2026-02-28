import calendar
from datetime import date, datetime
import tkinter as tk
from tkinter import ttk


_OPEN_DROPDOWNS = {}


class DatePickerDropdown(ttk.Frame):
    def __init__(self, parent, target_entry):
        super().__init__(parent, style="Card.TFrame", borderwidth=1, relief="solid", padding=6)
        self.parent = parent
        self.target_entry = target_entry
        self.host = parent.winfo_toplevel()
        self.current = self._get_initial_date().replace(day=1)
        self.header_var = tk.StringVar()
        self._bind_id = None

        nav = ttk.Frame(self)
        nav.pack(fill="x", pady=(0, 6))
        ttk.Button(nav, text="<", width=3, command=self.prev_month).pack(side="left")
        ttk.Label(nav, textvariable=self.header_var, font=("Segoe UI", 10, "bold")).pack(side="left", expand=True)
        ttk.Button(nav, text=">", width=3, command=self.next_month).pack(side="right")

        self.days_frame = ttk.Frame(self)
        self.days_frame.pack(fill="both", expand=True)
        ttk.Button(self, text="Today", command=self.select_today).pack(fill="x", pady=(6, 0))

        self.render_calendar()
        self._place_below_entry()
        self._bind_outside_click()

    def _get_initial_date(self):
        raw = self.target_entry.get().strip()
        try:
            if raw and raw not in ("YYYY-MM-DD", "DD-MM-YYYY"):
                for fmt in ("%d-%m-%Y", "%Y-%m-%d"):
                    try:
                        return datetime.strptime(raw, fmt).date()
                    except Exception:
                        continue
        except Exception:
            pass
        return date.today()

    def _place_below_entry(self):
        self.parent.update_idletasks()
        x = self.target_entry.winfo_rootx() - self.parent.winfo_rootx()
        y = self.target_entry.winfo_rooty() - self.parent.winfo_rooty() + self.target_entry.winfo_height() + 2
        self.place(x=x, y=y)
        self.lift()

    def _bind_outside_click(self):
        self._bind_id = self.host.bind("<Button-1>", self._on_host_click, add="+")

    def _on_host_click(self, event):
        widget = event.widget
        if widget is self.target_entry:
            return
        if self._is_child(widget):
            return
        self.close()

    def _is_child(self, widget):
        cur = widget
        while cur is not None:
            if cur is self:
                return True
            cur = getattr(cur, "master", None)
        return False

    def render_calendar(self):
        for w in self.days_frame.winfo_children():
            w.destroy()

        self.header_var.set(self.current.strftime("%B %Y"))
        week_days = ["Mo", "Tu", "We", "Th", "Fr", "Sa", "Su"]
        for col, name in enumerate(week_days):
            ttk.Label(self.days_frame, text=name, anchor="center").grid(row=0, column=col, padx=2, pady=2)

        month_grid = calendar.monthcalendar(self.current.year, self.current.month)
        for r, week in enumerate(month_grid, start=1):
            for c, day in enumerate(week):
                if day == 0:
                    ttk.Label(self.days_frame, text=" ").grid(row=r, column=c, padx=2, pady=2)
                    continue
                ttk.Button(
                    self.days_frame,
                    text=str(day),
                    width=3,
                    command=lambda d=day: self.select_day(d),
                ).grid(row=r, column=c, padx=1, pady=1)

    def prev_month(self):
        y = self.current.year
        m = self.current.month - 1
        if m == 0:
            m = 12
            y -= 1
        self.current = self.current.replace(year=y, month=m, day=1)
        self.render_calendar()

    def next_month(self):
        y = self.current.year
        m = self.current.month + 1
        if m == 13:
            m = 1
            y += 1
        self.current = self.current.replace(year=y, month=m, day=1)
        self.render_calendar()

    def _set_date(self, selected_date):
        self.target_entry.delete(0, tk.END)
        self.target_entry.insert(0, selected_date.strftime("%d-%m-%Y"))

    def select_day(self, day):
        self._set_date(self.current.replace(day=day))
        self.close()

    def select_today(self):
        self._set_date(date.today())
        self.close()

    def close(self):
        if self._bind_id:
            try:
                self.host.unbind("<Button-1>", self._bind_id)
            except Exception:
                pass
        if _OPEN_DROPDOWNS.get(self.target_entry) is self:
            _OPEN_DROPDOWNS.pop(self.target_entry, None)
        if self.winfo_exists():
            self.destroy()


def open_date_picker(parent, target_entry):
    existing = _OPEN_DROPDOWNS.get(target_entry)
    if existing and existing.winfo_exists():
        existing.close()
        return

    for _entry, dropdown in list(_OPEN_DROPDOWNS.items()):
        if dropdown and dropdown.winfo_exists():
            dropdown.close()

    dropdown = DatePickerDropdown(parent, target_entry)
    _OPEN_DROPDOWNS[target_entry] = dropdown
