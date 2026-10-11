# hal

A local assistant you talk to from any terminal. Models run on this machine behind an
OpenAI-compatible server; hal itself is standard-library Python.

    hal what does this error mean                  small tier: fast, thinking off
    git diff | hal review this                     piped stdin is appended as context
    hal -m design the migration                    medium tier: reasoning
    hal -L analyze this whole repo                 large tier: takes the machine, leaves when idle
    hal -r mlx ...                                 another runtime from the profile
    hal                                            multi-turn chat until 'exit' or ctrl-d
    hal -v ...                                     reasoning and timings on stderr
    hal sleep | wake | status                      unload everything | pre-load resident tiers | show servers

Servers start on demand the first time a tier is used. Run `hal sleep` before a game, a render,
or a big build so nothing of hal's stays resident. stdin is read whenever it is not a terminal;
where stdin is an idle pipe (`ssh host hal ...` without `-n`, editor task runners) add `</dev/null`.

## tiers

| slot   | role                                    | residency                                              |
|--------|-----------------------------------------|--------------------------------------------------------|
| small  | persistent daily driver, thinking off   | stays loaded until `hal sleep` or a long idle          |
| medium | reasoning tier and escalation target    | resident alongside small                               |
| large  | most capable model for repo-scale work  | evicts the others on start, unloads after a short idle |

Per-tier context, generation overrides, system prompt, residency, and idle timeout live in the
profile. Which model fills each slot is recorded in models/README.md. The small tier's
requirements and response shaping are in docs/small_tier.md.

## layout

    hal.py             CLI, tier routing, server start/stop/evict, streaming chat
    llm.py             OpenAI-compatible chat client, stdlib only
    bench.py           compare runtimes and slots: ttft, prefill and decode tok/s, native tool calls
    eval.py            judge a candidate model through hal's real pipeline; cases in evals/<slot>.toml
    profiles/          per-device settings including launch commands; profiles/mac.toml is the reference
    models/            small/medium/large slots: *.gguf for llama-server, *.mlx/ for mlx_lm.server
    logs/              server logs, pid and last-used files (gitignored)
    skills/            skill scripts, being reworked into JSON-schema tools
    memory/            long and short term memory, rework pending
    evals/             per-tier cases and thresholds, results.jsonl, transcripts in runs/, compare.md across models
    docs/              future_directions.md (deferred extensions), small_tier.md (model brief)

## setup (macOS)

    brew install llama.cpp                                                   # llama-server
    conda create -n hal_mlx python=3.12 && ~/miniconda3/envs/hal_mlx/bin/pip install mlx-lm   # optional, mlx comparison
    mkdir -p ~/.local/bin && ln -sf "$PWD/hal.sh" ~/.local/bin/hal           # ~/.local/bin on PATH

Link weights into the slots per models/README.md, then `hal hello`. `bench.py` compares whatever is up;
`eval.py -v` scores a candidate against the tier's brief and `eval.py --history` compares candidates.

Linux: same files plus a profile with its own launch commands. Windows: hal.bat is untested.
