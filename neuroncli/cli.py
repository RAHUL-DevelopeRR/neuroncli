"""NeuronCLI — CLI v2.0. Full Claude Code-style interface with modes and trust prompt."""

from __future__ import annotations

import argparse
import os
import sys

from .agent import Agent
from .config import VERSION, AgentConfig, MODE_STANDARD, MODE_PLAN, MODE_YOLO
from .provider import create_provider
from .ui import (
    render_startup_screen, _neuron_text, _ORANGE, _GREEN, _RED, _GRAY,
    RST, BOLD, DIM,
    SYM_OK, SYM_ERR, SYM_PROMPT,
)


# ── Argument Parser ───────────────────────────────────────────────

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="neuron",
        description="NeuronCLI - AI Coding Agent powered by Kimi K2.5 + Ollama",
    )
    parser.add_argument("task", nargs="?", default=None,
                        help="Task to execute (omit for interactive REPL)")
    parser.add_argument("--model", "-m", default=None, help="Model to use")
    parser.add_argument("--provider", "-p", choices=["openrouter", "ollama"],
                        default=None, help="LLM provider")
    parser.add_argument("--dir", "-d", default=None, help="Working directory")
    parser.add_argument("--max-iter", type=int, default=None)
    parser.add_argument("--no-stream", action="store_true")
    parser.add_argument("--yolo", action="store_true",
                        help="YOLO mode — skip all permission prompts")
    parser.add_argument("--plan", action="store_true",
                        help="Plan mode — reason and plan before coding")
    parser.add_argument("--version", action="version",
                        version=f"NeuronCLI v{VERSION}")
    return parser


# ── NEURON.md Support ─────────────────────────────────────────────

def _find_neuron_md(working_dir: str) -> str | None:
    p = os.path.join(working_dir, "NEURON.md")
    if os.path.isfile(p):
        try:
            with open(p, "r", encoding="utf-8", errors="replace") as f:
                return f.read()
        except OSError:
            pass
    return None


def _create_neuron_md(working_dir: str) -> None:
    template = """# NEURON.md — Project Context for NeuronCLI

## Project Overview
<!-- Describe what this project does -->

## Tech Stack
<!-- List the technologies used -->

## Project Structure
<!-- Outline the key directories and files -->

## Rules
<!-- Workflow rules for the AI agent -->
<!-- Examples: -->
<!-- - Always create a git branch before making changes -->
<!-- - Run tests after editing code -->
<!-- - Use TypeScript, not JavaScript -->

## Notes
<!-- Any additional context -->
"""
    path = os.path.join(working_dir, "NEURON.md")
    with open(path, "w", encoding="utf-8") as f:
        f.write(template)
    print(f"  {_GREEN}{BOLD}v{RST} Created NEURON.md in {working_dir}")
    print(f"  {DIM}Edit it to give NeuronCLI context about your project.{RST}\n")


# ── Trust Prompt ──────────────────────────────────────────────────

def _check_trust(working_dir: str) -> bool:
    """Check if user trusts this directory (first-run security prompt)."""
    trust_file = os.path.join(os.path.expanduser("~"), ".neuroncli", "trusted_dirs.txt")
    os.makedirs(os.path.dirname(trust_file), exist_ok=True)

    # Check if already trusted
    if os.path.isfile(trust_file):
        with open(trust_file, "r") as f:
            trusted = [line.strip() for line in f.readlines()]
            if working_dir in trusted:
                return True

    # Ask user to trust
    print(f"\n  {_ORANGE}{BOLD}Security Check{RST}")
    print(f"  {DIM}NeuronCLI can read, write, and execute commands in:{RST}")
    print(f"  {BOLD}{working_dir}{RST}\n")

    try:
        response = input(f"  {_ORANGE}Press 1 to trust this directory:{RST} ").strip()
    except (EOFError, KeyboardInterrupt):
        return False

    if response == "1":
        with open(trust_file, "a") as f:
            f.write(working_dir + "\n")
        print(f"  {_GREEN}{BOLD}v{RST} Directory trusted.\n")
        return True
    else:
        print(f"  {_RED}X{RST} Directory not trusted. Exiting.\n")
        return False


# ── Mode Display ──────────────────────────────────────────────────

_MODE_LABELS = {
    MODE_STANDARD: "",
    MODE_PLAN:     f" {_ORANGE}[plan]{RST}",
    MODE_YOLO:     f" {_RED}[yolo]{RST}",
}


# ── Interactive REPL ──────────────────────────────────────────────

