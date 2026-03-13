import sys, os, re

def normalize(text):
    return set(re.sub(r'[^\w\s]', '', text.lower()).split())

content = sys.argv[1] if len(sys.argv) > 1 else ""
if not content.strip():
    sys.exit(0)

memory_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "memory.txt")

try:
    with open(memory_file) as f:
        existing = f.readlines()
except FileNotFoundError:
    existing = []

new_words = normalize(content)
for line in existing:
    existing_words = normalize(line)
    if not existing_words:
        continue
    overlap = len(new_words & existing_words) / len(new_words | existing_words)
    if overlap > 0.8: #TODO: tune
        print(f"duplicate skipped")
        sys.exit(0)

with open(memory_file, "a") as f:
    f.write(content + "\n")
print(f"written")
