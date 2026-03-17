# hal

A local command line assistant project: real agent integration without the risk.

```
/memory   stores long and short term memory
  lt_memory   persistent, conventionally parsed
  st_memory   last n prompt/response pairs
/pfc      prefrontal cortex — skill selection learning and execution
  /data     generated datasets based on skill list
  /weights  trained DeBERTa-large weights
/skills   hal's skill scripts
  /mac      mac skills, included in init for preload
  /linux    linux skills
```

## Requirements

- Python 3
- Ollama

## Setup

### macOS (zsh)

```bash
chmod +x /path/to/hal/hal.sh
echo 'alias hal="/path/to/hal/hal.sh"' >> ~/.zshrc && source ~/.zshrc
```

### Linux (bash)

```bash
chmod +x /path/to/hal/hal.sh
echo 'alias hal="/path/to/hal/hal.sh"' >> ~/.bashrc && source ~/.bashrc
```

### Windows

Add the repo folder to your PATH (run in PowerShell, then restart your terminal):
```powershell
[Environment]::SetEnvironmentVariable("PATH", $env:PATH + ";C:\path\to\hal", "User")
```
Once the folder is on your PATH, `hal` will work natively.

> WSL users: follow the Linux instructions instead.

## Usage

```
hal <prompt>
```
