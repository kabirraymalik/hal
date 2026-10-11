# models

hal has three slots. Slot `<name>` loads `models/<name>.<ext>`: `.gguf` for llama-server, `.mlx/`
for mlx_lm.server. Symlinks are expected; weights are gitignored. Record what each slot points to
in the table below.

| slot   | llama-server loads   | mlx_lm.server loads  |
|--------|----------------------|----------------------|
| small  | `models/small.gguf`  | `models/small.mlx/`  |
| medium | `models/medium.gguf` | `models/medium.mlx/` |
| large  | `models/large.gguf`  | `models/large.mlx/`  |

Split GGUFs: link the first shard (`...-00001-of-0000N.gguf`); hal passes the resolved path so
llama.cpp finds the rest. Models downloaded with LM Studio / Bionic live under
`~/.lmstudio/models/<publisher>/<repo>/` and can be linked from there. Never let Bionic and hal
hold the same large model at the same time.

Small-slot candidates and their download links: `docs/small_tier_shortlist.md`; downloads land in `~/models/`.

## current

| slot   | runtime | model                                | quant  | context | notes |
|--------|---------|--------------------------------------|--------|---------|-------|
| small  | llama   | Qwen3.6-35B-A3B (`~/models/Qwen3.6-35B-A3B-UD-Q4_K_M.gguf`) | UD-Q4_K_M | 32768 | **selected 2026-10-11**; 96%, ~104 tok/s warm, ~20 GB resident; docs/small_tier.md |
| small  | mlx     | Qwen3.6-35B-A3B (`~/models/Qwen3.6-35B-A3B-4bit-mlx/`) | 4-bit | n/a | comparison runtime: 84 tok/s decode, 3890 tok/s prefill, 96%; `hal -r mlx` |
| medium | llama   |                                      |        |         | |
| medium | mlx     |                                      |        |         | |
| large  | llama   |                                      |        |         | candidate: Qwen3.8-Flash-Next UD-IQ4_XS, 87 GB, in `~/.lmstudio/models/unsloth/` |
| large  | mlx     |                                      |        |         | |

## getting weights

GGUF for llama-server, from a Hugging Face repo, then link it into a slot:

    curl -L -o ~/models/<file>.gguf https://huggingface.co/<org>/<repo>/resolve/main/<file>.gguf
    ln -sf ~/models/<file>.gguf models/small.gguf

MLX for mlx_lm.server, usually a converted repo under mlx-community:

    ~/miniconda3/envs/hal_mlx/bin/hf download mlx-community/<repo> --local-dir models/small.mlx

Then `hal hello` starts the slot on demand, or `bench.py` to compare runtimes.
