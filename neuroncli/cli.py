"""NeuronCLI — CLI entry point. Claude Code-style clean interface. v1.1"""

from __future__ import annotations

import argparse
import sys
import time

from .agent import Agent
from .config import VERSION, AgentConfig
from .provider import create_provider


# ── ANSI Colors ───────────────────────────────────────────────────

class C:
    RESET   = "\033[0m"
    BOLD    = "\033[1m"
    DIM     = "\033[2m"
    CYAN    = "\033[96m"
    GREEN   = "\033[92m"
    YELLOW  = "\033[93m"
    RED     = "\033[91m"
    MAGENTA = "\033[95m"
    BLUE    = "\033[94m"
    GRAY    = "\033[90m"
    WHITE   = "\033[97m"
    # Orange-ish for branding (via 256-color)
    ORANGE  = "\033[38;5;208m"


# ── Terminal Logo ─────────────────────────────────────────────────

LOGO = f"""
{C.ORANGE}{C.BOLD}  ╱╲
 ╱  ╲   ┃╻╻ ┏━╸╻ ╻┏━┓┏━┓┏╻╻
╱ ╱╲ ╲  ┃┃┃ ┣╸ ┃ ┃┣┳┛┃ ┃┃┃┃
╲ ╲╱ ╱  ┃┗┛ ┗━╸┗━┛╹╹┗┗━┛┃┗┛
 ╲  ╱   {C.RESET}{C.DIM}AI Coding Agent · v{VERSION}{C.RESET}
{C.ORANGE}{C.BOLD}  ╲╱{C.RESET}
"""

LOGO_COMPACT = f"{C.ORANGE}{C.BOLD}🧬 NEURON{C.RESET} {C.DIM}v{VERSION}{C.RESET}"


# ── Argument Parser ───────────────────────────────────────────────

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="neuron",
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
        "--no-confirm",
        action="store_true",
        help="Skip confirmation prompts for file writes",
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"NeuronCLI v{VERSION}",
    )
    return parser


# ── Interactive REPL ──────────────────────────────────────────────

def run_repl(config: AgentConfig):
    """Interactive session — Claude Code-style clean interface."""
    agent = Agent(config)

    print(LOGO)
    model_short = config.active_model.split("/")[-1]
    provider_icon = "☁" if config.provider == "openrouter" else "⌂"
    print(f"  {C.DIM}{provider_icon} {config.provider} · {model_short} · {config.working_dir}{C.RESET}")
    print(f"  {C.DIM}Type a task or /help. Ctrl+C to cancel, /exit to quit.{C.RESET}\n")

    while True:
        try:
            user_input = input(f"  {C.GREEN}{C.BOLD}>{C.RESET} ").strip()
            if not user_input:
                continue

            # ── Slash commands ────────────────────────────────
            if user_input.startswith("/"):
                result = _handle_command(user_input, agent, config)
                if result == "exit":
                    break
                continue

            # ── Execute task ──────────────────────────────────
            print()  # Spacing before output
            agent.run(user_input)

        except KeyboardInterrupt:
            print(f"\n  {C.DIM}(interrupted){C.RESET}")
            continue
        except EOFError:
            break

    print(f"\n  {C.DIM}Session ended.{C.RESET}\n")


