"""Baseline tests for every tool defined in src.tools."""

from pathlib import Path
from unittest.mock import patch

from src.tools import calculate, save_report, scrape_page, web_search


# ── web_search ──────────────────────────────────────────────────────────────

class TestWebSearch:
    """Tests for the web_search tool."""

    def test_web_search_missing_key(self, monkeypatch):
        """Should return the expected error when TAVILY_API_KEY is not set."""
        monkeypatch.delenv("TAVILY_API_KEY", raising=False)
        result = web_search("test query")
        assert result == (
            "Search failed: TAVILY_API_KEY is not set. "
            "Add it to your .env file."
        )

    def test_web_search_timeout_passed(self):
        """Verify that timeout=15 is passed to the Tavily client."""
        with patch("src.tools.TavilyClient") as MockClient:
            mock_instance = MockClient.return_value
            mock_instance.search.return_value = {"results": []}
            web_search("anything")
            _, kwargs = mock_instance.search.call_args
            assert kwargs.get("timeout") == 15, (
                f"Expected timeout=15, got timeout={kwargs.get('timeout')}"
            )


# ── scrape_page ─────────────────────────────────────────────────────────────

class TestScrapePage:
    """Tests for the scrape_page tool."""

    def test_scrape_page_invalid_url(self):
        """Non-HTTP URLs should produce an invalid-URL error."""
        result = scrape_page("not-a-valid-url")
        assert result.startswith("Could not scrape not-a-valid-url:")
        assert "invalid URL" in result

    def test_scrape_page_ftp_url(self):
        """FTP URLs should also be rejected."""
        result = scrape_page("ftp://files.example.com/doc.txt")
        assert "invalid URL" in result

    def test_scrape_page_private_ip(self):
        """Private IPv4 addresses must be blocked (SSRF protection)."""
        result = scrape_page("http://127.0.0.1/admin")
        assert "private" in result.lower() or "internal" in result.lower()

    def test_scrape_page_loopback_ipv6(self):
        """IPv6 loopback must also be blocked (SSRF protection)."""
        result = scrape_page("http://[::1]/")
        assert "private" in result.lower() or "internal" in result.lower()

    def test_scrape_page_link_local_ip(self):
        """Link-local address 169.254.1.1 must be blocked."""
        result = scrape_page("http://169.254.1.1/config")
        assert "private" in result.lower() or "internal" in result.lower()


# ── save_report ─────────────────────────────────────────────────────────────

class TestSaveReport:
    """Tests for the save_report tool."""

    def test_save_report_basic(self, tmp_reports_dir):
        """Writing a report should create the file with the correct content."""
        content = "# Test Report\n\nThis is a test."
        result = save_report(content)
        assert result.startswith("Report saved to ")

        filepath = result.replace("Report saved to ", "")
        saved = Path(filepath)
        assert saved.exists(), f"Report file {filepath} was not created"
        assert saved.read_text(encoding="utf-8") == content

    def test_save_report_empty_content(self, tmp_reports_dir):
        """Saving an empty string should still create a file."""
        result = save_report("")
        assert result.startswith("Report saved to ")

        filepath = result.replace("Report saved to ", "")
        assert Path(filepath).exists()
        assert Path(filepath).read_text(encoding="utf-8") == ""

    def test_save_report_unique_filenames(self, tmp_reports_dir):
        """Two saves in the same second must produce different filenames."""
        path1 = save_report("content1")
        path2 = save_report("content2")
        assert path1 != path2, f"Filenames must differ, got {path1!r} and {path2!r}"
        # Verify both files actually exist with the right content
        file1 = path1.replace("Report saved to ", "")
        file2 = path2.replace("Report saved to ", "")
        assert Path(file1).read_text(encoding="utf-8") == "content1"
        assert Path(file2).read_text(encoding="utf-8") == "content2"


# ── calculate ───────────────────────────────────────────────────────────────

class TestCalculate:
    """Tests for the calculate tool."""

    def test_calculate_basic(self):
        """2 + 2 should equal 4."""
        result = calculate("2+2")
        assert result == "2+2 = 4"

    def test_calculate_subtraction(self):
        """Basic subtraction."""
        result = calculate("10-3")
        assert result == "10-3 = 7"

    def test_calculate_multiplication(self):
        """Basic multiplication."""
        result = calculate("4*5")
        assert result == "4*5 = 20"

    def test_calculate_division(self):
        """Basic division."""
        result = calculate("100/4")
        assert result == "100/4 = 25.0"

    def test_calculate_parentheses(self):
        """Expressions with parentheses."""
        result = calculate("(2+3)*4")
        assert result == "(2+3)*4 = 20"

    def test_calculate_power(self):
        """Single exponentiation should work."""
        result = calculate("2**10")
        assert result == "2**10 = 1024"

    def test_calculate_modulo(self):
        """Modulo operator."""
        result = calculate("10%3")
        assert result == "10%3 = 1"

    def test_calculate_invalid_expression(self):
        """Non-math strings should be rejected."""
        result = calculate("hello + world")
        assert "Invalid expression" in result

    def test_calculate_repeated_power(self):
        """Repeated exponentiation (2**2**2) is explicitly blocked."""
        result = calculate("2**2**2")
        assert "repeated exponentiation" in result

    def test_calculate_too_long(self):
        """Expressions over 200 characters are blocked."""
        long_expr = "1" * 201
        result = calculate(long_expr)
        assert "too long" in result

    def test_calculate_expression_with_letters(self):
        """Letters anywhere in the expression should be rejected."""
        result = calculate("2a+2")
        assert "Invalid expression" in result

    def test_calculate_unicode_digit_rejected(self):
        """Unicode digits (e.g. Arabic-Indic) must be rejected by the regex."""
        result = calculate("١٢٣")  # Arabic-Indic digits
        assert "Invalid expression" in result or "not allowed" in result.lower()

    def test_calculate_trailing_newline(self):
        """A trailing newline should still work (the regex can match the digits)."""
        result = calculate("2+2\n")
        # The newline character is not in the allowed character set,
        # so it should either be rejected gracefully or stripped.
        # With re.fullmatch, "\n" does not match, so expect rejection.
        assert "Invalid expression" in result
