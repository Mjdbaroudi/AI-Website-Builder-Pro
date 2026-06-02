import sys as _sys, os as _os; _sys.path.insert(0, _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))))
"""
tabs_panel.py  –  Custom styled notebook tabs with icons.
Uses a hand-built tab system for full color control.
"""

import tkinter as tk


class StyledNotebook(tk.Frame):
    """A custom tab bar that looks great on dark themes."""

    def __init__(self, parent, **kw):
        super().__init__(parent, bg="#0d0d14", **kw)
        self._tabs    = {}   # name → (btn, page)
        self._active  = None

        self.tab_bar = tk.Frame(self, bg="#0d0d14", height=40)
        self.tab_bar.pack(fill="x")
        self.tab_bar.pack_propagate(False)

        self.pages = tk.Frame(self, bg="#0f0f1a")
        self.pages.pack(fill="both", expand=True)

    def add(self, name: str, icon: str = "") -> tk.Frame:
        page = tk.Frame(self.pages, bg="#0f0f1a")
        label = f"{icon}  {name}" if icon else name

        btn = tk.Button(
            self.tab_bar,
            text=label,
            bd=0, padx=14, pady=0,
            font=("Segoe UI", 9, "bold"),
            cursor="hand2",
            relief="flat",
            command=lambda n=name: self.show(n),
        )
        btn.pack(side="left", fill="y", padx=(0, 1))
        self._set_inactive(btn)

        self._tabs[name] = (btn, page)

        if self._active is None:
            self.show(name)

        return page

    def show(self, name: str):
        for n, (b, p) in self._tabs.items():
            if n == name:
                self._set_active(b)
                p.pack(fill="both", expand=True)
            else:
                self._set_inactive(b)
                p.pack_forget()
        self._active = name

    def _set_active(self, btn):
        btn.config(bg="#1a1a2e", fg="#00d4aa",
                   activebackground="#1a1a2e", activeforeground="#00d4aa")

    def _set_inactive(self, btn):
        btn.config(bg="#0d0d14", fg="#6b6b8a",
                   activebackground="#13131f", activeforeground="#c8c8e0")


def create_tabs(parent):
    nb = StyledNotebook(parent)
    nb.pack(fill="both", expand=True)

    ai_page       = nb.add("AI",       "🧠")
    images_page   = nb.add("Images",   "🖼")
    layout_page   = nb.add("Layout",   "🧩")
    projects_page = nb.add("Projects", "📁")
    settings_page = nb.add("Settings", "⚙")

    return ai_page, images_page, layout_page, projects_page, settings_page