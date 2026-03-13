import sys, os

query = sys.argv[1].lower() if len(sys.argv) > 1 else ""
memory_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "memory", "lt_memory.txt")

try:
    with open(memory_file) as f:
        lines = f.readlines()
except FileNotFoundError:
    lines = []

tokens = query.split()
matches = [l.strip() for l in lines if any(t in l.lower() for t in tokens)]
print("\n".join(matches) if matches else "(no matching memory)")
