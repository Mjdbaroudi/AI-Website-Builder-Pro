import sys as _sys, os as _os; _sys.path.insert(0, _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))))
"""
image_panel.py – Image scanner and uploader.
Fixed: current_project passed as lambda to stay up-to-date.
"""

import tkinter as tk


def create_image_panel(parent, editor, _unused,
                       scan_images, upload_image,
                       replace_selected_image, get_current_project,
                       get_current_file=None):

    tk.Label(parent, text="IMAGES IN PAGE", fg="#3a3a5a", bg="#0f0f1a",
             font=("Segoe UI", 8, "bold")).pack(anchor="w", padx=12, pady=(10, 2))

    scroll_frame = tk.Frame(parent, bg="#0f0f1a")
    scroll_frame.pack(fill="both", expand=True, padx=8)

    scroll = tk.Scrollbar(scroll_frame, bg="#1a1a2e", troughcolor="#0d0d14")
    scroll.pack(side="right", fill="y")

    image_list = tk.Listbox(
        scroll_frame,
        bg="#0d0d14", fg="#9090b0",
        selectbackground="#1a3a5e",
        selectforeground="#00d4aa",
        activestyle="none",
        font=("Consolas", 9),
        relief="flat", bd=0, highlightthickness=0,
        yscrollcommand=scroll.set,
        height=8,
    )
    image_list.pack(fill="both", expand=True)
    scroll.config(command=image_list.yview)

    btn_frame = tk.Frame(parent, bg="#0f0f1a")
    btn_frame.pack(fill="x", padx=8, pady=8)

    def ibtn(text, cmd, col):
        b = tk.Button(
            btn_frame, text=text, command=cmd,
            bg="#1a1a2e", fg="#c8c8e0",
            activebackground="#007acc", activeforeground="white",
            bd=0, padx=8, pady=5, font=("Segoe UI", 9),
            cursor="hand2", relief="flat",
        )
        b.grid(row=0, column=col, padx=3, sticky="we")
        return b

    btn_frame.columnconfigure(0, weight=1)
    btn_frame.columnconfigure(1, weight=1)
    btn_frame.columnconfigure(2, weight=1)

    ibtn("🔍 Scan",    lambda: scan_images(editor, image_list),              0)
    ibtn("📤 Upload",  lambda: upload_image(get_current_project()),          1)
    ibtn("🔄 Replace", lambda: replace_selected_image(
        editor, image_list, get_current_project, get_current_file),  2)

    return image_list