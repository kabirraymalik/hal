import os
import sys
import subprocess
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from skill import Skill, SkillData


class ReadClipboard(Skill):
    def __init__(self):
        super().__init__()
        self.name = "read_clipboard"
        self.description = "Read the current contents of the system clipboard"
        self.input = "string: unused"
        self.output = "string: clipboard contents, or '(clipboard empty)'"
        self.time_out = 200

        self.datagen = SkillData()
        self.datagen.tags = [
            "clipboard", "paste", "copied", "copy", "pbpaste",
            "just copied", "selection", "cut", "clipped"
        ]
        self.datagen.complementary_skills = ["read_path", "read_lt_memory"]
        self.datagen.confusion_skills = ["read_path", "read_lt_memory"]
        self.datagen.usage_hints = [
            "Triggers when the user references something they just copied or have on their clipboard — even without using the word 'clipboard'",
            "'Look at this', 'check this out', 'what do you think of this' with no attachment or path are strong clipboard signals — the user likely copied something and expects hal to see it",
            "'What did I just copy' is clipboard. 'What did I just write' could be clipboard or read_lt_memory depending on context",
            "Prompts asking hal to format, explain, debug, translate, or summarize something unspecified often imply clipboard contents",
            "Should NOT trigger when the user provides the content inline — if the prompt itself contains the text to analyze, clipboard is redundant",
            "Should NOT trigger for questions about how copy/paste works or clipboard managers — only for reading THIS clipboard's current contents",
        ]
        self.datagen.example_prompts = [
            "what's on my clipboard",
            "paste what I copied",
            "look at what I just copied",
            "explain this code I copied",
            "can you format this for me",
            "debug this",
            "what did I just copy",
            "translate what's on my clipboard",
            "I copied an error message, can you help",
            "check this out",
            "summarize what I just copied",
            "I copied a url, where does it go",
            "fix the syntax in what I copied",
            "what language is this code I copied",
            "clean up this text for me",
        ]
        self.datagen.wrong_skill_prompts = [
            "show me the contents of this file",         # read_path
            "what's in my downloads folder",             # read_path
            "read my config file",                       # read_path
            "what's in ~/notes.txt",                     # read_path
            "what do you remember about me",             # read_lt_memory
            "what's my preferred editor",                # read_lt_memory
            "what did I tell you earlier",               # read_lt_memory (not clipboard)
            "what branch am I on",                       # read_git_status
            "do I have uncommitted changes",             # read_git_status
        ]
        self.datagen.no_skill_prompts = [
            "how does the clipboard work on macOS",
            "what's a good clipboard manager app",
            "explain the difference between copy and cut",
            "write a python script that copies text to clipboard",
            "how do I use pbcopy in a shell script",
            "what is the system clipboard API on mac",
            "fix this code: print('hello world')",       # content provided inline, no clipboard needed
            "summarize the french revolution",           # topic provided inline
        ]

    async def use(self, _=""):
        result = subprocess.run(
            ["pbpaste"],
            capture_output=True, text=True, timeout=2
        )
        content = result.stdout
        if not content or not content.strip():
            return "(clipboard empty)"
        max_chars = 5000 # truncate when clipboard contents is large to keep context manageable
        if len(content) > max_chars:
            return content[:max_chars] + f"\n... (truncated, {len(content)} total characters)"
        return content


if __name__ == "__main__":
    import asyncio
    skill = ReadClipboard()
    print(asyncio.run(skill.use()))