import sys as _sys, os as _os; _sys.path.insert(0, _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))))
"""
project_panel.py  –  Project list + file explorer.
Improved: consistent dark styling, hover effects.
"""

import tkinter as tk


def create_project_panel(sidebar, main_frame, paned, load_project, open_selected_file):

    # ── Project list (in sidebar tab) ──
    tk.Label(sidebar, text="Your Projects", fg="#6b6b8a", bg="#0f0f1a",
             font=("Segoe UI", 9, "bold")).pack(anchor="w", padx=12, pady=(10, 2))

    list_frame = tk.Frame(sidebar, bg="#0f0f1a")
    list_frame.pack(fill="both", expand=True, padx=8, pady=(0, 8))

    proj_scroll = tk.Scrollbar(list_frame, bg="#1a1a2e", troughcolor="#0d0d14")
    proj_scroll.pack(side="right", fill="y")

    project_list = tk.Listbox(
        list_frame,
        bg="#0d0d14",
        fg="#c8c8e0",
        selectbackground="#1a3a5e",
        selectforeground="#00d4aa",
        activestyle="none",
        font=("Segoe UI", 10),
        relief="flat",
        bd=0,
        highlightthickness=0,
        yscrollcommand=proj_scroll.set,
    )
    project_list.pack(fill="both", expand=True)
    proj_scroll.config(command=project_list.yview)
    project_list.bind("<Double-Button-1>", lambda e: load_project())

    # ── File explorer pane ──
    explorer_frame = tk.Frame(main_frame, bg="#0d0d14", width=200)
    paned.add(explorer_frame, minsize=160)

    tk.Label(explorer_frame, text="FILES", fg="#3a3a5a", bg="#0d0d14",
             font=("Segoe UI", 8, "bold")).pack(anchor="w", padx=10, pady=(10, 2))

    file_scroll = tk.Scrollbar(explorer_frame, bg="#1a1a2e", troughcolor="#0d0d14")
    file_scroll.pack(side="right", fill="y")

    file_list = tk.Listbox(
        explorer_frame,
        bg="#0d0d14",
        fg="#9090b0",
        selectbackground="#1a3a5e",
        selectforeground="#00d4aa",
        activestyle="none",
        font=("Consolas", 10),
        relief="flat",
        bd=0,
        highlightthickness=0,
        yscrollcommand=file_scroll.set,
    )
    file_list.pack(fill="both", expand=True, padx=(8, 0))
    file_scroll.config(command=file_list.yview)
    file_list.bind("<Double-Button-1>", open_selected_file)

    # File icon mapping
    ICONS = {".html": "◈ ", ".css": "◉ ", ".js": "◎ ",
             ".png": "⬡ ", ".jpg": "⬡ ", ".svg": "⬡ "}

    def insert_file(name: str):
        ext = "." + name.rsplit(".", 1)[-1] if "." in name else ""
        icon = ICONS.get(ext, "○ ")
        file_list.insert(tk.END, icon + name)

    # patch to allow icon insertion
    file_list.insert_file = insert_file

    return project_list, explorer_frame, file_list
