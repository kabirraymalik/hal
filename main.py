import sys
import os
import ollama
import subprocess
import time
import importlib
import inspect
import ast
import pfc.DeBERTa as DeBERTa
from pfc.train import train_skill_selector
from utils import *

# Hyperparams
SKILLS_RELEVANT_THRESHOLD = 0.7
SKILL_RELEVANT_THRESHOLD = 0.5
SHORT_TERM_MEMORY_LEN = 3
DEBUG = False
SHOW_CONTEXT = False
HAL_DIR = os.path.dirname(os.path.abspath(__file__))

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

def load_st_memory():
    st_file = os.path.join(MEMORY_DIR, "st_memory.txt")
    try:
        with open(st_file) as f:
            st_memory = f.read().strip()
    except FileNotFoundError:
        st_memory = ""
    return st_memory

def get_platform():
    dbg(f"platform: {sys.platform}")
    if sys.platform == "win32":
        return "windows"
    elif sys.platform.startswith("linux"):
        return "linux"
    elif sys.platform == "darwin":
        return "mac"
    else:
        dbg("unrecognized platform")

def get_dirs_in_dir():
    repos = []
    cwd = os.getcwd()
    for repo in os.listdir(cwd):
        if os.path.isdir(os.path.join(cwd, repo)):
            repos.append(repo)
    return repos

def get_inputs(): # placeholder, TODO: develop live input group
    inputs = []
    inputs = inputs + get_dirs_in_dir()
    return inputs

def select_inputs(prompt, skill_name, relevant_inputs, skill_picker_model): # TODO: optimize with batch call instead of looping through skills? see query() loop
    system_prompt = (
        f"You are an input selector for skills. Your job is to, based on a prompt, a relevant skill, and a set of inputs:"
        f"Determine the best set of inputs to apply the skill to. These inputs should be selected based on relevance to the prompt and skill."
        f"Skill: {skill_name}. Available inputs: {relevant_inputs}. Simply respond with a comma-separated list of the best inputs to use for the skill."
        f"Format: 'input1, input2, input3', where the string inputx is included among available inputs. No markdown, no bullets, no explanation, no extra text."
    )
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
    input_list = []
    for i in content.split(","):
        i = i.strip().strip("\"'")
        if i and i in relevant_inputs:
            input_list.append(i)
    dbg(f"selected skill {skill_name} to use on {input_list}")
    return [skill_name, input_list]


def get_skills(platform):
    skills_dir = os.path.join(HAL_DIR, "skills", platform)
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

def compile_skills(platform):
    module = importlib.import_module(f"skills.{platform}")
    skills = {}
    catalog_lines = []

    for cls in module.SKILLS:
        instance = cls()
        skills[instance.name] = instance
        catalog_lines.append(
            f"SKILL: {instance.name}\n"
            f"  {instance.description}\n"
            f"  Input: {instance.input}\n"
            f"  Output: {instance.output}"
        )

    catalog = "\n".join(catalog_lines)
    return skills, catalog

def build_context(executes):
    context = ""
    for exec in executes:
        skill_name, inputs = exec
        for input in inputs:
            # TODO: clean inputs, error check per skill?
            context = context + f"[ran {skill_name} on {input}]\n" # TODO: run skill, add output
    return context

def query(prompt):
    start_time = time.time()
    deberta = DeBERTa()
    skill_relevances, skills_necessary = deberta.query(prompt) #TODO: async call to 2 headed DeBERTa for skill selection or bypass
    platform = get_platform()
    rag_guy, response_guy = select_models(platform)
    relevant_inputs = get_inputs()
    compiled_skills = compile_skills(platform) # pre compiles skills into LLM-understandable exec options
    context = ""
    while(deberta.is_thinking()):
        dbg("waitin on big DeBERTa...")
        time.sleep(0.001)
    if(skills_necessary > SKILLS_RELEVANT_THRESHOLD):
        dbg("skills are relevant! selecting skills and building context...")
        context_builder_executes = []
        for relevance in skill_relevances: # TODO: perhaps do a batch call for all skills?
            if relevance.value > SKILL_RELEVANT_THRESHOLD:
                dbg(f"selecting inputs for: {relevance.skill_name} with relevance {relevance.value}...")
                context_builder_executes.append([relevance.skill_name, select_inputs(prompt, relevance.skill_name, relevant_inputs)]) # [str: "skill_name", str[]: ["input1", "input2", ...]
        context = build_context(context_builder_executes) # [[str: "skill_name", str[]: ["input1", "input2", ...], [str: "skill_name", str[]: ["input1", "input2", ...], ...] -> str: "context"
    else:
        dbg("skills not relevant, skipping to agent loop...")
    dbg_context(context)
    st_memory = load_st_memory()

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
        for chunk in ollama.chat(model=response_guy, messages=messages, stream=True):
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
                skill_path = os.path.join(os.path.join(HAL_DIR, platform, "skills"), f"{skill}.py")
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
        save_short_term_memory(prompt, final_response, SHORT_TERM_MEMORY_LEN) # last 3 interactions are remembered


if __name__ == "__main__":
    args = sys.argv[1:]
    if "-t" in args:
        train_skill_selector()
        args.remove("-t")
    if "-d" in args:
        DEBUG = True
        args.remove("-d")
    if "-v" in args:
        SHOW_CONTEXT = True
        args.remove("-v")
    
    prompt = " ".join(args)
    query(prompt)