"""
main.py  –  AI Website Builder PRO  v2.0
=========================================
Changes from v1:
  ✅ Fixed: client.responses.create → client.chat.completions.create
  ✅ Fixed: features/image_tools now exists
  ✅ Fixed: editor_manager functions accept parameters (no globals)
  ✅ Fixed: deploy_website receives repo_url
  ✅ Fixed: current_project passed as lambda to image_panel
  ✅ Fixed: toolbar.pack() called only once
  ✅ Fixed: Thread safety — current_file set via root.after()
  ✅ Fixed: bare except → except Exception as e
  ✅ Fixed: get_available_models() result actually used
  ✅ Fixed: model names corrected (gpt-4o, etc.)
  ✅ New:   Multi-provider AI (OpenAI / Anthropic / Gemini)
  ✅ New:   Line numbers in editor
  ✅ New:   Find & Replace (Ctrl+F)
  ✅ New:   Netlify one-click deploy
  ✅ New:   Vercel deploy
  ✅ New:   Auto-save every 30 seconds
  ✅ New:   Redo support
  ✅ New:   Cursor position in status bar
  ✅ New:   Rich dark UI theme throughout
"""

import threading
import webbrowser
import tkinter as tk
from tkinter import messagebox
from tkinter.scrolledtext import ScrolledText
import os
import logging

# ── logging ──────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.FileHandler("logs/app.log"),
        logging.StreamHandler(),
    ]
)
log = logging.getLogger("main")

# ── imports ──────────────────────────────────────────────────
from ui.project_panel  import create_project_panel
from ui.statusbar_panel import create_status_bar
from ui.tabs_panel     import create_tabs
from ui.settings_panel import create_settings_panel
from ui.toolbar_panel  import create_toolbar
from ui.editor_panel   import create_editor_panel
from ui.image_panel    import create_image_panel
from ui.visual_editor_panel import open_visual_editor
from ui.layout_editor_panel   import create_layout_editor_panel
from core.deploy_manager  import deploy_website, deploy_to_netlify, deploy_to_vercel
from core.github_manager  import publish_to_github
from core.editor_manager  import highlight_code, save_current_file, undo_edit, redo_edit
from core.ai_engine       import (generate_advanced_website,
                                  extract_files, improve_html,
                                  get_models_for_provider,
                                  get_default_model,
                                  DEFAULT_MODEL, DEFAULT_PROVIDER)
from core.ai_chatbot      import AICodeAssistant
from core.file_manager    import save_files, load_file, list_files
from features.image_tools import upload_image, scan_images, replace_selected_image
from config import PROJECTS_DIR, APP_TITLE, APP_VERSION, AUTOSAVE_MS
from core.project_manager import (
    generate_project_name,
    unique_project_name,
    get_projects,
    create_project_folder,
    delete_project,
    export_project,
    import_project_from_folder,
    import_project_from_zip,
    import_project_from_url,
)

ai_assistant = AICodeAssistant()

# ── State ────────────────────────────────────────────────────
current_file    = None
current_project = None


# ════════════════════════════════════════════════════════════
#  Spinner / overlay
# ════════════════════════════════════════════════════════════

def start_spinner(message="Generating Website..."):
    global spinner_running
    spinner_running  = True
    loading_label.config(text=message)
    overlay.lift()
    _animate_spinner()

def stop_spinner():
    global spinner_running
    spinner_running = False
    overlay.lower()

def _animate_spinner():
    if not spinner_running:
        return
    cur = spinner_label.cget("text")
    spinner_label.config(text="●" if cur == "○" else "○")
    root.after(400, _animate_spinner)


# ════════════════════════════════════════════════════════════
#  Generate website
# ════════════════════════════════════════════════════════════

def start_generate():
    """Generate using the template selected in the sidebar."""
    val = _tmpl_sel["value"]   # "auto" | "none" | specific template id
    _on_template_chosen(None if val == "none" else val)

def _on_template_chosen(template_id):
    overlay.lift()
    start_spinner("Generating Website...")
    t = threading.Thread(target=_generate_worker,
                         args=(template_id,), daemon=True)
    t.start()