def _handle_command(cmd: str, agent: Agent, config: AgentConfig) -> str | None:
    """Handle slash commands."""
    parts = cmd.split(maxsplit=1)
    command = parts[0].lower()
    arg = parts[1] if len(parts) > 1 else ""

    if command in ("/exit", "/quit", "/q"):
        return "exit"

    elif command == "/help":
        print(f"""
  {C.BOLD}Commands:{C.RESET}
    {C.YELLOW}/help{C.RESET}              Show this help
    {C.YELLOW}/exit{C.RESET}              Exit NeuronCLI
    {C.YELLOW}/clear{C.RESET}             Clear conversation history
    {C.YELLOW}/model <name>{C.RESET}      Switch model
    {C.YELLOW}/models{C.RESET}            List available models
    {C.YELLOW}/provider <name>{C.RESET}   Switch provider (openrouter/ollama)
    {C.YELLOW}/login{C.RESET}             Re-authenticate with OpenRouter
    {C.YELLOW}/logout{C.RESET}            Remove stored API key
    {C.YELLOW}/dir <path>{C.RESET}        Change working directory
    {C.YELLOW}/status{C.RESET}            Check provider connection
    {C.YELLOW}/config{C.RESET}            Show current configuration
""")

    elif command == "/clear":
        agent.clear_history()
        print(f"  {C.GREEN}✓{C.RESET} History cleared.")

    elif command == "/model":
        if not arg:
            print(f"  Model: {C.BOLD}{config.active_model}{C.RESET}")
        else:
            if config.provider == "ollama":
                config.ollama_model = arg.strip()
            else:
                config.model = arg.strip()
            agent.client = create_provider(config)
            print(f"  {C.GREEN}✓{C.RESET} Model: {C.BOLD}{config.active_model}{C.RESET}")

    elif command == "/models":
        models = agent.client.list_models()
        if models:
            print(f"\n  {C.BOLD}Models ({config.provider}):{C.RESET}")
            for m in models:
                marker = f" {C.GREEN}◄{C.RESET}" if m == config.active_model else ""
                print(f"    {m}{marker}")
            print()
        else:
            print(f"  {C.RED}✗{C.RESET} Cannot fetch models.")

    elif command == "/provider":
        if not arg:
            print(f"  Provider: {C.BOLD}{config.provider}{C.RESET}")
        else:
            new_provider = arg.strip().lower()
            if new_provider not in ("openrouter", "ollama"):
                print(f"  {C.RED}✗{C.RESET} Unknown provider. Use 'openrouter' or 'ollama'.")
            else:
                config.provider = new_provider
                agent.client = create_provider(config)
                icon = "☁" if new_provider == "openrouter" else "⌂"
                print(f"  {C.GREEN}✓{C.RESET} {icon} {new_provider} ({config.active_model})")

    elif command == "/login":
        from .auth import run_oauth_flow
        new_key = run_oauth_flow()
        if new_key:
            config.api_key = new_key
            config.provider = "openrouter"
            agent.client = create_provider(config)
            print(f"  {C.GREEN}✓{C.RESET} Authenticated.")

    elif command == "/logout":
        from .auth import CONFIG_FILE
        if CONFIG_FILE.exists():
            CONFIG_FILE.unlink()
            print(f"  {C.GREEN}✓{C.RESET} API key removed.")
        else:
            print(f"  {C.DIM}No stored key.{C.RESET}")

    elif command == "/dir":
        if not arg:
            print(f"  Dir: {C.BOLD}{config.working_dir}{C.RESET}")
        else:
            import os
            path = os.path.abspath(arg.strip())
            if os.path.isdir(path):
                config.working_dir = path
                print(f"  {C.GREEN}✓{C.RESET} {path}")
            else:
                print(f"  {C.RED}✗{C.RESET} Not a directory: {path}")

    elif command == "/status":
        client = create_provider(config)
        if client.health_check():
            print(f"  {C.GREEN}✓{C.RESET} {config.provider} is up ({config.active_model})")
        else:
            print(f"  {C.RED}✗{C.RESET} {config.provider} is not responding.")

    elif command == "/config":
        key_display = "***" + config.api_key[-4:] if config.api_key else "(none)"
        print(f"""
  {C.BOLD}Configuration:{C.RESET}
    Provider:       {config.provider}
    Model:          {config.active_model}
    Temperature:    {config.temperature}
    Max Tokens:     {config.max_tokens}
    Max Iterations: {config.max_iterations}
    Working Dir:    {config.working_dir}
    Streaming:      {config.streaming}
    API Key:        {key_display}
""")

    else:
        print(f"  {C.DIM}Unknown command. Type /help{C.RESET}")

    return None


# ── Main Entry Point ──────────────────────────────────────────────

def main(argv: list[str] | None = None) -> int:
    import os as _os
    if sys.platform == "win32":
        _os.system("")  # Enable ANSI escape codes
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
    if hasattr(args, 'no_confirm') and args.no_confirm:
        config.confirm_dangerous = False

    # Check provider
    client = create_provider(config)
    if not client.health_check():
        if config.provider == "openrouter":
            print(f"\n  {C.RED}✗ OpenRouter not reachable.{C.RESET}")
            print(f"  {C.DIM}Check internet or use --provider ollama{C.RESET}\n")
        else:
            print(f"\n  {C.RED}✗ Ollama not running.{C.RESET}")
            print(f"  {C.DIM}Start with: ollama serve{C.RESET}\n")
        return 1

    if args.task:
        # One-shot mode
        print(f"\n{LOGO_COMPACT}")
        model_short = config.active_model.split("/")[-1]
        print(f"  {C.DIM}{config.provider} · {model_short} · {config.working_dir}{C.RESET}\n")
        agent = Agent(config)
        result = agent.run(args.task)
        return 0 if not result.aborted else 1
    else:
        run_repl(config)
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
