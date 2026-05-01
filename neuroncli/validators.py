"""NeuronCLI — Post-write file validation engine.

Automatically validates files after write/edit operations.
Feeds errors back into the agent loop for self-correction.
Inspired by Crush's LSP diagnostics + Aider's lint-fix pattern.
"""

from __future__ import annotations

import json
import subprocess
import re
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class ValidationResult:
    """Result of validating a generated file."""
    valid: bool
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    @property
    def feedback(self) -> str:
        """Format as feedback string for the agent loop."""
        if self.valid:
            return ""
        parts = []
        for e in self.errors:
            parts.append(f"  ERROR: {e}")
        for w in self.warnings:
            parts.append(f"  WARNING: {w}")
        return "\n".join(parts)


def validate_file(path: str, content: str | None = None) -> ValidationResult:
    """Validate a file based on its extension.

    Args:
        path: File path (used for extension detection)
        content: File content (read from disk if not provided)
    """
    p = Path(path)
    ext = p.suffix.lower()

    if content is None:
        try:
            content = p.read_text(encoding="utf-8", errors="replace")
        except OSError as e:
            return ValidationResult(valid=False, errors=[f"Cannot read file: {e}"])

    validators = {
        ".py": _validate_python,
        ".json": _validate_json,
        ".html": _validate_html,
        ".htm": _validate_html,
        ".css": _validate_css,
        ".js": _validate_javascript,
        ".ts": _validate_javascript,
    }

    validator = validators.get(ext)
    if validator is None:
        return ValidationResult(valid=True)  # No validator = assume OK

    return validator(str(p), content)


# ── Python Validator ──────────────────────────────────────────────

def _validate_python(path: str, content: str) -> ValidationResult:
    """Validate Python via py_compile (catches syntax errors)."""
    errors = []
    warnings = []

    try:
        compile(content, path, "exec")
    except SyntaxError as e:
        errors.append(f"SyntaxError at line {e.lineno}: {e.msg}")

    # Check for common mistakes
    if "import *" in content:
        warnings.append("Wildcard import detected (import *)")

    return ValidationResult(valid=len(errors) == 0, errors=errors, warnings=warnings)


# ── JSON Validator ────────────────────────────────────────────────

def _validate_json(path: str, content: str) -> ValidationResult:
    """Validate JSON structure."""
    try:
        json.loads(content)
        return ValidationResult(valid=True)
    except json.JSONDecodeError as e:
        return ValidationResult(valid=False, errors=[f"Invalid JSON at line {e.lineno}: {e.msg}"])


# ── HTML Validator ────────────────────────────────────────────────

def _validate_html(path: str, content: str) -> ValidationResult:
    """Validate HTML structure — checks for complete document."""
    errors = []
    warnings = []

    # Check for escaped tags (common LLM mistake)
    if "&lt;" in content and "<html" not in content.lower():
        errors.append("HTML tags are escaped (&lt; instead of <). The LLM outputted escaped HTML.")

    # Check for required structural elements
    lower = content.lower()
    if "<!doctype" not in lower:
        warnings.append("Missing <!DOCTYPE html> declaration")
    if "<html" not in lower:
        errors.append("Missing <html> tag")
    if "<head" not in lower:
        warnings.append("Missing <head> tag")
    if "<body" not in lower:
        errors.append("Missing <body> tag")

    # Check for unclosed tags (basic check)
    open_tags = len(re.findall(r'<(?!/)(?!meta)(?!br)(?!hr)(?!img)(?!input)(?!link)([a-z]+)', lower))
    close_tags = len(re.findall(r'</([a-z]+)', lower))
    if open_tags > 0 and close_tags == 0:
        errors.append("No closing tags found — file may be truncated")

    return ValidationResult(valid=len(errors) == 0, errors=errors, warnings=warnings)


# ── CSS Validator ─────────────────────────────────────────────────

def _validate_css(path: str, content: str) -> ValidationResult:
    """Basic CSS validation — brace matching."""
    errors = []

    open_braces = content.count("{")
    close_braces = content.count("}")
    if open_braces != close_braces:
        errors.append(f"Unmatched braces: {open_braces} open, {close_braces} close")

    return ValidationResult(valid=len(errors) == 0, errors=errors)


# ── JavaScript Validator ──────────────────────────────────────────

def _validate_javascript(path: str, content: str) -> ValidationResult:
    """Validate JS/TS — try node --check if available, else brace match."""
    errors = []

    # Try node --check (fast syntax check)
    try:
        result = subprocess.run(
            ["node", "--check", path],
            capture_output=True, text=True, timeout=5,
        )
        if result.returncode != 0:
            # Extract the actual error line
            stderr = result.stderr.strip()
            if stderr:
                errors.append(stderr.split("\n")[0])
    except (FileNotFoundError, subprocess.TimeoutExpired):
        # Node not available — fall back to brace matching
        open_braces = content.count("{")
        close_braces = content.count("}")
        if abs(open_braces - close_braces) > 2:
            errors.append(f"Suspicious brace mismatch: {open_braces} open, {close_braces} close")

    return ValidationResult(valid=len(errors) == 0, errors=errors)
