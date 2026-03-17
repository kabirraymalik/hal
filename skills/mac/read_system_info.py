import os
import sys
import platform
import subprocess
import getpass
from datetime import datetime
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from skill import Skill, SkillData


class ReadSystemInfo(Skill):
    def __init__(self):
        super().__init__()
        self.name = "read_system_info"
        self.description = "Read current system status including OS, hardware, time, shell, network, battery, disk, and working directory"
        self.input = "string: unused"
        self.output = "string: system status lines covering os, machine, cpu, ram, disk, battery, network, shell, python, user, cwd, and current datetime"
        self.time_out = 500

        self.datagen = SkillData()
        self.datagen.tags = [
            "system", "os", "hardware", "ram", "machine", "info", "platform",
            "cwd", "environment", "time", "date", "battery", "disk", "storage",
            "network", "wifi", "shell", "cpu", "user", "username", "directory",
            "clock", "today", "space", "connected"
        ]
        self.datagen.complementary_skills = ["read_path", "read_lt_memory"]
        self.datagen.confusion_skills = ["read_path"]
        self.datagen.usage_hints = [
            "This skill provides a snapshot of the machine's current state — it answers 'what is my system like right now', not 'what is in this folder'",
            "Time and date queries ('what time is it', 'what's today's date') should trigger this skill",
            "Questions about the current working directory trigger this skill, but questions about the contents of a directory trigger read_path instead",
            "'What directory am I in' is read_system_info. 'What's in this directory' is read_path. The distinction is location vs. contents",
            "Battery, network, and disk queries are system status — even if phrased casually like 'am I connected' or 'do I have space'",
            "Should NOT trigger for general knowledge about operating systems ('what is macOS') — only for querying THIS machine's state",
        ]
        self.datagen.example_prompts = [
            "what time is it",
            "what's today's date",
            "what OS am I running",
            "how much RAM does this machine have",
            "what directory am I in right now",
            "how much disk space do I have left",
            "am I connected to the internet",
            "what's my battery at",
            "what shell am I using",
            "what python version is installed",
            "what's my username on this machine",
            "give me a quick system overview",
            "is my laptop plugged in",
            "what cpu does this machine have",
            "what's the current date and time",
        ]
        self.datagen.wrong_skill_prompts = [
            "what files are in my home directory",       # read_path
            "show me the contents of ~/.zshrc",          # read_path
            "list everything in ~/Documents",            # read_path
            "what's in this folder",                     # read_path
            "read my config file",                       # read_path
            "what's my name",                            # read_lt_memory
            "do you remember my preferences",            # read_lt_memory
            "what editor do I like",                     # read_lt_memory
        ]
        self.datagen.no_skill_prompts = [
            "what is linux",
            "explain the difference between ARM and x86",
            "how do I install homebrew",
            "what's a good terminal emulator",
            "write me a bash script",
            "how does RAM work",
            "what is a CPU cache",
            "compare macOS and windows",
        ]

    async def use(self, _=""):
        lines = [
            f"datetime: {datetime.now().strftime('%Y-%m-%d %H:%M:%S %Z').strip()}",
            f"os: {platform.system()} {platform.release()} ({platform.mac_ver()[0]})",
            f"machine: {platform.machine()}",
            f"user: {getpass.getuser()}",
            f"shell: {os.environ.get('SHELL', 'unknown')}",
            f"python: {platform.python_version()}",
            f"cwd: {os.getcwd()}",
        ]

        cpu = subprocess.run(["sysctl", "-n", "machdep.cpu.brand_string"], capture_output=True, text=True)
        if cpu.stdout.strip():
            lines.append(f"cpu: {cpu.stdout.strip()}")
        cores = subprocess.run(["sysctl", "-n", "hw.ncpu"], capture_output=True, text=True)
        if cores.stdout.strip():
            lines.append(f"cores: {cores.stdout.strip()}")
        ram = subprocess.run(["sysctl", "-n", "hw.memsize"], capture_output=True, text=True)
        if ram.stdout.strip():
            gb = int(ram.stdout.strip()) // (1024 ** 3)
            lines.append(f"ram: {gb}GB")
        try:
            stat = os.statvfs("/")
            total = (stat.f_blocks * stat.f_frsize) // (1024 ** 3)
            free = (stat.f_bavail * stat.f_frsize) // (1024 ** 3)
            lines.append(f"disk: {free}GB free / {total}GB total")
        except OSError:
            pass
        battery = subprocess.run(["pmset", "-g", "batt"], capture_output=True, text=True)
        if battery.stdout:
            for bline in battery.stdout.splitlines():
                if "%" in bline:
                    # extract percentage and charging status
                    parts = bline.strip().split(";")
                    pct = bline.split("%")[0].split()[-1] + "%"
                    status = parts[1].strip() if len(parts) > 1 else "unknown"
                    lines.append(f"battery: {pct} ({status})")
                    break
        net = subprocess.run(["networksetup", "-getairportnetwork", "en0"], capture_output=True, text=True)
        if net.stdout.strip() and "not associated" not in net.stdout.lower():
            ssid = net.stdout.strip().split(":", 1)[-1].strip()
            lines.append(f"wifi: {ssid}")
        else:
            lines.append("wifi: disconnected")
        return "\n".join(lines)


if __name__ == "__main__":
    import asyncio
    skill = ReadSystemInfo()
    print(asyncio.run(skill.use()))