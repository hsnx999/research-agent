"""Shared fixtures for the research-agent test suite."""

import pytest


@pytest.fixture(autouse=True)
def load_env():
    """Load .env file if it exists (fail gracefully if missing or no dotenv)."""
    try:
        from dotenv import load_dotenv
        load_dotenv()
    except (ImportError, FileNotFoundError):
        pass


@pytest.fixture
def tmp_reports_dir(tmp_path, monkeypatch):
    """Change to a temporary directory so save_report writes to a clean location."""
    monkeypatch.chdir(tmp_path)
    return tmp_path
