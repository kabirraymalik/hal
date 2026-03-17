import os
import sys
import subprocess
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from skill import Skill, SkillData


def _run(*args, timeout=10):
    """Run a command, return stdout or None on any failure."""
    try:
        result = subprocess.run(
            list(args), capture_output=True, text=True, timeout=timeout
        )
        return result.stdout.strip() if result.returncode == 0 else None
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
        return None


class ReadEnvVars(Skill):
    def __init__(self):
        super().__init__()
        self.name = "read_env_vars"
        self.description = "Read environment variables, active conda environment and packages, and Docker status including running containers"
        self.input = "string: specific variable name, package name, or search term (reads full environment if empty)"
        self.output = "string: matching env vars as key=value lines, conda environment and package info, Docker container and image status"
        self.time_out = 4000

        self.datagen = SkillData()
        self.datagen.tags = [
            "env", "environment", "variable", "PATH", "export", "conda",
            "venv", "virtualenv", "python", "package", "installed",
            "pip", "api key", "secret", "token", "config", "GOPATH",
            "JAVA_HOME", "activate", "deactivate", "base",
            "docker", "container", "image", "running", "compose"
        ]
        self.datagen.complementary_skills = ["read_system_info", "read_path"]
        self.datagen.confusion_skills = ["read_system_info", "read_path"]
        self.datagen.usage_hints = [
            "Triggers when the user asks about environment variables, conda environments, installed Python packages, or Docker status",
            "'What environment am I in' or 'which conda env is active' are this skill, not read_system_info — even though they sound like system questions",
            "'What python packages do I have' is this skill when it means the current conda env's packages. 'What version of python is installed' could be either this or read_system_info",
            "Questions about PATH, API keys, tokens, or any specific env var by name should trigger this skill",
            "'Is my container running', 'what docker images do I have', 'is Docker up' are all this skill",
            "Should NOT trigger for 'how do I set an env var' or 'how does conda work' or 'explain Docker networking' — those are knowledge questions",
            "Should NOT trigger for 'what's in my .env file' — that's read_path on a specific file",
            "'Is numpy installed' or 'do I have pandas' is this skill — it checks the active conda environment's packages",
        ]
        self.datagen.example_prompts = [
            "what conda environment am I in",
            "which python packages are installed",
            "what's my PATH",
            "is OPENAI_API_KEY set",
            "do I have numpy installed",
            "show me my environment variables",
            "what environment am I using",
            "is pandas in my current env",
            "what's my JAVA_HOME",
            "which conda env is active",
            "list my installed packages",
            "do I have an API key set for anthropic",
            "what version of torch do I have",
            "what python is this conda env using",
            "am I in the base environment",
            "are any docker containers running",
            "what docker images do I have",
            "is my postgres container up",
            "is docker running",
            "what containers are active right now",
        ]
        self.datagen.wrong_skill_prompts = [
            "what OS am I running",                      # read_system_info
            "how much RAM do I have",                    # read_system_info
            "what time is it",                           # read_system_info
            "what's in my .env file",                    # read_path (file contents, not env vars)
            "show me my .bashrc",                        # read_path
            "what files are in this directory",          # read_path
            "what branch am I on",                       # read_git_status
            "do you remember what project I'm working on", # read_lt_memory
        ]
        self.datagen.no_skill_prompts = [
            "how do I create a conda environment",
            "explain the difference between conda and pip",
            "what is a virtual environment",
            "how do I set an environment variable on mac",
            "write a requirements.txt for my project",
            "what's the best way to manage python versions",
            "how does PATH resolution work",
            "explain conda channels",
            "how do I write a Dockerfile",
            "explain docker compose",
            "what's the difference between a container and a VM",
            "how does docker networking work",
        ]

    async def use(self, input_str=""):
        query = input_str.strip().lower()
        is_broad = query in ("", "all", "full", "everything")
        sections = []

        # ---- conda ----
        conda_env = os.environ.get("CONDA_DEFAULT_ENV", "")
        conda_prefix = os.environ.get("CONDA_PREFIX", "")
        if conda_env:
            sections.append(f"conda env: {conda_env}")
            sections.append(f"conda prefix: {conda_prefix}")
            python_path = _run("which", "python")
            if python_path:
                sections.append(f"python: {python_path}")
            packages = _run("conda", "list", "--no-banner")
            if packages:
                pkg_lines = []
                for l in packages.splitlines():
                    if l and not l.startswith("#"):
                        pkg_lines.append(l)
                if not is_broad:
                    matched = [l for l in pkg_lines if query in l.lower()]
                    if matched:
                        sections.append(f"matching packages ({len(matched)}):")
                        for p in matched:
                            sections.append(f"  {p}")
                    else:
                        sections.append(f"no packages matching '{query}'")
                else:
                    sections.append(f"installed packages ({len(pkg_lines)}):")
                    for p in pkg_lines[:50]:
                        sections.append(f"  {p}")
                    if len(pkg_lines) > 50:
                        sections.append(f"  ... and {len(pkg_lines) - 50} more")
        elif _run("conda", "--version") is not None:
            sections.append("conda: installed but no environment active")
        else:
            sections.append("conda: not installed")

        # ---- docker ----
        docker_version = _run("docker", "--version")
        if docker_version:
            sections.append(f"docker: {docker_version}")
            docker_info = _run("docker", "info", "--format", "{{.ServerVersion}}", timeout=4) # check if daemon responsive?
            if docker_info:
                containers = _run("docker", "ps", "--format", "{{.Names}}\t{{.Image}}\t{{.Status}}\t{{.Ports}}")
                if containers:
                    container_lines = containers.splitlines()
                    if not is_broad:
                        matched = [l for l in container_lines if query in l.lower()]
                        if matched:
                            sections.append(f"running containers matching '{query}' ({len(matched)}):")
                            for c in matched:
                                sections.append(f"  {c}")
                        else:
                            sections.append(f"no running containers matching '{query}'")
                    else:
                        sections.append(f"running containers ({len(container_lines)}):")
                        for c in container_lines:
                            sections.append(f"  {c}")
                else:
                    sections.append("running containers: none")
                images = _run("docker", "images", "--format", "{{.Repository}}:{{.Tag}}\t{{.Size}}")
                if images:
                    image_lines = images.splitlines()
                    if not is_broad:
                        matched = [l for l in image_lines if query in l.lower()]
                        if matched:
                            sections.append(f"images matching '{query}' ({len(matched)}):")
                            for i in matched:
                                sections.append(f"  {i}")
                    else:
                        sections.append(f"docker images ({len(image_lines)}):")
                        for i in image_lines[:20]:
                            sections.append(f"  {i}")
                        if len(image_lines) > 20:
                            sections.append(f"  ... and {len(image_lines) - 20} more")
            else:
                sections.append("docker daemon: not running")
        else:
            sections.append("docker: not installed")

        # ---- environment variables ----
        env = os.environ
        if not is_broad:
            matches = {
                k: v for k, v in env.items()
                if query in k.lower() or query in v.lower()
            }
            if matches:
                sections.append(f"env vars matching '{query}' ({len(matches)}):")
                for k, v in sorted(matches.items()):
                    display = _mask_if_sensitive(k, v)
                    sections.append(f"  {k}={display}")
            else:
                sections.append(f"no env vars matching '{query}'")
        else:
            notable = [
                "PATH", "HOME", "USER", "SHELL", "LANG",
                "EDITOR", "VISUAL", "TERM",
                "GOPATH", "JAVA_HOME", "RUST_HOME",
                "OPENAI_API_KEY", "ANTHROPIC_API_KEY",
                "AWS_ACCESS_KEY_ID", "GITHUB_TOKEN",
                "DOCKER_HOST", "COMPOSE_PROJECT_NAME",
                "VIRTUAL_ENV", "PYTHONPATH",
            ]
            found = []
            for key in notable:
                val = env.get(key)
                if val is not None:
                    found.append(f"  {key}={_mask_if_sensitive(key, val)}")
            if found:
                sections.append(f"notable env vars ({len(found)}):")
                sections.extend(found)

        return "\n".join(sections)


def _mask_if_sensitive(key, value):
    """Mask values that look like secrets, truncate long values."""
    sensitive = ("KEY", "TOKEN", "SECRET", "PASSWORD", "CREDENTIAL")
    if any(s in key.upper() for s in sensitive):
        return value[:4] + "..." if len(value) > 4 else "***"
    if len(value) > 200:
        return value[:200] + "..."
    return value


if __name__ == "__main__":
    import asyncio
    skill = ReadEnvVars()
    print(asyncio.run(skill.use(sys.argv[1] if len(sys.argv) > 1 else "")))