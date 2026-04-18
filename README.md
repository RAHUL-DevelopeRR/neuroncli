# NeuronCLI v1.1

**AI Coding Agent** — a Claude Code-style agentic CLI that runs on **Kimi K2.5** (free, cloud) with **Ollama** as local fallback.

> Built by **zero-x Corporation**

## Quick Start

```powershell
# Interactive REPL (uses Kimi K2.5 by default — free, no setup)
python -m neuroncli

# One-shot task
python -m neuroncli "add error handling to main.py"

# Use local Ollama instead
python -m neuroncli --provider ollama --model qwen2.5-coder:7b "explain this codebase"

# Point at a specific project
python -m neuroncli --dir C:\myproject "list all files"
```

## Architecture

NeuronCLI uses a **ReAct (Reasoning + Acting)** loop:

1. **Think** — Analyze the task, decide next action (Kimi K2.5 shows chain-of-thought)
2. **Act** — Call a tool (read file, edit, run command, etc.)
3. **Observe** — Process the tool result
4. **Repeat** until task is done or max iterations reached

## Dual Provider System

| Provider | Model | Cost | Speed | Requires |
|----------|-------|------|-------|----------|
| **OpenRouter** (default) | Kimi K2.5 | **$0.00** | ~34 tps | Internet |
| **Ollama** (fallback) | Any local model | Free | Varies | `ollama serve` |

Switch at runtime with `/provider ollama` or `--provider ollama`.

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

## CLI Options

| Flag | Description |
|------|-------------|
| `--model`, `-m` | Model to use |
| `--provider`, `-p` | `openrouter` or `ollama` |
| `--dir`, `-d` | Working directory |
| `--max-iter` | Max agent iterations |
| `--no-stream` | Disable token streaming |

## REPL Commands

| Command | Description |
|---------|-------------|
| `/help` | Show commands |
| `/exit` | Exit |
| `/clear` | Clear history |
| `/model <name>` | Switch model |
| `/models` | List models |
| `/provider <name>` | Switch provider (openrouter/ollama) |
| `/dir <path>` | Change working dir |
| `/status` | Check connection |
| `/config` | Show config |

## Requirements

- Python 3.10+
- Internet connection (for Kimi K2.5 via OpenRouter)
- **Optional:** Ollama installed for local fallback (`ollama serve`)
