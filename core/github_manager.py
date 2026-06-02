import sys as _sys, os as _os; _sys.path.insert(0, _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))))
"""
github_manager.py – Git initialization and GitHub publish helpers.
"""

import os
import subprocess
from tkinter import messagebox, simpledialog
from config import PROJECTS_DIR

log = __import__("logging").getLogger(__name__)


def publish_to_github(project_name: str):
    if not project_name:
        messagebox.showerror("Error", "Load a project first")
        return

    folder = os.path.join(PROJECTS_DIR, project_name)

    try:
        subprocess.run(["git", "init"],  cwd=folder, check=True, capture_output=True)
        subprocess.run(["git", "add", "."], cwd=folder, check=True, capture_output=True)
        subprocess.run(
            ["git", "commit", "-m", "Initial commit from AI Website Builder PRO"],
            cwd=folder, check=True, capture_output=True
        )
        messagebox.showinfo(
            "Git Ready ✅",
            "Project initialized with Git.\n\n"
            "Next steps:\n"
            "1. Create a new repo on GitHub\n"
            "2. Copy the repo URL\n"
            "3. Use Deploy button to push"
        )
    except subprocess.CalledProcessError as e:
        messagebox.showerror("Git Error", e.stderr.decode() if e.stderr else str(e))
    except Exception as e:
        messagebox.showerror("Error", str(e))
