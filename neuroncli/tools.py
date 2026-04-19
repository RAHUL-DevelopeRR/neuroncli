"""NeuronCLI — Tool implementations and registry."""

from __future__ import annotations

import fnmatch
import os
import re
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

from .config import AgentConfig


# ── Tool Registry ─────────────────────────────────────────────────

@dataclass
class ToolSpec:
    """Metadata for a single tool."""
    name: str
    description: str
    parameters: dict[str, str]         # param_name -> description
    required: list[str]
    function: Callable[..., str]

    def signature_for_prompt(self) -> str:
        """Generate a description for the system prompt."""
        params = ", ".join(
            f'{name}: {desc}' for name, desc in self.parameters.items()
        )
        req = ", ".join(self.required)
        return (
            f"### {self.name}\n"
            f"Description: {self.description}\n"
            f"Parameters: {params}\n"
            f"Required: {req}"
        )


class ToolRegistry:
    """Central registry of all available tools."""

    def __init__(self):
        self._tools: dict[str, ToolSpec] = {}

    def register(
        self,
        name: str,
        description: str,
        parameters: dict[str, str],
        required: list[str] | None = None,
    ) -> Callable:
        """Decorator to register a tool function."""
        def decorator(func: Callable[..., str]) -> Callable[..., str]:
            self._tools[name] = ToolSpec(
                name=name,
                description=description,
                parameters=parameters,
                required=required or list(parameters.keys()),
                function=func,
            )
            return func
        return decorator

    def get(self, name: str) -> ToolSpec | None:
        return self._tools.get(name)

    def all_tools(self) -> list[ToolSpec]:
        return list(self._tools.values())

    def tool_names(self) -> list[str]:
        return list(self._tools.keys())

    def execute(self, name: str, args: dict, config: AgentConfig) -> str:
        """Execute a tool by name with given arguments."""
        spec = self._tools.get(name)
        if spec is None:
            return f"Error: Unknown tool '{name}'. Available: {', '.join(self.tool_names())}"

        # Validate required params
        for req in spec.required:
            if req not in args:
                return f"Error: Missing required parameter '{req}' for tool '{name}'"

        try:
            return spec.function(config=config, **args)
        except Exception as exc:
            return f"Error executing {name}: {type(exc).__name__}: {exc}"

    def generate_prompt_section(self) -> str:
        """Generate tool descriptions for the system prompt."""
        sections = []
        for spec in self._tools.values():
            sections.append(spec.signature_for_prompt())
        return "\n\n".join(sections)


# ── Global registry instance ─────────────────────────────────────

registry = ToolRegistry()


# ── Tool Implementations ─────────────────────────────────────────

@registry.register(
    name="read_file",
    description="Read the contents of a file. Returns the file content with line numbers.",
    parameters={
        "path": "Path to the file (relative to working directory or absolute)",
    },
    required=["path"],
)
def read_file(config: AgentConfig, path: str) -> str:
    resolved = config.resolve_path(path)
    if not resolved.exists():
        return f"Error: File not found: {resolved}"
    if not resolved.is_file():
        return f"Error: Not a file: {resolved}"
    try:
        content = resolved.read_text(encoding="utf-8", errors="replace")
        lines = content.splitlines()
        # Add line numbers
        numbered = "\n".join(f"{i+1:4d} | {line}" for i, line in enumerate(lines))
        return f"File: {path} ({len(lines)} lines, {resolved.stat().st_size} bytes)\n{'─' * 60}\n{numbered}"
    except Exception as exc:
        return f"Error reading {path}: {exc}"


@registry.register(
    name="write_file",
    description="Write content to a file. Creates the file (and parent directories) if it doesn't exist, or overwrites it.",
    parameters={
        "path": "Path to the file",
        "content": "The full content to write to the file",
    },
    required=["path", "content"],
)
def write_file(config: AgentConfig, path: str, content: str) -> str:
    resolved = config.resolve_path(path)
    try:
        resolved.parent.mkdir(parents=True, exist_ok=True)
        resolved.write_text(content, encoding="utf-8")
        line_count = content.count("\n") + (1 if content and not content.endswith("\n") else 0)
        return f"[OK] Written {len(content)} bytes ({line_count} lines) to {path}"
    except Exception as exc:
        return f"Error writing {path}: {exc}"


