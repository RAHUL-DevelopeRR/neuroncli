"""NeuronCLI — Configuration module. v1.1 with OpenRouter + Ollama dual-provider."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class AgentConfig:
    """All configurable settings for the NeuronCLI agent."""

    # ── Provider Selection ────────────────────────────────────────
    provider: str = "openrouter"      # "openrouter" or "ollama"

    # ── OpenRouter Settings ───────────────────────────────────────
    api_key: str = ""
    model: str = "moonshotai/kimi-k2.5"     # Free reasoning model
    max_tokens: int = 4096

    # ── Ollama Settings (fallback) ────────────────────────────────
    ollama_model: str = "qwen2.5-coder:7b"
    base_url: str = "http://localhost:11434"
    num_ctx: int = 8192               # Context window (tokens)

    # ── Shared LLM Settings ──────────────────────────────────────
    temperature: float = 0.2          # Low = more precise code output
    top_p: float = 0.9

    # ── Agent Behavior ────────────────────────────────────────────
    max_iterations: int = 15          # Safety cap for ReAct loop
    streaming: bool = True            # Stream tokens to terminal
    confirm_dangerous: bool = True    # Ask before destructive commands
    show_thinking: bool = True        # Show reasoning tokens (K2.5)

    # ── Working Directory ─────────────────────────────────────────
    working_dir: str = field(default_factory=lambda: os.getcwd())

    # ── Dangerous command patterns (require confirmation) ─────────
    dangerous_patterns: tuple[str, ...] = (
        "rm ", "del ", "rmdir", "format ",
        "shutdown", "restart",
        "> /dev/null", "| rm",
        "drop table", "drop database",
        "git push --force", "git reset --hard",
    )

    @classmethod
    def from_env(cls) -> "AgentConfig":
        """Build config from environment variables with defaults."""
        provider = os.environ.get("NEURON_PROVIDER", "openrouter")
        api_key = os.environ.get(
            "OPENROUTER_API_KEY",
            "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"
        )

        # If no API key and provider is openrouter, fall back to ollama
        if provider == "openrouter" and not api_key:
            provider = "ollama"

        model = os.environ.get("NEURON_MODEL", "moonshotai/kimi-k2.5")
        ollama_model = os.environ.get("NEURON_OLLAMA_MODEL", "qwen2.5-coder:7b")

        return cls(
            provider=provider,
            api_key=api_key,
            model=model,
            ollama_model=ollama_model,
            base_url=os.environ.get("OLLAMA_HOST", "http://localhost:11434"),
            temperature=float(os.environ.get("NEURON_TEMPERATURE", "0.2")),
            max_iterations=int(os.environ.get("NEURON_MAX_ITER", "15")),
            max_tokens=int(os.environ.get("NEURON_MAX_TOKENS", "4096")),
            num_ctx=int(os.environ.get("NEURON_CTX", "8192")),
            working_dir=os.environ.get("NEURON_WORK_DIR", os.getcwd()),
        )

    def resolve_path(self, path: str) -> Path:
        """Resolve a relative path against the working directory."""
        p = Path(path)
        if p.is_absolute():
            return p
        return Path(self.working_dir) / p

    def is_dangerous_command(self, cmd: str) -> bool:
        """Check if a command matches any dangerous pattern."""
        lower = cmd.lower().strip()
        return any(pat in lower for pat in self.dangerous_patterns)

    @property
    def active_model(self) -> str:
        """Return the active model name depending on provider."""
        if self.provider == "ollama":
            return self.ollama_model
        return self.model


# ── App-wide constants ────────────────────────────────────────────

APP_NAME = "NeuronCLI"
VERSION = "1.1.0"
BANNER = f"""
\033[96m\033[1m╔══════════════════════════════════════════════════╗
║                                                  ║
║   >>  N E U R O N  C L I  v{VERSION}              ║
║   AI Coding Agent · Kimi K2.5 + Ollama           ║
║   zero-x Corporation                             ║
║                                                  ║
╚══════════════════════════════════════════════════╝\033[0m"""
