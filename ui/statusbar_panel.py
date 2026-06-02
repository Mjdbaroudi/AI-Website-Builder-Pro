import sys as _sys, os as _os; _sys.path.insert(0, _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))))
"""
statusbar_panel.py – Rich status bar with file info, cursor pos, AI status.
"""

import tkinter as tk
import datetime


def create_status_bar(parent):
    bar = tk.Frame(parent, bg="#0a0a14", height=24)
    bar.pack(fill="x", side="bottom")
    bar.pack_propagate(False)

    # left: status message
    status_label = tk.Label(
        bar, text="Ready",
        bg="#0a0a14", fg="#5a8a6a",
        font=("Segoe UI", 9),
        anchor="w",
    )
    status_label.pack(side="left", padx=12)

    # thin separator
    tk.Frame(bar, bg="#1a1a2e", width=1).pack(side="left", fill="y", pady=4)

    # right side items
    def right_lbl(text="", fg="#3a3a5a"):
        l = tk.Label(bar, text=text, bg="#0a0a14", fg=fg, font=("Consolas", 8))
        l.pack(side="right", padx=8)
        return l

    clock_lbl  = right_lbl(fg="#3a3a5a")
    cursor_lbl = right_lbl(fg="#3a3a5a")
    lang_lbl   = right_lbl("HTML", fg="#4a4a6a")

    def tick():
        now = datetime.datetime.now().strftime("%H:%M")
        clock_lbl.config(text=now)
        bar.after(10_000, tick)

    tick()

    # attach cursor tracker
    def track_cursor(editor):
        def _update(_=None):
            try:
                idx  = editor.index("insert")
                line, col = idx.split(".")
                cursor_lbl.config(text=f"Ln {line}  Col {int(col)+1}")
            except Exception:
                pass
        editor.bind("<KeyRelease>",   _update)
        editor.bind("<ButtonRelease>", _update)

    status_label.track_cursor = track_cursor

    def set_lang(ext):
        names = {".html": "HTML", ".css": "CSS", ".js": "JavaScript",
                 ".py": "Python", ".json": "JSON"}
        lang_lbl.config(text=names.get(ext, ext.upper().lstrip(".")))

    status_label.set_lang = set_lang

    return status_label
