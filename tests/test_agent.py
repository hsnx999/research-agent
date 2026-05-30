"""Tests for input validation and callback safety."""
import pytest
from agent import run, LiveThoughtHandler


class TestInputValidation:
    def test_run_empty_task(self):
        with pytest.raises(ValueError, match="cannot be empty"):
            run("")

    def test_run_whitespace_only_task(self):
        with pytest.raises(ValueError, match="cannot be empty"):
            run("   \n  ")

    def test_run_too_long_task(self):
        with pytest.raises(ValueError, match="too long"):
            run("x" * 10001)

    def test_valid_task_passes_validation(self, monkeypatch):
        # Should pass validation but fail at LLM init (no real API key)
        monkeypatch.delenv("GROQ_API_KEY", raising=False)
        with pytest.raises(RuntimeError, match="GROQ_API_KEY"):
            run("valid research task")


class TestCallbackSafety:
    def test_on_agent_action_does_not_crash(self, capsys):
        handler = LiveThoughtHandler()
        handler.on_agent_action(None)  # None has no .tool attr
        captured = capsys.readouterr()
        assert "Warning" in captured.err

    def test_on_tool_end_does_not_crash(self, capsys):
        handler = LiveThoughtHandler()
        handler.on_tool_end(None)  # str(None) works, no crash
        captured = capsys.readouterr()
        assert "Result: None" in captured.out

    def test_on_agent_finish_does_not_crash(self, capsys):
        handler = LiveThoughtHandler()
        handler.on_agent_finish(None)  # No operations on finish, no crash
        captured = capsys.readouterr()
        assert "Agent finished" in captured.out