@registry.register(
    name="edit_file",
    description="Edit a file by replacing a specific text block with new content. Use this for surgical edits instead of rewriting the entire file.",
    parameters={
        "path": "Path to the file",
        "old_text": "The exact text to find and replace (must match precisely including whitespace)",
        "new_text": "The replacement text",
    },
    required=["path", "old_text", "new_text"],
)
def edit_file(config: AgentConfig, path: str, old_text: str, new_text: str) -> str:
    resolved = config.resolve_path(path)
    if not resolved.exists():
        return f"Error: File not found: {resolved}"
    try:
        content = resolved.read_text(encoding="utf-8")
        if old_text not in content:
            # Try with normalized whitespace
            normalized_content = content.replace("\r\n", "\n")
            normalized_old = old_text.replace("\r\n", "\n")
            if normalized_old in normalized_content:
                content = normalized_content
                old_text = normalized_old
            else:
                # Show a snippet of the file for debugging
                preview = content[:500]
                return (
                    f"Error: Could not find the exact text to replace in {path}.\n"
                    f"File preview (first 500 chars):\n{preview}"
                )
        count = content.count(old_text)
        new_content = content.replace(old_text, new_text, 1)
        resolved.write_text(new_content, encoding="utf-8")
        return f"[OK] Edited {path}: replaced {count} occurrence(s) ({len(old_text)} chars -> {len(new_text)} chars)"
    except Exception as exc:
        return f"Error editing {path}: {exc}"


@registry.register(
    name="list_directory",
    description="List files and subdirectories in a directory. Shows a tree view with file sizes.",
    parameters={
        "path": "Directory path (default: current working directory)",
        "recursive": "If 'true', show full recursive tree (default: 'false', shows 2 levels)",
    },
    required=["path"],
)
def list_directory(config: AgentConfig, path: str = ".", recursive: str = "false") -> str:
    resolved = config.resolve_path(path)
    if not resolved.exists():
        return f"Error: Directory not found: {resolved}"
    if not resolved.is_dir():
        return f"Error: Not a directory: {resolved}"

    is_recursive = recursive.lower() in ("true", "yes", "1")
    max_depth = 100 if is_recursive else 2

    lines: list[str] = [f"[DIR] {resolved.name}/"]
    _tree_walk(resolved, lines, prefix="", depth=0, max_depth=max_depth)

    if len(lines) > 200:
        lines = lines[:200]
        lines.append(f"... (truncated, {len(lines)}+ entries)")

    return "\n".join(lines)


def _tree_walk(directory: Path, lines: list[str], prefix: str, depth: int, max_depth: int):
    """Recursively build a tree view. Robust against Windows permission errors."""
    if depth >= max_depth:
        return

    SKIP = {".git", "__pycache__", "node_modules", ".venv", "venv", ".mypy_cache", ".pytest_cache", "dist", "build", ".tox", ".eggs"}

    try:
        entries = sorted(directory.iterdir(), key=lambda e: (not e.is_dir(), e.name.lower()))
    except (PermissionError, OSError):
        lines.append(f"{prefix}└── [access denied]")
        return

    entries = [e for e in entries if e.name not in SKIP and not e.name.startswith('.')]
    total = len(entries)

    for idx, entry in enumerate(entries):
        is_last = idx == total - 1
        connector = "└── " if is_last else "├── "
        extension = "    " if is_last else "│   "

        try:
            if entry.is_dir():
                try:
                    child_count = sum(1 for _ in entry.iterdir()) if depth < max_depth - 1 else 0
                except (PermissionError, OSError):
                    child_count = 0
                lines.append(f"{prefix}{connector}[DIR] {entry.name}/ ({child_count} items)")
                _tree_walk(entry, lines, prefix + extension, depth + 1, max_depth)
            else:
                try:
                    size = entry.stat().st_size
                    size_str = _format_size(size)
                except (PermissionError, OSError):
                    size_str = "?"
                lines.append(f"{prefix}{connector}{entry.name} ({size_str})")
        except (PermissionError, OSError):
            lines.append(f"{prefix}{connector}{entry.name} [access denied]")


def _format_size(size: int) -> str:
    if size < 1024:
        return f"{size} B"
    elif size < 1024 * 1024:
        return f"{size / 1024:.1f} KB"
    else:
        return f"{size / (1024 * 1024):.1f} MB"


