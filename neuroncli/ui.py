"""NeuronCLI — Terminal UI components v2.0.
Brand symbols, NO emojis, consistent colors, proper table rendering."""

from __future__ import annotations

import getpass
import os

from .config import VERSION


# ── True Color ANSI ───────────────────────────────────────────────

def _rgb(r: int, g: int, b: int) -> str:
    return f"\033[38;2;{r};{g};{b}m"

def _bg_rgb(r: int, g: int, b: int) -> str:
    return f"\033[48;2;{r};{g};{b}m"

RST   = "\033[0m"
BOLD  = "\033[1m"
DIM   = "\033[2m"

# ── Brand Colors (sampled from the Neuron DNA watercolor logo) ────
_BLUE    = _rgb(65, 105, 195)
_INDIGO  = _rgb(95, 55, 140)
_RED     = _rgb(200, 50, 40)
_ORANGE  = _rgb(240, 160, 40)    # PRIMARY brand color
_GREEN   = _rgb(45, 140, 60)
_CYAN    = _rgb(80, 170, 210)
_GRAY    = _rgb(100, 100, 100)
_YELLOW  = _rgb(230, 190, 50)
_WHITE   = _rgb(220, 220, 220)

# ── Brand Symbols (NO emojis — Claude uses plain Unicode chars) ───
# Claude uses: * (asterisk) colored orange for their logo indicator
# We use the same approach with our brand color

SYM_LOGO    = f"{_ORANGE}{BOLD}*{RST}"       # Brand indicator (like Claude's flower)
SYM_BULLET  = f"{_ORANGE}{BOLD}*{RST}"       # Action bullet
SYM_THINK   = f"{_ORANGE}+{RST}"             # Thinking/working spinner
SYM_OK      = f"{_GREEN}{BOLD}v{RST}"        # Success checkmark
SYM_ERR     = f"{_RED}{BOLD}x{RST}"          # Error cross
SYM_WARN    = f"{_YELLOW}{BOLD}!{RST}"       # Warning
SYM_ARROW   = f"{_GRAY}|_{RST}"             # Sub-item tree connector
SYM_PROMPT  = f"{_ORANGE}{BOLD}>{RST}"       # Input prompt


# ── DNA Helix Logo (brand-colored ASCII art) ──────────────────────

def _build_logo() -> list[str]:
    """Build the colored DNA helix logo matching the Neuron watercolor logo.
    Blue (top) -> Indigo -> Red -> Orange -> Green (bottom)."""
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
    """'Neuron' in gradient colors: N(blue) e(red) u(red) r(orange) o(orange) n(green)."""
    return f"{_BLUE}{BOLD}N{_RED}e{_RED}u{_ORANGE}r{_ORANGE}o{_GREEN}n{RST}"


# ── Startup Screen ────────────────────────────────────────────────

def render_startup_screen(
    working_dir: str,
    provider: str,
    model: str,
    neuron_md_exists: bool = False,
) -> str:
    """Claude Code-style startup: logo left, tips right, in a box."""
    try:
        username = getpass.getuser().capitalize()
    except Exception:
        username = "Developer"

    model_short = model.split("/")[-1] if "/" in model else model

    logo = _build_logo()
    width = 64
    bc = _GRAY  # border color

    # Right panel
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
        "",
        f"{_ORANGE}{BOLD}Recent activity{RST}",
        f"{DIM}No recent activity{RST}",
    ]
    right_panel = tips + activity

    lines = []
    title = f" {_neuron_text()} {DIM}CLI v{VERSION}{RST} "
    lines.append(f"  {bc}+-{RST}{title}{bc}{'-' * (width - 22)}+{RST}")
    lines.append(f"  {bc}|{RST}")
    lines.append(f"  {bc}|{RST}      {BOLD}Welcome, {username}!{RST}")
    lines.append(f"  {bc}|{RST}")

    ri = 0
    for logo_line in logo:
        right = right_panel[ri] if ri < len(right_panel) else ""
        ri += 1
        lines.append(f"  {bc}|{RST}   {logo_line}     {right}")

    while ri < len(right_panel):
        lines.append(f"  {bc}|{RST}{'':30}{right_panel[ri]}")
        ri += 1

    lines.append(f"  {bc}|{RST}")
    lines.append(f"  {bc}|{RST}      {DIM}{model_short} . {provider}{RST}")
    lines.append(f"  {bc}|{RST}      {DIM}{working_dir}{RST}")
    lines.append(f"  {bc}|{RST}")
    lines.append(f"  {bc}+{'-' * width}+{RST}")

    return "\n".join(lines)