def run_repl(config: AgentConfig):
    """Interactive session — full Claude Code-style experience."""
    neuron_md = _find_neuron_md(config.working_dir)
    agent = Agent(config)

    # Render startup screen
    startup = render_startup_screen(
        working_dir=config.working_dir,
        provider=config.provider,
        model=config.active_model,
        neuron_md_exists=neuron_md is not None,
    )
    print(startup)

    # Mode indicator
    mode_label = _MODE_LABELS.get(config.mode, "")
    print(f"  {DIM}Type a task, /help for commands, /exit to quit.{RST}{mode_label}\n")

    while True:
        try:
            mode_tag = _MODE_LABELS.get(config.mode, "")
            prompt_text = f"  {_ORANGE}{BOLD}>{RST}{mode_tag} "
            user_input = input(prompt_text).strip()
            if not user_input:
                continue

            # Slash commands
            if user_input.startswith("/"):
                result = _handle_command(user_input, agent, config)
                if result == "exit":
                    break
                # Refresh neuron_md in case /init was run
                neuron_md = _find_neuron_md(config.working_dir)
                continue

            # Execute task
            print()
            agent.run(user_input, neuron_md=neuron_md)

        except KeyboardInterrupt:
            print(f"\n  {DIM}(interrupted){RST}")
            continue
        except EOFError:
            break

    print(f"\n  {DIM}Session ended.{RST}\n")


def _handle_command(cmd: str, agent: Agent, config: AgentConfig) -> str | None:
    parts = cmd.split(maxsplit=1)
    command = parts[0].lower()
    arg = parts[1] if len(parts) > 1 else ""

    if command in ("/exit", "/quit", "/q"):
        return "exit"

    elif command == "/help":
        print(f"""
  {BOLD}Commands:{RST}
    {_ORANGE}/help{RST}              Show this help
    {_ORANGE}/exit{RST}              Exit NeuronCLI
    {_ORANGE}/init{RST}              Create NEURON.md project context
    {_ORANGE}/clear{RST}             Clear conversation history
    {_ORANGE}/compact{RST}           Compress context (free up memory)
    {_ORANGE}/mode <mode>{RST}       Switch mode: standard, plan, yolo
    {_ORANGE}/model <name>{RST}      Switch model
    {_ORANGE}/models{RST}            List available models
    {_ORANGE}/provider <name>{RST}   Switch provider (openrouter/ollama)
    {_ORANGE}/upgrade{RST}           Info on faster response times
    {_ORANGE}/login{RST}             Re-authenticate with OpenRouter
    {_ORANGE}/logout{RST}            Remove stored API key
    {_ORANGE}/dir <path>{RST}        Change working directory
    {_ORANGE}/status{RST}            Check provider connection
    {_ORANGE}/config{RST}            Show current configuration
""")

    elif command == "/init":
        _create_neuron_md(config.working_dir)

    elif command == "/clear":
        agent.clear_history()
        print(f"  {_GREEN}{BOLD}v{RST} History cleared.\n")

    elif command == "/compact":
        removed = agent.compact()
        if removed > 0:
            print(f"  {_GREEN}{BOLD}v{RST} Context compressed ({removed} messages removed).\n")
        else:
            print(f"  {DIM}Context is already compact.{RST}\n")

    elif command == "/mode":
        if not arg:
            print(f"  Mode: {BOLD}{config.mode}{RST}")
            print(f"  {DIM}Options: standard, plan, yolo{RST}\n")
        else:
            new_mode = arg.strip().lower()
            if new_mode in (MODE_STANDARD, MODE_PLAN, MODE_YOLO):
                config.mode = new_mode
                label = _MODE_LABELS.get(new_mode, "")
                print(f"  {_GREEN}{BOLD}v{RST} Mode: {BOLD}{new_mode}{RST}{label}\n")
            else:
                print(f"  {_RED}X{RST} Unknown mode. Use: standard, plan, yolo\n")

    elif command == "/upgrade":
        print(f"""
  {BOLD}Faster Responses{RST}

  The free tier routes through OpenRouter's shared queue,
  which can be slow during peak hours.

  {_ORANGE}Option 1: Moonshot Direct ($1 one-time){RST}
    Sign up at platform.moonshot.ai
    $1 recharge = ~230 fast tasks
    Set: NEURON_PROVIDER=moonshot

  {_ORANGE}Option 2: Local Ollama (free, offline){RST}
    Install from ollama.com
    Run: ollama pull qwen2.5-coder:7b
    Use: neuron --provider ollama

  {_ORANGE}Option 3: Self-host Kimi K2.5{RST}
    Requires a GPU with 48GB+ VRAM
    Fastest possible, zero API cost
""")

    elif command == "/model":
        if not arg:
            print(f"  Model: {BOLD}{config.active_model}{RST}\n")
        else:
            if config.provider == "ollama":
                config.ollama_model = arg.strip()
            else:
                config.model = arg.strip()
            agent.client = create_provider(config)
            print(f"  {_GREEN}{BOLD}v{RST} Model: {BOLD}{config.active_model}{RST}\n")

    elif command == "/models":
        models = agent.client.list_models()
        if models:
            print(f"\n  {BOLD}Models ({config.provider}):{RST}")
            for m in models:
                marker = f" {_GREEN}<{RST}" if m == config.active_model else ""
                print(f"    {m}{marker}")
            print()
        else:
            print(f"  {_RED}X{RST} Cannot fetch models.\n")

    elif command == "/provider":
        if not arg:
            print(f"  Provider: {BOLD}{config.provider}{RST}\n")
        else:
            new_provider = arg.strip().lower()
            if new_provider not in ("openrouter", "ollama"):
                print(f"  {_RED}X{RST} Unknown provider. Use 'openrouter' or 'ollama'.\n")
            else:
                config.provider = new_provider
                agent.client = create_provider(config)
                print(f"  {_GREEN}{BOLD}v{RST} {new_provider} ({config.active_model})\n")

    elif command == "/login":
        from .auth import run_oauth_flow
        new_key = run_oauth_flow()
        if new_key:
            config.api_key = new_key
            config.provider = "openrouter"
            agent.client = create_provider(config)
            print(f"  {_GREEN}{BOLD}v{RST} Authenticated.\n")

    elif command == "/logout":
        from .auth import CONFIG_FILE
        if CONFIG_FILE.exists():
            CONFIG_FILE.unlink()
            print(f"  {_GREEN}{BOLD}v{RST} API key removed.\n")
        else:
            print(f"  {DIM}No stored key.{RST}\n")

    elif command == "/dir":
        if not arg:
            print(f"  Dir: {BOLD}{config.working_dir}{RST}\n")
        else:
            path = os.path.abspath(arg.strip())
            if os.path.isdir(path):
                config.working_dir = path
                print(f"  {_GREEN}{BOLD}v{RST} {path}\n")
            else:
                print(f"  {_RED}X{RST} Not a directory: {path}\n")

    elif command == "/status":
        client = create_provider(config)
        if client.health_check():
            print(f"  {_GREEN}{BOLD}v{RST} {config.provider} is up ({config.active_model})\n")
        else:
            print(f"  {_RED}X{RST} {config.provider} is not responding.\n")

    elif command == "/config":
        key_display = "***" + config.api_key[-4:] if config.api_key else "(none)"
        print(f"""
  {BOLD}Configuration:{RST}
    Provider:       {config.provider}
    Model:          {config.active_model}
    Mode:           {config.mode}
    Temperature:    {config.temperature}
    Max Tokens:     {config.max_tokens}
    Max Iterations: {config.max_iterations}
    Working Dir:    {config.working_dir}
    Streaming:      {config.streaming}
    API Key:        {key_display}
""")

    else:
        print(f"  {DIM}Unknown command. Type /help{RST}\n")

    return None


