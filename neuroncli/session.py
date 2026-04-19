"""NeuronCLI — Session persistence. Save/resume conversation history."""

from __future__ import annotations

import hashlib
import json
import os
import time
from pathlib import Path
from typing import Any


SESSIONS_DIR = Path.home() / ".neuroncli" / "sessions"


def _session_id(working_dir: str) -> str:
    """Generate a stable session ID from the working directory."""
    return hashlib.md5(working_dir.encode()).hexdigest()[:12]


def _session_path(working_dir: str) -> Path:
    return SESSIONS_DIR / f"{_session_id(working_dir)}.json"


def save_session(working_dir: str, messages: list[dict], metadata: dict | None = None) -> Path:
    """Save the current conversation to disk."""
    SESSIONS_DIR.mkdir(parents=True, exist_ok=True)
    path = _session_path(working_dir)

    data = {
        "working_dir": working_dir,
        "saved_at": time.time(),
        "saved_at_human": time.strftime("%Y-%m-%d %H:%M:%S"),
        "message_count": len(messages),
        "messages": messages,
        "metadata": metadata or {},
    }

    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

    return path


def load_session(working_dir: str) -> list[dict] | None:
    """Load previous session for this directory. Returns messages or None."""
    path = _session_path(working_dir)
    if not path.exists():
        return None

    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data.get("messages")
    except (json.JSONDecodeError, OSError):
        return None


def list_sessions() -> list[dict[str, Any]]:
    """List all saved sessions with metadata."""
    if not SESSIONS_DIR.exists():
        return []

    sessions = []
    for f in SESSIONS_DIR.glob("*.json"):
        try:
            with open(f, "r", encoding="utf-8") as fh:
                data = json.load(fh)
            sessions.append({
                "id": f.stem,
                "working_dir": data.get("working_dir", "?"),
                "saved_at": data.get("saved_at_human", "?"),
                "messages": data.get("message_count", 0),
            })
        except (json.JSONDecodeError, OSError):
            continue

    sessions.sort(key=lambda s: s.get("saved_at", ""), reverse=True)
    return sessions


def delete_session(working_dir: str) -> bool:
    """Delete the session for a directory."""
    path = _session_path(working_dir)
    if path.exists():
        path.unlink()
        return True
    return False
