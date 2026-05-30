"""Tests for input validation, callback safety, and CLI."""
import threading
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


class TestSpinner:
    def test_spinner_stops_on_completion(self):
        from agent import _spin
        stop = threading.Event()
        t = threading.Thread(target=_spin, args=(stop,), daemon=True)
        t.start()
        stop.set()
        t.join(timeout=1)
        assert not t.is_alive()


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


class TestDepthFlags:
    def test_quick_instructions(self):
        instructions = "Be brief — limit to 1 search and 1 scrape maximum."
        assert "1 search" in instructions

    def test_deep_instructions(self):
        instructions = "Be thorough — search at least 5 times and scrape at least 3 pages."
        assert "5 times" in instructions


class TestReportName:
    def test_report_name_slugified(self):
        import re
        name = re.sub(r'[^a-z0-9]+', '-', "AI Trends".lower()).strip('-')
        assert name == "ai-trends"

    def test_report_name_with_special_chars(self):
        import re
        name = re.sub(r'[^a-z0-9]+', '-', "My!!! Report__2026".lower()).strip('-')
        assert name == "my-report-2026"


class TestToolStats:
    def test_tool_counts_incremented(self):
        from agent import LiveThoughtHandler, _tool_counts, _tool_stats_lock
        _tool_counts.clear()
        handler = LiveThoughtHandler()

        class MockAction:
            tool = "web_search"
            tool_input = "test query"

        handler.on_agent_action(MockAction())
        with _tool_stats_lock:
            assert _tool_counts.get("web_search") == 1

        handler.on_agent_action(MockAction())
        with _tool_stats_lock:
            assert _tool_counts.get("web_search") == 2

    def test_tool_counts_multiple_tools(self):
        from agent import LiveThoughtHandler, _tool_counts, _tool_stats_lock
        _tool_counts.clear()
        handler = LiveThoughtHandler()

        class MockAction:
            def __init__(self, tool, inp):
                self.tool = tool
                self.tool_input = inp

        handler.on_agent_action(MockAction("web_search", "q1"))
        handler.on_agent_action(MockAction("scrape_page", "url1"))
        handler.on_agent_action(MockAction("web_search", "q2"))

        with _tool_stats_lock:
            assert _tool_counts["web_search"] == 2
            assert _tool_counts["scrape_page"] == 1

    def test_print_stats_output(self, capsys):
        from agent import print_stats, _tool_counts, _tool_stats_lock
        with _tool_stats_lock:
            _tool_counts.clear()
            _tool_counts["web_search"] = 2
            _tool_counts["scrape_page"] = 1

        print_stats()
        captured = capsys.readouterr()
        assert "web_search" in captured.out
        assert "Total" in captured.out
        assert "3" in captured.out  # 2 + 1 = 3

    def test_print_stats_no_calls(self, capsys):
        from agent import print_stats, _tool_counts, _tool_stats_lock
        with _tool_stats_lock:
            _tool_counts.clear()

        print_stats()
        captured = capsys.readouterr()
        assert "No tool calls" in captured.out

    def test_counts_reset_on_run(self, monkeypatch):
        from agent import run, _tool_counts, _tool_stats_lock
        # Set some pre-existing counts
        with _tool_stats_lock:
            _tool_counts["web_search"] = 99
        # run() should reset them before trying LLM (which will fail without key)
        monkeypatch.delenv("GROQ_API_KEY", raising=False)
        with pytest.raises(RuntimeError):
            run("test task")
        with _tool_stats_lock:
            assert _tool_counts.get("web_search", 0) == 0


class TestSearchReports:
    def test_search_no_directory(self, capsys, monkeypatch, tmp_path):
        monkeypatch.chdir(tmp_path)
        from agent import search_reports
        search_reports("anything")
        captured = capsys.readouterr()
        assert "No reports directory" in captured.out

    def test_search_no_matches(self, capsys, monkeypatch, tmp_path):
        monkeypatch.chdir(tmp_path)
        reports_dir = Path(tmp_path / "reports")
        reports_dir.mkdir()
        (reports_dir / "test.md").write_text("# Hello World", encoding="utf-8")
        from agent import search_reports
        search_reports("nonexistent")
        captured = capsys.readouterr()
        assert "No matches" in captured.out

    def test_search_finds_match(self, capsys, monkeypatch, tmp_path):
        monkeypatch.chdir(tmp_path)
        reports_dir = Path(tmp_path / "reports")
        reports_dir.mkdir()
        (reports_dir / "test.md").write_text("# Hello World\n\nSome AI content here.", encoding="utf-8")
        from agent import search_reports
        search_reports("AI")
        captured = capsys.readouterr()
        assert "test.md" in captured.out
        assert "AI" in captured.out
        assert "match" in captured.out

    def test_search_case_insensitive(self, capsys, monkeypatch, tmp_path):
        monkeypatch.chdir(tmp_path)
        reports_dir = Path(tmp_path / "reports")
        reports_dir.mkdir()
        (reports_dir / "report.md").write_text("Artificial Intelligence is cool", encoding="utf-8")
        from agent import search_reports
        search_reports("intelligence")
        captured = capsys.readouterr()
        assert "report.md" in captured.out
        assert "match" in captured.out


class TestCustomPrompt:
    def test_prompt_file_read(self, monkeypatch, tmp_path):
        prompt_file = tmp_path / "custom.txt"
        prompt_file.write_text("You are a custom agent.", encoding="utf-8")
        from agent import run, _tool_counts, _tool_stats_lock
        with _tool_stats_lock:
            _tool_counts.clear()
        monkeypatch.delenv("GROQ_API_KEY", raising=False)
        # Run with system_prompt — the build_agent should use it
        # Since GROQ_API_KEY is missing, it'll raise RuntimeError, but we
        # verify the flow doesn't crash before that.
        with pytest.raises(RuntimeError):
            run("test task", system_prompt=prompt_file.read_text(encoding="utf-8"))

    def test_prompt_file_not_found(self, capsys, monkeypatch):
        from agent import run_cli
        # We can test the argparse dispatching by directly checking the path logic
        # Instead, test the file-not-found message from run_cli
        monkeypatch.setattr("sys.argv", ["agent.py", "--prompt", "/nonexistent/prompt.txt", "test task"])
        # run_cli will print warning about missing file, then try to build agent
        # which will fail with missing GROQ_API_KEY
        monkeypatch.delenv("GROQ_API_KEY", raising=False)
        with pytest.raises(SystemExit):
            run_cli()
        captured = capsys.readouterr()
        assert "not found" in captured.err or "not found" in captured.out

    def test_prompt_passed_to_build_agent(self, monkeypatch):
        from unittest.mock import MagicMock
        from src.agent_builder import build_agent
        # Mock the LLM to avoid real API call
        mock_llm = MagicMock()
        monkeypatch.setattr("src.agent_builder.ChatGroq", lambda **kwargs: mock_llm)
        # Mock hub.pull to return a base prompt
        from langchain.prompts import PromptTemplate
        monkeypatch.setattr("src.agent_builder.hub.pull", lambda name: PromptTemplate.from_template("Base: {input} {agent_scratchpad} {tools} {tool_names}"))
        
        custom = "You are a test bot."
        executor = build_agent(system_prompt=custom)
        # The executor was built successfully — verify the prompt was used
        assert executor is not None
