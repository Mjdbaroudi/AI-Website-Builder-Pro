import os

def save_files(folder, files):
    for name, content in files.items():
        if content.strip():
            with open(os.path.join(folder,name),
                      "w",encoding="utf-8") as f:
                f.write(content)

def load_file(path):
    with open(path,"r",encoding="utf-8") as f:
        return f.read()

def list_files(folder):
    return os.listdir(folder)