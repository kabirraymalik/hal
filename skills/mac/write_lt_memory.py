import os
import sys
import re
import json
from datetime import datetime
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from skill import Skill


def _normalize(text):
    return set(re.sub(r'[^\w\s]', '', text.lower()).split())


class WriteLtMemory(Skill):
    def __init__(self):
        super().__init__()
        self.name = "write_lt_memory"
        self.description = "Write a fact or piece of information to long-term memory"
        self.input = "string: the memory content to store"
        self.output = "string: 'written' or 'duplicate skipped'"
        self.context_builder = False
        self.time_out = 200
        self.tags = ["remember", "save", "store", "memory", "note", "fact", "learn", "write"]

    async def use(self, input_str=""):
        content = input_str.strip()
        if not content:
            return "nothing to write"

        memory_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "memory", "lt_memory.jsonl")

        existing = []
        try:
            with open(memory_file) as f:
                for line in f:
                    line = line.strip()
                    if line:
                        try:
                            existing.append(json.loads(line))
                        except json.JSONDecodeError:
                            pass
        except FileNotFoundError:
            pass

        new_words = _normalize(content)
        for entry in existing:
            existing_words = _normalize(entry.get("content", ""))
            if not existing_words:
                continue
            overlap = len(new_words & existing_words) / len(new_words | existing_words)
            if overlap > 0.8:
                return "duplicate skipped"

        record = {"content": content, "timestamp": datetime.now().strftime("%Y-%m-%dT%H:%M:%S")}
        with open(memory_file, "a") as f:
            f.write(json.dumps(record) + "\n")
        return "written"


if __name__ == "__main__":
    import asyncio
    skill = WriteLtMemory()
    print(asyncio.run(skill.use(sys.argv[1] if len(sys.argv) > 1 else "")))
