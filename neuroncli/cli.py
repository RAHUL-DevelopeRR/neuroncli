"""NeuronCLI — CLI entry point with one-shot and REPL modes. v1.1"""

from __future__ import annotations

import argparse
import sys
import time

from .agent import Agent
from .config import BANNER, VERSION, AgentConfig
from .provider import create_provider


# ── ANSI Colors ───────────────────────────────────────────────────

class C:
    RESET = "\033[0m"
    BOLD = "\033[1m"
    DIM = "\033[2m"
    CYAN = "\033[96m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    RED = "\033[91m"
    MAGENTA = "\033[95m"


# ── Argument Parser ───────────────────────────────────────────────

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="neuroncli",
        description="NeuronCLI — AI Coding Agent powered by Kimi K2.5 + Ollama",
    )
    parser.add_argument(
        "task",
        nargs="?",
        default=None,
        help="Task to execute (omit for interactive REPL mode)",
    )
    parser.add_argument(
        "--model", "-m",
        default=None,
        help="Model to use (default: moonshotai/kimi-k2.5)",
    )
    parser.add_argument(
        "--provider", "-p",
        choices=["openrouter", "ollama"],
        default=None,
        help="LLM provider: openrouter (cloud, free) or ollama (local)",
    )
    parser.add_argument(
        "--dir", "-d",
        default=None,
        help="Working directory (default: current directory)",
    )
    parser.add_argument(
        "--max-iter",
        type=int,
        default=None,
        help="Max agent iterations (default: 15)",
    )
    parser.add_argument(
        "--no-stream",
        action="store_true",
        help="Disable streaming (wait for full response)",
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"NeuronCLI v{VERSION}",
    )
    return parser


# ── Interactive REPL ──────────────────────────────────────────────

def run_repl(config: AgentConfig):
    """Interactive chat/task REPL mode."""
    agent = Agent(config)

    print(BANNER)
    provider_icon = "☁️ " if config.provider == "openrouter" else "🏠"
    print(f"  {C.GREEN}Provider:{C.RESET} {provider_icon} {C.BOLD}{config.provider}{C.RESET}")
    print(f"  {C.GREEN}Model:{C.RESET}    {C.BOLD}{config.active_model}{C.RESET}")
    print(f"  {C.GREEN}Dir:{C.RESET}      {C.BOLD}{config.working_dir}{C.RESET}")
    if config.provider == "openrouter":
        print(f"  {C.GREEN}Cost:{C.RESET}     {C.BOLD}$0.00 (free tier){C.RESET}")
    print(f"\n  {C.DIM}Type a task, or use /help for commands. /exit to quit.{C.RESET}\n")

    while True:
        try:
            user_input = input(f"{C.GREEN}{C.BOLD}neuron > {C.RESET}").strip()
            if not user_input:
                continue

            # ── Slash commands ────────────────────────────────────
            if user_input.startswith("/"):
                result = _handle_repl_command(user_input, agent, config)
                if result == "exit":
                    break
                continue

            # ── Execute task ──────────────────────────────────────
            agent.run(user_input)

        except KeyboardInterrupt:
            print(f"\n{C.DIM}(Ctrl+C — type /exit to quit){C.RESET}")
            continue
        except EOFError:
            break

    print(f"\n{C.CYAN}{C.BOLD}NeuronCLI session ended.{C.RESET}\n")


