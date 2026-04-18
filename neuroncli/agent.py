"""NeuronCLI — ReAct loop agent engine. Claude Code-style compact output."""

from __future__ import annotations

import json
import re
import sys
import time
from dataclasses import dataclass, field

from .config import AgentConfig
from .provider import ChatMessage, create_provider, ProviderConnectionError
from .prompts import build_system_prompt
from .tools import registry as tool_registry


# ── ANSI Colors ───────────────────────────────────────────────────

class C:
    RESET   = "\033[0m"
    BOLD    = "\033[1m"
    DIM     = "\033[2m"
    ITALIC  = "\033[3m"
    CYAN    = "\033[96m"
    GREEN   = "\033[92m"
    YELLOW  = "\033[93m"
    RED     = "\033[91m"
    MAGENTA = "\033[95m"
    BLUE    = "\033[94m"
    GRAY    = "\033[90m"
    WHITE   = "\033[97m"
    # Diff colors
    DIFF_ADD = "\033[92m"   # Green
    DIFF_DEL = "\033[91m"   # Red
    DIFF_HDR = "\033[96m"   # Cyan


# ── Tool Call Parsing ─────────────────────────────────────────────

TOOL_CALL_PATTERN = re.compile(
    r"<tool_call>\s*(\{.*?\})\s*</tool_call>",
    re.DOTALL,
)

CODE_BLOCK_TOOL_PATTERN = re.compile(
    r"```(?:json)?\s*(\{[^`]*?\"tool\"\s*:.*?\})\s*```",
    re.DOTALL,
)

BARE_JSON_TOOL_PATTERN = re.compile(
    r'(\{\s*"tool"\s*:\s*"[^"]+"\s*,\s*"args"\s*:\s*\{.*?\}\s*\})',
    re.DOTALL,
)

FINAL_ANSWER_PATTERN = re.compile(
    r"<final_answer>(.*?)</final_answer>",
    re.DOTALL,
)


@dataclass
class ParsedToolCall:
    tool: str
    args: dict

    def display(self) -> str:
        args_str = ", ".join(f"{k}={v!r}" for k, v in self.args.items())
        return f"{self.tool}({args_str})"


def _try_parse_json(raw: str) -> dict | None:
    raw = raw.strip().replace("'", '"')
    raw = re.sub(r',\s*}', '}', raw)
    raw = re.sub(r',\s*]', ']', raw)
    try:
        data = json.loads(raw)
        if isinstance(data, dict) and "tool" in data:
            return data
    except json.JSONDecodeError:
        pass
    return None


def parse_tool_call(text: str) -> ParsedToolCall | None:
    for pattern in [TOOL_CALL_PATTERN, CODE_BLOCK_TOOL_PATTERN, BARE_JSON_TOOL_PATTERN]:
        match = pattern.search(text)
        if match:
            data = _try_parse_json(match.group(1))
            if data:
                return ParsedToolCall(tool=data["tool"], args=data.get("args", {}))
    return None


def parse_final_answer(text: str) -> str | None:
    match = FINAL_ANSWER_PATTERN.search(text)
    if match:
        return match.group(1).strip()
    return None


def _strip_ansi(text: str) -> str:
    return re.sub(r'\033\[[0-9;]*m', '', text)


# ── Compact Tool Summaries ────────────────────────────────────────

def _tool_summary(tool_name: str, tool_args: dict, result: str) -> str:
    """Generate a Claude Code-style one-liner summary for a tool call."""
    if tool_name == "read_file":
        path = tool_args.get("path", "?")
        # Count lines in result
        lines = result.count('\n')
        return f"  Read {path} ({lines} lines)"

    elif tool_name == "write_file":
        path = tool_args.get("path", "?")
        content = tool_args.get("content", "")
        lines = content.count('\n') + 1
        return f"  Wrote {path} ({lines} lines)"

    elif tool_name == "edit_file":
        path = tool_args.get("path", "?")
        old = tool_args.get("old_text", "")
        new = tool_args.get("new_text", "")
        old_lines = old.count('\n') + 1 if old else 0
        new_lines = new.count('\n') + 1 if new else 0
        diff = f"+{new_lines} -{old_lines}"
        return f"  Edited {path} ({diff})"

    elif tool_name == "run_command":
        cmd = tool_args.get("command", "?")
        # Truncate long commands
        if len(cmd) > 60:
            cmd = cmd[:57] + "..."
        exit_code = "0" if "error" not in result.lower() else "1"
        return f"  Ran: {cmd}"

    elif tool_name in ("list_directory", "get_project_structure"):
        path = tool_args.get("path", ".")
        items = result.count('\n')
        return f"  Listed {path} ({items} items)"

    elif tool_name == "search_in_files":
        pattern = tool_args.get("pattern", "?")
        matches = result.count('\n')
        return f"  Searched for \"{pattern}\" ({matches} matches)"

    else:
        return f"  {tool_name}({', '.join(f'{k}={v!r}' for k, v in tool_args.items())})"


