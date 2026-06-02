import sys as _sys, os as _os; _sys.path.insert(0, _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))))
import tkinter as tk


def create_buttons_panel(parent,
                         start_generate,
                         improve_selected,
                         load_project,
                         open_browser,
                         delete_selected,
                         export_selected,
                         publish_github,
                         deploy):

    frame = tk.Frame(parent, bg="#252526")

    # ROW 0
    tk.Button(
        frame,
        text="Generate",
        bg="#007acc",
        fg="white",
        width=14,
        command=start_generate
    ).grid(row=0, column=0, padx=5, pady=5)

    tk.Button(
        frame,
        text="Improve AI",
        bg="#00a86b",
        fg="white",
        width=14,
        command=improve_selected
    ).grid(row=0, column=1, padx=5, pady=5)

    tk.Button(
        frame,
        text="Load Project",
        bg="#555",
        fg="white",
        width=14,
        command=load_project
    ).grid(row=0, column=2, padx=5, pady=5)

    # ROW 1
    tk.Button(
        frame,
        text="Open Browser",
        bg="#ffaa00",
        fg="black",
        width=14,
        command=open_browser
    ).grid(row=1, column=0, padx=5, pady=5)

    tk.Button(
        frame,
        text="Delete Project",
        bg="#aa3333",
        fg="white",
        width=14,
        command=delete_selected
    ).grid(row=1, column=1, padx=5, pady=5)

    tk.Button(
        frame,
        text="Export ZIP",
        bg="#888",
        fg="white",
        width=14,
        command=export_selected
    ).grid(row=1, column=2, padx=5, pady=5)

    # ROW 2
    tk.Button(
        frame,
        text="Publish GitHub",
        bg="#24292e",
        fg="white",
        width=14,
        command=publish_github
    ).grid(row=2, column=0, padx=5, pady=5)

    tk.Button(
        frame,
        text="Deploy Website",
        bg="#28a745",
        fg="white",
        width=14,
        command=deploy
    ).grid(row=2, column=1, padx=5, pady=5)

    return frame