# ── Main Entry Point ──────────────────────────────────────────────

def main(argv: list[str] | None = None) -> int:
    if sys.platform == "win32":
        os.system("")
        try:
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
            sys.stderr.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass

    parser = build_parser()
    args = parser.parse_args(argv)

    config = AgentConfig.from_env()
    if args.provider:
        config.provider = args.provider
    if args.model:
        if config.provider == "ollama":
            config.ollama_model = args.model
        else:
            config.model = args.model
    if args.dir:
        config.working_dir = args.dir
    if args.max_iter:
        config.max_iterations = args.max_iter
    if args.no_stream:
        config.streaming = False
    if args.yolo:
        config.mode = MODE_YOLO
        config.confirm_dangerous = False
    if args.plan:
        config.mode = MODE_PLAN

    # Check provider
    client = create_provider(config)
    if not client.health_check():
        if config.provider == "openrouter":
            print(f"\n  {_RED}X OpenRouter not reachable.{RST}")
            print(f"  {DIM}Check internet or use --provider ollama{RST}\n")
        else:
            print(f"\n  {_RED}X Ollama not running.{RST}")
            print(f"  {DIM}Start with: ollama serve{RST}\n")
        return 1

    # Trust check for REPL mode
    if not args.task and not _check_trust(config.working_dir):
        return 1

    if args.task:
        # One-shot mode
        model_short = config.active_model.split("/")[-1]
        mode_tag = f" [{config.mode}]" if config.mode != "standard" else ""
        print(f"\n  {_neuron_text()} {DIM}v{VERSION} | {config.provider} | {model_short}{mode_tag}{RST}\n")
        neuron_md = _find_neuron_md(config.working_dir)
        agent = Agent(config)
        result = agent.run(args.task, neuron_md=neuron_md)
        return 0 if not result.aborted else 1
    else:
        run_repl(config)
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
