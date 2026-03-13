import sys
import os
import ollama
import subprocess
import time

def get_os():
    print(f"sys.platform identifier: {sys.platform}")
    if sys.platform == "win32":
        print("Running on Windows")
        return "windows"
    elif sys.platform == "linux" or sys.platform == "linux2":
        print("Running on Linux")
        return "linux"
    elif sys.platform == "darwin":
        print("Running on macOS")
        return "mac"
    else:
        print("HUH")

def get_skills(skills_dir):
    skills = []
    for filename in os.listdir(skills_dir):
        if filename.endswith(".py") or filename.endswith(".sh"):
            skill_name = os.path.splitext(filename)[0]
            skills.append(skill_name)
    return skills

def get_repos():
    repos = []
    cwd = os.getcwd()
    for repo in os.listdir(cwd):
        full_path = os.path.join(cwd, repo)
        repos.append(repo)
    return repos

def select_models(operating_system):
    if operating_system == "windows":
        return "null", "null" # TODO: define and tune
    elif operating_system == "linux":
        return "devstral_small", "devstral_large" # TODO: define and tune
    elif operating_system == "mac":
        # return "qwen3:4b", "qwen3:30b-a3b"
        return "qwen3:4b", "qwen3:4b"
    return "null", "null"

def select_skills(prompt, skills_list, repos_list, skill_picker_model):
    system_prompt = (
        f"You are a skill picker. Available skills: {skills_list}. "
        f"Available repositories: {repos_list}. "
        f"If any skills are relevant, return it with the repos it applies to, one skill per line. "
        f"Format: skill|repo1,repo2. No explanation, no extra text. Always respond with at least 1 skill." #If no relevant skills, return empty."
    )
    print(skills_list)
    print(repos_list)

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
            for repo in repos_str.split(","):
                pairs.append((skill.strip(), repo.strip()))
    return pairs

def build_context(relevant_skills, skills_dir):
    context = ""
    for skill, repo in relevant_skills:
        skill_path = os.path.join(skills_dir, f"{skill}.py")
        result = subprocess.run(["python3", skill_path, repo], capture_output=True, text=True)
        if result.stdout:
            context += f"[{skill} on {repo}]:\n{result.stdout}\n"
    return context

def query(prompt):
    start_time = time.time()
    print("started\n")
    operating_system = get_os()
    skill_picker_model, response_model = select_models(operating_system)
    skills_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "skills", operating_system)
    skills_list = get_skills(skills_dir)
    repos_list = get_repos()
    print("got skills and repos\n")
    relevant_skills = select_skills(prompt, skills_list, repos_list, skill_picker_model)
    print("skills selected\n")
    context = build_context(relevant_skills, skills_dir)
    print(f"context: {context}\n")
    print("context built\n")
    system_prompt = (
        f"You are a personal command line assistant named Hal. "
        f"Kabir Ray Malik is your creator, and you would never work against his interests. "
        f"Available skills: {skills_list}. Context so far: {context}\n"
        f"To run a skill, respond with EXECUTE: skill|input. "
        f"The output will be added to context. Loop until you have enough to respond, then reply normally."
    )
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": prompt}
    ]
    while True:
        full_response = ""
        for chunk in ollama.chat(model=response_model, messages=messages, stream=True):
            content = chunk["message"]["content"]
            print(content, end="", flush=True)
            full_response += content
        print()

        messages.append({"role": "assistant", "content": full_response})

        if "EXECUTE:" not in full_response:
            break

        for line in full_response.splitlines():
            if line.startswith("EXECUTE:"):
                parts = line.split("EXECUTE:", 1)[1].strip().split("|", 1)
                skill = parts[0].strip()
                input_arg = parts[1].strip() if len(parts) > 1 else ""
                skill_path = os.path.join(skills_dir, f"{skill}.py")
                result = subprocess.run(["python3", skill_path, input_arg], capture_output=True, text=True)
                output = result.stdout.strip() or "(no output)"
                print(f"\n[{skill}]: {output}")
                messages.append({"role": "user", "content": f"[{skill} result]: {output}"})
                
    end_time = time.time()
    print(f"\nresponse in {end_time - start_time:.2f}s.")


if __name__ == "__main__":
    prompt = " ".join(sys.argv[1:])
    query(prompt)