"""NeuronCLI — Configuration module. v2.0 with modes, context management, and hybrid pricing."""

from __future__ import annotations
from .auth import ensure_api_key

import os
from dataclasses import dataclass, field
from pathlib import Path


# ── Operational Modes ─────────────────────────────────────────────
MODE_STANDARD = "standard"    # Ask permission for writes/commands
MODE_PLAN     = "plan"        # Plan first, then execute after approval
MODE_YOLO     = "yolo"        # Skip all permission prompts


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
    num_ctx: int = 8192

    # ── Shared LLM Settings ──────────────────────────────────────
    temperature: float = 0.2
    top_p: float = 0.9

    # ── Agent Behavior ────────────────────────────────────────────
    max_iterations: int = 15          # Safety cap for ReAct loop
    streaming: bool = True            # Stream tokens to terminal
    confirm_dangerous: bool = True    # Ask before destructive commands
    show_thinking: bool = True        # Show reasoning tokens (K2.5)
    mode: str = MODE_STANDARD         # standard / plan / yolo

    # ── Context Management ────────────────────────────────────────
    context_warn_percent: float = 0.85     # Warn at 85% context usage
    context_compress_percent: float = 0.92 # Auto-compress at 92%
    max_context_tokens: int = 128000       # K2.5 supports 128k

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
        api_key = ensure_api_key() or ""

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
        p = Path(path)
        if p.is_absolute():
            return p
        return Path(self.working_dir) / p

    def is_dangerous_command(self, cmd: str) -> bool:
        lower = cmd.lower().strip()
        return any(pat in lower for pat in self.dangerous_patterns)

    @property
    def active_model(self) -> str:
        if self.provider == "ollama":
            return self.ollama_model
        return self.model

    @property
    def needs_confirmation(self) -> bool:
        """Whether current mode requires user confirmation for writes."""
        return self.mode == MODE_STANDARD and self.confirm_dangerous


# ── App-wide constants ────────────────────────────────────────────

APP_NAME = "NeuronCLI"
VERSION = "2.2.0"
