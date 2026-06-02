"""
ui/layout_editor_panel.py  —  AI Layout Editor Panel
=====================================================
A sidebar panel that lets the user:
  • See all detected sections in the current page
  • Add new sections from a preset catalog
  • Modify / remove individual sections
  • Reorder sections via Up/Down buttons
  • Free-text AI request on any section
"""

import tkinter as tk
from tkinter import messagebox
import threading

from core.layout_editor import (
    analyze_sections, add_section, modify_section,
    remove_section, reorder_sections, SECTION_PRESETS
)

# ── Palette ──────────────────────────────────────────────────
BG      = "#0f0f1a"
BG2     = "#12122a"
BG3     = "#1a1a35"
CARD    = "#16162e"
BORDER  = "#2a2a4a"
TEAL    = "#00d4aa"
BLUE    = "#4a9eff"
RED     = "#ef4444"
YELLOW  = "#f59e0b"
DIM     = "#44445a"
TEXT    = "#c8c8e0"
WHITE   = "#ffffff"
FONT    = ("Segoe UI", 9)
FONT_B  = ("Segoe UI", 9, "bold")
FONT_SM = ("Segoe UI", 8)


def create_layout_editor_panel(parent,
                                get_html_fn,
                                set_html_fn,
                                get_model_fn,
                                get_provider_fn,
                                status_fn=None):
    """
    Build and return the layout editor frame.

    Parameters
    ----------
    parent        : tk widget to pack into
    get_html_fn   : () → str   — returns current editor HTML
    set_html_fn   : (str) → None — writes new HTML to editor
    get_model_fn  : () → str
    get_provider_fn : () → str
    status_fn     : (str) → None  — update status bar
    """

    frame = tk.Frame(parent, bg=BG)

    # ── Header ───────────────────────────────────────────────
    hdr = tk.Frame(frame, bg=BG2)
    hdr.pack(fill="x")
    tk.Label(hdr, text="🧩  AI LAYOUT EDITOR",
             font=("Segoe UI", 9, "bold"),
             fg=TEAL, bg=BG2, pady=8).pack(side="left", padx=12)
    refresh_btn = tk.Button(hdr, text="↻ Scan",
                            font=FONT_SM, bg=BG3, fg=TEAL,
                            relief="flat", bd=0, padx=8, pady=4,
                            cursor="hand2", activebackground=BORDER,
                            activeforeground=WHITE)
    refresh_btn.pack(side="right", padx=8, pady=6)

    # ── Sections list ─────────────────────────────────────────
    tk.Label(frame, text="PAGE SECTIONS", font=("Segoe UI", 7, "bold"),
             fg=DIM, bg=BG).pack(anchor="w", padx=12, pady=(10, 3))

    sections_frame = tk.Frame(frame, bg=BG)
    sections_frame.pack(fill="x", padx=8)

    # listbox + scrollbar
    lb_frame = tk.Frame(sections_frame, bg=BG)
    lb_frame.pack(fill="x")

    sections_lb = tk.Listbox(
        lb_frame, height=7,
        bg=CARD, fg=TEXT, font=FONT,
        selectbackground=BLUE, selectforeground=WHITE,
        relief="flat", bd=0, highlightthickness=1,
        highlightbackground=BORDER,
        activestyle="none"
    )
    sb = tk.Scrollbar(lb_frame, orient="vertical",
                      command=sections_lb.yview, bg=BG3)
    sections_lb.config(yscrollcommand=sb.set)
    sb.pack(side="right", fill="y")
    sections_lb.pack(side="left", fill="x", expand=True)

    # section action buttons row
    act_row = tk.Frame(sections_frame, bg=BG)
    act_row.pack(fill="x", pady=(4, 0))

    def _abtn(parent, text, color, cmd):
        b = tk.Button(parent, text=text, font=FONT_SM,
                      bg=BG3, fg=color, relief="flat", bd=0,
                      padx=6, pady=4, cursor="hand2",
                      activebackground=BORDER, activeforeground=WHITE,
                      command=cmd)
        b.pack(side="left", padx=2, expand=True, fill="x")
        return b

    btn_up   = _abtn(act_row, "▲ Up",     BLUE,   lambda: _move_section(-1))
    btn_down = _abtn(act_row, "▼ Down",   BLUE,   lambda: _move_section(1))
    btn_del  = _abtn(act_row, "🗑 Remove", RED,    lambda: _remove_selected())

    # modify row
    mod_row = tk.Frame(sections_frame, bg=BG)
    mod_row.pack(fill="x", pady=(4, 0))

    mod_entry = tk.Entry(mod_row, bg=BG2, fg=TEXT,
                         insertbackground=WHITE, relief="flat",
                         font=FONT, bd=0)
    mod_entry.pack(side="left", fill="x", expand=True, ipady=5, padx=(0, 4))
    mod_entry.insert(0, "e.g. make it 2 columns, add icons")

    def _clear_mod(e):
        if mod_entry.get() == "e.g. make it 2 columns, add icons":
            mod_entry.delete(0, "end")
    mod_entry.bind("<FocusIn>", _clear_mod)

    btn_mod = tk.Button(mod_row, text="✏ Modify", font=FONT_SM,
                        bg=BLUE, fg=WHITE, relief="flat", bd=0,
                        padx=8, pady=5, cursor="hand2",
                        command=lambda: _modify_selected())
    btn_mod.pack(side="right")

    # ── Divider ───────────────────────────────────────────────
    tk.Frame(frame, bg=BORDER, height=1).pack(fill="x", padx=8, pady=(12, 4))

    # ── Add section ───────────────────────────────────────────
    tk.Label(frame, text="ADD SECTION", font=("Segoe UI", 7, "bold"),
             fg=DIM, bg=BG).pack(anchor="w", padx=12, pady=(4, 6))

    catalog_outer = tk.Frame(frame, bg=BG)
    catalog_outer.pack(fill="x", padx=8)

    # Catalog canvas (scrollable grid)
    cat_canvas = tk.Canvas(catalog_outer, bg=BG, highlightthickness=0,
                           height=200)
    cat_sb = tk.Scrollbar(catalog_outer, orient="vertical",
                          command=cat_canvas.yview, bg=BG3)
    cat_canvas.config(yscrollcommand=cat_sb.set)
    cat_sb.pack(side="right", fill="y")
    cat_canvas.pack(side="left", fill="both", expand=True)
    cat_inner = tk.Frame(cat_canvas, bg=BG)
    cat_win = cat_canvas.create_window((0, 0), window=cat_inner, anchor="nw")

    def _cat_configure(e):
        cat_canvas.configure(scrollregion=cat_canvas.bbox("all"))
        cat_canvas.itemconfig(cat_win, width=cat_canvas.winfo_width())
    cat_inner.bind("<Configure>", _cat_configure)
    cat_canvas.bind("<Configure>",
                    lambda e: cat_canvas.itemconfig(cat_win, width=e.width))
    cat_canvas.bind("<MouseWheel>",
                    lambda e: cat_canvas.yview_scroll(-1*(e.delta//120), "units"))

    # Build preset cards (2 per row)
    COLS = 2
    for i, preset in enumerate(SECTION_PRESETS):
        row, col = divmod(i, COLS)
        card = tk.Frame(cat_inner, bg=BG3, cursor="hand2",
                        highlightthickness=1, highlightbackground=BORDER)
        card.grid(row=row, column=col, padx=3, pady=3, sticky="nsew")
        cat_inner.columnconfigure(col, weight=1)

        tk.Label(card, text=preset["icon"],
                 font=("Segoe UI", 16), bg=BG3).pack(pady=(8, 0))
        tk.Label(card, text=preset["label"],
                 font=FONT_B, fg=WHITE, bg=BG3).pack()
        tk.Label(card, text=preset["desc"],
                 font=FONT_SM, fg=DIM, bg=BG3,
                 wraplength=120, justify="center").pack(padx=6, pady=(2, 8))

        def _make_add(pid=preset["id"]):
            return lambda e=None: _add_section(pid)

        fn = _make_add()
        for w in [card] + list(card.winfo_children()):
            w.bind("<Button-1>", fn)
            w.bind("<Enter>", lambda e, c=card: c.config(
                highlightbackground=TEAL, bg="#1e1e3a") or
                [ch.config(bg="#1e1e3a") for ch in c.winfo_children()
                 if hasattr(ch, 'config')])
            w.bind("<Leave>", lambda e, c=card: c.config(
                highlightbackground=BORDER, bg=BG3) or
                [ch.config(bg=BG3) for ch in c.winfo_children()
                 if hasattr(ch, 'config')])

    # ── State ─────────────────────────────────────────────────
    _sections = []   # list of section dicts from analyze_sections()

    def _status(msg):
        if status_fn:
            status_fn(msg)

    def _set_busy(flag: bool):
        state = "disabled" if flag else "normal"
        for w in [btn_up, btn_down, btn_del, btn_mod, refresh_btn]:
            try: w.config(state=state)
            except: pass

    # ── Scan / refresh ────────────────────────────────────────
    def _scan():
        nonlocal _sections
        html = get_html_fn()
        if not html or not html.strip():
            sections_lb.delete(0, "end")
            sections_lb.insert("end", "  (no file loaded)")
            return

        _sections = analyze_sections(html)
        sections_lb.delete(0, "end")

        if not _sections:
            sections_lb.insert("end", "  (no named sections detected)")
            return

        for s in _sections:
            icon = _section_icon(s["name"])
            label = f"  {icon}  {s['name'].capitalize()}"
            if s["id"]:
                label += f"  #{s['id']}"
            sections_lb.insert("end", label)

    refresh_btn.config(command=_scan)

    def _section_icon(name: str) -> str:
        icons = {
            "hero": "🚀", "nav": "📌", "services": "⚙️", "about": "👥",
            "pricing": "💰", "testimonials": "💬", "team": "👤",
            "faq": "❓", "gallery": "🖼️", "stats": "📊", "cta": "📣",
            "contact": "📬", "blog": "📝", "footer": "🔻",
            "products": "🛍️", "partners": "🤝", "newsletter": "📧",
            "video": "🎥", "map": "📍", "timeline": "⏳",
        }
        return icons.get(name, "▪")

    def _get_selected_section():
        sel = sections_lb.curselection()
        if not sel:
            messagebox.showinfo("Layout Editor", "Select a section first.")
            return None
        idx = sel[0]
        if idx >= len(_sections):
            return None
        return _sections[idx], idx

    # ── Remove ────────────────────────────────────────────────
    def _remove_selected():
        result = _get_selected_section()
        if not result: return
        sec, idx = result
        sec_id = sec.get("id") or sec["name"]
        if not messagebox.askyesno("Remove Section",
                                   f"Remove the '{sec['name']}' section?"):
            return
        _set_busy(True)
        _status(f"🗑 Removing {sec['name']}…")

        def _worker():
            html = get_html_fn()
            new_html = remove_section(
                html, sec_id,
                get_model_fn(), get_provider_fn()
            )
            frame.after(0, lambda: _apply(new_html, f"✓ Removed {sec['name']}"))

        threading.Thread(target=_worker, daemon=True).start()

    # ── Modify ────────────────────────────────────────────────
    def _modify_selected():
        result = _get_selected_section()
        if not result: return
        sec, idx = result
        request = mod_entry.get().strip()
        if not request or request == "e.g. make it 2 columns, add icons":
            messagebox.showinfo("Layout Editor", "Enter a modification request.")
            return
        sec_id = sec.get("id") or sec["name"]
        _set_busy(True)
        _status(f"🤖 Modifying {sec['name']}…")

        def _worker():
            html = get_html_fn()
            new_html = modify_section(
                html, sec_id, request,
                get_model_fn(), get_provider_fn()
            )
            frame.after(0, lambda: _apply(new_html, f"✓ Modified {sec['name']}"))

        threading.Thread(target=_worker, daemon=True).start()

    # ── Move up / down ────────────────────────────────────────
    def _move_section(direction: int):
        result = _get_selected_section()
        if not result: return
        sec, idx = result
        new_idx = idx + direction
        if new_idx < 0 or new_idx >= len(_sections):
            return

        new_order = list(_sections)
        new_order.insert(new_idx, new_order.pop(idx))
        order_ids = [s.get("id") or s["name"] for s in new_order]

        # Pure Python reorder — instant, no AI needed
        html     = get_html_fn()
        new_html = reorder_sections(html, order_ids)
        _apply(new_html, "✓ Sections reordered", select_idx=new_idx)

    # ── Add section ───────────────────────────────────────────
    def _add_section(section_id: str):
        _set_busy(True)
        _status(f"🤖 Adding {section_id} section…")

        def _worker():
            html = get_html_fn()
            if not html or not html.strip():
                frame.after(0, lambda: messagebox.showinfo(
                    "Layout Editor", "No HTML file loaded."))
                frame.after(0, lambda: _set_busy(False))
                return
            new_html = add_section(
                html, section_id,
                get_model_fn(), get_provider_fn(),
                progress_cb=lambda m: frame.after(0, lambda msg=m: _status(msg))
            )
            frame.after(0, lambda: _apply(new_html, f"✓ Added {section_id}"))

        threading.Thread(target=_worker, daemon=True).start()

    # ── Apply result ──────────────────────────────────────────
    def _apply(new_html: str, status_msg: str, select_idx: int = None):
        set_html_fn(new_html)
        _set_busy(False)
        _status(status_msg)
        _scan()   # refresh section list
        if select_idx is not None:
            try:
                sections_lb.selection_clear(0, "end")
                sections_lb.selection_set(select_idx)
                sections_lb.see(select_idx)
            except: pass

    return frame, _scan