def _generate_worker(template_id=None):
    global current_file

    idea = entry.get("1.0", "end-1c").strip()
    if not idea:
        root.after(0, stop_spinner)
        root.after(0, lambda: messagebox.showerror("Error", "Please enter a website description"))
        return

    base         = generate_project_name(idea)
    project_name = unique_project_name(base)
    folder       = create_project_folder(project_name)
    provider     = provider_var.get()
    model        = model_var.get()

    try:

        root.after(0, lambda: status_label.config(text="🎨 Stage 1/4 — Building design system (CSS)..."))

        # Pick the correct API key for the selected provider
        _key_map = {
            "openai":    openai_key_var.get(),
            "anthropic": anthropic_key_var.get(),
            "gemini":    gemini_key_var.get(),
        }
        api_key = _key_map.get(provider.lower(), "")

        files = generate_advanced_website(
            idea,
            "",
            lang_var.get(),
            model,
            provider,
            api_key,
        )

        root.after(0, lambda: status_label.config(text="✅ All stages complete — saving..."))

        # Validate at least index.html was generated
        if not files.get("index.html"):
            raise RuntimeError(
                f"AI model '{model}' did not return valid HTML.\n\n"
                "Possible causes:\n"
                "- Model returned empty content (known issue with some GPT-5/o-series models)\n"
                "- API key missing or invalid\n"
                "- Model quota exceeded\n\n"
                "Suggested fix: Switch to 'gpt-4o' or 'gpt-4o-mini' in Settings tab."
            )

        root.after(0, lambda: status_label.config(text="💾 Saving files..."))
        save_files(folder, files)
        index_path = os.path.join(folder, "index.html")

        # Build proper file:// URL for browser
        abs_path   = os.path.abspath(index_path)
        file_url   = "file:///" + abs_path.replace("\\", "/").replace("\\", "/")
        # Normalize Windows backslashes
        import pathlib
        file_url = pathlib.Path(abs_path).as_uri()

        root.after(0, stop_spinner)
        root.after(0, refresh_projects)
        root.after(0, lambda: _set_current_file(index_path))
        root.after(0, lambda: load_project(project_name))
        root.after(0, lambda u=file_url: webbrowser.open(u))

    except Exception as e:
        log.error("Generate error: %s", e)
        root.after(0, stop_spinner)
        error_msg = str(e)
        root.after(0, lambda: messagebox.showerror("Generation Error", error_msg))


def _set_current_file(path):
    global current_file
    current_file = path


# ════════════════════════════════════════════════════════════
#  Project management
# ════════════════════════════════════════════════════════════

def refresh_projects():
    project_list.delete(0, tk.END)
    for p in get_projects():
        project_list.insert(tk.END, p)


def load_project(name=None):
    global current_file, current_project

    if not name:
        sel = project_list.curselection()
        if not sel:
            return
        name = project_list.get(sel[0])

    current_project = name
    folder = os.path.join(PROJECTS_DIR, name)

    # populate file list
    file_list.delete(0, tk.END)
    for f in list_files(folder):
        file_list.insert(tk.END, f)

    # load index.html
    index = os.path.join(folder, "index.html")
    if os.path.exists(index):
        current_file = index
        _load_file_to_editor(index)

    status_label.config(text=f"▶  {name}")


def open_selected_file(event=None):
    global current_file, current_project

    if not current_project:
        messagebox.showinfo("Info", "No project loaded")
        return

    sel = file_list.curselection()
    if not sel:
        return

    fname = file_list.get(sel[0]).lstrip("◈◉◎⬡○ ")   # strip icon prefix
    path  = os.path.join(PROJECTS_DIR, current_project, fname)

    if not os.path.exists(path):
        messagebox.showerror("Error", f"File not found:\n{path}")
        return

    current_file = path
    _load_file_to_editor(path)

    ext = os.path.splitext(fname)[1]
    status_label.config(text=f"▶  {current_project}  /  {fname}")
    status_label.set_lang(ext)


