"""Tests for input validation, callback safety, and CLI."""
from pathlib import Path

import pytest
from agent import run, LiveThoughtHandler, list_reports


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


class TestCLI:
    def test_list_reports_no_directory(self, capsys, monkeypatch, tmp_path):
        monkeypatch.chdir(tmp_path)
        Path(tmp_path / "reports").mkdir()
        list_reports()
        captured = capsys.readouterr()
        assert "No reports found" in captured.out

    def test_list_reports_with_file(self, capsys, monkeypatch, tmp_path):
        monkeypatch.chdir(tmp_path)
        reports_dir = Path(tmp_path / "reports")
        reports_dir.mkdir()
        report_file = reports_dir / "test_report.md"
        report_file.write_text("# Test Report\n\nSome content.")
        list_reports()
        captured = capsys.readouterr()
        assert "test_report.md" in captured.out
        assert "Total:" in captured.out


class TestInteractive:
    def test_run_interactive_exit(self, monkeypatch, capsys):
        monkeypatch.setattr("builtins.input", lambda _: "exit")
        from agent import run_interactive
        run_interactive()
        captured = capsys.readouterr()
        assert "Goodbye" in captured.out

    def test_run_interactive_quit(self, monkeypatch, capsys):
        monkeypatch.setattr("builtins.input", lambda _: "quit")
        from agent import run_interactive
        run_interactive()
        captured = capsys.readouterr()
        assert "Goodbye" in captured.out

    def test_run_interactive_empty_input(self, monkeypatch, capsys):
        inputs = iter(["", "exit"])
        monkeypatch.setattr("builtins.input", lambda _: next(inputs))
        from agent import run_interactive
        run_interactive()
        captured = capsys.readouterr()
        assert "Goodbye" in captured.out

    def test_run_interactive_maintains_history(self, monkeypatch, capsys):
        # Verify history is built up across turns
        from agent import run_interactive
        # Simulate one valid query then exit
        calls = []
        def mock_input(prompt):
            calls.append(prompt)
            if len(calls) == 1:
                return "valid task"
            return "exit"
        monkeypatch.setattr("builtins.input", mock_input)
        # Mock run() to return a fixed answer
        monkeypatch.setattr("agent.run", lambda task: "mock answer for: " + task[:20])
        run_interactive()
        captured = capsys.readouterr()
        assert "Final Answer" in captured.out
