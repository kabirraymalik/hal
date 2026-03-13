import os

skills_dir = os.path.dirname(os.path.abspath(__file__))
skills = [os.path.splitext(f)[0] for f in os.listdir(skills_dir)
          if f.endswith(".py") or f.endswith(".sh")]

print("\n".join(skills))