def _format_diff(path: str, old_text: str, new_text: str) -> str:
    """Generate a Claude Code-style inline diff display."""
    lines = []
    lines.append(f"\n  {C.DIFF_HDR}{C.BOLD}  {path}{C.RESET}")
    lines.append(f"  {C.DIM}  {'─' * min(len(path) + 4, 50)}{C.RESET}")

    old_lines = old_text.splitlines() if old_text else []
    new_lines = new_text.splitlines() if new_text else []

    for line in old_lines:
        lines.append(f"  {C.DIFF_DEL}  - {line}{C.RESET}")
    for line in new_lines:
        lines.append(f"  {C.DIFF_ADD}  + {line}{C.RESET}")

    return "\n".join(lines)


def _confirm_action(tool_name: str, tool_args: dict) -> bool:
    """Prompt user for permission before destructive operations."""
    if tool_name == "write_file":
        path = tool_args.get("path", "?")
        prompt = f"\n  {C.YELLOW}● Write to {C.BOLD}{path}{C.RESET}{C.YELLOW}?{C.RESET} [Y/n] "
    elif tool_name == "edit_file":
        path = tool_args.get("path", "?")
        # Show diff
        old_text = tool_args.get("old_text", "")
        new_text = tool_args.get("new_text", "")
        diff = _format_diff(path, old_text, new_text)
        print(diff)
        prompt = f"\n  {C.YELLOW}Apply this edit?{C.RESET} [Y/n] "
    elif tool_name == "run_command":
        cmd = tool_args.get("command", "?")
        prompt = f"\n  {C.YELLOW}● Run: {C.BOLD}{cmd}{C.RESET}{C.YELLOW}?{C.RESET} [Y/n] "
    else:
        return True

    try:
        response = input(prompt).strip().lower()
        return response in ("", "y", "yes")
    except (EOFError, KeyboardInterrupt):
        return False


# ── Agent Engine ──────────────────────────────────────────────────

@dataclass
class AgentStep:
    step_number: int
    thinking: str
    tool_call: ParsedToolCall | None
    tool_result: str
    is_final: bool
    final_answer: str = ""
    elapsed: float = 0.0


@dataclass
class AgentResult:
    task: str
    steps: list[AgentStep] = field(default_factory=list)
    final_answer: str = ""
    total_elapsed: float = 0.0
    iterations_used: int = 0
    aborted: bool = False