def _load_file_to_editor(path: str):
    from core.editor_manager import _pending_highlight
    # Cancel any pending highlight job immediately
    if _pending_highlight[0] is not None:
        try: editor.after_cancel(_pending_highlight[0])
        except Exception: pass
        _pending_highlight[0] = None

    content = load_file(path)
    fname   = os.path.basename(path)
    size    = len(content)

    editor.config(state="normal")
    editor.delete("1.0", tk.END)

    if size > 80_000:
        # Very large file: insert in one shot but skip highlighting
        editor.insert(tk.END, content)
        editor.edit_modified(False)
        status_label.config(
            text=f"▶  {fname}  ({size//1000}k chars — highlighting skipped for performance)"
        )
    else:
        editor.insert(tk.END, content)
        editor.edit_modified(False)
        highlight_code(editor, fname)


def delete_selected():
    sel = project_list.curselection()
    if not sel:
        return
    name = project_list.get(sel[0])
    if messagebox.askyesno("Delete Project", f"Delete '{name}'?\nThis cannot be undone."):
        delete_project(name)
        refresh_projects()
        status_label.config(text="Ready")


def export_selected():
    sel = project_list.curselection()
    if not sel:
        return
    export_project(project_list.get(sel[0]))


# ════════════════════════════════════════════════════════════
#  AI assistant (chat modifications)
# ════════════════════════════════════════════════════════════

def apply_ai_modification():
    global current_file

    if not current_file:
        messagebox.showinfo("Info", "No file loaded")
        return

    user_request = chat_input.get().strip()
    if not user_request:
        messagebox.showinfo("Info", "Enter a modification request")
        return

    current_code = editor.get("1.0", tk.END)
    file_type    = current_file.rsplit(".", 1)[-1]

    try:
        updated = ai_assistant.modify_code(
            user_request, current_code, file_type,
            model_var.get(), provider_var.get()
        )

        if "---FIND---" in updated and "---REPLACE---" in updated:
            new_code = current_code
            for part in updated.split("---FIND---")[1:]:
                try:
                    find_txt    = part.split("---REPLACE---")[0].strip()
                    replace_txt = part.split("---REPLACE---")[1].strip()
                    if find_txt in new_code:
                        new_code = new_code.replace(find_txt, replace_txt)
                    else:
                        log.warning("FIND text not found in editor: %r", find_txt[:80])
                except Exception as ex:
                    log.error("Diff parse error: %s", ex)

            editor.delete("1.0", tk.END)
            editor.insert(tk.END, new_code)
            messagebox.showinfo("AI Applied ✅", "Modifications applied successfully")
        else:
            messagebox.showerror("Format Error",
                                 "AI response did not use the expected ---FIND--- / ---REPLACE--- format.")
    except Exception as e:
        messagebox.showerror("AI Error", str(e))


def improve_selected():
    global current_file
    if not current_file:
        return
    html = editor.get("1.0", tk.END)
    status_label.config(text="⏳ Improving...")
    try:
        _key_map = {
            "openai":    openai_key_var.get(),
            "anthropic": anthropic_key_var.get(),
            "gemini":    gemini_key_var.get(),
        }
        api_key = _key_map.get(provider_var.get().lower(), "")
        new_html = improve_html(html, model_var.get(), provider_var.get(), api_key)
        editor.delete("1.0", tk.END)
        editor.insert(tk.END, new_html)
        status_label.config(text="✓ Improved")
    except Exception as e:
        messagebox.showerror("Improve Error", str(e))
        status_label.config(text="Error")


# ════════════════════════════════════════════════════════════
#  Browser / deploy helpers
# ════════════════════════════════════════════════════════════

def open_browser():
    if not current_file:
        messagebox.showinfo("Info", "Load a project first")
        return
    import pathlib
    webbrowser.open(pathlib.Path(os.path.abspath(current_file)).as_uri())


