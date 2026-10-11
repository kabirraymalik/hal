#!/usr/bin/env python3
"""hal: talk to a local model from any terminal.

  hal what is a good name for this function      small tier: fast, thinking off; piped stdin is appended
  git diff | hal review this
  hal -m ...                                     medium tier: reasoning
  hal -L ...                                     large tier: evicts the others, unloads when idle
  hal -r mlx ...                                 another runtime from the profile
  hal                                            multi-turn chat until 'exit' or ctrl-d
  hal sleep | wake | status                      unload everything | pre-load resident tiers | show servers

Servers start on demand. Tiers, ports, and launch commands live in profiles/<name>.toml.
"""
import argparse
import os
import pathlib
import re
import shlex
import signal
import subprocess
import sys
import time
import tomllib
from urllib.parse import urlsplit

import llm

ROOT = pathlib.Path(__file__).resolve().parent
LOGS = ROOT / "logs"
SYSTEM = "You are hal, a local assistant running on the user's own machine. Be concise and direct."
DIM, RESET = "\033[2m", "\033[0m"


def note(msg):
    print(f"{DIM}{msg}{RESET}", file=sys.stderr, flush=True)


def model_size_gb(path):
    """Weights on disk, following the shards of a split GGUF or the files of an MLX directory."""
    path = pathlib.Path(path).resolve()
    if path.is_dir():
        return sum(f.stat().st_size for f in path.rglob("*") if f.is_file()) / 1e9
    m = re.match(r"(.*)-\d{5}-of-\d{5}\.gguf$", path.name)
    files = sorted(path.parent.glob(m.group(1) + "-*-of-*.gguf")) if m else [path]
    return sum(f.stat().st_size for f in files) / 1e9


def available_gb():
    """Memory macOS currently counts as available, in GB; None if that cannot be read."""
    try:
        level = int(subprocess.check_output(["sysctl", "-n", "kern.memorystatus_level"], text=True))
        total = int(subprocess.check_output(["sysctl", "-n", "hw.memsize"], text=True))
        return level / 100 * total / 1e9
    except (OSError, ValueError, subprocess.CalledProcessError):
        return None


