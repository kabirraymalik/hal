import os
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from skill import Skill, SkillData


class ReadPath(Skill):
    def __init__(self):
        super().__init__()
        self.name = "read_path"
        self.description = "Read the contents of a file or list the contents of a directory"
        self.input = "string: file or directory path (absolute, relative, or ~-prefixed)"
        self.output = "string: file contents (truncated if large), or directory listing with [file]/[dir] tags per entry"
        self.time_out = 500

        self.datagen = SkillData()
        self.datagen.tags = [
            "read", "file", "directory", "list", "contents", "open",
            "cat", "ls", "path", "folder", "show", "view", "look",
            "tree", "readme", "config", "log", "source", "code",
            "text", "script", "json", "yaml", "csv"
        ]
        self.datagen.complementary_skills = ["read_git_status", "read_system_info"]
        self.datagen.confusion_skills = ["read_git_status", "read_system_info", "read_clipboard"]
        self.datagen.usage_hints = [
            "Triggers when the user wants to see the contents of a specific file or the listing of a directory",
            "'What's in this folder' is read_path. 'What directory am I in' is read_system_info — contents vs. location",
            "'Show me the project' or 'what's in this repo' often means a directory listing, but if the user is asking about project health/status it could be read_git_status instead",
            "'What have I changed' in a project context is read_git_status, not read_path — even though both involve files",
            "'Read my config' or 'show me .zshrc' is read_path. 'What shell am I using' is read_system_info",
            "Should NOT trigger for 'what's on my clipboard' or 'look at what I copied' — those are read_clipboard even though they use 'look at' / 'show me' phrasing",
            "Should NOT trigger for general questions about file systems or formats — 'what is a .json file' is a knowledge question",
        ]
        self.datagen.example_prompts = [
            "what's in this directory",
            "show me the files in ~/Documents",
            "read my .zshrc",
            "cat the readme",
            "what's in the src folder",
            "list everything in this project",
            "open my config file",
            "show me the contents of package.json",
            "what files are in ~/Downloads",
            "read the log file",
            "what's in main.py",
            "ls my home directory",
            "show me what's in this folder",
            "can you read ~/notes.txt for me",
            "what does my .gitignore look like",
        ]
        self.datagen.wrong_skill_prompts = [
            "what branch am I on",                       # read_git_status
            "do I have uncommitted changes",             # read_git_status
            "show me recent commits",                    # read_git_status
            "what directory am I in",                    # read_system_info (location, not contents)
            "what OS am I running",                      # read_system_info
            "what time is it",                           # read_system_info
            "what's on my clipboard",                    # read_clipboard
            "look at what I just copied",                # read_clipboard
            "do you remember my preferences",            # read_lt_memory
            "what conda environment am I in",            # read_env_vars
            "what's in my .env file",                    # this IS read_path — included as a note
        ]
        self.datagen.no_skill_prompts = [
            "what is a file system",
            "explain the difference between absolute and relative paths",
            "how do I create a new file in python",
            "what's a good text editor",
            "write me a script that reads a csv",
            "how does ls work",
            "what is json format",
            "explain file permissions on unix",
        ]

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
                if len(lines) > 100:
                    truncated = lines[:100]
                    truncated.append(f"... and {len(lines) - 100} more entries")
                    return "\n".join(truncated)
                return "\n".join(lines)
            elif os.path.isfile(path):
                size = os.path.getsize(path)
                if size > 50000:
                    with open(path) as f:
                        content = f.read(50000)
                    return content + f"\n... (truncated, {size} bytes total)"
                with open(path) as f:
                    return f.read()
            else:
                return f"error: path not found: {path}"
        except (PermissionError, IsADirectoryError, UnicodeDecodeError) as ex:
            return f"error: {ex}"


if __name__ == "__main__":
    import asyncio
    skill = ReadPath()
    print(asyncio.run(skill.use(sys.argv[1] if len(sys.argv) > 1 else ".")))