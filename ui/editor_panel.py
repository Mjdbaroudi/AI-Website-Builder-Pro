import sys as _sys, os as _os; _sys.path.insert(0, _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))))
"""
editor_panel.py  –  Code editor with line numbers, find/replace, minimap gutter.
New features:
  - Line number gutter (auto-updates on scroll/edit)
  - Find & Replace bar (Ctrl+F / Ctrl+H)
  - Redo button
  - Word-wrap toggle
"""

import tkinter as tk
from core.editor_manager import apply_highlight_tags


# ─── Line number canvas ──────────────────────────────────────

class LineNumbers(tk.Canvas):
    def __init__(self, parent, text_widget, **kw):
        kw.setdefault("width", 44)
        kw.setdefault("bg", "#0d0d14")
        kw.setdefault("highlightthickness", 0)
        super().__init__(parent, **kw)
        self.text = text_widget
        self.text.bind("<KeyRelease>",     self._redraw)
        self.text.bind("<MouseWheel>",     self._redraw)
        self.text.bind("<Button-4>",       self._redraw)
        self.text.bind("<Button-5>",       self._redraw)
        self.text.bind("<<Change>>",       self._redraw)
        self.text.bind("<Configure>",      self._redraw)
        self.bind("<Button-1>",            self._on_click)

    def _redraw(self, _=None):
        self.delete("all")
        i = self.text.index("@0,0")
        while True:
            dline = self.text.dlineinfo(i)
            if dline is None:
                break
            y    = dline[1]
            lnum = str(i).split(".")[0]
            self.create_text(
                38, y + 1,
                anchor="ne",
                text=lnum,
                fill="#3a3a5a",
                font=("Consolas", 9),
            )
            i = self.text.index(f"{i}+1line")

    def _on_click(self, event):
        """Click line number → select that line in editor."""
        y    = event.y
        i    = self.text.index(f"@0,{y}")
        line = i.split(".")[0]
        self.text.tag_remove("sel", "1.0", "end")
        self.text.tag_add("sel", f"{line}.0", f"{line}.end")
        self.text.mark_set("insert", f"{line}.0")
        self.text.see(f"{line}.0")


# ─── Find / Replace bar ─────────────────────────────────────

class FindBar(tk.Frame):
    def __init__(self, parent, text_widget):
        super().__init__(parent, bg="#13131f")
        self.text   = text_widget
        self._build()
        self.text.tag_config("found", background="#264f78", foreground="white")

    def _build(self):
        style = dict(bg="#1a1a2e", fg="#c8c8e0", insertbackground="white",
                     relief="flat", font=("Consolas", 10), bd=0)

        tk.Label(self, text="Find:", bg="#13131f", fg="#6b6b8a",
                 font=("Segoe UI", 9)).pack(side="left", padx=(8, 2))

        self.find_var = tk.StringVar()
        self.find_entry = tk.Entry(self, textvariable=self.find_var,
                                   width=22, **style)
        self.find_entry.pack(side="left", padx=2, pady=4, ipady=3)
        self.find_var.trace_add("write", lambda *_: self._highlight())

        tk.Label(self, text="Replace:", bg="#13131f", fg="#6b6b8a",
                 font=("Segoe UI", 9)).pack(side="left", padx=(8, 2))

        self.rep_var = tk.StringVar()
        self.rep_entry = tk.Entry(self, textvariable=self.rep_var,
                                  width=22, **style)
        self.rep_entry.pack(side="left", padx=2, pady=4, ipady=3)

        def ibtn(text, cmd, tip=""):
            b = tk.Button(self, text=text, command=cmd,
                          bg="#1a1a2e", fg="#c8c8e0",
                          activebackground="#007acc", activeforeground="white",
                          bd=0, padx=8, pady=2,
                          font=("Segoe UI", 9), cursor="hand2", relief="flat")
            b.pack(side="left", padx=2, pady=4)
            return b

        ibtn("↑",      self._prev,    "Previous match")
        ibtn("↓",      self._next,    "Next match")
        ibtn("Replace",self._replace, "Replace current")
        ibtn("All",    self._replace_all, "Replace all")

        self._close_btn = ibtn("✕", self.hide)
        self._count_lbl = tk.Label(self, text="", bg="#13131f",
                                   fg="#6b6b8a", font=("Consolas", 9))
        self._count_lbl.pack(side="left", padx=6)

        self.find_entry.bind("<Return>",   lambda _: self._next())
        self.find_entry.bind("<Escape>",   lambda _: self.hide())
        self.rep_entry.bind("<Return>",    lambda _: self._replace())

        self._matches = []
        self._idx     = -1

    def show(self):
        self.pack(fill="x", before=self.master.winfo_children()[0]
                  if self.master.winfo_children() else None)
        self.find_entry.focus_set()
        sel = self.text.tag_ranges("sel")
        if sel:
            self.find_var.set(self.text.get(sel[0], sel[1]))
        self._highlight()

    def hide(self):
        self.text.tag_remove("found", "1.0", "end")
        self.pack_forget()

    def _highlight(self, *_):
        self.text.tag_remove("found", "1.0", "end")
        self._matches = []
        q = self.find_var.get()
        if not q:
            self._count_lbl.config(text="")
            return
        idx = "1.0"
        while True:
            idx = self.text.search(q, idx, stopindex="end", nocase=True)
            if not idx:
                break
            end = f"{idx}+{len(q)}c"
            self.text.tag_add("found", idx, end)
            self._matches.append(idx)
            idx = end
        count = len(self._matches)
        self._count_lbl.config(text=f"{count} match{'es' if count != 1 else ''}")
        self._idx = 0 if self._matches else -1
        if self._matches:
            self.text.see(self._matches[0])

    def _next(self):
        if not self._matches:
            return
        self._idx = (self._idx + 1) % len(self._matches)
        self.text.see(self._matches[self._idx])

    def _prev(self):
        if not self._matches:
            return
        self._idx = (self._idx - 1) % len(self._matches)
        self.text.see(self._matches[self._idx])

    def _replace(self):
        q = self.find_var.get()
        r = self.rep_var.get()
        if not q or self._idx < 0 or not self._matches:
            return
        pos = self._matches[self._idx]
        end = f"{pos}+{len(q)}c"
        self.text.delete(pos, end)
        self.text.insert(pos, r)
        self._highlight()

    def _replace_all(self):
        q = self.find_var.get()
        r = self.rep_var.get()
        if not q:
            return
        content = self.text.get("1.0", "end-1c")
        import re
        new_content = re.sub(re.escape(q), r, content, flags=re.IGNORECASE)
        self.text.delete("1.0", "end")
        self.text.insert("1.0", new_content)
        self._highlight()


