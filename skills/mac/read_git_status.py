import os
import sys
import subprocess
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from skill import Skill, SkillData


def _git(*args, cwd=None):
    """Run a git command, return stdout or empty string on failure."""
    result = subprocess.run(
        ["git"] + list(args),
        capture_output=True, text=True,
        cwd=cwd, timeout=5
    )
    return result.stdout.strip() if result.returncode == 0 else ""


class ReadGitStatus(Skill):
    def __init__(self):
        super().__init__()
        self.name = "read_git_status"
        self.description = "Read the git status of a repository including branch, uncommitted changes, recent commits, and remote tracking state"
        self.input = "string: path to a git repo (defaults to cwd if empty)"
        self.output = "string: git status summary lines (branch, tracking, dirty files, recent commits) or 'not a git repo'"
        self.time_out = 3000

        self.datagen = SkillData()
        self.datagen.tags = [
            "git", "branch", "commit", "push", "pull", "merge", "diff",
            "status", "changes", "modified", "staged", "uncommitted",
            "repo", "repository", "remote", "origin", "upstream", "log",
            "stash", "checkout", "ahead", "behind", "untracked"
        ]
        self.datagen.complementary_skills = ["read_path"]
        self.datagen.confusion_skills = ["read_path", "read_system_info"]
        self.datagen.usage_hints = [
            "Triggers when the user asks about the state of their code project — changes, branches, commit history, sync status",
            "'What have I changed' in a project context means git status, not read_path",
            "'What branch am I on' is git status. 'What's in the branch directory' would be read_path — but users almost never mean the latter",
            "Prompts mentioning push, pull, merge, rebase, commit, or diff are almost always git-related even without the word 'git'",
            "Should NOT trigger for general questions about version control concepts ('what is a git branch', 'explain rebasing') — only for querying THIS repo's state",
            "'Show me the project' or 'what's in this repo' is ambiguous — if it's about file listing it's read_path, if it's about project health/status it's read_git_status. Both may be relevant together",
        ]
        self.datagen.example_prompts = [
            "what branch am I on",
            "have I committed everything",
            "do I have uncommitted changes",
            "what did I change recently",
            "am I up to date with remote",
            "show me recent commits",
            "did I push my latest changes",
            "what's the git status",
            "are there any untracked files",
            "how far ahead am I from origin",
            "what's the state of this repo",
            "do I have anything staged",
            "when was the last commit",
            "is there anything to pull",
            "what files have I modified",
        ]
        self.datagen.wrong_skill_prompts = [
            "what files are in this directory",          # read_path
            "show me the contents of README.md",         # read_path
            "list everything in ~/projects",             # read_path
            "what's in the src folder",                  # read_path
            "what OS am I running",                      # read_system_info
            "how much disk space do I have",             # read_system_info
            "what time is it",                           # read_system_info
            "do you remember what project I'm working on",  # read_lt_memory
        ]
        self.datagen.no_skill_prompts = [
            "explain how git works",
            "what is a merge conflict",
            "how do I resolve a rebase",
            "what's the difference between merge and rebase",
            "write me a .gitignore for python",
            "what's a good git branching strategy",
            "how do I undo a commit",
            "teach me about git hooks",
        ]

    async def use(self, input_str=""):
        path = input_str.strip().strip("\"'")
        path = os.path.expanduser(path) if path else os.getcwd()
        if not os.path.isabs(path):
            path = os.path.join(os.getcwd(), path)
        toplevel = _git("rev-parse", "--show-toplevel", cwd=path) # verify this is a git repo
        if not toplevel:
            return "not a git repo"
        lines = [f"repo: {toplevel}"]
        branch = _git("branch", "--show-current", cwd=path) # get branch info
        lines.append(f"branch: {branch or '(detached HEAD)'}")
        tracking = _git("rev-parse", "--abbrev-ref", "@{upstream}", cwd=path) # get tracking info
        if tracking:
            ahead_behind = _git("rev-list", "--left-right", "--count", f"{tracking}...HEAD", cwd=path)
            if ahead_behind:
                behind, ahead = ahead_behind.split()
                status_parts = []
                if int(ahead) > 0:
                    status_parts.append(f"{ahead} ahead")
                if int(behind) > 0:
                    status_parts.append(f"{behind} behind")
                lines.append(f"tracking: {tracking} ({', '.join(status_parts) if status_parts else 'up to date'})")
            else:
                lines.append(f"tracking: {tracking}")
        else:
            lines.append("tracking: no upstream set")
        status = _git("status", "--porcelain", cwd=path) # get working tree status
        if status:
            status_lines = status.splitlines()
            staged = [l for l in status_lines if l[0] != ' ' and l[0] != '?']
            modified = [l for l in status_lines if len(l) > 1 and l[1] == 'M']
            untracked = [l for l in status_lines if l.startswith('??')]
            lines.append(f"dirty: {len(status_lines)} changed ({len(staged)} staged, {len(modified)} modified, {len(untracked)} untracked)")
            # show up to 15 files, truncate if more
            for fl in status_lines[:15]:
                lines.append(f"  {fl}")
            if len(status_lines) > 15:
                lines.append(f"  ... and {len(status_lines) - 15} more")
        else:
            lines.append("dirty: clean working tree")
        stash = _git("stash", "list", cwd=path) # get stash count
        if stash:
            count = len(stash.splitlines())
            lines.append(f"stash: {count} {'entry' if count == 1 else 'entries'}")
        log = _git("log", "--oneline", "-5", "--no-decorate", cwd=path) # get recent commits
        if log:
            lines.append("recent commits:")
            for entry in log.splitlines():
                lines.append(f"  {entry}")

        return "\n".join(lines)


if __name__ == "__main__":
    import asyncio
    skill = ReadGitStatus()
    print(asyncio.run(skill.use(sys.argv[1] if len(sys.argv) > 1 else "")))