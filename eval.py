#!/usr/bin/env python3
"""Evaluate a candidate model through hal's real pipeline: the slot's system prompt, generation
settings, server, and client. Cases and pass thresholds live in evals/<slot>.toml. Every run appends
one JSON line to evals/results.jsonl and writes a readable transcript to evals/runs/.

  eval.py                           evaluate the small slot, starting its server on demand
  eval.py -v                        also print every prompt and answer
  eval.py --model ~/models/x.gguf   link that file into the slot first (restarts the slot's server)
  eval.py --sleep                   stop the slot's server afterwards
  eval.py medium                    another slot, using evals/medium.toml
  eval.py --history                 one line per recorded run
  eval.py --compare                 write evals/compare.md: each prompt with every model's answer side by side

Scored kinds: command, fact, debug, escalate, destructive, tool. Kind `open` is qualitative: logged and compared, not scored.
"""
import argparse
import json
import os
import pathlib
import re
import shlex
import statistics
import subprocess
import sys
import time
import tomllib

import hal
import llm

ROOT = pathlib.Path(__file__).resolve().parent
RESULTS = ROOT / "evals" / "results.jsonl"
RUNS = ROOT / "evals" / "runs"
COMPARE = ROOT / "evals" / "compare.md"
TOOL = {"type": "function", "function": {"name": "read_file", "description": "Read a text file from disk and return its contents.",
        "parameters": {"type": "object", "properties": {"path": {"type": "string", "description": "Absolute or ~-prefixed path"}},
                       "required": ["path"]}}}
PREAMBLE = re.compile(r"^(sure|certainly|of course|great question|here('s| is| are)|okay|ok[,!]|absolutely|happy to)", re.I)
EMOJI = re.compile("[\U0001F300-\U0001FAFF☀-➿]")
DIM, RESET = "\033[2m", "\033[0m"


def ask(url, system, gen, prompt, tools=None):
    """One turn exactly as hal would send it. Tool cases go non-streaming so the call comes back whole."""
    messages = [{"role": "system", "content": system}, {"role": "user", "content": prompt}]
    t0 = time.monotonic()
    if tools:
        msg = llm.chat(url, messages, tools=tools, **gen)["choices"][0]["message"]
        return dict(answer=(msg.get("content") or "").strip(), calls=msg.get("tool_calls") or [], ttft=None, decode=None,
                    total=time.monotonic() - t0)
    first = None
    n = 0
    out = []
    timings = None
    for ev in llm.stream(url, messages, **gen):
        if "text" in ev or "reasoning" in ev:
            first = first or time.monotonic()
            n += 1
        if "text" in ev:
            out.append(ev["text"])
        timings = ev.get("timings", timings)
    t1 = time.monotonic()
    decode = n / max(t1 - first, 1e-9) if first and n > 1 else None
    if timings and timings.get("predicted_per_second"):
        decode = timings["predicted_per_second"]  # server-side; the client clock starts late when the server buffers the first tokens
    return dict(answer="".join(out).strip(), calls=[], ttft=first - t0 if first else None, decode=decode, total=t1 - t0)


def judge(case, res):
    """Return (passed, notes). Style notes (preamble, header, emoji) are counted but do not fail a case."""
    a = res["answer"]
    notes = []
    ok = all(re.search(p, a, re.I | re.S) for p in case.get("expect", []))
    if not ok:
        notes.append("expected pattern missing")
    if any(re.search(p, a, re.I) for p in case.get("forbid", [])):
        ok = False
        notes.append("forbidden pattern")
    kind = case["kind"]
    if kind == "command" and "```" not in a:
        ok = False
        notes.append("no code fence")
    if kind == "fact" and len(re.split(r"(?<=[.!?])\s+", a)) > 3:
        ok = False
        notes.append("over three sentences")
    if kind == "debug" and len(a.splitlines()) > 8:
        ok = False
        notes.append("over eight lines")
    if kind == "destructive" and not re.search(r"delet|remov|irreversib|be undone|careful|caution|trash|permanent|destructive|warning",
                                                a.split("```")[0], re.I):
        ok = False
        notes.append("no warning before the command")
    if kind == "tool":
        calls = res["calls"]
        if case.get("expect_call", True):
            try:
                ok = calls[0]["function"]["name"] == "read_file" and "path" in json.loads(calls[0]["function"]["arguments"])
            except (IndexError, KeyError, TypeError, ValueError):
                ok = False
            if not ok:
                notes.append("no valid tool call")
        elif calls:
            ok = False
            notes.append("called a tool needlessly")
    prose = re.sub(r"```.*?```", "", a, flags=re.S)  # shell comments inside code blocks are not markdown headers
    if PREAMBLE.match(a):
        notes.append("preamble")
    if re.search(r"^#{1,6}\s", prose, re.M):
        notes.append("header")
    if EMOJI.search(prose):
        notes.append("emoji")
    return ok, ", ".join(notes)


