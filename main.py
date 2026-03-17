import sys
import os
import ollama
import subprocess
import time

import inspect
import ast

DEBUG = False
SHOW_CONTEXT = False

MEMORY_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "memory")

def save_short_term_memory(prompt, response, x):
    st_file = os.path.join(MEMORY_DIR, "st_memory.txt")
    try:
        with open(st_file) as f:
            content = f.read()
        entries = [e.strip() for e in content.split("---") if e.strip()]
    except FileNotFoundError:
        entries = []
    entries.append(f"[PROMPT]: {prompt}\n[RESPONSE]: {response.strip()}")
    entries = entries[-x:]
    with open(st_file, "w") as f:
        f.write("\n---\n".join(entries) + "\n")

def dbg(msg):
    if DEBUG:
        print(f"[dbg] {msg}", file=sys.stderr)

def dbg_context(msg):
    if SHOW_CONTEXT:
        print(f"[ctx] {msg}", file=sys.stderr)

def get_os():
    dbg(f"platform: {sys.platform}")
    if sys.platform == "win32":
        return "windows"
    elif sys.platform == "linux" or sys.platform == "linux2":
        return "linux"
    elif sys.platform == "darwin":
        return "mac"
    else:
        dbg("unrecognized platform")

def get_skills(skills_dir):
    skill_docstring = "NULL"
    skills = []
    for filename in os.listdir(skills_dir):
        if filename.endswith(".py") or filename.endswith(".sh"):
            skill_path = os.path.join(skills_dir, filename)
            with open(skill_path) as f:
                code = f.read()
                tree = ast.parse(code)
                for node in ast.walk(tree):
                    if isinstance(node, ast.FunctionDef):
                        docstring = inspect.getdoc(node)
                        skill_docstring = "NULL"
                        if docstring:
                            skill_docstring = docstring
                            print(f"{node.name}: {docstring}")
            skill_name = os.path.splitext(filename)[0]
            skills.append([skill_name, skill_docstring])
    return skills

def get_repos():
    repos = []
    cwd = os.getcwd()
    for repo in os.listdir(cwd):
        if os.path.isdir(os.path.join(cwd, repo)):
            repos.append(repo)
    return repos

def select_models(operating_system):
    if operating_system == "windows":
        return "null", "null" # TODO: define and tune
    elif operating_system == "linux":
        return "devstral_small", "devstral_large" # TODO: define and tune
    elif operating_system == "mac":
        # return "qwen3:4b", "qwen3:30b-a3b"
        return "llama3.2:3b", "rnj-1" # "gemma3:4b"
    return "null", "null"

NO_INPUT_SKILLS = {"read_system_info", "read_skills"}

def select_skills(prompt, skills_list, repos_list, skill_picker_model):
    input_skills = [s for s in skills_list if s not in NO_INPUT_SKILLS]
    system_prompt = (
        f"Your job is to pick the best set of skill, input combinations to respond to a prompt. "
        f"Available skills with zero inputs: {NO_INPUT_SKILLS} "
        f"Available skills with one input: {input_skills}. Available repositories: {repos_list}. "
        f"For each relevant skill/argument pair, print it, one skill per line. "
        f"Format: skill|arg1. No markdown, no bullets, no explanation, no extra text."
    )
    dbg(f"skills: {skills_list}")
    dbg(f"repos: {repos_list}")

    no_think_flag = ""
    if skill_picker_model == "qwen3:4b":
        no_think_flag = " /no_think"
    response = ollama.chat(
        model=skill_picker_model,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": prompt + no_think_flag}
        ],
    )
    content = response["message"]["content"].strip()
    pairs = []
    for line in content.splitlines():
        line = line.strip()
        if "|" in line:
            skill, repos_str = line.split("|", 1)
            skill = skill.strip().lstrip("-• ").strip("()[]\"'")
            if skill not in skills_list:
                print(f"warning: skill '{skill}' not found")
                continue
            for repo in repos_str.split(","):
                pairs.append((skill, repo.strip().strip("()[]\"'")))
    return pairs

def compile_skills(skills_list):
    skills = ""
    for skill in skills_list:
        skills = skills + f"{skill[0]}: {skill[1]}\n"
    return skills


def query(prompt):
    start_time = time.time()
    operating_system = get_os()
    skill_picker_model, response_model = select_models(operating_system)
    skills_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "skills", operating_system)
    skills_list = get_skills(skills_dir)
    repos_list = get_repos()
    #dbg("selecting skills...")
    #relevant_skills = select_skills(prompt, skills_list, repos_list, skill_picker_model)
    #relevant_skills.append(("read_lt_memory", prompt))
    #dbg(f"selected: {relevant_skills}")
    context = "" # build_context(skills_list, skills_dir)
    compiled_skills = compile_skills(skills_list)
    dbg_context(context)
    st_file = os.path.join(MEMORY_DIR, "st_memory.txt")
    try:
        with open(st_file) as f:
            st_memory = f.read().strip()
    except FileNotFoundError:
        st_memory = ""

    system_prompt = (
        f"You are Hal, a local command line assistive agent."
        + (f"Short term memory:\n{st_memory}\n\n" if st_memory != "" else "")
        + f"AVAILABLE SKILLS: \n{compiled_skills}. Context so far: {context}\n"
        f"To run a skill, respond with EXECUTE: skill|input. The output will be added to context. "
        f"Loop until you have enough to respond, and after building context reply to prompt in a concise and direct manner. "
        f"Ensure your final response to the user always makes sense directly following the prompt, and end responses with :3."
    )
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": prompt}
    ]
    dbg(f"--- system prompt ---\n{system_prompt}\n--- user prompt ---\n{prompt}\n---")
    final_response = ""
    for _ in range(20):
        full_response = ""
        lines_printed = 0
        for chunk in ollama.chat(model=response_model, messages=messages, stream=True):
            content = chunk["message"]["content"]
            full_response += content
            print(content, end="", flush=True)
            lines_printed += content.count("\n")
        print()
        lines_printed += 1

        messages.append({"role": "user", "content": full_response})

        if "EXECUTE:" not in full_response:
            final_response = full_response
            break

        if not DEBUG:
            print(f"\033[{lines_printed}A\033[J", end="", flush=True)
        dbg(f"execute: {full_response.strip()}")
        for line in full_response.splitlines():
            if line.startswith("EXECUTE:"):
                parts = line.split("EXECUTE:", 1)[1].strip().split("|", 1)
                skill = parts[0].strip().strip("()[]\"'")
                input_arg = parts[1].strip().strip("()[]\"'") if len(parts) > 1 else ""
                skill_path = os.path.join(skills_dir, f"{skill}.py")
                if not os.path.exists(skill_path):
                    messages.append({"role": "user", "content": f"[{skill}]: skill not found"})
                    continue
                result = subprocess.run(["python3", skill_path, input_arg], capture_output=True, text=True)
                output = result.stdout.strip() or result.stderr.strip() or "(no output)"
                dbg(f"[{skill}]: {output}")
                messages.append({"role": "user", "content": f"[{skill} result]: {output}"})
    end_time = time.time()
    print(f"\nresponse in {end_time - start_time:.2f}s.")
    if final_response:
        save_short_term_memory(prompt, final_response, 5) # last 5 interactions are remembered


if __name__ == "__main__":
    args = sys.argv[1:]
    if "-d" in args:
        DEBUG = True
        args.remove("-d")
    if "-v" in args:
        SHOW_CONTEXT = True
        args.remove("-v")
    prompt = " ".join(args)
    query(prompt)