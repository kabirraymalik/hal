import os
import platform
import subprocess

print(f"os: {platform.system()} {platform.release()}")
print(f"machine: {platform.machine()}")
print(f"python: {platform.python_version()}")
print(f"cwd: {os.getcwd()}")

ram = subprocess.run(["sysctl", "-n", "hw.memsize"], capture_output=True, text=True)
if ram.stdout:
    gb = int(ram.stdout.strip()) // (1024 ** 3)
    print(f"ram: {gb}GB")
