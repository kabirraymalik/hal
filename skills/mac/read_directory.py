import sys, os

path = sys.argv[1] if len(sys.argv) > 1 else "."
path = os.path.expanduser(path)

try:
    entries = os.listdir(path)
    for e in sorted(entries):
        full = os.path.join(path, e)
        tag = "[dir]" if os.path.isdir(full) else "[file]"
        print(f"{tag} {e}")
except (FileNotFoundError, PermissionError) as ex:
    print(f"error: {ex}")
