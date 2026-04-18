"""NeuronCLI — ReAct loop agent engine. The core brain."""

from __future__ import annotations

import json
import re
import time
from dataclasses import dataclass, field

from .config import AgentConfig
from .provider import ChatMessage, create_provider, ProviderConnectionError
from .prompts import build_system_prompt
from .tools import registry as tool_registry


# ── ANSI Colors ───────────────────────────────────────────────────

class C:
    RESET = "\033[0m"
    BOLD = "\033[1m"
    DIM = "\033[2m"
    CYAN = "\033[96m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    RED = "\033[91m"
    MAGENTA = "\033[95m"
    BLUE = "\033[94m"
    GRAY = "\033[90m"
    WHITE = "\033[97m"


# ── Tool Call Parsing ─────────────────────────────────────────────

# Pattern 1: Proper <tool_call> tags
TOOL_CALL_PATTERN = re.compile(
    r"<tool_call>\s*(\{.*?\})\s*</tool_call>",
    re.DOTALL,
)

# Pattern 2: JSON in ```json code blocks (common with Qwen/DeepSeek)
CODE_BLOCK_TOOL_PATTERN = re.compile(
    r"```(?:json)?\s*(\{[^`]*?\"tool\"\s*:.*?\})\s*```",
    re.DOTALL,
)

# Pattern 3: Bare JSON with "tool" key on its own line
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
    """Try to parse JSON with common fixups for LLM-generated JSON."""
    raw = raw.strip()
    raw = raw.replace("'", '"')          # single to double quotes
    raw = re.sub(r',\s*}', '}', raw)     # trailing commas in objects
    raw = re.sub(r',\s*]', ']', raw)     # trailing commas in arrays
    raw = re.sub(r'(?<=\w)"(?=\w)', '\\"', raw)  # escape inner quotes
    try:
        data = json.loads(raw)
        if isinstance(data, dict) and "tool" in data:
            return data
    except json.JSONDecodeError:
        pass
    return None


def parse_tool_call(text: str) -> ParsedToolCall | None:
    """
    Extract a tool call from the LLM output.
    Tries multiple patterns: <tool_call> tags, ```json blocks, bare JSON.
    """
    # Try Pattern 1: <tool_call> tags (preferred)
    match = TOOL_CALL_PATTERN.search(text)
    if match:
        data = _try_parse_json(match.group(1))
        if data:
            return ParsedToolCall(tool=data["tool"], args=data.get("args", {}))

    # Try Pattern 2: JSON in code blocks
    match = CODE_BLOCK_TOOL_PATTERN.search(text)
    if match:
        data = _try_parse_json(match.group(1))
        if data:
            return ParsedToolCall(tool=data["tool"], args=data.get("args", {}))

    # Try Pattern 3: Bare JSON with "tool" key
    match = BARE_JSON_TOOL_PATTERN.search(text)
    if match:
        data = _try_parse_json(match.group(1))
        if data:
            return ParsedToolCall(tool=data["tool"], args=data.get("args", {}))

    return None


def parse_final_answer(text: str) -> str | None:
    """Extract the final answer from the LLM output."""
    match = FINAL_ANSWER_PATTERN.search(text)
    if match:
        return match.group(1).strip()
    return None


def _strip_ansi(text: str) -> str:
    """Remove ANSI escape codes from text (for parsing tool calls from streamed output)."""
    return re.sub(r'\033\[[0-9;]*m', '', text)


# ── Agent Engine ──────────────────────────────────────────────────

@dataclass
class AgentStep:
    """Record of a single agent step."""
    step_number: int
    thinking: str
    tool_call: ParsedToolCall | None
    tool_result: str
    is_final: bool
    final_answer: str = ""
    elapsed: float = 0.0


@dataclass
class AgentResult:
    """Complete result of an agent run."""
    task: str
    steps: list[AgentStep] = field(default_factory=list)
    final_answer: str = ""
    total_elapsed: float = 0.0
    iterations_used: int = 0
    aborted: bool = False


class Agent:
    """
    ReAct (Reasoning + Acting) loop agent.

    Flow:
    1. Build system prompt with tool descriptions
    2. Add user task
    3. Loop: stream LLM → parse for tool_call or final_answer
    4. If tool_call: execute tool, inject result, continue
    5. If final_answer: return
    6. Safety: abort after max_iterations
    """

    def __init__(self, config: AgentConfig | None = None):
        self.config = config or AgentConfig.from_env()
        self.client = create_provider(self.config)
        self.messages: list[ChatMessage] = []

    def run(self, task: str) -> AgentResult:
        """Execute a task through the ReAct loop."""
        start_time = time.time()
        result = AgentResult(task=task)

        # Build initial messages
        system_prompt = build_system_prompt(tool_registry, self.config.working_dir)
        self.messages = [
            ChatMessage(role="system", content=system_prompt),
            ChatMessage(role="user", content=task),
        ]

        print(f"\n{C.CYAN}{C.BOLD}>> Task:{C.RESET} {task}")
        print(f"{C.DIM}{'─' * 60}{C.RESET}\n")

        for iteration in range(1, self.config.max_iterations + 1):
            step_start = time.time()
            result.iterations_used = iteration

            # ── Step header ───────────────────────────────────────
            print(f"{C.MAGENTA}{C.BOLD}[Step {iteration}/{self.config.max_iterations}]{C.RESET}")

            # ── Stream LLM response ──────────────────────────────
            full_response = ""
            print(f"{C.GRAY}", end="", flush=True)

            try:
                if self.config.streaming:
                    for token in self.client.chat_stream(self.messages):
                        print(token, end="", flush=True)
                        full_response += token
                else:
                    full_response = self.client.chat(self.messages)
                    print(full_response, end="")
            except Exception as exc:
                print(f"\n{C.RED}{exc}{C.RESET}")
                result.aborted = True
                break

            print(f"{C.RESET}\n")

            # Strip ANSI codes for parsing (reasoning models inject escape codes)
            clean_response = _strip_ansi(full_response)

            # ── Add assistant message to history ──────────────────
            self.messages.append(ChatMessage(role="assistant", content=clean_response))

            # ── Check for final answer ────────────────────────────
            final = parse_final_answer(clean_response)
            if final:
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
                self._print_final_answer(final)
                break

            # ── Check for tool call ───────────────────────────────
            tool_call = parse_tool_call(clean_response)
            if tool_call:
                self._print_tool_call(tool_call)

                # Execute the tool
                tool_result = tool_registry.execute(
                    tool_call.tool,
                    tool_call.args,
                    self.config,
                )
                self._print_tool_result(tool_result)

                # Inject result back into conversation
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

            # ── No tool call and no final answer ──────────────────
            # Nudge the model to take action
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
            # Max iterations hit
            result.aborted = True
            print(f"\n{C.RED}{C.BOLD}[!] Max iterations ({self.config.max_iterations}) reached. Stopping.{C.RESET}")
            # Ask for a summary of what was accomplished
            if not result.final_answer:
                result.final_answer = "Task was not completed within the iteration limit."

        result.total_elapsed = time.time() - start_time
        self._print_summary(result)
        return result

    def clear_history(self):
        """Clear conversation history."""
        self.messages.clear()

    # ── Display helpers ───────────────────────────────────────────

    def _print_tool_call(self, tool_call: ParsedToolCall):
        print(f"  {C.YELLOW}{C.BOLD}[TOOL] {C.RESET}{C.YELLOW}{tool_call.display()}{C.RESET}")

    def _print_tool_result(self, result: str):
        # Truncate for display
        display = result if len(result) <= 1500 else result[:1500] + f"\n{C.DIM}... ({len(result)} chars total){C.RESET}"
        print(f"  {C.CYAN}[RESULT]{C.RESET}")
        for line in display.splitlines():
            print(f"  {C.CYAN}│{C.RESET} {line}")
        print()

    def _print_final_answer(self, answer: str):
        print(f"\n{C.GREEN}{C.BOLD}{'═' * 60}")
        print(f"  FINAL ANSWER")
        print(f"{'═' * 60}{C.RESET}")
        print(f"{C.GREEN}{answer}{C.RESET}")
        print(f"{C.GREEN}{C.BOLD}{'═' * 60}{C.RESET}\n")

    def _print_summary(self, result: AgentResult):
        tool_steps = sum(1 for s in result.steps if s.tool_call)
        provider_tag = f"{self.config.provider}:{self.config.active_model}"
        print(f"\n{C.DIM}{'─' * 60}")
        print(f"  Provider: {provider_tag}")
        print(f"  Steps: {result.iterations_used} | Tools used: {tool_steps} | Time: {result.total_elapsed:.1f}s")
        if result.aborted:
            print(f"  Status: ABORTED (max iterations)")
        else:
            print(f"  Status: COMPLETED")
        print(f"{'─' * 60}{C.RESET}")