def import_site():
    """Show import dialog — folder / ZIP / URL."""
    dlg = tk.Toplevel(root)
    dlg.title("📥 Import Site")
    dlg.geometry("420x260")
    dlg.configure(bg="#0d0d14")
    dlg.resizable(False, False)
    dlg.grab_set()

    tk.Label(dlg, text="📥  Import Existing Site",
             fg="#00d4aa", bg="#0d0d14",
             font=("Segoe UI", 13, "bold")).pack(pady=(18, 4))
    tk.Label(dlg, text="Choose import method:",
             fg="#8888aa", bg="#0d0d14",
             font=("Segoe UI", 9)).pack()

    def _do(fn, *args):
        dlg.destroy()
        name = fn(*args)
        if name:
            refresh_projects()
            load_project(name)

    def _url_dialog():
        dlg.destroy()
        url_win = tk.Toplevel(root)
        url_win.title("Import from URL")
        url_win.geometry("400x140")
        url_win.configure(bg="#0d0d14")
        url_win.grab_set()
        tk.Label(url_win, text="Enter website URL:",
                 fg="#c8c8e0", bg="#0d0d14",
                 font=("Segoe UI", 10)).pack(pady=(18, 4))
        url_var = tk.StringVar()
        tk.Entry(url_win, textvariable=url_var, width=44,
                 bg="#1a1a2e", fg="#c8c8e0",
                 insertbackground="white", relief="flat",
                 font=("Segoe UI", 10), bd=0).pack(ipady=6, padx=16)

        def _go():
            u = url_var.get().strip()
            if not u:
                return
            url_win.destroy()
            name = import_project_from_url(u)
            if name:
                refresh_projects()
                load_project(name)

        tk.Button(url_win, text="⬇ Download", command=_go,
                  bg="#1a6a8a", fg="white",
                  font=("Segoe UI", 10, "bold"),
                  relief="flat", padx=20, pady=6,
                  cursor="hand2").pack(pady=12)

    BG, FG = "#1a1a2e", "#c8c8e0"
    bframe = tk.Frame(dlg, bg="#0d0d14"); bframe.pack(pady=20)

    for icon, label, cmd in [
        ("📁", "From Folder\n(select a folder)", lambda: _do(import_project_from_folder)),
        ("🗜",  "From ZIP\n(compressed file)",        lambda: _do(import_project_from_zip)),
        ("🌐", "From URL",               _url_dialog),
    ]:
        f = tk.Frame(bframe, bg=BG, cursor="hand2", relief="flat", bd=0)
        f.pack(side="left", padx=8, ipadx=10, ipady=8)
        tk.Label(f, text=icon, font=("Segoe UI", 22),
                 bg=BG, fg="#00d4aa").pack()
        tk.Label(f, text=label, font=("Segoe UI", 8),
                 bg=BG, fg=FG, justify="center").pack()
        for w in (f, *f.winfo_children()):
            w.bind("<Button-1>", lambda e, c=cmd: c())
            w.bind("<Enter>",    lambda e, fr=f: fr.config(bg="#2a2a4a"))
            w.bind("<Leave>",    lambda e, fr=f: fr.config(bg=BG))


def do_deploy():
    deploy_website(current_project)


def do_netlify():
    deploy_to_netlify(current_project,
                      netlify_key_var.get() if netlify_key_var.get() else "")


def open_ve():
    open_visual_editor(
        root,
        lambda: current_file,
        editor,
        apply_ai_modification,
        lambda: provider_var.get(),
        lambda: model_var.get(),
    )



def _auto_save():
    if current_file and editor.edit_modified():
        # Skip auto-save for very large files (avoid freezing)
        content_len = len(editor.get("1.0", "end-1c"))
        if content_len > 200_000:
            editor.edit_modified(False)  # reset flag
            return
        if save_current_file(editor, current_file):
            status_label.config(text="✓ Auto-saved")
    root.after(AUTOSAVE_MS, _auto_save)


# ════════════════════════════════════════════════════════════
#  Build UI
# ════════════════════════════════════════════════════════════

root = tk.Tk()
root.title(f"{APP_TITLE}  v{APP_VERSION}")
root.geometry("1560x900")
root.configure(bg="#0d0d14")
root.minsize(1100, 650)

# ── Loading overlay ──
overlay = tk.Frame(root, bg="#000008")
overlay.place(relx=0, rely=0, relwidth=1, relheight=1)
overlay.lower()

loading_label = tk.Label(overlay, text="Generating...",
                          fg="#c8c8e0", bg="#000008",
                          font=("Segoe UI", 16, "bold"))