class Agent:
    """
    ReAct (Reasoning + Acting) loop agent.
    Claude Code-style compact output — hides raw LLM text,
    shows only tool summaries and clean final answer.
    """

    def __init__(self, config: AgentConfig | None = None):
        self.config = config or AgentConfig.from_env()
        self.client = create_provider(self.config)
        self.messages: list[ChatMessage] = []
        self._auto_approve_writes = False
        self._auto_approve_commands = False

    def run(self, task: str) -> AgentResult:
        start_time = time.time()
        result = AgentResult(task=task)

        system_prompt = build_system_prompt(tool_registry, self.config.working_dir)
        self.messages = [
            ChatMessage(role="system", content=system_prompt),
            ChatMessage(role="user", content=task),
        ]

        for iteration in range(1, self.config.max_iterations + 1):
            step_start = time.time()
            result.iterations_used = iteration

            # ── Show thinking indicator ───────────────────────
            print(f"\r  {C.MAGENTA}●{C.RESET} {C.DIM}Thinking...{C.RESET}", end="", flush=True)

            # ── Get LLM response (silently) ───────────────────
            full_response = ""
            try:
                if self.config.streaming:
                    reasoning_shown = False
                    for token in self.client.chat_stream(self.messages):
                        full_response += token
                        # Show a subtle spinner while streaming
                        if not reasoning_shown:
                            clean_so_far = _strip_ansi(full_response)
                            # Update status with first few words of thinking
                            words = clean_so_far.strip().split()[:6]
                            if words:
                                hint = " ".join(words)
                                if len(hint) > 50:
                                    hint = hint[:47] + "..."
                                print(f"\r  {C.MAGENTA}●{C.RESET} {C.DIM}{hint}...{C.RESET}    ", end="", flush=True)
                else:
                    full_response = self.client.chat(self.messages)
            except Exception as exc:
                print(f"\r  {C.RED}✗ {exc}{C.RESET}")
                result.aborted = True
                break

            clean_response = _strip_ansi(full_response)
            self.messages.append(ChatMessage(role="assistant", content=clean_response))

            # ── Check for final answer ────────────────────────
            final = parse_final_answer(clean_response)
            if final:
                # Clear the thinking indicator
                print(f"\r{' ' * 80}\r", end="")
                step = AgentStep(
                    step_number=iteration,
                    thinking=clean_response,
                    tool_call=None,
                    tool_result="",
                    is_final=True,
                    final_answer=final,
                    elapsed=time.time() - step_start,
                )
                result.steps.append(step)
                result.final_answer = final
                # Print clean answer
                print(f"\n{final}\n")
                break

            # ── Check for tool call ───────────────────────────
            tool_call = parse_tool_call(clean_response)
            if tool_call:
                # Permission check for destructive tools
                needs_confirm = (
                    self.config.confirm_dangerous
                    and tool_call.tool in ("write_file", "edit_file", "run_command")
                )

                if needs_confirm and tool_call.tool == "write_file" and not self._auto_approve_writes:
                    print(f"\r{' ' * 80}\r", end="")
                    if not _confirm_action(tool_call.tool, tool_call.args):
                        self.messages.append(ChatMessage(role="user", content="[User denied this action. Try a different approach or ask for clarification.]"))
                        continue

                if needs_confirm and tool_call.tool == "edit_file" and not self._auto_approve_writes:
                    print(f"\r{' ' * 80}\r", end="")
                    if not _confirm_action(tool_call.tool, tool_call.args):
                        self.messages.append(ChatMessage(role="user", content="[User denied this action. Try a different approach or ask for clarification.]"))
                        continue

                if needs_confirm and tool_call.tool == "run_command":
                    cmd = tool_call.args.get("command", "")
                    if self.config.is_dangerous_command(cmd) and not self._auto_approve_commands:
                        print(f"\r{' ' * 80}\r", end="")
                        if not _confirm_action(tool_call.tool, tool_call.args):
                            self.messages.append(ChatMessage(role="user", content="[User denied this command. Try something safer.]"))
                            continue

                # Execute the tool
                tool_result = tool_registry.execute(
                    tool_call.tool,
                    tool_call.args,
                    self.config,
                )

                # Show compact one-liner
                summary = _tool_summary(tool_call.tool, tool_call.args, tool_result)
                print(f"\r{' ' * 80}\r{C.GREEN}{summary}{C.RESET}")

                # Show diff for edit operations
                if tool_call.tool == "edit_file" and "✓" in tool_result:
                    old_text = tool_call.args.get("old_text", "")
                    new_text = tool_call.args.get("new_text", "")
                    if old_text and new_text and not needs_confirm:
                        diff = _format_diff(tool_call.args.get("path", "?"), old_text, new_text)
                        print(diff)

                # Inject result back
                result_message = (
                    f"[Tool Result: {tool_call.tool}]\n{tool_result}\n\n"
                    f"Analyze this result and decide your next action. "
                    f"If the task is complete, provide your <final_answer>. "
                    f"Otherwise, use another tool."
                )
                self.messages.append(ChatMessage(role="user", content=result_message))

                step = AgentStep(
                    step_number=iteration,
                    thinking=clean_response,
                    tool_call=tool_call,
                    tool_result=tool_result,
                    is_final=False,
                    elapsed=time.time() - step_start,
                )
                result.steps.append(step)
                continue

            # ── No tool call and no final answer → nudge ──────
            nudge = (
                "You didn't use a tool or provide a final answer. "
                "Please either:\n"
                "1. Use a tool with <tool_call>{...}</tool_call>\n"
                "2. Provide your final answer with <final_answer>...</final_answer>"
            )
            self.messages.append(ChatMessage(role="user", content=nudge))
            step = AgentStep(
                step_number=iteration,
                thinking=clean_response,
                tool_call=None,
                tool_result="",
                is_final=False,
                elapsed=time.time() - step_start,
            )
            result.steps.append(step)

        else:
            result.aborted = True
            print(f"\r{' ' * 80}\r", end="")
            print(f"  {C.RED}✗ Max iterations ({self.config.max_iterations}) reached.{C.RESET}")
            if not result.final_answer:
                result.final_answer = "Task was not completed within the iteration limit."

        result.total_elapsed = time.time() - start_time
        self._print_status(result)
        return result

    def clear_history(self):
        self.messages.clear()

    def _print_status(self, result: AgentResult):
        tool_steps = sum(1 for s in result.steps if s.tool_call)
        tools_used = [s.tool_call.tool for s in result.steps if s.tool_call]
        # Compact summary like Claude Code
        parts = []
        if tool_steps:
            parts.append(f"read {sum(1 for t in tools_used if t == 'read_file')} files" if any(t == 'read_file' for t in tools_used) else "")
            parts.append(f"edited {sum(1 for t in tools_used if t == 'edit_file')} files" if any(t == 'edit_file' for t in tools_used) else "")
            parts.append(f"wrote {sum(1 for t in tools_used if t == 'write_file')} files" if any(t == 'write_file' for t in tools_used) else "")
            parts.append(f"ran {sum(1 for t in tools_used if t == 'run_command')} commands" if any(t == 'run_command' for t in tools_used) else "")
            parts.append(f"searched {sum(1 for t in tools_used if t == 'search_in_files')} patterns" if any(t == 'search_in_files' for t in tools_used) else "")
            parts = [p for p in parts if p]

        summary = ", ".join(parts) if parts else "no tools used"
        elapsed = f"{result.total_elapsed:.1f}s"
        model = self.config.active_model.split("/")[-1]  # short name

        print(f"  {C.DIM}{model} · {summary} · {elapsed} · $0.00{C.RESET}\n")
