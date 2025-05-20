import os

def scan_files(root_dir, exts=(".py",)):
    files = []
    for dirpath, _, filenames in os.walk(root_dir):
        for fname in filenames:
            if fname.endswith(exts):
                files.append(os.path.join(dirpath, fname))
    return files 