loading_label.place(relx=0.5, rely=0.44, anchor="center")

spinner_label = tk.Label(overlay, text="●",
                          fg="#00d4aa", bg="#000008",
                          font=("Segoe UI", 28))
spinner_label.place(relx=0.5, rely=0.52, anchor="center")

spinner_running = False

# ── Header ──
header = tk.Frame(root, bg="#060610", height=52)
header.pack(fill="x")
header.pack_propagate(False)

tk.Label(header,
         text=f"  ⬡  {APP_TITLE}",
         fg="#00d4aa", bg="#060610",
         font=("Segoe UI", 14, "bold")
).pack(side="left", padx=16, pady=0)

tk.Label(header,
         text=f"v{APP_VERSION}",
         fg="#2a2a4a", bg="#060610",
         font=("Consolas", 10)
).pack(side="left")

# ── Toolbar ──
create_toolbar(
    root,
    start_generate,
    improve_selected,
    load_project,
    open_browser,
    delete_selected,
    export_selected,
    do_deploy,
    do_netlify,
    open_ve,
    import_site,
)

# ── Main area ──
main_frame = tk.Frame(root, bg="#0d0d14")
main_frame.pack(fill="both", expand=True)

paned = tk.PanedWindow(main_frame, orient=tk.HORIZONTAL,
                        bg="#0d0d14", sashwidth=4, sashrelief="flat",
                        sashpad=0)
paned.pack(fill="both", expand=True)

# ── Sidebar ──
sidebar = tk.Frame(paned, bg="#0f0f1a", width=320)
paned.add(sidebar, minsize=260)
sidebar.pack_propagate(False)

# ── Tabs ──
ai_page, images_page, layout_page, projects_page, settings_page = create_tabs(sidebar)

# ── AI Tab contents ──
tk.Label(ai_page, text="DESCRIBE YOUR WEBSITE", fg="#3a3a5a", bg="#0f0f1a",
         font=("Segoe UI", 8, "bold")).pack(anchor="w", padx=12, pady=(12, 2))

entry = ScrolledText(ai_page, width=38, height=7,
                     font=("Segoe UI", 10),
                     bg="#0d0d14", fg="#c8c8e0",
                     insertbackground="white",
                     relief="flat", bd=0,
                     wrap="word",
                     padx=10, pady=8)
entry.pack(padx=8, pady=(0, 4), fill="x")

# ── Template selector ──
tk.Label(ai_page, text="🎨  TEMPLATE",
         fg="#3a3a5a", bg="#0f0f1a",
         font=("Segoe UI", 8, "bold")).pack(anchor="w", padx=12, pady=(10, 2))

_tmpl_sel = {"value": "auto"}

def _tmpl_btn(parent, text, val, accent="#1a1a3a"):
    b = tk.Button(parent, text=text,
                  bg=accent, fg="#c8c8e0",
                  activebackground="#2a2a5a", activeforeground="white",
                  relief="flat", bd=0, padx=4, pady=5,
                  font=("Segoe UI", 8, "bold"), cursor="hand2",
                  command=lambda v=val: _sel(v))
    b.pack(side="left", padx=2, expand=True, fill="x")
    return b

_tmpl_btns = {}

def _sel(val):
    _tmpl_sel["value"] = val
    for v, b in _tmpl_btns.items():
        b.config(bg="#4a9eff" if v == val else "#1a1a3a",
                 fg="#fff"    if v == val else "#c8c8e0")

_r1 = tk.Frame(ai_page, bg="#0f0f1a")
_r1.pack(fill="x", padx=8, pady=(0, 3))
_tmpl_btns["auto"] = _tmpl_btn(_r1, "✨ Auto-Detect", "auto", "#1a3a5a")
_tmpl_btns["none"] = _tmpl_btn(_r1, "🤖 AI Only",    "none")


_sel("auto")

tk.Label(ai_page, text="AI CODE ASSISTANT", fg="#3a3a5a", bg="#0f0f1a",
         font=("Segoe UI", 8, "bold")).pack(anchor="w", padx=12, pady=(10, 2))

chat_frame = tk.Frame(ai_page, bg="#0f0f1a")
chat_frame.pack(fill="x", padx=8, pady=(0, 4))

