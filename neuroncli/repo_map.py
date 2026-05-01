"""NeuronCLI — AST-based semantic repo map.

Generates a concise structural overview of the project for the system prompt.
Replaces the 200-item directory dump with ~500 tokens of meaningful context.
Inspired by Aider's repo-map concept.
"""

from __future__ import annotations

import ast
import os
from pathlib import Path


# Directories to always skip
_SKIP_DIRS = {
    ".git", "__pycache__", "node_modules", ".venv", "venv",
    ".mypy_cache", ".pytest_cache", "dist", "build", ".tox",
    ".eggs", ".next", ".nuxt", "coverage", ".coverage",
}


def build_repo_map(working_dir: str, max_tokens: int = 500) -> str:
    """Generate a concise structural overview of the project.

    Output format:
        src/
          agent.py: class Agent [run, compact, clear_history]
          tools.py: class ToolRegistry [register, execute]; read_file, write_file
        tests/
          test_agent.py: TestAgent [test_run_simple, test_tools]
    """
    root = Path(working_dir)
    if not root.is_dir():
        return f"[Not a directory: {working_dir}]"

    lines: list[str] = []
    _walk_dir(root, root, lines, depth=0, max_depth=3)

    full_map = "\n".join(lines)
    return _smart_truncate(full_map, max_tokens)


def _walk_dir(base: Path, current: Path, lines: list[str], depth: int, max_depth: int):
    """Recursively build the repo map."""
    if depth >= max_depth:
        return

    try:
        entries = sorted(current.iterdir(), key=lambda e: (not e.is_dir(), e.name.lower()))
    except (PermissionError, OSError):
        return

    for entry in entries:
        if entry.name.startswith(".") or entry.name in _SKIP_DIRS:
            continue

        rel = entry.relative_to(base)
        indent = "  " * depth

        if entry.is_dir():
            # Count meaningful files in directory
            try:
                child_count = sum(1 for c in entry.iterdir()
                                  if not c.name.startswith(".") and c.name not in _SKIP_DIRS)
            except (PermissionError, OSError):
                child_count = 0

            if child_count > 0:
                lines.append(f"{indent}{entry.name}/")
                _walk_dir(base, entry, lines, depth + 1, max_depth)

        elif entry.is_file():
            symbols = _extract_symbols(entry)
            if symbols:
                lines.append(f"{indent}{entry.name}: {symbols}")
            else:
                lines.append(f"{indent}{entry.name}")


def _extract_symbols(filepath: Path) -> str:
    """Extract key symbols from a file based on its type."""
    ext = filepath.suffix.lower()

    if ext == ".py":
        return _extract_python_symbols(filepath)
    elif ext in (".js", ".ts", ".jsx", ".tsx"):
        return _extract_js_symbols(filepath)
    elif ext == ".go":
        return _extract_go_symbols(filepath)

    # For other files, return size hint
    try:
        size = filepath.stat().st_size
        if size > 10240:
            return f"({size // 1024}KB)"
    except OSError:
        pass
    return ""


def _extract_python_symbols(filepath: Path) -> str:
    """Use Python's ast module to extract classes and top-level functions."""
    try:
        source = filepath.read_text(encoding="utf-8", errors="replace")
        tree = ast.parse(source, filename=str(filepath))
    except (SyntaxError, OSError, ValueError):
        return ""

    parts = []

    for node in ast.iter_child_nodes(tree):
        if isinstance(node, ast.ClassDef):
            methods = [n.name for n in ast.iter_child_nodes(node)
                       if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
                       and not n.name.startswith("_")]
            if methods:
                methods_str = ", ".join(methods[:5])
                if len(methods) > 5:
                    methods_str += f" +{len(methods) - 5}"
                parts.append(f"class {node.name} [{methods_str}]")
            else:
                parts.append(f"class {node.name}")

        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if not node.name.startswith("_"):
                parts.append(node.name + "()")

    if not parts:
        # Fallback: count lines
        try:
            line_count = len(source.splitlines())
            return f"({line_count} lines)"
        except Exception:
            pass

    return "; ".join(parts[:6])


def _extract_js_symbols(filepath: Path) -> str:
    """Basic regex extraction for JS/TS files."""
    import re
    try:
        source = filepath.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""

    parts = []

    # Classes
    for match in re.finditer(r'(?:export\s+)?class\s+(\w+)', source):
        parts.append(f"class {match.group(1)}")
    # Named exports / functions
    for match in re.finditer(r'(?:export\s+)?(?:async\s+)?function\s+(\w+)', source):
        parts.append(match.group(1) + "()")
    # Arrow function exports
    for match in re.finditer(r'export\s+(?:const|let)\s+(\w+)\s*=', source):
        name = match.group(1)
        if name not in [p.rstrip("()") for p in parts]:
            parts.append(name)

    return "; ".join(parts[:6])


def _extract_go_symbols(filepath: Path) -> str:
    """Basic regex extraction for Go files."""
    import re
    try:
        source = filepath.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""

    parts = []
    for match in re.finditer(r'type\s+(\w+)\s+struct', source):
        parts.append(f"type {match.group(1)}")
    for match in re.finditer(r'func\s+(?:\([^)]+\)\s+)?(\w+)\s*\(', source):
        name = match.group(1)
        if name[0].isupper():  # Only exported
            parts.append(name + "()")

    return "; ".join(parts[:6])


def _smart_truncate(map_text: str, max_tokens: int) -> str:
    """Progressively reduce detail to fit within token budget.

    Estimation: 1 token ≈ 4 characters.
    """
    max_chars = max_tokens * 4
    if len(map_text) <= max_chars:
        return map_text

    # Phase 1: Remove size hints like (123 lines), (45KB)
    import re
    truncated = re.sub(r'\s*\(\d+\s*(?:lines|KB|B)\)', '', map_text)
    if len(truncated) <= max_chars:
        return truncated

    # Phase 2: Remove method lists from classes
    truncated = re.sub(r'\s*\[.+?\]', '', truncated)
    if len(truncated) <= max_chars:
        return truncated

    # Phase 3: Just keep directory structure + filenames
    lines = truncated.split("\n")
    kept = [l for l in lines if l.strip().endswith("/") or "." in l.split("/")[-1]]
    truncated = "\n".join(kept)
    if len(truncated) <= max_chars:
        return truncated

    # Phase 4: Hard truncate
    return truncated[:max_chars] + "\n... (truncated)"
