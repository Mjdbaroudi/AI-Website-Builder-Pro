import sys as _sys, os as _os; _sys.path.insert(0, _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))))
"""
deploy_manager.py – Deploy to GitHub Pages, Netlify, and Vercel.
Fixed: deploy_website now takes repo_url parameter.
New: Netlify one-click deploy via API.
"""

import os
import io
import zipfile
import subprocess
import webbrowser
import logging
from tkinter import messagebox, simpledialog
from config import PROJECTS_DIR, NETLIFY_TOKEN, GITHUB_TOKEN

log = logging.getLogger(__name__)


# ─── Git / GitHub Pages ─────────────────────────────────────

def deploy_website(project_name: str, repo_url: str = "", _legacy=False):
    """Push project to GitHub and optionally enable GitHub Pages."""
    if not project_name:
        messagebox.showerror("Error", "Load a project first")
        return

    folder = os.path.join(PROJECTS_DIR, project_name)

    if not repo_url:
        repo_url = simpledialog.askstring(
            "🚀 Publish to GitHub",
            "Enter your GitHub repository URL:\n(e.g. https://github.com/user/repo.git)"
        )
        if not repo_url:
            return

    try:
        def run(cmd):
            return subprocess.run(cmd, cwd=folder, capture_output=True, text=True)

        run(["git", "init"])
        run(["git", "add", "."])
        run(["git", "commit", "-m", "Deploy from AI Website Builder PRO"])
        run(["git", "branch", "-M", "main"])
        # remove old remote if exists, then re-add
        run(["git", "remote", "remove", "origin"])
        run(["git", "remote", "add", "origin", repo_url])
        result = run(["git", "push", "-u", "origin", "main", "--force"])

        if result.returncode != 0:
            messagebox.showerror("Push Failed", result.stderr or result.stdout)
            return

        # build GitHub Pages URL
        import re
        match = re.search(r"github\.com[:/](.+?)(?:\.git)?$", repo_url)
        pages_url = ""
        if match:
            user, repo = match.group(1).split("/", 1)
            pages_url = f"https://{user}.github.io/{repo}"

        msg = "✅ Project published to GitHub!"
        if pages_url:
            msg += f"\n\nTo enable GitHub Pages:\nRepo Settings → Pages → Branch: main\n\n🌍 Your site will be at:\n{pages_url}"

        messagebox.showinfo("Published!", msg)

    except Exception as e:
        messagebox.showerror("Deploy Error", str(e))
        log.error("Deploy error: %s", e)


# ─── Netlify Drop API ────────────────────────────────────────

def deploy_to_netlify(project_name: str, netlify_token: str = "") -> str:
    """Zip project and deploy to Netlify. Returns live URL."""
    try:
        import requests
    except ImportError:
        messagebox.showerror("Missing Library", "Run: pip install requests")
        return ""

    if not project_name:
        messagebox.showerror("Error", "Load a project first")
        return ""

    token = netlify_token or NETLIFY_TOKEN
    if not token:
        token = simpledialog.askstring("Netlify Token", "Enter your Netlify personal access token:")
        if not token:
            return ""

    folder = os.path.join(PROJECTS_DIR, project_name)

    try:
        # Zip the project in memory
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
            for fname in os.listdir(folder):
                fpath = os.path.join(folder, fname)
                if os.path.isfile(fpath):
                    zf.write(fpath, fname)
        buf.seek(0)

        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/zip",
        }
        resp = requests.post(
            "https://api.netlify.com/api/v1/sites",
            headers=headers,
            data=buf.read(),
            timeout=60,
        )
        resp.raise_for_status()
        data = resp.json()
        url = data.get("ssl_url") or data.get("url", "")

        if url:
            messagebox.showinfo("✅ Netlify Deploy!", f"Live at:\n{url}")
            webbrowser.open(url)
        return url

    except Exception as e:
        messagebox.showerror("Netlify Error", str(e))
        log.error("Netlify deploy error: %s", e)
        return ""


# ─── Vercel (via CLI) ────────────────────────────────────────

def deploy_to_vercel(project_name: str):
    """Deploy using Vercel CLI (must be installed and logged in)."""
    if not project_name:
        messagebox.showerror("Error", "Load a project first")
        return

    folder = os.path.join(PROJECTS_DIR, project_name)
    try:
        result = subprocess.run(
            ["vercel", "--prod", "--yes"],
            cwd=folder, capture_output=True, text=True, timeout=120
        )
        output = result.stdout + result.stderr
        url_match = __import__("re").search(r"https://\S+\.vercel\.app", output)
        url = url_match.group(0) if url_match else ""

        if url:
            messagebox.showinfo("✅ Vercel Deploy!", f"Live at:\n{url}")
            webbrowser.open(url)
        else:
            messagebox.showinfo("Vercel", output or "Deployed (check terminal)")
    except FileNotFoundError:
        messagebox.showerror("Vercel CLI Missing", "Install Vercel CLI:\nnpm i -g vercel")
    except Exception as e:
        messagebox.showerror("Vercel Error", str(e))