import sys as _sys, os as _os; _sys.path.insert(0, _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))))
"""
project_manager.py – Project CRUD operations.
Unchanged logic, improved docstrings and error handling.
"""

import os
import re
import datetime
import zipfile
import shutil
from tkinter import filedialog, messagebox
from config import PROJECTS_DIR

log = __import__("logging").getLogger(__name__)


def generate_project_name(text: str) -> str:
    text  = re.sub(r"[^a-zA-Z0-9 ]", "", text)
    words = text.lower().split()[:3]
    name  = "-".join(words) if words else "project"
    date  = datetime.datetime.now().strftime("%d-%m")
    return f"{name}_{date}"


def unique_project_name(base: str) -> str:
    name, i = base, 2
    while os.path.exists(os.path.join(PROJECTS_DIR, name)):
        name = f"{base}_{i}"
        i += 1
    return name


def get_projects() -> list:
    try:
        projects = os.listdir(PROJECTS_DIR)
        return sorted(projects, reverse=True)
    except FileNotFoundError:
        return []


def create_project_folder(name: str) -> str:
    folder = os.path.join(PROJECTS_DIR, name)
    os.makedirs(folder, exist_ok=True)
    return folder


def delete_project(name: str):
    folder = os.path.join(PROJECTS_DIR, name)
    shutil.rmtree(folder, ignore_errors=True)