def footprint_gb(pid):
    """(resident GB, mapped-file GB) from macOS `footprint`, or (None, None)."""
    try:
        out = subprocess.run(["footprint", "-p", str(pid)], capture_output=True, text=True, timeout=30).stdout
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return None, None
    unit = {"B": 1e-9, "KB": 1e-6, "MB": 1e-3, "GB": 1.0}
    gb = lambda s: max((float(v) * unit[u] for v, u in re.findall(r"([\d.]+)\s*(GB|MB|KB|B)\b", s)), default=0.0)
    phys = re.search(r"phys_footprint:.*", out)
    mapped = re.search(r".*mapped file.*", out)
    return (gb(phys.group()) if phys else None), (gb(mapped.group()) if mapped else None)


def server_build(cfg):
    exe = shlex.split(os.path.expanduser(cfg.get("launch", "")))[:1]
    try:
        r = subprocess.run(exe + ["--version"], capture_output=True, text=True, timeout=15)
        return (r.stdout + r.stderr).strip().splitlines()[0]
    except (OSError, subprocess.TimeoutExpired, IndexError):
        return None


def fmt(x, w=6, d=2):
    return f"{x:{w}.{d}f}" if x is not None else " " * max(w - 1, 0) + "-"


def indent(text):
    return "\n".join("    " + l for l in (text or "(empty)").splitlines())


def load_results():
    return [json.loads(l) for l in RESULTS.read_text().splitlines() if l.strip()] if RESULTS.exists() else []


def verdict(c):
    return "open" if c["kind"] == "open" else ("pass" if c["ok"] else "FAIL")


def case_line(c):
    return f"{verdict(c)} · {fmt(c['ttft'], 0)}s · {fmt(c['decode'], 0, 0)} tok/s · {c['words']} words" + (f" · {c['notes']}" if c["notes"] else "")


def history():
    print(f"{'date':<10} {'slot':<6} {'model':<44} {'GB':>5} {'fp GB':>5} {'ttft':>5} {'tok/s':>5} {'words':>5} {'acc':>4} tools esc fit")
    for r in load_results():
        print(f"{r['ts'][:10]:<10} {r['slot']:<6} {r['model'][-44:]:<44} {fmt(r['size_gb'], 5, 1)} {fmt(r['footprint_gb'], 5, 1)} "
              f"{fmt(r['ttft_warm'], 5, 2)} {fmt(r['decode'], 5, 0)} {fmt(r['words'], 5, 0)} {r['accuracy'] * 100:>3.0f}% "
              f"{r['tools']:<5} {r.get('over_escalate', 0):>3} {r['fit']}")


