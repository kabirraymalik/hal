import os
from skill import Skill


class ReadPath(Skill):
    def __init__(self):
        super().__init__()
        self.name = "read_path"
        self.description = "Read the contents of a file or list the contents of a directory"
        self.input = "string: file or directory path (absolute, relative, or ~-prefixed)"
        self.output = "string: file contents, or directory listing with [file]/[dir] tags per entry"
        self.context_builder = True
        self.time_out = 500
        self.tags = ["read", "file", "directory", "list", "contents", "open", "cat", "ls", "path", "folder"]

    async def use(self, input_str=""):
        path = input_str.strip().strip("\"'")
        path = os.path.expanduser(path) if path else "."
        if not os.path.isabs(path):
            path = os.path.join(os.getcwd(), path)
        try:
            if os.path.isdir(path):
                entries = os.listdir(path)
                lines = []
                for e in sorted(entries):
                    tag = "[dir]" if os.path.isdir(os.path.join(path, e)) else "[file]"
                    lines.append(f"{tag} {e}")
                return "\n".join(lines)
            elif os.path.isfile(path):
                with open(path) as f:
                    return f.read()
            else:
                return f"error: path not found: {path}"
        except (PermissionError, IsADirectoryError) as ex:
            return f"error: {ex}"


if __name__ == "__main__":
    import sys, asyncio
    skill = ReadPath()
    print(asyncio.run(skill.use(sys.argv[1] if len(sys.argv) > 1 else ".")))