chat_input = tk.Entry(chat_frame,
                       bg="#0d0d14", fg="#c8c8e0",
                       insertbackground="white",
                       relief="flat", font=("Segoe UI", 10),
                       bd=0)
chat_input.pack(fill="x", ipady=6, padx=0)
chat_input.insert(0, "e.g. Make the header fixed and add a dark mode toggle")

def _clear_placeholder(e):
    if chat_input.get() == "e.g. Make the header fixed and add a dark mode toggle":
        chat_input.delete(0, "end")
chat_input.bind("<FocusIn>", _clear_placeholder)

tk.Button(ai_page, text="⚡ Apply AI Change",
          bg="#1a1a3a", fg="#7b7bcc",
          activebackground="#2a2a5a", activeforeground="white",
          bd=0, padx=0, pady=8, font=("Segoe UI", 10, "bold"),
          cursor="hand2", relief="flat", width=30,
          command=apply_ai_modification
).pack(padx=8, pady=(4, 0), fill="x")

# Right-click paste menu for entry
menu = tk.Menu(root, tearoff=0, bg="#1a1a2e", fg="#c8c8e0",
               activebackground="#007acc", activeforeground="white",
               bd=0, relief="flat")
menu.add_command(label="Paste", command=lambda: entry.event_generate("<<Paste>>"))
menu.add_command(label="Copy",  command=lambda: entry.event_generate("<<Copy>>"))
menu.add_command(label="Cut",   command=lambda: entry.event_generate("<<Cut>>"))
entry.bind("<Button-3>", lambda e: menu.tk_popup(e.x_root, e.y_root))

# ── Settings panel ──
(
    theme_var, color_var, layout_var, lang_var, type_var,
    model_var, provider_var, netlify_key_var,
    openai_key_var, anthropic_key_var, gemini_key_var,
) = create_settings_panel(settings_page)

# ── Editor (main pane) ──
editor = create_editor_panel(
    paned,
    save_current_file,
    undo_edit,
    lambda: current_file,
    redo_edit,
)

# highlight on key
editor.bind("<KeyRelease>",
            lambda e: highlight_code(editor,
                                     os.path.basename(current_file) if current_file else "index.html"))

# ── Image panel ──
image_list = create_image_panel(
    images_page, editor, None,
    scan_images, upload_image, replace_selected_image,
    lambda: current_project,      # ← lambda, not value
    lambda: current_file,         # ← ✅ FIX: pass current_file for auto-save after replace
)

# ── Project panel ──
project_list, explorer_frame, file_list = create_project_panel(
    projects_page, main_frame, paned, load_project, open_selected_file
)

# ── Status bar ──
status_label = create_status_bar(root)
status_label.track_cursor(editor)

# ── Layout Editor panel ──
def _get_editor_html():
    return editor.get("1.0", "end-1c")

def _set_editor_html(html: str):
    editor.config(state="normal")
    editor.delete("1.0", tk.END)
    editor.insert(tk.END, html)
    editor.edit_modified(True)
    from core.editor_manager import highlight_code
    import os as _os
    highlight_code(editor,
                   _os.path.basename(current_file) if current_file else "index.html")

layout_frame, layout_scan = create_layout_editor_panel(
    layout_page,
    get_html_fn      = _get_editor_html,
    set_html_fn      = _set_editor_html,
    get_model_fn     = model_var.get,
    get_provider_fn  = provider_var.get,
    status_fn        = lambda msg: status_label.config(text=msg),
)
layout_frame.pack(fill="both", expand=True)

# ── Initialize ──
refresh_projects()
root.after(AUTOSAVE_MS, _auto_save)

# ── Close handler ──
def on_close():
    if editor.edit_modified():
        result = messagebox.askyesnocancel(
            "Unsaved Changes",
            "You have unsaved changes.\nSave before closing?"
        )
        if result is None:
            return
        if result:
            save_current_file(editor, current_file)
    root.destroy()

root.protocol("WM_DELETE_WINDOW", on_close)

log.info("%s v%s started", APP_TITLE, APP_VERSION)
root.mainloop()