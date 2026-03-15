import sys, os

path = sys.argv[1] if len(sys.argv) > 1 else "."
path = os.path.expanduser(path)

try:
    if os.path.isdir(path):
        entries = os.listdir(path)
        for e in sorted(entries):
            full = os.path.join(path, e)
            tag = "[dir]" if os.path.isdir(full) else "[file]"
            print(f"{tag} {e}")
    elif os.path.isfile(path):
        with open(path) as f:
            print(f.read())
    else:
        print(f"error: path not found: {path}")
except (PermissionError, IsADirectoryError) as ex:
    print(f"error: {ex}")
