# hal

A local command line assistant.

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