@registry.register(
    name="run_command",
    description="Run a shell command and return its stdout and stderr. Use for build, test, git, or any terminal command.",
    parameters={
        "command": "The shell command to execute",
    },
    required=["command"],
)
def run_command(config: AgentConfig, command: str) -> str:
    # Safety check
    if config.is_dangerous_command(command):
        return (
            f"[BLOCKED] The command '{command}' matches a dangerous pattern.\n"
            f"If you're sure, the user can re-run with confirm_dangerous=False."
        )

    try:
        result = subprocess.run(
            command,
            shell=True,
            capture_output=True,
            text=True,
            cwd=config.working_dir,
            timeout=60,
        )
        parts = []
        if result.stdout:
            parts.append(f"STDOUT:\n{result.stdout.strip()}")
        if result.stderr:
            parts.append(f"STDERR:\n{result.stderr.strip()}")
        parts.append(f"Exit code: {result.returncode}")

        output = "\n".join(parts) if parts else "Command completed with no output."

        # Truncate very long output
        if len(output) > 5000:
            output = output[:5000] + f"\n... (truncated, {len(output)} total chars)"

        return output

    except subprocess.TimeoutExpired:
        return f"Error: Command timed out after 60 seconds: {command}"
    except Exception as exc:
        return f"Error running command: {exc}"


@registry.register(
    name="search_in_files",
    description="Search for a text pattern across files in a directory. Like grep. Returns matching lines with file paths and line numbers.",
    parameters={
        "query": "Text or regex pattern to search for",
        "directory": "Directory to search in (default: working directory)",
        "pattern": "File glob pattern to filter files (default: '*.*')",
    },
    required=["query"],
)
def search_in_files(
    config: AgentConfig,
    query: str,
    directory: str = ".",
    pattern: str = "*.*",
) -> str:
    resolved = config.resolve_path(directory)
    if not resolved.exists():
        return f"Error: Directory not found: {resolved}"

    SKIP_DIRS = {".git", "__pycache__", "node_modules", ".venv", "venv", "dist", "build"}
    matches: list[str] = []
    files_searched = 0

    try:
        compiled = re.compile(query, re.IGNORECASE)
    except re.error:
        compiled = re.compile(re.escape(query), re.IGNORECASE)

    for root_path, dirs, files in os.walk(resolved):
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
        for filename in files:
            if not fnmatch.fnmatch(filename, pattern):
                continue
            filepath = Path(root_path) / filename
            files_searched += 1
            try:
                text = filepath.read_text(encoding="utf-8", errors="replace")
                for line_no, line in enumerate(text.splitlines(), 1):
                    if compiled.search(line):
                        rel = filepath.relative_to(resolved)
                        matches.append(f"  {rel}:{line_no}  {line.strip()}")
                        if len(matches) >= 50:
                            break
            except (OSError, UnicodeDecodeError):
                continue
            if len(matches) >= 50:
                break

    if not matches:
        return f"No matches for '{query}' in {files_searched} files."

    header = f"Found {len(matches)} match(es) for '{query}' in {files_searched} files:\n"
    return header + "\n".join(matches)


@registry.register(
    name="get_project_structure",
    description="Get a comprehensive overview of the project: directory tree, key files, and README content if available.",
    parameters={
        "path": "Root path of the project (default: working directory)",
    },
    required=[],
)
def get_project_structure(config: AgentConfig, path: str = ".") -> str:
    resolved = config.resolve_path(path)
    if not resolved.exists():
        return f"Error: Path not found: {resolved}"

    parts: list[str] = ["# Project Structure\n"]

    # Directory tree (2 levels)
    tree_lines: list[str] = [f"[DIR] {resolved.name}/"]
    _tree_walk(resolved, tree_lines, prefix="", depth=0, max_depth=2)
    parts.append("\n".join(tree_lines))

    # Count stats
    py_files = list(resolved.rglob("*.py"))
    js_files = list(resolved.rglob("*.js")) + list(resolved.rglob("*.ts"))
    rs_files = list(resolved.rglob("*.rs"))

    parts.append(f"\nStats: {len(py_files)} .py | {len(js_files)} .js/.ts | {len(rs_files)} .rs")

    # Check for key files
    key_files = ["README.md", "setup.py", "pyproject.toml", "package.json",
                 "Cargo.toml", "requirements.txt", "Makefile", ".gitignore"]
    found = [f for f in key_files if (resolved / f).exists()]
    if found:
        parts.append(f"Key files: {', '.join(found)}")

    # Read README if available
    readme = resolved / "README.md"
    if readme.exists():
        try:
            content = readme.read_text(encoding="utf-8", errors="replace")
            if len(content) > 1000:
                content = content[:1000] + "\n... (truncated)"
            parts.append(f"\n## README.md\n{content}")
        except OSError:
            pass

    return "\n".join(parts)