# ─── Main editor factory ────────────────────────────────────

def create_editor_panel(paned, save_current_file, undo_edit, get_current_file,
                        redo_edit=None):

    outer = tk.Frame(paned, bg="#0d0d14")
    paned.add(outer, minsize=400)

    # ── Find bar (hidden by default) ──
    find_bar_container = tk.Frame(outer, bg="#0d0d14")
    find_bar_container.pack(fill="x")

    # ── Editor row ──
    editor_row = tk.Frame(outer, bg="#0d0d14")
    editor_row.pack(fill="both", expand=True)

    # scrollbars
    scroll_y = tk.Scrollbar(editor_row, bg="#1a1a2e", troughcolor="#0d0d14")
    scroll_y.pack(side="right", fill="y")
    scroll_x = tk.Scrollbar(editor_row, orient="horizontal",
                             bg="#1a1a2e", troughcolor="#0d0d14")
    scroll_x.pack(side="bottom", fill="x")

    # editor
    editor = tk.Text(
        editor_row,
        bg="#0d0d14",
        fg="#d4d4d4",
        insertbackground="#aeafad",
        insertwidth=2,
        selectbackground="#264f78",
        selectforeground="white",
        wrap="none",
        undo=True,
        maxundo=-1,
        font=("Consolas", 11),
        padx=8, pady=6,
        spacing1=2, spacing3=2,
        yscrollcommand=scroll_y.set,
        xscrollcommand=scroll_x.set,
        relief="flat",
    )

    # line numbers
    line_nums = LineNumbers(editor_row, editor)
    line_nums.pack(side="left", fill="y")

    editor.pack(fill="both", expand=True)
    scroll_y.config(command=lambda *a: (editor.yview(*a), line_nums._redraw()))
    scroll_x.config(command=editor.xview)

    apply_highlight_tags(editor)

    # ── Find bar (inside container) ──
    find_bar = FindBar(find_bar_container, editor)

    # Ctrl+F / Ctrl+H shortcuts
    editor.bind("<Control-f>", lambda _: find_bar.show())
    editor.bind("<Control-F>", lambda _: find_bar.show())
    editor.bind("<Control-h>", lambda _: find_bar.show())
    editor.bind("<Control-H>", lambda _: find_bar.show())
    editor.bind("<Escape>",    lambda _: find_bar.hide())

    # ── Bottom toolbar ──
    toolbar = tk.Frame(outer, bg="#13131f", height=38)
    toolbar.pack(fill="x")
    toolbar.pack_propagate(False)

    btn_style = dict(
        bd=0, padx=10, pady=3, relief="flat", cursor="hand2",
        font=("Segoe UI", 9, "bold"), activeforeground="white",
    )

    def make_btn(text, bg, active_bg, cmd):
        b = tk.Button(toolbar, text=text, bg=bg,
                      fg="#c8c8e0", activebackground=active_bg, **btn_style,
                      command=cmd)
        b.pack(side="left", padx=4, pady=5)
        return b

    make_btn("💾 Save", "#1e3a2f", "#00a86b",
             lambda: save_current_file(editor, get_current_file()))
    make_btn("↩ Undo", "#2a2a1a", "#e67e22",
             lambda: undo_edit(editor))
    if redo_edit:
        make_btn("↪ Redo", "#1a1a2e", "#5a5aaa",
                 lambda: redo_edit(editor))
    make_btn("🔍 Find", "#1a1a2e", "#007acc",
             lambda: find_bar.show())

    # word wrap toggle
    wrap_state = {"on": False}
    def toggle_wrap():
        wrap_state["on"] = not wrap_state["on"]
        editor.config(wrap="word" if wrap_state["on"] else "none")
        wrap_btn.config(text="↔ Wrap ON" if wrap_state["on"] else "↔ Wrap OFF")

    wrap_btn = tk.Button(toolbar, text="↔ Wrap OFF",
                         bg="#1a1a2e", fg="#6b6b8a",
                         activebackground="#2a2a45",
                         **{k: v for k, v in btn_style.items() if k != "activeforeground"},
                         activeforeground="#aaaacc",
                         command=toggle_wrap)
    wrap_btn.pack(side="right", padx=4, pady=5)

    return editor
