import sys
import json
from skill import Skill, SkillData
from ...config import LT_MEMORY_DIR

class ReadLtMemory(Skill):
    def __init__(self):
        super().__init__()
        self.name = "read_lt_memory"
        self.description = "Search long-term memory for facts relevant to a query"
        self.input = "string: query to search memory against"
        self.output = "string: matching memory entries as 'content (timestamp)' lines, or '(no matching memory)'"
        self.time_out = 200

        self.datagen = SkillData()
        self.datagen.tags = ["memory", "recall", "remember", "fact", "know", "lookup", "retrieve", "forgot", "told", "said", "mentioned", "preference"]
        self.datagen.complementary_skills = ["read_system_info"]
        self.datagen.confusion_skills = ["write_lt_memory"]
        self.datagen.usage_hints = [
            "Triggers when the user references something they expect hal to already know — prior preferences, personal facts, or past corrections",
            "The word 'remember' is ambiguous: 'do you remember X' is a read, 'remember that X' is a write",
            "Implicit recall is common: 'what editor do I use' assumes hal was told before, even without the word 'remember'",
            "Questions phrased as identity or preference ('what's my name', 'which model do I prefer') are reads, not writes",
            "Should NOT trigger for general knowledge questions — 'what is python' is not a memory lookup even though it starts with 'what is'",
        ]
        self.datagen.example_prompts = [
            "what's my name",
            "meowwww",
            "do you remember my birthday",
            "what editor do I prefer",
            "who is sud?",
            "who is elen?",
            "what did I tell you about josh",
            "which ollama model do I like for fast tasks",
            "ligma",
            "do you know where my work repo is",
            "what are my preferences",
            "mreowwww :33"
            "what do you know about me",
            "who is my favorite rapper",
            "what's my shell config path",
            "remind me what programming language I default to",
        ]
        self.datagen.wrong_skill_prompts = [
            "my name is kabir",                         # write_lt_memory, not read
            "remember that I prefer dark mode",         # write_lt_memory
            "note that my project is at ~/dev/hal",     # write_lt_memory
            "keep in mind I hate emojis",               # write_lt_memory
            "show me what's in ~/Documents",            # read_path
            "what files are in this directory",          # read_path
            "what OS am I running",                     # read_system_info
            "how much RAM does this machine have",      # read_system_info
        ]
        self.datagen.no_skill_prompts = [
            "what is the capital of france",
            "explain how neural networks work",
            "write a python function that reverses a string",
            "what's 2 + 2",
            "tell me a joke",
            "how do I install pytorch",
            "what's the difference between TCP and UDP",
            "who won the 2024 election",
        ]

    async def use(self, input_str=""):
        query = input_str.lower().strip()
        entries = []
        try:
            with open(LT_MEMORY_DIR) as f:
                for line in f:
                    line = line.strip()
                    if line:
                        try:
                            entries.append(json.loads(line))
                        except json.JSONDecodeError:
                            pass
        except FileNotFoundError:
            pass

        tokens = query.split()
        matches = [e for e in entries if any(t in e.get("content", "").lower() for t in tokens)]
        if not matches:
            return "(no matching memory)"
        return "\n".join(f"{e['content']} ({e.get('timestamp', '')})" for e in matches)


if __name__ == "__main__":
    import asyncio
    skill = ReadLtMemory()
    print(asyncio.run(skill.use(sys.argv[1] if len(sys.argv) > 1 else "")))