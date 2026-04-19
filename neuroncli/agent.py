"""NeuronCLI — ReAct agent engine v2.0. Parallel tools, context compression, hybrid speed."""

from __future__ import annotations

import json
import re
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field

from .config import AgentConfig, MODE_YOLO, MODE_PLAN
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
    DIFF_ADD = "\033[92m"
    DIFF_DEL = "\033[91m"
    DIFF_HDR = "\033[96m"


# ── Tool Call Parsing ─────────────────────────────────────────────

TOOL_CALL_PATTERN = re.compile(
    r"<tool_call>\s*(\{.*?\})\s*</tool_call>", re.DOTALL)
CODE_BLOCK_TOOL_PATTERN = re.compile(
    r"```(?:json)?\s*(\{[^`]*?\"tool\"\s*:.*?\})\s*```", re.DOTALL)
BARE_JSON_TOOL_PATTERN = re.compile(
    r'(\{\s*"tool"\s*:\s*"[^"]+"\s*,\s*"args"\s*:\s*\{.*?\}\s*\})', re.DOTALL)
FINAL_ANSWER_PATTERN = re.compile(
    r"<final_answer>(.*?)</final_answer>", re.DOTALL)


@dataclass
class ParsedToolCall:
    tool: str
    args: dict


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


def parse_all_tool_calls(text: str) -> list[ParsedToolCall]:
    """Parse ALL tool calls — enables parallel execution."""
    calls = []
    seen = set()
    for pattern in [TOOL_CALL_PATTERN, CODE_BLOCK_TOOL_PATTERN, BARE_JSON_TOOL_PATTERN]:
        for match in pattern.finditer(text):
            data = _try_parse_json(match.group(1))
            if data:
                key = (data["tool"], json.dumps(data.get("args", {}), sort_keys=True))
                if key not in seen:
                    seen.add(key)
                    calls.append(ParsedToolCall(tool=data["tool"], args=data.get("args", {})))
    return calls


def parse_final_answer(text: str) -> str | None:
    match = FINAL_ANSWER_PATTERN.search(text)
    return match.group(1).strip() if match else None


def _strip_ansi(text: str) -> str:
    return re.sub(r'\033\[[0-9;]*m', '', text)


def _clean_for_display(text: str) -> str:
    """Strip XML tags, render markdown as ANSI for terminal display."""
    text = re.sub(r'</?final_answer>', '', text)
    text = re.sub(r'</?tool_call>', '', text)
    text = re.sub(r'<[a-z_/][^>]*>', '', text)
    text = re.sub(r'(?i)\b(tags? as instructed|as instructed)\.?\s*', '', text)
    text = re.sub(r'\*\*(.+?)\*\*', f'{C.BOLD}\\1{C.RESET}', text)
    text = re.sub(r'(?<!\*)\*([^*]+)\*(?!\*)', f'{C.DIM}\\1{C.RESET}', text)
    text = re.sub(r'`([^`]+)`', f'{C.CYAN}\\1{C.RESET}', text)
    text = re.sub(r'^#{1,3}\s+(.+)$', f'{C.BOLD}\\1{C.RESET}', text, flags=re.MULTILINE)
    text = re.sub(r'^(\s*)- ', lambda m: m.group(1) + '  \u2022 ', text, flags=re.MULTILINE)
    text = re.sub(r'\n{3,}', '\n\n', text)
    return text.strip()


# ── Tool Summaries ────────────────────────────────────────────────

def _tool_summary(name: str, args: dict, result: str) -> str:
    if name == "read_file":
        return f"  Read {args.get('path', '?')} ({result.count(chr(10))} lines)"
    elif name == "write_file":
        lines = args.get('content', '').count('\n') + 1
        return f"  Wrote {args.get('path', '?')} ({lines} lines)"
    elif name == "edit_file":
        old_n = args.get('old_text', '').count('\n') + 1 if args.get('old_text') else 0
        new_n = args.get('new_text', '').count('\n') + 1 if args.get('new_text') else 0
        return f"  Edited {args.get('path', '?')} (+{new_n} -{old_n})"
    elif name == "run_command":
        cmd = args.get('command', '?')
        return f"  Ran: {cmd[:57] + '...' if len(cmd) > 60 else cmd}"
    elif name in ("list_directory", "get_project_structure"):
        return f"  Listed {args.get('path', '.')} ({result.count(chr(10))} items)"
    elif name == "search_in_files":
        return f"  Searched \"{args.get('pattern', '?')}\" ({result.count(chr(10))} matches)"
    return f"  {name}()"