def _handle_repl_command(cmd: str, agent: Agent, config: AgentConfig) -> str | None:
    """Handle slash commands in REPL mode."""
    parts = cmd.split(maxsplit=1)
    command = parts[0].lower()
    arg = parts[1] if len(parts) > 1 else ""

    if command in ("/exit", "/quit", "/q"):
        return "exit"

    elif command == "/help":
        print(f"""
{C.CYAN}{C.BOLD}Commands:{C.RESET}
  {C.YELLOW}/help{C.RESET}              Show this help
  {C.YELLOW}/exit{C.RESET}              Exit NeuronCLI
  {C.YELLOW}/clear{C.RESET}             Clear conversation history
  {C.YELLOW}/model <name>{C.RESET}      Switch model
  {C.YELLOW}/models{C.RESET}            List available models
  {C.YELLOW}/provider <name>{C.RESET}   Switch provider (openrouter / ollama)
  {C.YELLOW}/login{C.RESET}             Re-authenticate with OpenRouter
  {C.YELLOW}/logout{C.RESET}            Remove stored API key
  {C.YELLOW}/dir <path>{C.RESET}        Change working directory
  {C.YELLOW}/status{C.RESET}            Check provider connection
  {C.YELLOW}/config{C.RESET}            Show current configuration
""")

    elif command == "/clear":
        agent.clear_history()
        print(f"{C.GREEN}✓ Conversation history cleared.{C.RESET}")

    elif command == "/model":
        if not arg:
            print(f"{C.CYAN}Current model: {C.BOLD}{config.active_model}{C.RESET}")
        else:
            if config.provider == "ollama":
                config.ollama_model = arg.strip()
            else:
                config.model = arg.strip()
            agent.client = create_provider(config)
            print(f"{C.GREEN}✓ Switched to: {C.BOLD}{config.active_model}{C.RESET}")

    elif command == "/models":
        models = agent.client.list_models()
        if models:
            print(f"\n{C.CYAN}{C.BOLD}Available Models ({config.provider}):{C.RESET}")
            for m in models:
                marker = f" {C.GREEN}◄ active{C.RESET}" if m == config.active_model else ""
                print(f"  • {C.BOLD}{m}{C.RESET}{marker}")
        else:
            print(f"{C.RED}Cannot fetch model list from {config.provider}.{C.RESET}")

    elif command == "/provider":
        if not arg:
            print(f"{C.CYAN}Current provider: {C.BOLD}{config.provider}{C.RESET}")
        else:
            new_provider = arg.strip().lower()
            if new_provider not in ("openrouter", "ollama"):
                print(f"{C.RED}Unknown provider: {new_provider}. Use 'openrouter' or 'ollama'.{C.RESET}")
            else:
                config.provider = new_provider
                agent.client = create_provider(config)
                icon = "☁️ " if new_provider == "openrouter" else "🏠"
                print(f"{C.GREEN}✓ Switched to: {icon}{C.BOLD}{new_provider}{C.RESET} ({config.active_model})")

    elif command == "/dir":
        if not arg:
            print(f"{C.CYAN}Working dir: {C.BOLD}{config.working_dir}{C.RESET}")
        else:
            import os
            path = os.path.abspath(arg.strip())
            if os.path.isdir(path):
                config.working_dir = path
                print(f"{C.GREEN}✓ Working directory: {C.BOLD}{path}{C.RESET}")
            else:
                print(f"{C.RED}Not a directory: {path}{C.RESET}")

    elif command == "/status":
        client = create_provider(config)
        if client.health_check():
            print(f"{C.GREEN}[OK] {config.provider} is responding. Model: {config.active_model}{C.RESET}")
        else:
            if config.provider == "openrouter":
                print(f"{C.RED}[X] OpenRouter is not responding. Check internet connection.{C.RESET}")
            else:
                print(f"{C.RED}[X] Ollama is not responding. Start with: ollama serve{C.RESET}")

    elif command == "/config":
        print(f"""
{C.CYAN}Configuration:{C.RESET}
  Provider:         {config.provider}
  Model:            {config.active_model}
  Temperature:      {config.temperature}
  Max Tokens:       {config.max_tokens}
  Max Iterations:   {config.max_iterations}
  Working Dir:      {config.working_dir}
  Streaming:        {config.streaming}
  API Key:          {"***" + config.api_key[-6:] if config.api_key else "(none)"}
""")

    elif command == "/login":
        from .auth import run_oauth_flow, store_api_key
        new_key = run_oauth_flow()
        if new_key:
            config.api_key = new_key
            config.provider = "openrouter"
            agent.client = create_provider(config)
            print(f"{C.GREEN}✓ Re-authenticated. Provider switched to openrouter.{C.RESET}")

    elif command == "/logout":
        from .auth import CONFIG_FILE
        if CONFIG_FILE.exists():
            CONFIG_FILE.unlink()
            print(f"{C.GREEN}✓ API key removed from {CONFIG_FILE}{C.RESET}")
        else:
            print(f"{C.YELLOW}No stored API key found.{C.RESET}")

    else:
        print(f"{C.YELLOW}Unknown command: {command}. Type /help for available commands.{C.RESET}")

    return None


# ── Main Entry Point ──────────────────────────────────────────────

def main(argv: list[str] | None = None) -> int:
    # Fix Windows terminal encoding
    import os as _os
    if sys.platform == "win32":
        _os.system("")  # Enable ANSI
        try:
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
            sys.stderr.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass

    parser = build_parser()
    args = parser.parse_args(argv)

    # Build config
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

    # Check provider is reachable
    client = create_provider(config)
    if not client.health_check():
        if config.provider == "openrouter":
            print(f"\n{C.RED}{C.BOLD}[X] OpenRouter API not reachable!{C.RESET}")
            print(f"{C.YELLOW}   Check your internet connection and API key.{C.RESET}")
            print(f"{C.YELLOW}   Or switch to local: --provider ollama{C.RESET}\n")
        else:
            print(f"\n{C.RED}{C.BOLD}[X] Ollama is not running!{C.RESET}")
            print(f"{C.YELLOW}   Start it with: {C.BOLD}ollama serve{C.RESET}")
            print(f"{C.YELLOW}   Or use cloud: --provider openrouter{C.RESET}\n")
        return 1

    # One-shot mode or REPL
    if args.task:
        agent = Agent(config)
        print(BANNER)
        result = agent.run(args.task)
        return 0 if not result.aborted else 1
    else:
        run_repl(config)
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
