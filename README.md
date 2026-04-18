# NeuronCLI v1.1

**AI Coding Agent** — a Claude Code-style agentic CLI that runs on **Kimi K2.5** (free, cloud) with **Ollama** as local fallback.

> Built by **zero-x Corporation**

## Quick Start

```powershell
# Just run it — first launch auto-provisions your free API key
python -m neuroncli

# One-shot task
python -m neuroncli "add error handling to main.py"

# Use local Ollama instead
python -m neuroncli --provider ollama --model qwen2.5-coder:7b "explain this codebase"
```

## First Run — Zero Setup

On first launch, NeuronCLI automatically:
1. Opens your browser to **OpenRouter** login
2. You sign up or log in (free account)
3. An API key is provisioned and saved locally to `~/.neuroncli/config.json`
4. **Done.** No copy-paste, no manual config.

All subsequent launches use the stored key automatically.

## Architecture

NeuronCLI uses a **ReAct (Reasoning + Acting)** loop:

1. **Think** — Analyze the task (Kimi K2.5 shows chain-of-thought in dimmed text)
2. **Act** — Call a tool (read file, edit, run command, etc.)
3. **Observe** — Process the tool result
4. **Repeat** until task is done or max iterations reached

## Dual Provider System

| Provider | Model | Cost | Speed | Requires |
|----------|-------|------|-------|----------|
| **OpenRouter** (default) | Kimi K2.5 | **$0.00** | ~34 tps | Internet |
| **Ollama** (fallback) | Any local model | Free | Varies | `ollama serve` |

Switch at runtime: `/provider ollama` or `--provider ollama`

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
| `/provider <name>` | Switch provider |
| `/login` | Re-authenticate with OpenRouter |
| `/logout` | Remove stored API key |
| `/dir <path>` | Change working dir |
| `/status` | Check connection |
| `/config` | Show config |

## File Structure

```
neuroncli/
├── __init__.py          # Package exports
├── __main__.py          # Entry point (python -m neuroncli)
├── agent.py             # ReAct loop engine (parse tool calls, execute)
├── auth.py              # OAuth PKCE auto-key provisioning
├── cli.py               # CLI with REPL mode and slash commands
├── config.py            # Dual-provider config (OpenRouter + Ollama)
├── ollama_client.py     # Local Ollama HTTP client
├── openrouter_client.py # OpenRouter HTTP client (Kimi K2.5 reasoning)
├── prompts.py           # System prompt builder with tool docs
├── provider.py          # Provider abstraction layer
└── tools.py             # Tool implementations (read, write, edit, etc.)
```

## Requirements

- Python 3.10+
- Internet connection (for Kimi K2.5 via OpenRouter)
- **Optional:** Ollama installed for local fallback (`ollama serve`)