def compare():
    """Latest run per model, every prompt with each model's answer underneath."""
    latest = {}
    for r in load_results():
        latest[(r["slot"], r["model"])] = r
    runs = sorted(latest.values(), key=lambda r: r["ts"])
    if not runs:
        sys.exit("eval: no results yet")
    out = ["# Candidates side by side", "", f"Latest run per model, generated {time.strftime('%Y-%m-%d %H:%M')}. Answers are verbatim.", "",
           "| model | slot | GB | fp GB | ttft | tok/s | words | acc | tools | over-esc | fit |",
           "|---|---|---:|---:|---:|---:|---:|---:|---|---:|---|"]
    for r in runs:
        out.append(f"| {r['model']} | {r['slot']} | {fmt(r['size_gb'], 0, 1)} | {fmt(r['footprint_gb'], 0, 1)} | {fmt(r['ttft_warm'], 0)} | "
                   f"{fmt(r['decode'], 0, 0)} | {fmt(r['words'], 0, 0)} | {r['accuracy'] * 100:.0f}% | {r['tools']} | {r.get('over_escalate', 0)} | {r['fit']} |")
    prompts = []
    for r in runs:
        for c in r["cases"]:
            if c.get("prompt") and c["prompt"] not in prompts:
                prompts.append(c["prompt"])
    for i, p in enumerate(prompts, 1):
        kinds = sorted({c["kind"] for r in runs for c in r["cases"] if c.get("prompt") == p})
        out += ["", f"## {i}. {p.splitlines()[0][:90]}  ({', '.join(kinds)})"]
        for r in runs:
            for c in r["cases"]:
                if c.get("prompt") == p:
                    out += ["", f"**{r['model']}** · {case_line(c)}", "", indent(c["answer"])]
    COMPARE.write_text("\n".join(out) + "\n")
    print(f"wrote {COMPARE.relative_to(ROOT)}: {len(runs)} models, {len(prompts)} prompts")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("slot", nargs="?", default="small")
    ap.add_argument("-p", "--profile", default=os.environ.get("HAL_PROFILE", "mac"))
    ap.add_argument("-r", "--runtime")
    ap.add_argument("-v", "--verbose", action="store_true", help="print every prompt and answer")
    ap.add_argument("--model", help="GGUF file or MLX dir to link into the slot before evaluating")
    ap.add_argument("--sleep", action="store_true", help="stop the slot's server afterwards")
    ap.add_argument("--history", action="store_true")
    ap.add_argument("--compare", action="store_true")
    a = ap.parse_args()
    if a.history:
        return history()
    if a.compare:
        return compare()
    with open(ROOT / "profiles" / f"{a.profile}.toml", "rb") as f:
        prof = tomllib.load(f)
    prof["_name"] = a.profile
    with open(ROOT / "evals" / f"{a.slot}.toml", "rb") as f:
        suite = tomllib.load(f)
    runtime = a.runtime or prof.get("default_runtime", "llama")
    servers = hal.Servers(prof, runtime)
    if a.model:
        target = pathlib.Path(a.model).expanduser().resolve()
        link = servers.path(a.slot)
        if not target.exists():
            sys.exit(f"eval: no such model: {target}")
        if link.exists() and not link.is_symlink():
            sys.exit(f"eval: {link.relative_to(ROOT)} is a real file, not a symlink; move it aside first")
        servers.stop(a.slot)
        link.unlink(missing_ok=True)
        link.symlink_to(target)
        print(f"{DIM}{link.relative_to(ROOT)} -> {target}{RESET}")
    if servers.managed():
        hal.sleep_all(prof, keep=(runtime, a.slot))  # measure this slot alone: no routing to a resident large, no shared memory
    url, serving = servers.ensure(a.slot)
    system = prof["slots"][a.slot].get("system", prof.get("system", hal.SYSTEM))
    gen = {**prof.get("gen", {}), **prof["slots"][a.slot].get("gen", {})}
    gen.setdefault("seed", suite.get("seed", 7))  # same sampling settings as hal, but reproducible run to run
    ctx = prof["slots"][a.slot].get("ctx")
    model = servers.path(serving).resolve().name if servers.managed() else url
    size = hal.model_size_gb(servers.path(serving)) if servers.managed() else None
    build = server_build(servers.cfg) if servers.managed() else None
    print(f"{runtime}/{a.slot}: {model}" + (f" ({size:.1f} GB on disk)" if size else "") + f" · ctx {ctx} · {build or runtime}")
    print(f"{'#':>2} {'kind':<8} {'ttft':>6} {'tok/s':>6} {'words':>5}  result")

    rows = []
    for i, case in enumerate(suite["case"], 1):
        try:
            res = ask(url, system, gen, case["prompt"], tools=[TOOL] if case["kind"] == "tool" else None)
            ok, notes = judge(case, res)
        except (llm.ServerDown, RuntimeError) as e:  # a crashed or erroring server fails the case, not the run
            res = dict(answer=f"(error: {str(e)[:200]})", calls=[], ttft=None, decode=None, total=None)
            ok, notes = False, "server error"
        row = dict(prompt=case["prompt"], kind=case["kind"], ok=ok, notes=notes, words=len(res["answer"].split()),
                   ttft=res["ttft"], decode=res["decode"], answer=res["answer"])
        print(f"{i:>2} {case['kind']:<8} {fmt(row['ttft'])} {fmt(row['decode'], 6, 0)} {row['words']:>5}  {verdict(row):<4}  {notes}", flush=True)
        if a.verbose:
            print(f"{DIM}   > {case['prompt'].splitlines()[0][:100]}\n{indent(res['answer'])}{RESET}")
        rows.append(row)

    med = lambda xs: statistics.median(xs) if xs else None
    scored = [r for r in rows if r["kind"] != "open"]
    streamed = [r for r in rows if r["ttft"] is not None]
    ttft_cold = streamed[0]["ttft"] if streamed else None
    ttft_warm = med([r["ttft"] for r in streamed[1:]])
    decode = med([r["decode"] for r in rows if r["decode"]])
    words = med([r["words"] for r in rows if r["kind"] != "tool"])
    accuracy = sum(r["ok"] for r in scored) / len(scored)
    by_kind = " · ".join(f"{k} {sum(r['ok'] for r in scored if r['kind'] == k)}/{sum(r['kind'] == k for r in scored)}"
                         for k in dict.fromkeys(r["kind"] for r in scored))
    tools = f"{sum(r['ok'] for r in scored if r['kind'] == 'tool')}/{sum(r['kind'] == 'tool' for r in scored)}"
    style = {n: sum(n in r["notes"] for r in rows) for n in ("preamble", "header", "emoji")}
    over_escalate = sum("hal -m" in r["answer"] for r in scored if r["kind"] != "escalate")  # punting on questions it should answer
    fp, mapped = footprint_gb(servers.pid(serving)) if servers.managed() and servers.pid(serving) else (None, None)
    footprint = (fp or 0) + (mapped or 0) if fp is not None else None

    th = suite.get("thresholds", {})
    checks = {
        "ttft": (ttft_warm is not None and ttft_warm <= th.get("ttft_s", 0.5),
                 f"warm median {fmt(ttft_warm, 4)}s, cold {fmt(ttft_cold, 4)}s (≤ {th.get('ttft_s', 0.5)})"),
        "decode": (decode is not None and decode >= th.get("decode_tps", 60), f"median {fmt(decode, 4, 0)} tok/s (≥ {th.get('decode_tps', 60)})"),
        "footprint": (footprint is not None and footprint <= th.get("footprint_gb", 25),
                      f"{fmt(footprint, 4, 1)} GB resident incl. mapped weights, KV at {ctx} (≤ {th.get('footprint_gb', 25)})"),
        "accuracy": (accuracy >= th.get("accuracy", 0.9),
                     f"{accuracy * 100:.0f}%: {by_kind} · over-escalated {over_escalate} (≥ {th.get('accuracy', 0.9) * 100:.0f}%)"),
        "brevity": (words is not None and words <= th.get("median_words", 60) and style["preamble"] == 0,
                    f"median {fmt(words, 3, 0)} words · preamble {style['preamble']} · headers {style['header']} · emoji {style['emoji']} "
                    f"(≤ {th.get('median_words', 60)} words, no preamble)"),
    }
    fit = f"{sum(ok for ok, _ in checks.values())}/{len(checks)}"
    summary = [f"{name:<10} {'ok  ' if ok else 'MISS'} {text}" for name, (ok, text) in checks.items()] + [f"{'fit':<10} {fit}"]
    print()
    print("\n".join(summary))

    stamp = time.strftime("%Y-%m-%dT%H:%M:%S")
    RUNS.mkdir(parents=True, exist_ok=True)
    transcript = RUNS / f"{stamp.replace(':', '')}-{a.slot}-{re.sub(r'[^A-Za-z0-9._-]+', '_', model)[:60]}.md"
    lines = [f"# {a.slot} · {model}", "", f"{stamp} · {runtime} · {build or '?'} · ctx {ctx} · gen `{json.dumps(gen)}`", "", "    " + "\n    ".join(summary), ""]
    for i, r in enumerate(rows, 1):
        lines += [f"## {i}. {r['prompt'].splitlines()[0][:90]}  ({r['kind']})", "", case_line(r), "", indent(r["answer"]), ""]
    transcript.write_text("\n".join(lines))
    with open(RESULTS, "a") as f:
        f.write(json.dumps(dict(ts=stamp, profile=a.profile, runtime=runtime, slot=a.slot, served_by=serving, model=model, size_gb=size,
                                build=build, ctx=ctx, footprint_gb=footprint, ttft_cold=ttft_cold, ttft_warm=ttft_warm, decode=decode,
                                words=words, accuracy=accuracy, tools=tools, style=style, over_escalate=over_escalate, fit=fit, gen=gen,
                                cases=rows)) + "\n")
    print(f"{DIM}transcript {transcript.relative_to(ROOT)} · recorded to evals/results.jsonl · --history / --compare to line candidates up{RESET}")
    if a.sleep and servers.managed():
        servers.stop(serving)
        print(f"{DIM}stopped {runtime}/{serving}{RESET}")


if __name__ == "__main__":
    main()
