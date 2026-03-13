import sys, os

content = sys.argv[1] if len(sys.argv) > 1 else ""
memory_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "memory.txt")
with open(memory_file, "a") as f:
    f.write(content + "\n")