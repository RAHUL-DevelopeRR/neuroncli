"""NeuronCLI — Terminal UI components. Claude Code-style startup screen + logo."""

from __future__ import annotations

import getpass
import os
from pathlib import Path

from .config import VERSION


# ── True Color ANSI ───────────────────────────────────────────────

def _rgb(r: int, g: int, b: int) -> str:
    return f"\033[38;2;{r};{g};{b}m"

RST   = "\033[0m"
BOLD  = "\033[1m"
DIM   = "\033[2m"

# Logo colors (sampled from the Neuron DNA watercolor logo)
_BLUE    = _rgb(65, 105, 195)
_INDIGO  = _rgb(95, 55, 140)
_RED     = _rgb(200, 50, 40)
_ORANGE  = _rgb(240, 160, 40)
_GREEN   = _rgb(45, 140, 60)
_CYAN    = _rgb(80, 170, 210)
_GRAY    = _rgb(100, 100, 100)
_YELLOW  = _rgb(230, 190, 50)


# ── DNA Helix Logo (colored, matching the Neuron logo) ────────────

def _build_logo() -> list[str]:
    """Build the colored DNA helix logo lines."""
    return [
        f"        {_BLUE}*    *{RST}",
        f"       {_BLUE}/ \\  / \\{RST}",
        f"      {_BLUE}/ {_INDIGO}/ \\/ \\{_BLUE} \\{RST}",
        f"     {_INDIGO}/ / /--\\ \\ \\{RST}",
        f"    {_INDIGO}| {_RED}/--------\\{_INDIGO} |{RST}",
        f"     {_RED}X----------X{RST}",
        f"    {_RED}| {_ORANGE}\\--------/{_RED} |{RST}",
        f"     {_ORANGE}\\ \\ \\--/ / /{RST}",
        f"      {_ORANGE}\\ {_GREEN}\\    /{_ORANGE} /{RST}",
        f"       {_GREEN}\\ /  \\ /{RST}",
        f"        {_GREEN}*    *{RST}",
    ]


def _neuron_text() -> str:
    """The word 'Neuron' in gradient colors matching the logo."""
    return (
        f"{_BLUE}{BOLD}N{_RED}e{_RED}u{_ORANGE}r{_ORANGE}o{_GREEN}n{RST}"
    )


# ── Startup Screen (Claude Code-style box layout) ────────────────

def render_startup_screen(
    working_dir: str,
    provider: str,
    model: str,
    neuron_md_exists: bool = False,
) -> str:
    """
    Render the full startup screen like Claude Code:
    
    ┌─ Neuron CLI v1.1.0 ───────────────────────────────────────┐
    │                                                            │
    │   Welcome, Rahul!          Tips for getting started        │
    │                            Run /init to create a           │
    │       *    *               NEURON.md file...               │
    │      / \  / \                                              │
    │     /  /\/\  \             Recent activity                 │
    │    / / /--\ \ \            No recent activity              │
    │   | /--------\ |                                           │
    │    X----------X                                            │
    │   | \--------/ |                                           │
    │    \ \ \--/ / /                                            │
    │     \  \  /  /                                             │
    │      \ /  \ /     Kimi K2.5 · OpenRouter                  │
    │       *    *      C:\current\dir                           │
    │                                                            │
    └────────────────────────────────────────────────────────────┘
    """
    # Get username
    try:
        username = getpass.getuser().capitalize()
    except Exception:
        username = "Developer"

    model_short = model.split("/")[-1] if "/" in model else model
    provider_icon = "cloud" if provider == "openrouter" else "local"

    # Logo lines
    logo = _build_logo()

    # Right panel content
    if neuron_md_exists:
        tips = [
            f"{_ORANGE}{BOLD}Tips{RST}",
            f"{DIM}NEURON.md loaded for this project{RST}",
            f"{DIM}Type a task to get started{RST}",
        ]
    else:
        tips = [
            f"{_ORANGE}{BOLD}Tips for getting started{RST}",
            f"{DIM}Run {RST}/init{DIM} to create a NEURON.md{RST}",
            f"{DIM}file with project context...{RST}",
        ]

    activity = [
        f"",
        f"{_ORANGE}{BOLD}Recent activity{RST}",
        f"{DIM}No recent activity{RST}",
    ]

    right_panel = tips + activity

    # Build the box
    width = 64
    border_color = _GRAY

    lines = []
    title = f" {_neuron_text()} {DIM}CLI v{VERSION}{RST} "
    lines.append(f"  {border_color}+-{RST}{title}{border_color}{'-' * (width - 22)}+{RST}")

    # Welcome line
    lines.append(f"  {border_color}|{RST}")
    lines.append(f"  {border_color}|{RST}      {BOLD}Welcome, {username}!{RST}")
    lines.append(f"  {border_color}|{RST}")

    # Logo left + tips right (side by side)
    right_start = 0
    for i, logo_line in enumerate(logo):
        # Pad logo to fixed width (raw chars ~22 wide)
        padded_logo = f"  {logo_line}"

        # Right panel item
        if right_start < len(right_panel):
            right_text = right_panel[right_start]
            right_start += 1
        else:
            right_text = ""

        lines.append(f"  {border_color}|{RST} {padded_logo}     {right_text}")

    # Remaining right panel items
    while right_start < len(right_panel):
        lines.append(f"  {border_color}|{RST}{'':30}{right_panel[right_start]}")
        right_start += 1

    # Model and directory info
    lines.append(f"  {border_color}|{RST}")
    lines.append(f"  {border_color}|{RST}      {DIM}{model_short} · {provider}{RST}")
    lines.append(f"  {border_color}|{RST}      {DIM}{working_dir}{RST}")
    lines.append(f"  {border_color}|{RST}")
    lines.append(f"  {border_color}+{'-' * width}+{RST}")

    return "\n".join(lines)


# ── Compact Status Line ──────────────────────────────────────────

def render_status_line(
    model: str,
    tools_summary: str,
    elapsed: float,
    cost: str = "$0.00",
) -> str:
    """Render the bottom status line after agent completes."""
    model_short = model.split("/")[-1] if "/" in model else model
    return f"  {DIM}{model_short} · {tools_summary} · {elapsed:.1f}s · {cost}{RST}"


# ── Bullet-style Output ─────────────────────────────────────────

def bullet(text: str, color: str = "") -> str:
    """Agent action bullet point."""
    c = color or _ORANGE
    return f"  {c}{BOLD}*{RST} {text}"


def sub_item(text: str) -> str:
    """Sub-item under a bullet."""
    return f"    {DIM}|_{RST} {DIM}{text}{RST}"


def tool_line(text: str) -> str:
    """Compact tool summary line (indented under bullet)."""
    return f"    {_GREEN}{text}{RST}"


def error_line(text: str) -> str:
    """Error display."""
    return f"  {_RED}X {text}{RST}"


def success_line(text: str) -> str:
    """Success indicator."""
    return f"  {_GREEN}{BOLD}v{RST} {text}"