def _truncate_result(result: str, max_chars: int = 4000) -> str:
    """Truncate tool results to keep context window lean."""
    if len(result) <= max_chars:
        return result
    half = max_chars // 2
    return result[:half] + f"\n\n... [{len(result) - max_chars} chars truncated] ...\n\n" + result[-half:]


def _format_diff(path: str, old_text: str, new_text: str) -> str:
    lines = [f"\n  {C.DIFF_HDR}{C.BOLD}  {path}{C.RESET}",
             f"  {C.DIM}  {'─' * min(len(path) + 4, 50)}{C.RESET}"]
    for line in (old_text.splitlines() if old_text else []):
        lines.append(f"  {C.DIFF_DEL}  - {line}{C.RESET}")
    for line in (new_text.splitlines() if new_text else []):
        lines.append(f"  {C.DIFF_ADD}  + {line}{C.RESET}")
    return "\n".join(lines)


def _confirm_action(tool_name: str, tool_args: dict) -> bool:
    """Permission prompt for destructive operations."""
    if tool_name == "edit_file":
        old, new = tool_args.get("old_text", ""), tool_args.get("new_text", "")
        print(_format_diff(tool_args.get("path", "?"), old, new))
        prompt = f"\n  {C.YELLOW}Apply this edit?{C.RESET} [Y/n] "
    elif tool_name == "write_file":
        prompt = f"\n  {C.YELLOW}Write to {C.BOLD}{tool_args.get('path', '?')}{C.RESET}{C.YELLOW}?{C.RESET} [Y/n] "
    elif tool_name == "run_command":
        prompt = f"\n  {C.YELLOW}Run: {C.BOLD}{tool_args.get('command', '?')}{C.RESET}{C.YELLOW}?{C.RESET} [Y/n] "
    else:
        return True
    try:
        r = input(prompt).strip().lower()
        return r in ("", "y", "yes")
    except (EOFError, KeyboardInterrupt):
        return False


# ── Context Compression (H2A-style) ──────────────────────────────

def _estimate_tokens(messages: list[ChatMessage]) -> int:
    """Rough token estimate: ~4 chars per token."""
    return sum(len(m.content) for m in messages) // 4


def _compress_context(messages: list[ChatMessage], keep_system: bool = True) -> list[ChatMessage]:
    """H2A-style context compression:
    Keep system prompt (head) + last 4 messages (tail).
    Summarize everything in the middle.
    """
    if len(messages) <= 6:
        return messages

    head = [messages[0]] if keep_system else []  # System prompt
    tail = messages[-4:]  # Last 4 messages (recent context)
    middle = messages[1:-4] if keep_system else messages[:-4]

    # Summarize middle section
    tool_calls = sum(1 for m in middle if "<tool_call>" in m.content or "[Tool:" in m.content)
    summary = (
        f"[Context compressed: {len(middle)} messages summarized. "
        f"{tool_calls} tool operations were performed. "
        f"Key context is preserved in recent messages below.]"
    )
    compressed = head + [ChatMessage(role="user", content=summary)] + tail
    return compressed


# ── Agent Data Types ──────────────────────────────────────────────

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


# ── Agent Engine ──────────────────────────────────────────────────

