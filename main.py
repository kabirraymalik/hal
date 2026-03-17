import sys
import os
import ollama
import time
import importlib
import asyncio
from pfc.DeBERTa import DeBERTaSmall, DeBERTaBase
from pfc.train import train_skill_selector
from utils import *
import config

def save_short_term_memory(prompt, response, x):
    try:
        with open(config.ST_MEMORY_DIR) as f:
            content = f.read()
        entries = [e.strip() for e in content.split("---") if e.strip()]
    except FileNotFoundError:
        entries = []
    entries.append(f"[PROMPT]: {prompt}\n[RESPONSE]: {response.strip()}")
    entries = entries[-x:]
    with open(config.ST_MEMORY_DIR, "w") as f:
        f.write("\n---\n".join(entries) + "\n")

def load_st_memory():
    try:
        with open(config.ST_MEMORY_DIR) as f:
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
        dbg(f"how????? unidentified platform: {sys.platform}")

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
    return input_list

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

async def build_context(executes, skills):
    context = ""
    for execution in executes:
        skill_name, skill_inputs = execution
        if skill_name not in skills:
            dbg(f"skill {skill_name} not found in compiled skills, skipping execution")
            continue
        for input_value in skill_inputs:
            try:
                output = await skills[skill_name].use(input_value)
                context = context + f"[EXECUTED {skill_name}({input_value})] WITH RESULT:\n{output}\n\n"
            except Exception as e:
                dbg(f"[ERROR: {skill_name}({input_value})] -> {e}")
                context = context + f"[FAILED TO EXECUTE {skill_name}({input_value})] WITH ERROR:\n{e}\n\n"
    return context

async def query(prompt):
    start_time = time.time()
    deberta_small = DeBERTaSmall()
    skills_necessary = deberta_small.predict(prompt) #TODO: async call to 2 headed DeBERTa for skill selection or bypass
    platform = get_platform()
    rag_guy, response_guy = select_models(platform)
    relevant_inputs = get_inputs()
    skills, skills_catalog = compile_skills(platform) # pre compiles skills into LLM-understandable exec options
    deberta_base = DeBERTaBase(skills.keys())
    context = ""
    while(deberta_small.is_thinking()):
        dbg("waitin on lil DeBERTa...")
        time.sleep(0.001)
    if(skills_necessary > config.SKILLS_RELEVANT_THRESHOLD):
        dbg("skills are relevant! selecting skills...")
        skill_relevances = deberta_base.predict(prompt)
        while(deberta_base.is_thinking()):
            dbg("waitin on big DeBERTa...")
            time.sleep(0.001)
        dbg("building context...")
        context_builder_executes = []
        for relevance in skill_relevances: # TODO: perhaps do a batch call for all skills? currently looping llama3.2:3b for each
            if relevance.value > config.SKILL_RELEVANT_THRESHOLD:
                dbg(f"selecting inputs for: {relevance.skill_name} with relevance {relevance.value}...")
                context_builder_executes.append([relevance.skill_name, select_inputs(prompt, relevance.skill_name, relevant_inputs, rag_guy)]) # [str: "skill_name", str[]: ["input1", "input2", ...]
        context = await build_context(context_builder_executes, skills) # [[str: "skill_name", str[]: ["input1", "input2", ...], [str: "skill_name", str[]: ["input1", "input2", ...], ...] -> str: "context"
    else:
        dbg("skills not relevant, skipping to agent loop...")
    dbg_context(context)
    st_memory = load_st_memory()

    system_prompt = (
        f"You are Hal, a local command line assistive agent."
        + (f"Short term memory:\n{st_memory}\n\n" if st_memory != "" else "")
        + f"AVAILABLE SKILLS: \n{skills_catalog}. Context so far: {context}\n"
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

        messages.append({"role": "assistant", "content": full_response})

        if "EXECUTE:" not in full_response:
            final_response = full_response
            break

        if not config.DEBUG:
            print(f"\033[{lines_printed}A\033[J", end="", flush=True)
        dbg(f"execute: {full_response.strip()}")
        for line in full_response.splitlines():
            if line.startswith("EXECUTE:"):
                parts = line.split("EXECUTE:", 1)[1].strip().split("|", 1)
                skill = parts[0].strip().strip("()[]\"'")
                input_arg = parts[1].strip().strip("()[]\"'") if len(parts) > 1 else ""
                if skill not in skills:
                    messages.append({"role": "user", "content": f"[{skill}]: ERROR: skill not found"})
                    continue
                output = await skills[skill].use(input_arg)
                dbg(f"[{skill}]: {output}")
                messages.append({"role": "user", "content": f"[{skill} result]: {output}"})
    end_time = time.time()
    print(f"\nresponse in {end_time - start_time:.2f}s.")
    if final_response:
        save_short_term_memory(prompt, final_response, config.SHORT_TERM_MEMORY_LEN) # last n interactions are remembered


if __name__ == "__main__":
    args = sys.argv[1:]
    if "-t" in args:
        train_skill_selector()
        args.remove("-t")
    if "-d" in args:
        config.DEBUG = True
        args.remove("-d")
    if "-v" in args:
        config.SHOW_CONTEXT = True
        args.remove("-v")
    
    prompt = " ".join(args)
    asyncio.run(query(prompt))