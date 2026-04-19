"""Tests for NeuronCLI tool call parsing and display formatting."""

import pytest
import sys
import os

# Add project root to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from neuroncli.agent import (
    parse_all_tool_calls,
    parse_final_answer,
    _render_table,
    _clean_for_display,
    _truncate_result,
    _strip_ansi,
)


# ── Tool Call Parsing ─────────────────────────────────────────────

class TestToolCallParsing:
    def test_single_tool_call(self):
        text = '<tool_call>\n{"tool": "read_file", "args": {"path": "test.py"}}\n</tool_call>'
        calls = parse_all_tool_calls(text)
        assert len(calls) == 1
        assert calls[0].tool == "read_file"
        assert calls[0].args["path"] == "test.py"

    def test_multiple_tool_calls(self):
        text = """
<tool_call>
{"tool": "read_file", "args": {"path": "a.py"}}
</tool_call>
<tool_call>
{"tool": "read_file", "args": {"path": "b.py"}}
</tool_call>
<tool_call>
{"tool": "list_directory", "args": {"path": "src"}}
</tool_call>
"""
        calls = parse_all_tool_calls(text)
        assert len(calls) == 3
        assert calls[0].args["path"] == "a.py"
        assert calls[1].args["path"] == "b.py"
        assert calls[2].tool == "list_directory"

    def test_deduplicate_tool_calls(self):
        text = """
<tool_call>
{"tool": "read_file", "args": {"path": "same.py"}}
</tool_call>
<tool_call>
{"tool": "read_file", "args": {"path": "same.py"}}
</tool_call>
"""
        calls = parse_all_tool_calls(text)
        assert len(calls) == 1  # Deduped

    def test_no_tool_call(self):
        text = "Just some thinking text without any tool calls."
        calls = parse_all_tool_calls(text)
        assert len(calls) == 0

    def test_code_block_tool_call(self):
        text = '```json\n{"tool": "run_command", "args": {"command": "ls"}}\n```'
        calls = parse_all_tool_calls(text)
        assert len(calls) == 1
        assert calls[0].tool == "run_command"

    def test_bare_json_tool_call(self):
        text = 'I will read the file now.\n{"tool": "read_file", "args": {"path": "main.py"}}'
        calls = parse_all_tool_calls(text)
        assert len(calls) == 1


# ── Final Answer Parsing ─────────────────────────────────────────

class TestFinalAnswer:
    def test_extract_answer(self):
        text = "Some thinking...\n<final_answer>\nHere is the result.\n</final_answer>"
        answer = parse_final_answer(text)
        assert answer == "Here is the result."

    def test_no_answer(self):
        text = "Just thinking, no answer yet."
        assert parse_final_answer(text) is None

    def test_multiline_answer(self):
        text = "<final_answer>\nLine 1\nLine 2\nLine 3\n</final_answer>"
        answer = parse_final_answer(text)
        assert "Line 1" in answer
        assert "Line 3" in answer


# ── Table Rendering ──────────────────────────────────────────────

class TestTableRendering:
    def test_basic_table(self):
        table = """| Name | Age |
|------|-----|
| Alice | 30 |
| Bob | 25 |"""
        result = _render_table(table)
        plain = _strip_ansi(result)
        assert "Alice" in plain
        assert "Bob" in plain
        assert "|" not in plain  # No raw markdown pipes
        assert "---" in plain  # Separator exists

    def test_truncation(self):
        # Long cell should be truncated at MAX_COL_WIDTH (40)
        table = """| Col |
|-----|
| """ + "x" * 60 + """ |"""
        result = _render_table(table)
        plain = _strip_ansi(result)
        assert "..." in plain  # Truncated

    def test_empty_table(self):
        result = _render_table("")
        assert result == ""


# ── Display Cleaning ─────────────────────────────────────────────

class TestCleanDisplay:
    def test_strip_xml_tags(self):
        text = "<final_answer>Hello world</final_answer>"
        result = _clean_for_display(text)
        plain = _strip_ansi(result)
        assert "<final_answer>" not in plain
        assert "Hello world" in plain

    def test_strip_tool_call_tags(self):
        text = '<tool_call>{"tool": "test"}</tool_call>'
        result = _clean_for_display(text)
        plain = _strip_ansi(result)
        assert "<tool_call>" not in plain

    def test_markdown_bold(self):
        text = "This is **bold** text"
        result = _clean_for_display(text)
        # Should contain ANSI bold codes, not raw **
        assert "**" not in _strip_ansi(result)
        assert "bold" in _strip_ansi(result)


# ── Result Truncation ────────────────────────────────────────────

class TestTruncation:
    def test_short_not_truncated(self):
        text = "short text"
        assert _truncate_result(text) == text

    def test_long_truncated(self):
        text = "x" * 10000
        result = _truncate_result(text, max_chars=1000)
        assert len(result) < 10000
        assert "truncated" in result

    def test_preserves_head_tail(self):
        text = "HEAD" + "x" * 10000 + "TAIL"
        result = _truncate_result(text, max_chars=1000)
        assert result.startswith("HEAD")
        assert result.endswith("TAIL")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