class Servers:
    """Start, stop, and probe the model servers one runtime table describes. Pid, log, and
    last-used files live in logs/<runtime>-<slot>.*"""

    def __init__(self, prof, runtime):
        self.prof, self.rt = prof, runtime
        self.cfg = prof["runtime"][runtime]
        self.slots = prof["slots"]
        LOGS.mkdir(exist_ok=True)

    def url(self, slot):
        return self.cfg[slot]

    def managed(self):
        return "launch" in self.cfg

    def path(self, slot):
        return ROOT / "models" / f"{slot}.{self.cfg['ext']}"

    def _file(self, slot, kind):
        return LOGS / f"{self.rt}-{slot}.{kind}"

    def pid(self, slot):
        try:
            pid = int(self._file(slot, "pid").read_text())
            os.kill(pid, 0)
            return pid
        except (FileNotFoundError, ValueError, ProcessLookupError, PermissionError):
            return None

    def healthy(self, slot):
        return llm.get(self.url(slot) + self.cfg.get("health", "/health")) is not None

    def touch(self, slot):
        self._file(slot, "last").touch()

    def start(self, slot):
        if self.pid(slot):
            return
        model = self.path(slot)
        if not model.exists():
            sys.exit(f"hal: missing models/{model.name} for {self.rt}/{slot} (see models/README.md)")
        need, avail = model_size_gb(model) + 8, available_gb()  # weights plus KV cache and buffers
        if avail is not None and avail < need and not os.environ.get("HAL_FORCE"):
            sys.exit(f"hal: {avail:.0f} GB available but loading {slot} needs about {need:.0f} GB; something else holds memory "
                     f"(Bionic's model? another tier?). Free it, or HAL_FORCE=1 to load anyway.")
        cmd = os.path.expanduser(self.cfg["launch"]).format(
            model=model.resolve(), slot=slot, port=urlsplit(self.url(slot)).port, ctx=self.slots[slot].get("ctx", 32768),
            args=self.slots[slot].get("args", ""))
        log = open(self._file(slot, "log"), "ab")
        proc = subprocess.Popen(shlex.split(cmd), stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
        self._file(slot, "pid").write_text(str(proc.pid))
        self.touch(slot)
        if self.slots[slot].get("idle_minutes"):
            subprocess.Popen([sys.executable, __file__, "--watch", slot, "-r", self.rt, "-p", self.prof["_name"]],
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)

    def stop(self, slot):
        pid = self.pid(slot)
        if pid:
            os.kill(pid, signal.SIGTERM)
        self._file(slot, "pid").unlink(missing_ok=True)
        return pid

    def wait(self, slot, timeout=900):
        t0 = time.monotonic()
        noted = False
        while time.monotonic() - t0 < timeout:
            if self.healthy(slot):
                return
            if not self.pid(slot):
                sys.exit(f"hal: {self.rt}/{slot} exited while loading; see logs/{self.rt}-{slot}.log")
            if not noted:
                note(f"loading {slot}...")
                noted = True
            time.sleep(0.5)
        sys.exit(f"hal: {self.rt}/{slot} did not come up within {timeout}s")

    def ensure(self, slot):
        """Return (url, slot actually serving), starting or evicting servers as the tier's residency requires."""
        if not self.managed() or self.healthy(slot):
            return self.url(slot), slot
        resident = [s for s in self.slots if self.slots[s].get("exclusive") and self.pid(s)]
        if resident and not self.slots[slot].get("exclusive"):
            self.wait(resident[0])  # the whole-machine tier is up: let it answer rather than reload a smaller one
            return self.url(resident[0]), resident[0]
        if self.slots[slot].get("exclusive"):
            sleep_all(self.prof, keep=(self.rt, slot))
        self.start(slot)
        self.wait(slot)
        return self.url(slot), slot

    def watch(self, slot):
        """Detached loop: unload `slot` once it has been idle for its window."""
        idle = self.slots[slot].get("idle_minutes", 0) * 60
        while idle and self.pid(slot):
            time.sleep(max(5, min(60, idle / 2)))
            try:
                if time.time() - self._file(slot, "last").stat().st_mtime > idle:
                    self.stop(slot)
            except FileNotFoundError:
                self.touch(slot)


def sleep_all(prof, keep=None):
    for rt in prof["runtime"]:
        s = Servers(prof, rt)
        for slot in prof["slots"]:
            if s.managed() and (rt, slot) != keep and s.stop(slot):
                note(f"stopped {rt}/{slot}")


def wake(servers):
    for slot in servers.slots:
        if servers.slots[slot].get("exclusive") and servers.stop(slot):
            note(f"evicted {slot}")
    resident = [s for s in servers.slots if not servers.slots[s].get("exclusive") and servers.path(s).exists()]
    for slot in resident:
        servers.start(slot)
    for slot in resident:
        servers.wait(slot)
        print(f"{servers.rt}/{slot} ready")


def status(prof):
    for rt in prof["runtime"]:
        s = Servers(prof, rt)
        if not s.managed():
            print(f"{rt:<9} external  {'reachable' if s.healthy('small') else 'unreachable'}")
            continue
        for slot in prof["slots"]:
            pid = s.pid(slot)
            state = f"up  pid {pid}  {'ready' if s.healthy(slot) else 'loading'}" if pid else "down"
            print(f"{rt + '/' + slot:<16} {state}")


def respond(url, messages, gen, verbose):
    """Stream one assistant turn to stdout and append it to messages."""
    t0 = time.monotonic()
    first = None
    thinking = False
    out = []
    timings = None
    for ev in llm.stream(url, messages, **gen):
        timings = ev.get("timings", timings)
        if "reasoning" in ev and verbose:
            if not thinking:
                print(DIM, end="", file=sys.stderr)
                thinking = True
            print(ev["reasoning"], end="", file=sys.stderr, flush=True)
        if "text" in ev:
            text = ev["text"] if out else ev["text"].lstrip()  # drop leading blank lines and spaces after thinking
            if not text:
                continue
            if thinking:
                print(RESET, file=sys.stderr, flush=True)
                thinking = False
            first = first or time.monotonic()
            out.append(text)
            print(text, end="", flush=True)
    print()
    messages.append({"role": "assistant", "content": "".join(out)})
    if verbose and first:
        t1 = time.monotonic()
        rate = timings["predicted_per_second"] if timings and timings.get("predicted_per_second") else len(out) / max(t1 - first, 1e-9)
        note(f"[ttft {first - t0:.2f}s · {rate:.0f} tok/s · {t1 - t0:.1f}s]")


def main():
    ap = argparse.ArgumentParser(prog="hal", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("prompt", nargs="*")
    tier = ap.add_mutually_exclusive_group()
    tier.add_argument("-m", "--medium", dest="slot", action="store_const", const="medium", help="medium tier")
    tier.add_argument("-L", "--large", dest="slot", action="store_const", const="large", help="large tier")
    ap.add_argument("-r", "--runtime", help="runtime table in the profile (default: the profile's default_runtime)")
    ap.add_argument("-p", "--profile", default=os.environ.get("HAL_PROFILE", "mac"), help="profiles/<name>.toml")
    ap.add_argument("-v", "--verbose", action="store_true", help="show reasoning and timings on stderr")
    ap.add_argument("--watch", help=argparse.SUPPRESS)
    a = ap.parse_args()
    signal.signal(signal.SIGPIPE, signal.SIG_DFL)  # `hal status | head` should end quietly

    try:
        with open(ROOT / "profiles" / f"{a.profile}.toml", "rb") as f:
            prof = tomllib.load(f)
    except FileNotFoundError:
        sys.exit(f"hal: no profile at profiles/{a.profile}.toml")
    prof["_name"] = a.profile
    runtime = a.runtime or prof.get("default_runtime", "llama")
    slot = a.slot or "small"
    if runtime not in prof["runtime"] or slot not in prof["runtime"][runtime]:
        sys.exit(f"hal: profile '{a.profile}' has no [runtime.{runtime}] {slot}")
    servers = Servers(prof, runtime)
    if a.watch:
        return servers.watch(a.watch)
    if a.prompt == ["sleep"]:
        return sleep_all(prof)
    if a.prompt == ["wake"]:
        return wake(servers)
    if a.prompt == ["status"]:
        return status(prof)

    prompt = " ".join(a.prompt)
    if not sys.stdin.isatty():
        piped = sys.stdin.read().strip()
        if piped:
            prompt = f"{prompt}\n\n```\n{piped}\n```" if prompt else piped
    if not prompt and not sys.stdin.isatty():
        ap.error("no prompt")
    try:
        url, serving = servers.ensure(slot)
        servers.touch(serving)
        gen = {**prof.get("gen", {}), **prof["slots"][slot].get("gen", {})}
        messages = [{"role": "system", "content": prof["slots"][slot].get("system", prof.get("system", SYSTEM))}]
        if prompt:
            messages.append({"role": "user", "content": prompt})
            respond(url, messages, gen, a.verbose)
            return
        note(f"hal · {runtime}/{serving} · 'exit' or ctrl-d to leave")
        while True:
            try:
                line = input("> ").strip()
            except EOFError:
                print()
                break
            if line in ("exit", "quit"):
                break
            if line:
                messages.append({"role": "user", "content": line})
                respond(url, messages, gen, a.verbose)
                servers.touch(serving)
    except llm.ServerDown as e:
        sys.exit(f"hal: {e}")
    except RuntimeError as e:
        sys.exit(f"hal: {e}")
    except KeyboardInterrupt:
        print()


if __name__ == "__main__":
    main()
