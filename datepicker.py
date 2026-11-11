"""Service date box: shows the date and opens a small month calendar to pick another one.

Plain Tk (no extra package to install or bundle). Weeks start on Sunday and Sundays are marked,
since the service date is almost always a Sunday.
"""
import calendar
import datetime as dt
import tkinter as tk
from tkinter import ttk

from churchyear import default_service_date

SUNDAY = 6  # date.weekday()
DAY_NAMES = ("Su", "Mo", "Tu", "We", "Th", "Fr", "Sa")
SUNDAY_FG, PICKED_BG, TODAY_BG = "#a01818", "#2f6fd0", "#e3ecfa"


def month_weeks(year, month):
    """The weeks of a month (Sunday first) as lists of 7 dates or None for days outside it."""
    cal = calendar.Calendar(firstweekday=SUNDAY)
    return [[d if d.month == month else None for d in week] for week in cal.monthdatescalendar(year, month)]


def add_months(day, n):
    """The first of the month n months after day's month."""
    m = day.year * 12 + day.month - 1 + n
    return dt.date(m // 12, m % 12 + 1, 1)


class DateField(ttk.Frame):
    """A read-only date box with a calendar button. get() is the date shown; changed is True
    once the person picked a date themselves (set_date from code does not count)."""

    def __init__(self, parent, date=None, on_change=None):
        super().__init__(parent)
        self._date, self.on_change, self.changed, self.popup = date or default_service_date(), on_change, False, None
        self.var = tk.StringVar()
        self.entry = ttk.Entry(self, textvariable=self.var, width=12, state="readonly", justify="center")
        self.entry.pack(side="left")
        self.button = ttk.Button(self, text="\u25BE", width=2, command=self.open)
        self.button.pack(side="left", padx=(2, 0))
        self.entry.bind("<Button-1>", lambda e: self.open())
        self.entry.bind("<Down>", lambda e: self.open())
        self.entry.bind("<space>", lambda e: self.open())
        self._show()

    def get(self):
        return self._date

    def set_date(self, date, by_person=False):
        self._date = date
        self.changed = self.changed or by_person
        self._show()
        if by_person and self.on_change:
            self.on_change(date)

    def _show(self):
        self.var.set(f"{self._date:%m/%d/%Y}")

    # ---- the pop-out calendar -----------------------------------------------------------
    def open(self):
        if self.popup is not None and self.popup.winfo_exists():
            self.close()
            return
        self.month = self._date.replace(day=1)
        self.popup = p = tk.Toplevel(self)
        p.withdraw()
        p.overrideredirect(True)
        p.transient(self.winfo_toplevel())
        frame = tk.Frame(p, bd=1, relief="solid", bg="white")
        frame.pack()
        head = tk.Frame(frame, bg="white")
        head.pack(fill="x", padx=4, pady=(4, 0))
        tk.Button(head, text="◀", relief="flat", bg="white", command=lambda: self._move(-1)).pack(side="left")
        tk.Button(head, text="▶", relief="flat", bg="white", command=lambda: self._move(1)).pack(side="right")
        self.title = tk.Label(head, bg="white", font=("Segoe UI", 10, "bold"))
        self.title.pack(side="left", expand=True)
        self.grid_frame = tk.Frame(frame, bg="white")
        self.grid_frame.pack(padx=4, pady=4)
        foot = tk.Frame(frame, bg="white")
        foot.pack(fill="x", padx=4, pady=(0, 4))
        tk.Button(foot, text="This Sunday" if dt.date.today().weekday() == SUNDAY else "Next Sunday",
                  relief="flat", bg="white", fg="#2f6fd0",
                  command=lambda: self._pick(default_service_date())).pack(side="left")
        tk.Button(foot, text="Today", relief="flat", bg="white", fg="#2f6fd0",
                  command=lambda: self._pick(dt.date.today())).pack(side="right")
        self._fill()
        p.bind("<Escape>", lambda e: self.close())
        p.bind("<ButtonPress>", self._click_outside)
        p.bind("<Prior>", lambda e: self._move(-1))
        p.bind("<Next>", lambda e: self._move(1))
        p.update_idletasks()
        x, y = self.entry.winfo_rootx(), self.entry.winfo_rooty() + self.entry.winfo_height() + 2
        x = max(0, min(x, p.winfo_screenwidth() - p.winfo_reqwidth()))
        if y + p.winfo_reqheight() > p.winfo_screenheight():  # no room below: open above
            y = self.entry.winfo_rooty() - p.winfo_reqheight() - 2
        p.geometry(f"+{x}+{y}")
        p.deiconify()
        p.lift()
        try:
            p.wait_visibility()
            p.grab_set()  # clicks anywhere else in the app come here and close it
        except tk.TclError:
            pass
        p.focus_set()

    def close(self):
        if self.popup is not None and self.popup.winfo_exists():
            try:
                self.popup.grab_release()
            except tk.TclError:
                pass
            self.popup.destroy()
        self.popup = None
        if self.entry.winfo_exists():
            self.entry.focus_set()

    def _click_outside(self, e):
        p = self.popup
        if p is None:
            return
        inside = p.winfo_rootx() <= e.x_root < p.winfo_rootx() + p.winfo_width() and \
            p.winfo_rooty() <= e.y_root < p.winfo_rooty() + p.winfo_height()
        if not inside:
            self.close()

    def _move(self, n):
        self.month = add_months(self.month, n)
        self._fill()

    def _pick(self, date):
        self.close()
        self.set_date(date, by_person=True)

    def _fill(self):
        for w in self.grid_frame.winfo_children():
            w.destroy()
        self.title.config(text=f"{calendar.month_name[self.month.month]} {self.month.year}")
        for c, name in enumerate(DAY_NAMES):
            tk.Label(self.grid_frame, text=name, bg="white", fg=SUNDAY_FG if c == 0 else "#555555",
                     font=("Segoe UI", 8, "bold"), width=3).grid(row=0, column=c)
        today = dt.date.today()
        for r, week in enumerate(month_weeks(self.month.year, self.month.month), start=1):
            for c, day in enumerate(week):
                if day is None:
                    tk.Label(self.grid_frame, text="", bg="white", width=3).grid(row=r, column=c)
                    continue
                picked = day == self._date
                bg = PICKED_BG if picked else (TODAY_BG if day == today else "white")
                fg = "white" if picked else (SUNDAY_FG if c == 0 else "black")
                tk.Button(self.grid_frame, text=str(day.day), width=3, relief="flat", bd=0, bg=bg, fg=fg,
                          activebackground=TODAY_BG, font=("Segoe UI", 9, "bold" if c == 0 else "normal"),
                          command=lambda d=day: self._pick(d)).grid(row=r, column=c, padx=1, pady=1)
