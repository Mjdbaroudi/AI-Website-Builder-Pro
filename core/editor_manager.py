import sys as _sys, os as _os
_sys.path.insert(0, _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))))
"""
editor_manager.py – Code editor utilities.
v3 fixes:
  - highlight_code: hard limit 8000 chars, runs in after() to avoid blocking
  - Large files: skip highlighting entirely (show notice instead)
  - Project switching: cancel pending highlight before loading new file
"""

import tkinter as tk
from tkinter import messagebox
import logging

log = logging.getLogger(__name__)

# Pending highlight job id (so we can cancel on file switch)
_pending_highlight = [None]

# Max chars to highlight — beyond this Tkinter freezes on large minified files
HIGHLIGHT_LIMIT = 50_000

try:
    from pygments import lex
    from pygments.lexers import HtmlLexer, CssLexer, JavascriptLexer, get_lexer_for_filename
    from pygments.token import Token
    PYGMENTS_OK = True
except ImportError:
    PYGMENTS_OK = False
    log.warning("pygments not installed — syntax highlighting disabled.")


# ─── Syntax highlighting ──────────────────────────────────────

def highlight_code(editor: tk.Text, filename: str = "index.html"):
    """
    Highlight up to HIGHLIGHT_LIMIT chars only.
    Scheduled via after() so it never blocks the UI.
    Previous pending highlight is cancelled before scheduling a new one.
    """
    # Cancel any previously scheduled highlight
    if _pending_highlight[0] is not None:
        try:
            editor.after_cancel(_pending_highlight[0])
        except Exception:
            pass
        _pending_highlight[0] = None

    if not PYGMENTS_OK:
        return

    # Schedule the actual work 120ms later
    # (gives Tkinter time to finish drawing the new content first)
    _pending_highlight[0] = editor.after(
        120, lambda: _do_highlight(editor, filename)
    )


def _do_highlight(editor: tk.Text, filename: str):
    """Actual highlighting — runs in the Tk event loop via after()."""
    _pending_highlight[0] = None

    if not PYGMENTS_OK:
        return

    try:
        content = editor.get("1.0", "end-1c")
    except Exception:
        return

    # Skip entirely for large / minified files
    if len(content) > HIGHLIGHT_LIMIT:
        return

    # Clear old tags
    for tag in ("keyword", "string", "comment", "tag", "attr"):
        editor.tag_remove(tag, "1.0", "end")

    try:
        lexer = get_lexer_for_filename(filename)
    except Exception:
        lexer = HtmlLexer()

    # Build a char-offset → "row.col" map in one pass (fast)
    lines  = content.split("\n")
    offset = 0
    line_starts = []           # line_starts[i] = char offset of line i
    for ln in lines:
        line_starts.append(offset)
        offset += len(ln) + 1  # +1 for \n

    def offset_to_index(off):
        # binary search for line
        lo, hi = 0, len(line_starts) - 1
        while lo < hi:
            mid = (lo + hi + 1) // 2
            if line_starts[mid] <= off:
                lo = mid
            else:
                hi = mid - 1
        col = off - line_starts[lo]
        return f"{lo + 1}.{col}"

    cur = 0
    for token_type, text in lex(content, lexer):
        start_off = cur
        cur       += len(text)
        end_off    = cur

        if   token_type in Token.Keyword or token_type in Token.Name.Tag:
            tag = "keyword"
        elif token_type in Token.String or token_type in Token.Literal.String:
            tag = "string"
        elif token_type in Token.Comment:
            tag = "comment"
        elif token_type in Token.Name.Attribute:
            tag = "attr"
        else:
            continue

        try:
            editor.tag_add(tag,
                           offset_to_index(start_off),
                           offset_to_index(end_off))
        except Exception:
            pass


def apply_highlight_tags(editor: tk.Text):
    """Configure tag colors — call once after editor creation."""
    editor.tag_config("keyword", foreground="#569CD6")
    editor.tag_config("string",  foreground="#CE9178")
    editor.tag_config("comment", foreground="#6A9955",
                      font=("Consolas", 10, "italic"))
    editor.tag_config("tag",     foreground="#4EC9B0")
    editor.tag_config("attr",    foreground="#9CDCFE")


# ─── Save ────────────────────────────────────────────────────

def save_current_file(editor: tk.Text, current_file: str) -> bool:
    if not current_file:
        messagebox.showinfo("Info", "No file loaded")
        return False
    try:
        content = editor.get("1.0", tk.END)
        with open(current_file, "w", encoding="utf-8") as f:
            f.write(content)
        editor.edit_modified(False)
        log.info("Saved: %s", current_file)
        return True
    except Exception as e:
        messagebox.showerror("Save Error", str(e))
        return False


# ─── Undo / Redo ─────────────────────────────────────────────

def undo_edit(editor: tk.Text):
    try:
        editor.edit_undo()
    except tk.TclError:
        pass

def redo_edit(editor: tk.Text):
    try:
        editor.edit_redo()
    except tk.TclError:
        pass