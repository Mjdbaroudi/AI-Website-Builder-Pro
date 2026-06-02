import threading
import os
import webbrowser
from tkinter import messagebox


def generate_ai_website(
    entry,
    type_var,
    theme_var,
    color_var,
    layout_var,
    lang_var,
    model_var,
    generate_project_name,
    unique_project_name,
    create_project_folder,
    generate_blueprint,
    generate_advanced_website,
    extract_files,
    save_files,
    stop_spinner,
    refresh_projects,
    load_project,
    root
):

    idea = entry.get("1.0", "end-1c")

    if not idea.strip():
        messagebox.showerror("Error", "Enter description")
        root.after(0, stop_spinner)
        return

    base = generate_project_name(idea)
    project_name = unique_project_name(base)
    folder = create_project_folder(project_name)

    try:

        blueprint = generate_blueprint(
            idea,
            type_var.get(),
            theme_var.get(),
            color_var.get(),
            layout_var.get(),
            model_var.get()
        )

        result = generate_advanced_website(
            blueprint,
            "",
            lang_var.get(),
            model_var.get()
        )

        files = extract_files(result)
        save_files(folder, files)

        index_file = os.path.join(folder, "index.html")

        root.after(0, stop_spinner)
        root.after(0, refresh_projects)
        root.after(0, lambda: load_project(project_name))

        webbrowser.open(index_file)

    except Exception as e:
        root.after(0, stop_spinner)
        messagebox.showerror("Error", str(e))


def start_generate(root, overlay, start_spinner, generate_function):

    overlay.lift()
    start_spinner()

    thread = threading.Thread(target=generate_function)
    thread.daemon = True
    thread.start()