def export_project(name: str):
    folder  = os.path.join(PROJECTS_DIR, name)
    default = f"{name}.zip"
    out_path = filedialog.asksaveasfilename(
        defaultextension=".zip",
        initialfile=default,
        filetypes=[("ZIP Archive", "*.zip")],
        title="Export Project"
    )
    if not out_path:
        return

    with zipfile.ZipFile(out_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for root_dir, _, files in os.walk(folder):
            for file in files:
                fpath    = os.path.join(root_dir, file)
                arc_name = os.path.relpath(fpath, folder)
                zf.write(fpath, arc_name)

    messagebox.showinfo("Export Complete", f"Project exported to:\n{out_path}")


def import_project_from_folder() -> str | None:
    """Let user pick an existing website folder and copy it into PROJECTS_DIR.
    Returns the new project name, or None if cancelled."""
    src = filedialog.askdirectory(title="اختر مجلد الموقع")
    if not src:
        return None

    base_name = os.path.basename(src.rstrip("/\\")) or "imported-site"
    base_name = re.sub(r"[^a-zA-Z0-9_\-]", "-", base_name)
    project_name = unique_project_name(base_name)
    dest = os.path.join(PROJECTS_DIR, project_name)

    try:
        shutil.copytree(src, dest)
    except Exception as e:
        messagebox.showerror("Import Error", f"فشل النسخ:\n{e}")
        return None

    if not os.path.exists(os.path.join(dest, "index.html")):
        # try to find any .html file and rename it index.html
        html_files = [f for f in os.listdir(dest) if f.endswith(".html")]
        if html_files:
            os.rename(
                os.path.join(dest, html_files[0]),
                os.path.join(dest, "index.html")
            )

    messagebox.showinfo("✅ تم الاستيراد", f"تم استيراد المشروع:\n{project_name}")
    return project_name


def import_project_from_zip() -> str | None:
    """Let user pick a ZIP file and extract it into PROJECTS_DIR.
    Returns the new project name, or None if cancelled."""
    zip_path = filedialog.askopenfilename(
        title="اختر ملف ZIP للموقع",
        filetypes=[("ZIP files", "*.zip")]
    )
    if not zip_path:
        return None

    base_name = os.path.splitext(os.path.basename(zip_path))[0]
    base_name = re.sub(r"[^a-zA-Z0-9_\-]", "-", base_name)
    project_name = unique_project_name(base_name)
    dest = os.path.join(PROJECTS_DIR, project_name)
    os.makedirs(dest, exist_ok=True)

    try:
        with zipfile.ZipFile(zip_path, "r") as zf:
            # Detect if ZIP has a single root folder
            names = zf.namelist()
            roots = {n.split("/")[0] for n in names if n.strip()}
            if len(roots) == 1:
                root_prefix = list(roots)[0] + "/"
                for member in zf.infolist():
                    rel = member.filename[len(root_prefix):]
                    if not rel:
                        continue
                    target = os.path.join(dest, rel)
                    if member.filename.endswith("/"):
                        os.makedirs(target, exist_ok=True)
                    else:
                        os.makedirs(os.path.dirname(target), exist_ok=True)
                        with zf.open(member) as src_f, open(target, "wb") as dst_f:
                            dst_f.write(src_f.read())
            else:
                zf.extractall(dest)
    except Exception as e:
        messagebox.showerror("Import Error", f"فشل فك الضغط:\n{e}")
        shutil.rmtree(dest, ignore_errors=True)
        return None

    if not os.path.exists(os.path.join(dest, "index.html")):
        html_files = []
        for root_dir, _, files in os.walk(dest):
            for f in files:
                if f.endswith(".html"):
                    html_files.append(os.path.join(root_dir, f))
        if html_files:
            shutil.copy2(html_files[0], os.path.join(dest, "index.html"))

    messagebox.showinfo("✅ تم الاستيراد", f"تم استيراد المشروع:\n{project_name}")
    return project_name


def import_project_from_url(url: str) -> str | None:
    """Download a webpage (HTML + linked CSS/JS/images) and save as a project.
    Returns the new project name, or None on failure."""
    import urllib.request
    import urllib.parse
    import html.parser

    if not url.startswith("http"):
        url = "https://" + url

    # Extract clean project name from URL
    parsed = urllib.parse.urlparse(url)
    base_name = re.sub(r"[^a-zA-Z0-9_\-]", "-", parsed.netloc or "website")
    project_name = unique_project_name(base_name)
    dest = os.path.join(PROJECTS_DIR, project_name)
    os.makedirs(dest, exist_ok=True)

    headers = {"User-Agent": "Mozilla/5.0 (compatible; WebsiteImporter/1.0)"}

    def _fetch(fetch_url):
        try:
            req = urllib.request.Request(fetch_url, headers=headers)
            with urllib.request.urlopen(req, timeout=15) as r:
                return r.read(), r.headers.get("Content-Type", "")
        except Exception:
            return None, ""

    # Download main HTML
    html_bytes, _ = _fetch(url)
    if not html_bytes:
        messagebox.showerror("Import Error", f"تعذّر تنزيل الصفحة:\n{url}")
        shutil.rmtree(dest, ignore_errors=True)
        return None

    html_text = html_bytes.decode("utf-8", errors="replace")

    # Parse linked assets (css, js, images)
    class AssetParser(html.parser.HTMLParser):
        def __init__(self):
            super().__init__()
            self.assets = []
        def handle_starttag(self, tag, attrs):
            attrs = dict(attrs)
            if tag == "link" and attrs.get("rel") == "stylesheet":
                if attrs.get("href"): self.assets.append(attrs["href"])
            elif tag == "script" and attrs.get("src"):
                self.assets.append(attrs["src"])
            elif tag == "img" and attrs.get("src"):
                self.assets.append(attrs["src"])

    parser = AssetParser()
    parser.feed(html_text)

    base_url = f"{parsed.scheme}://{parsed.netloc}"
    downloaded = {}

    for asset in parser.assets:
        # Skip data URIs and absolute external URLs from different domains
        if asset.startswith("data:"):
            continue
        asset_url = urllib.parse.urljoin(url, asset)
        asset_parsed = urllib.parse.urlparse(asset_url)
        if asset_parsed.netloc != parsed.netloc:
            continue  # skip CDN assets — keep their original URLs

        asset_bytes, content_type = _fetch(asset_url)
        if not asset_bytes:
            continue

        # Save with safe filename
        asset_path = asset_parsed.path.lstrip("/")
        asset_name = os.path.basename(asset_path) or "asset"
        asset_name = re.sub(r"[^a-zA-Z0-9._\-]", "_", asset_name)
        # Avoid filename collisions
        if asset_name in downloaded.values():
            asset_name = f"{len(downloaded)}_{asset_name}"

        save_path = os.path.join(dest, asset_name)
        with open(save_path, "wb") as f:
            f.write(asset_bytes)

        downloaded[asset] = asset_name

    # Rewrite asset URLs in HTML to local filenames
    for original, local in downloaded.items():
        html_text = html_text.replace(f'"{original}"', f'"{local}"')
        html_text = html_text.replace(f"'{original}'", f"'{local}'")

    with open(os.path.join(dest, "index.html"), "w", encoding="utf-8") as f:
        f.write(html_text)

    count = len(downloaded)
    messagebox.showinfo("✅ تم الاستيراد",
                        f"تم تنزيل الموقع:\n{project_name}\n\nملفات محلية: {count + 1}")
    return project_name