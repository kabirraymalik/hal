#!/usr/bin/env python3
"""Compare runtimes and slots: time to first token, prefill and decode tok/s, native tool calls.

  bench.py                          every runtime/slot in the profile (unreachable ones print 'down')
  bench.py llama/small mlx/small -n 3
"""
import argparse
import json
import os
import pathlib
import random
import statistics
import sys
import time
import tomllib
import uuid

import llm

ROOT = pathlib.Path(__file__).resolve().parent
SENTENCES = (
    "The archive room smelled of dust and cold iron. ",
    "Nobody had opened the ledger since the flood. ",
    "A clerk once swore the numbers rearranged themselves overnight. ",
    "The river kept its own accounts. ",
    "Every spring the town argued about the bridge again. ",
    "Maps of the district never agreed on the mill's position. ",
)
SYS = "You are a terse assistant."
TOOL = {
    "type": "function",
    "function": {
        "name": "read_file",
        "description": "Read a text file from disk and return its contents.",
        "parameters": {
            "type": "object",
            "properties": {"path": {"type": "string", "description": "Absolute or ~-prefixed path"}},
            "required": ["path"],
        },
    },
}


def timed(url, messages, **gen):
    """Stream once. Return (ttft seconds, decode tok/s, prompt_tokens or None)."""
    t0 = time.monotonic()
    first = None
    n = 0
    usage = None
    timings = None
    for ev in llm.stream(url, messages, **gen):
        if "text" in ev or "reasoning" in ev:
            first = first or time.monotonic()
            n += 1
        usage = ev.get("usage", usage)
        timings = ev.get("timings", timings)
    t1 = time.monotonic()
    if usage:
        n = usage.get("completion_tokens", n)
    ttft = first - t0 if first else None
    decode = n / max(t1 - first, 1e-9) if first and n > 1 else None
    prefill = None
    if timings:  # llama-server reports its own rates; prefer them over client-side estimates
        decode = timings.get("predicted_per_second") or decode
        if timings.get("prompt_n", 0) > 64:
            prefill = timings.get("prompt_per_second")
    return ttft, decode, usage.get("prompt_tokens") if usage else None, prefill


def run(url, reps, gen):
    name = llm.chat(url, [{"role": "user", "content": "Say ok."}], max_tokens=4, **gen).get("model", "?")
    ttfts, prefills, decodes = [], [], []
    for _ in range(reps):
        # A unique prefix defeats the server's prompt cache so prefill is measured cold.
        filler = f"Note {uuid.uuid4()}. " + "".join(random.choices(SENTENCES, k=400))
        long = [{"role": "system", "content": SYS}, {"role": "user", "content": filler + "\n\nReply with the single word: done."}]
        ttft, _, ptoks, prefill = timed(url, long, max_tokens=8, **gen)
        if ptoks is None:  # server did not report usage while streaming; ask once more (cached, fast)
            ptoks = llm.chat(url, long, max_tokens=1, **gen).get("usage", {}).get("prompt_tokens")
        if ttft:
            ttfts.append(ttft)
            if prefill or ptoks:
                prefills.append(prefill or ptoks / ttft)
        short = [{"role": "system", "content": SYS}, {"role": "user", "content": "Write a 300-word story about a lighthouse keeper."}]
        _, decode, _, _ = timed(url, short, max_tokens=256, **gen)
        if decode:
            decodes.append(decode)
    try:
        msg = llm.chat(
            url,
            [{"role": "system", "content": "Use the tools when they help."}, {"role": "user", "content": "What does ~/notes.txt say?"}],
            tools=[TOOL], max_tokens=1024, **gen,  # thinking models need room before they emit the call
        )["choices"][0]["message"]
        calls = msg.get("tool_calls") or []
        if calls:
            try:
                ok = calls[0]["function"]["name"] == "read_file" and "path" in json.loads(calls[0]["function"]["arguments"])
            except (KeyError, TypeError, ValueError):
                ok = False
            tools = "native" if ok else "native, bad args"
        else:
            tools = "in text only" if "read_file" in (msg.get("content") or "") else "none"
    except RuntimeError as e:
        tools = f"error: {str(e)[:60]}"
    med = lambda xs: statistics.median(xs) if xs else float("nan")
    return name, med(ttfts), med(prefills), med(decodes), tools


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("targets", nargs="*", help="runtime/slot pairs, e.g. llama/small")
    ap.add_argument("-p", "--profile", default=os.environ.get("HAL_PROFILE", "mac"))
    ap.add_argument("-n", "--reps", type=int, default=2)
    a = ap.parse_args()
    with open(ROOT / "profiles" / f"{a.profile}.toml", "rb") as f:
        prof = tomllib.load(f)
    targets = a.targets or [f"{rt}/{slot}" for rt in prof["runtime"] for slot in prof["slots"]]
    print(f"{'target':<16} {'model':<28} {'ttft s':>7} {'prefill t/s':>12} {'decode t/s':>11}  tools")
    seen = set()
    for t in targets:
        rt, slot = t.split("/")
        url = prof["runtime"][rt][slot]
        if url in seen:
            continue  # external runtimes map every slot to one endpoint
        seen.add(url)
        gen = {**prof.get("gen", {}), **prof["slots"][slot].get("gen", {})}
        gen.pop("max_tokens", None)
        try:
            name, ttft, pre, dec, tools = run(url, a.reps, gen)
            print(f"{t:<16} {str(name)[-28:]:<28} {ttft:>7.2f} {pre:>12.0f} {dec:>11.0f}  {tools}", flush=True)
            with open(ROOT / "evals" / "bench.jsonl", "a") as f:
                f.write(json.dumps(dict(ts=time.strftime("%Y-%m-%dT%H:%M:%S"), target=t, model=name, ttft=ttft, prefill=pre, decode=dec, tools=tools)) + "\n")
        except llm.ServerDown:
            print(f"{t:<16} down", flush=True)
        except RuntimeError as e:
            print(f"{t:<16} error: {str(e)[:90]}", flush=True)


if __name__ == "__main__":
    main()