class Agent:
    """ReAct agent with parallel tools, context compression, and mode support."""

    def __init__(self, config: AgentConfig | None = None):
        self.config = config or AgentConfig.from_env()
        self.client = create_provider(self.config)
        self.messages: list[ChatMessage] = []
        self._slow_response_count = 0  # Track slow responses for upgrade nudge

    def run(self, task: str, neuron_md: str | None = None) -> AgentResult:
        start_time = time.time()
        result = AgentResult(task=task)

        system_prompt = build_system_prompt(
            tool_registry, self.config.working_dir,
            mode=self.config.mode, neuron_md=neuron_md,
        )

        # Preserve conversation history for follow-ups, but reset system prompt
        if not self.messages:
            self.messages = [ChatMessage(role="system", content=system_prompt)]
        else:
            self.messages[0] = ChatMessage(role="system", content=system_prompt)

        self.messages.append(ChatMessage(role="user", content=task))

        for iteration in range(1, self.config.max_iterations + 1):
            step_start = time.time()
            result.iterations_used = iteration

            # ── Context compression check ─────────────────────
            tokens_est = _estimate_tokens(self.messages)
            if tokens_est > self.config.max_context_tokens * self.config.context_compress_percent:
                self.messages = _compress_context(self.messages)
                print(f"  {C.DIM}/compact: context compressed{C.RESET}")

            # ── Show thinking indicator ───────────────────────
            elapsed_so_far = time.time() - start_time
            print(f"\r  {C.MAGENTA}*{C.RESET} {C.DIM}Thinking...{C.RESET}", end="", flush=True)

            # ── Get LLM response ──────────────────────────────
            full_response = ""
            try:
                if self.config.streaming:
                    for token in self.client.chat_stream(self.messages):
                        full_response += token
                        # Dynamic status hint
                        clean = _strip_ansi(full_response).strip()
                        words = clean.split()[:6]
                        if words:
                            hint = " ".join(words)
                            if len(hint) > 50:
                                hint = hint[:47] + "..."
                            secs = time.time() - step_start
                            print(f"\r  {C.MAGENTA}*{C.RESET} {C.DIM}{hint}... ({secs:.0f}s){C.RESET}    ", end="", flush=True)
                else:
                    full_response = self.client.chat(self.messages)
            except Exception as exc:
                print(f"\r  {C.RED}X {exc}{C.RESET}")
                result.aborted = True
                break

            step_elapsed = time.time() - step_start
            clean_response = _strip_ansi(full_response)
            self.messages.append(ChatMessage(role="assistant", content=clean_response))

            # ── Track slow responses for upgrade nudge ────────
            if step_elapsed > 30:
                self._slow_response_count += 1

            # ── Check for final answer ────────────────────────
            final = parse_final_answer(clean_response)
            if final:
                print(f"\r{' ' * 80}\r", end="")
                display_text = _clean_for_display(final)
                step = AgentStep(iteration, clean_response, None, "", True, final, step_elapsed)
                result.steps.append(step)
                result.final_answer = final
                print(f"\n{display_text}\n")
                break

            # ── Check for tool calls (PARALLEL) ───────────────
            all_tool_calls = parse_all_tool_calls(clean_response)
            if all_tool_calls:
                safe_calls = []
                dangerous_calls = []
                for tc in all_tool_calls:
                    if tc.tool in ("write_file", "edit_file", "run_command"):
                        dangerous_calls.append(tc)
                    else:
                        safe_calls.append(tc)

                all_results = []

                # Execute safe calls in PARALLEL
                if safe_calls:
                    with ThreadPoolExecutor(max_workers=min(len(safe_calls), 4)) as pool:
                        futures = {
                            pool.submit(tool_registry.execute, tc.tool, tc.args, self.config): tc
                            for tc in safe_calls
                        }
                        for future in as_completed(futures):
                            tc = futures[future]
                            try:
                                tool_result = future.result()
                            except Exception as e:
                                tool_result = f"Error: {e}"
                            summary = _tool_summary(tc.tool, tc.args, tool_result)
                            print(f"\r{' ' * 80}\r{C.GREEN}{summary}{C.RESET}")
                            all_results.append((tc, tool_result))

                # Execute dangerous calls sequentially
                for tc in dangerous_calls:
                    yolo = self.config.mode == MODE_YOLO

                    if not yolo and self.config.needs_confirmation:
                        print(f"\r{' ' * 80}\r", end="")
                        if not _confirm_action(tc.tool, tc.args):
                            all_results.append((tc, "[User denied]"))
                            continue

                    tool_result = tool_registry.execute(tc.tool, tc.args, self.config)
                    summary = _tool_summary(tc.tool, tc.args, tool_result)
                    print(f"\r{' ' * 80}\r{C.GREEN}{summary}{C.RESET}")

                    # Show diff for edits (in YOLO mode, show after applying)
                    if tc.tool == "edit_file" and "done" in tool_result.lower():
                        old_text = tc.args.get("old_text", "")
                        new_text = tc.args.get("new_text", "")
                        if old_text and new_text and yolo:
                            print(_format_diff(tc.args.get("path", "?"), old_text, new_text))

                    all_results.append((tc, tool_result))

                # Build result message
                result_parts = [f"[Tool: {tc.tool}] {_truncate_result(tr)}" for tc, tr in all_results]
                combined = "\n---\n".join(result_parts)
                self.messages.append(ChatMessage(role="user", content=(
                    f"{combined}\n\nAnalyze results. If done, give <final_answer>. "
                    f"Otherwise, call more tools (multiple allowed for parallel execution)."
                )))

                step = AgentStep(iteration, clean_response, all_tool_calls[0], combined, False, "", step_elapsed)
                result.steps.append(step)
                continue

            # ── No tool call, no final answer ─────────────────
            stripped = clean_response.strip()
            if len(stripped) > 20 and not stripped.startswith('{') and 'tool' not in stripped[:30].lower():
                display_text = _clean_for_display(stripped)
                print(f"\r{' ' * 80}\r\n{display_text}\n")
                step = AgentStep(iteration, clean_response, None, "", True, stripped, step_elapsed)
                result.steps.append(step)
                result.final_answer = stripped
                break

            # Nudge
            self.messages.append(ChatMessage(role="user", content=(
                "Provide a <final_answer> or use <tool_call> tags.")))
            result.steps.append(AgentStep(iteration, clean_response, None, "", False, "", step_elapsed))

        else:
            result.aborted = True
            print(f"\r{' ' * 80}\r  {C.RED}X Max iterations reached.{C.RESET}")
            if not result.final_answer:
                result.final_answer = "Task was not completed within the iteration limit."

        result.total_elapsed = time.time() - start_time
        self._print_status(result)

        # Upgrade nudge for slow responses
        if self._slow_response_count >= 2 and self.config.provider == "openrouter":
            print(f"  {C.YELLOW}Tip:{C.RESET} {C.DIM}Responses are slow on the free tier. "
                  f"Run /upgrade for faster speed.{C.RESET}\n")

        return result

    def compact(self) -> int:
        """Manually compress context. Returns messages removed."""
        before = len(self.messages)
        self.messages = _compress_context(self.messages)
        removed = before - len(self.messages)
        return removed

    def clear_history(self):
        self.messages.clear()
        self._slow_response_count = 0

    def _print_status(self, result: AgentResult):
        tools_used = [s.tool_call.tool for s in result.steps if s.tool_call]
        parts = []
        for tool_name, label in [("read_file", "read"), ("edit_file", "edited"),
                                  ("write_file", "wrote"), ("run_command", "ran"),
                                  ("search_in_files", "searched")]:
            count = sum(1 for t in tools_used if t == tool_name)
            if count:
                noun = "files" if "file" in tool_name else ("commands" if "command" in tool_name else "patterns")
                parts.append(f"{label} {count} {noun}")

        summary = ", ".join(parts) if parts else "no tools used"
        model = self.config.active_model.split("/")[-1]
        mode_tag = f" [{self.config.mode}]" if self.config.mode != "standard" else ""
        print(f"  {C.DIM}{model}{mode_tag} · {summary} · {result.total_elapsed:.1f}s · $0.00{C.RESET}\n")
