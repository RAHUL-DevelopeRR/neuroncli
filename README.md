# NeuronCLI

**Free AI Coding Agent** — Claude Code alternative powered by Kimi K2.5. Works on **Windows, Linux, macOS**.

> Built by [zero-x Corporation](https://zero-x.live)

---

## Install

```bash
# From PyPI (all platforms)
pip install neuroncli

# Or from source
git clone https://github.com/RAHUL-DevelopeRR/neuroncli.git
cd neuroncli
pip install -e .
```

```bash
# Linux/macOS one-liner
curl -fsSL https://raw.githubusercontent.com/RAHUL-DevelopeRR/neuroncli/master/install.sh | bash
```

## Quick Start

```bash
# Start interactive REPL
neuron

# One-shot task
neuron "fix the bug in main.py"

# YOLO mode — no permission prompts
neuron --yolo "refactor src/ to use async"

# Plan mode — think first, code later
neuron --plan "add authentication to this API"

# Use local Ollama instead
neuron --provider ollama "explain this codebase"
```

## Zero Setup — First Run

1. Type `neuron` in any project directory
2. Browser opens to **OpenRouter** login (free account)
3. API key auto-provisioned + saved to `~/.neuroncli/config.json`
4. **Done.** No manual config, no copy-paste.

## Features

| Feature | Description |
|---------|-------------|
| **Parallel Tool Execution** | Reads 5 files simultaneously, not one-by-one |
| **Git Auto-Commit** | Every AI edit is auto-committed like Aider |
| **Context Compression** | H2A-style compression prevents context bloat |
| **3 Modes** | Standard (ask permission), Plan (think first), YOLO (full auto) |
| **Session Persistence** | Resume previous conversations with `/resume` |
| **Brand Color Output** | Clean terminal output with colored tables, headers |
| **NEURON.md** | Project context file (like Claude's CLAUDE.md) |
| **Token Tracking** | Shows token usage per session |
| **Dual Provider** | OpenRouter (cloud, free) + Ollama (local, offline) |

## Modes

```bash
neuron                    # Standard — asks before writing/running
neuron --plan             # Plan — generates plan, waits for approval
neuron --yolo             # YOLO — full autonomous, no prompts
```

Switch at runtime: `/mode plan`, `/mode yolo`, `/mode standard`

## Available Tools

| Tool | Description |
|------|-------------|
| `read_file` | Read file contents with line numbers |
| `write_file` | Create or overwrite a file |
| `edit_file` | Surgical find-and-replace edit |
| `list_directory` | Tree view of directory contents |
| `run_command` | Execute shell commands |
| `search_in_files` | Grep-style search across files |
| `get_project_structure` | Full project overview |

## REPL Commands

| Command | Description |
|---------|-------------|
| `/help` | Show all commands |
| `/init` | Create NEURON.md project context |
| `/compact` | Compress context (free up memory) |
| `/mode <mode>` | Switch: standard, plan, yolo |
| `/model <name>` | Switch model |
| `/provider <name>` | Switch: openrouter, ollama |
| `/upgrade` | Info on faster response times |
| `/clear` | Clear conversation history |
| `/config` | Show current configuration |
| `/exit` | Exit |

## CLI Flags

| Flag | Description |
|------|-------------|
| `--yolo` | Skip all permission prompts |
| `--plan` | Plan mode — reason before coding |
| `--model`, `-m` | Model to use |
| `--provider`, `-p` | `openrouter` or `ollama` |
| `--dir`, `-d` | Working directory |
| `--no-stream` | Disable token streaming |

## Architecture

```
neuroncli/
  agent.py              # ReAct engine — parallel tools, context compression
  auth.py               # OpenRouter OAuth auto-provisioning
  cli.py                # REPL + slash commands
  config.py             # Modes (standard/plan/yolo)
  git_integration.py    # Auto-commit AI edits
  session.py            # Save/resume conversations
  prompts.py            # Mode-aware system prompt builder
  tools.py              # Tool registry + 7 tool implementations
  ui.py                 # Brand colors, startup screen
  provider.py           # Provider abstraction layer
  openrouter_client.py  # OpenRouter (Kimi K2.5)
  ollama_client.py      # Local Ollama
tests/
  test_agent.py         # 18 unit tests
```

## Requirements

- **Python 3.10+**
- Internet connection (for Kimi K2.5 via OpenRouter)
- **Optional:** [Ollama](https://ollama.com) for local offline mode

## License

MIT — free to use, modify, and distribute commercially.

---

*By [zero-x Corporation](https://zero-x.live) — Tamil Nadu, India*
