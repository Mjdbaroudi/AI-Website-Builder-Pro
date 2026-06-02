import sys as _sys, os as _os; _sys.path.insert(0, _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))))
"""
toolbar_panel.py – Sleek flat toolbar with icon buttons and tooltips.
Fixed: pack() called only once.
"""

import tkinter as tk


# ─── Tooltip helper ─────────────────────────────────────────

class _Tooltip:
    def __init__(self, widget, text):
        self.widget = widget
        self.text   = text
        self.tip    = None
        widget.bind("<Enter>", self._show)
        widget.bind("<Leave>", self._hide)

    def _show(self, _=None):
        x = self.widget.winfo_rootx() + 10
        y = self.widget.winfo_rooty() + self.widget.winfo_height() + 4
        self.tip = tk.Toplevel(self.widget)
        self.tip.wm_overrideredirect(True)
        self.tip.geometry(f"+{x}+{y}")
        tk.Label(
            self.tip, text=self.text,
            bg="#1a1a2e", fg="#c8c8e0",
            font=("Consolas", 9), relief="flat",
            padx=8, pady=4
        ).pack()

    def _hide(self, _=None):
        if self.tip:
            self.tip.destroy()
            self.tip = None


# ─── Toolbar builder ────────────────────────────────────────

def create_toolbar(
    parent,
    start_generate,
    improve_selected,
    load_project,
    open_browser,
    delete_selected,
    export_selected,
    deploy_website,
    deploy_netlify=None,
    open_visual_editor=None,
    import_project=None,
):
    toolbar = tk.Frame(parent, bg="#0f0f1a", height=48)
    toolbar.pack(fill="x")           # ← only ONE pack() call
    toolbar.pack_propagate(False)

    # ── separator ──
    def sep():
        tk.Frame(toolbar, bg="#2a2a45", width=1, height=28).pack(
            side="left", padx=8, pady=10
        )

    # ── button factory ──
    def btn(icon_text, label, color, command, tip=""):
        frame = tk.Frame(toolbar, bg="#0f0f1a")
        frame.pack(side="left", padx=2, pady=6)

        b = tk.Button(
            frame,
            text=f"{icon_text} {label}",
            bg="#1a1a2e",
            fg="#c8c8e0",
            activebackground=color,
            activeforeground="white",
            bd=0,
            padx=10, pady=4,
            font=("Segoe UI", 9, "bold"),
            cursor="hand2",
            relief="flat",
            command=command,
        )
        b.pack()

        # hover
        def on_enter(e, b=b, c=color):
            b.config(bg=c, fg="white")
        def on_leave(e, b=b):
            b.config(bg="#1a1a2e", fg="#c8c8e0")

        b.bind("<Enter>", on_enter)
        b.bind("<Leave>", on_leave)

        if tip:
            _Tooltip(b, tip)
        return b

    # ── Generate group ──
    btn("🧠", "Generate",  "#007acc", start_generate,    "Generate website with AI  [Ctrl+G]")
    btn("✨", "Improve",   "#00a86b", improve_selected,  "AI-improve current file")
    btn("📂", "Load",      "#4a4a6a", load_project,      "Load selected project")
    btn("🌍", "Preview",   "#e67e22", open_browser,      "Open in browser")
    if open_visual_editor:
        btn("🎨", "Visual Edit", "#9b59b6", open_visual_editor, "Open Visual Editor — click any element to edit")

    sep()

    # ── Import group ──
    if import_project:
        btn("📥", "Import Site", "#1a6a8a", import_project, "Import an existing site (folder / ZIP / URL)")

    sep()

    # ── File group ──
    btn("📦", "Export",    "#555577", export_selected,   "Export project as ZIP")
    btn("🗑",  "Delete",   "#aa3333", delete_selected,   "Delete selected project")

    sep()

    # ── Publish group ──
    btn("🚀", "Publish",  "#28a745", deploy_website,    "Publish to GitHub in one click")
    if deploy_netlify:
        btn("⚡", "Netlify", "#00ad9f", deploy_netlify, "Deploy to Netlify (one-click)")

    return toolbar