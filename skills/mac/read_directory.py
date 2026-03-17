"""Read directory contents and return file information.
    
    This function provides automated extraction of directory contents including
    metadata about files and subdirectories within a given path.

    Args:
        path (str): The path to the directory or file to read.
            Supports relative and absolute paths. Hidden entries are included.

    Returns:
        list[os.DirEntry[str]]: List of directory entry objects containing:
            - path: Full path to the item
"""

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
