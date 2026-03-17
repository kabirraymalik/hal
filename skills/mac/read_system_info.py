import os
import sys
import platform
import subprocess
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from skill import Skill


class ReadSystemInfo(Skill):
    def __init__(self):
        super().__init__()
        self.name = "read_system_info"
        self.description = "Read system information including OS, hardware, Python version, and working directory"
        self.input = "string: unused"
        self.output = "string: system info lines (os, machine, python, cwd, ram)"
        self.context_builder = False
        self.time_out = 200
        self.tags = ["system", "os", "hardware", "ram", "machine", "info", "platform", "cwd", "environment"]

    async def use(self, _=""):
        lines = [
            f"os: {platform.system()} {platform.release()}",
            f"machine: {platform.machine()}",
            f"python: {platform.python_version()}",
            f"cwd: {os.getcwd()}",
        ]
        ram = subprocess.run(["sysctl", "-n", "hw.memsize"], capture_output=True, text=True)
        if ram.stdout:
            gb = int(ram.stdout.strip()) // (1024 ** 3)
            lines.append(f"ram: {gb}GB")
        return "\n".join(lines)


if __name__ == "__main__":
    import asyncio
    skill = ReadSystemInfo()
    print(asyncio.run(skill.use()))
