import os
import sys
import json
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from skill import Skill


class ReadLtMemory(Skill):
    def __init__(self):
        super().__init__()
        self.name = "read_lt_memory"
        self.description = "Search long-term memory for facts relevant to a query"
        self.input = "string: query to search memory against"
        self.output = "string: matching memory entries as 'content (timestamp)' lines, or '(no matching memory)'"
        self.context_builder = True
        self.time_out = 200
        self.tags = ["memory", "recall", "remember", "fact", "know", "lookup", "retrieve"]

    async def use(self, input_str=""):
        query = input_str.lower().strip()
        memory_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "memory", "lt_memory.jsonl")

        entries = []
        try:
            with open(memory_file) as f:
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
