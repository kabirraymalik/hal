import os
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from skill import Skill


class ReadSkills(Skill):
    def __init__(self):
        super().__init__()
        self.name = "read_skills"
        self.description = "List all available skills"
        self.input = "string: unused"
        self.output = "string: newline-separated list of skill names"
        self.context_builder = False
        self.time_out = 100
        self.tags = ["skills", "list", "available", "capabilities", "what can you do"]

    async def use(self, _=""):
        skills_dir = os.path.dirname(os.path.abspath(__file__))
        skills = [os.path.splitext(f)[0] for f in os.listdir(skills_dir)
                  if f.endswith(".py") or f.endswith(".sh")]
        return "\n".join(skills)


if __name__ == "__main__":
    import asyncio
    skill = ReadSkills()
    print(asyncio.run(skill.use()))
