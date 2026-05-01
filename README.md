# NeuronCLI

**Free AI Coding Agent** — Claude Code alternative. Native Rust binary with Azure AI + OpenRouter support.

> Built by [zero-x Corporation](https://zero-x.live)

---

## Install

```bash
# Windows / macOS / Cloud VMs
pip install neuroncli

# Debian / Ubuntu (Python 3.11+)
pip install neuroncli --break-system-packages

# Or use pipx (recommended for Debian)
pipx install neuroncli
```

> **v3.0.0** ships a native Rust binary (14MB) for maximum performance.  
> On systems without the binary, the Python implementation runs as fallback.

## Quick Start

```bash
# Start interactive REPL
neuron

# One-shot task
neuron "fix the bug in main.py"

# Plan mode — architecture first, execute later
neuron --plan "add authentication to this API"

# YOLO mode — no permission prompts
neuron --yolo "refactor src/ to use async"
```

## Zero Setup — First Run

1. Type `neuron` in any project directory
2. Browser opens to **OpenRouter** login (free account)
3. API key auto-provisioned + encrypted in `~/.neuroncli/vault.enc`
4. **Done.** No manual config, no copy-paste.

## Features

| Feature | Description |
|---------|-------------|
| **Native Rust Binary** | 14MB single binary, instant startup |
| **Plan Mode** | `/plan` generates architecture plans, `/plan off` to execute |
| **? Shortcuts Panel** | Press `?` for Claude Code-style two-column cheatsheet |
| **Shell Escape** | `!git status`, `!ls` — run commands without burning tokens |
| **Dynamic Prompt** | Shows current mode: `>`, `[plan] >`, `[edit] >`, `[auto] >` |
| **Azure AI Foundry** | GPT-5.5 primary (44K tokens/day free quota) |
| **OpenRouter Fallback** | Free-tier model when Azure quota is exhausted |
| **Directory Trust** | Interactive security prompt on first use per directory |
| **Session Persistence** | Resume previous conversations with `/resume` |
| **Git Auto-Commit** | Every AI edit is auto-committed |
| **Context Compression** | `/compact` prevents context bloat |
| **NEURON.md** | Project context file (like Claude's CLAUDE.md) |

## Shortcuts (press `?` in REPL)

| Key | Action | Key | Action |
|-----|--------|-----|--------|
| `?` | Shortcuts panel | `/help` | Full command list |
| `!cmd` | Shell command | `/plan` | Toggle plan mode |
| `Up/Down` | History | `/compact` | Compress context |
| `Ctrl+C` | Cancel | `/clear` | Reset session |
| `Ctrl+D` | Exit | `/model` | Switch model |

## Plan Mode

```
> /plan                              ← Enter plan mode
[plan] > add user authentication     ← Agent generates architecture plan
[plan] > /plan off                   ← Exit plan mode
> execute the plan                   ← Agent implements with full access
```

## CLI Flags

| Flag | Description |
|------|-------------|
| `--yolo` | Skip all permission prompts |
| `--plan` | Plan mode — reason before coding |
| `--model`, `-m` | Model to use |
| `--provider`, `-p` | `openrouter` or `ollama` |
| `--dir`, `-d` | Working directory |
| `--no-stream` | Disable token streaming |

## Requirements

- **Windows:** Works out of the box (native Rust binary)
- **Linux/macOS:** Python 3.10+ (Python fallback), or install Rust binary separately
- Internet connection for Azure AI / OpenRouter

## License

MIT — free to use, modify, and distribute commercially.

---

*By [zero-x Corporation](https://zero-x.live) — Tamil Nadu, India*
