import os
import shutil
import re
from tkinter import filedialog, messagebox

last_uploaded_image = None


def upload_image(current_project):

    global last_uploaded_image

    file_path = filedialog.askopenfilename(
        filetypes=[("Images", "*.png *.jpg *.jpeg *.webp")]
    )

    if not file_path:
        return

    filename = os.path.basename(file_path)

    dest = os.path.join("projects", current_project, "images", filename)

    shutil.copy(file_path, dest)

    last_uploaded_image = f"images/{filename}"

    messagebox.showinfo("Success", f"Image uploaded:\n{last_uploaded_image}")


def scan_images(editor, image_list):

    code = editor.get("1.0", "end")

    pattern = r'<img[^>]+src="([^"]+)"'

    matches = re.findall(pattern, code)

    image_list.delete(0, "end")

    for img in matches:
        image_list.insert("end", img)


def replace_selected_image(editor, image_list):

    global last_uploaded_image

    if not last_uploaded_image:
        messagebox.showinfo("Info", "Upload image first")
        return

    try:
        selected = image_list.get(image_list.curselection())
    except:
        messagebox.showerror("Error", "Select image from list")
        return

    code = editor.get("1.0", "end")

    new_code = code.replace(selected, last_uploaded_image, 1)

    editor.delete("1.0", "end")
    editor.insert("end", new_code)

    messagebox.showinfo("Success", "Image replaced")