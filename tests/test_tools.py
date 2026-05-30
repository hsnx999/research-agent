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

    def test_search_cache_hit(self, monkeypatch):
        """Same query twice: second call returns cached result, Tavily called once."""
        from src.tools import web_search, _search_cache
        from unittest.mock import MagicMock

        _search_cache.clear()
        import src.tools

        fake_time = [100.0]
        monkeypatch.setattr(src.tools, "time", lambda: fake_time[0])
        mock_client = MagicMock()
        mock_client.search.return_value = {"results": []}
        monkeypatch.setattr(src.tools, "TavilyClient", lambda api_key: mock_client)
        monkeypatch.setenv("TAVILY_API_KEY", "fake-key")

        result1 = web_search("hit-test")
        assert result1 == "No results found. Try a different search query."
        assert mock_client.search.call_count == 1

        result2 = web_search("hit-test")
        assert result2 == "No results found. Try a different search query."
        assert mock_client.search.call_count == 1  # cache hit, no extra call

    def test_search_cache_miss_after_ttl(self, monkeypatch):
        """Expired cache entry is removed and re-fetched (fresh TTL)."""
        from src.tools import web_search, _search_cache, _search_cache_ttl
        from unittest.mock import MagicMock

        _search_cache.clear()
        import src.tools

        fake_time = [100.0]
        monkeypatch.setattr(src.tools, "time", lambda: fake_time[0])
        mock_client = MagicMock()
        mock_client.search.return_value = {"results": []}
        monkeypatch.setattr(src.tools, "TavilyClient", lambda api_key: mock_client)
        monkeypatch.setenv("TAVILY_API_KEY", "fake-key")

        # Insert an expired entry
        _search_cache["ttl-test"] = ("old cached value", fake_time[0] - 1)

        fake_time[0] += 1
        result = web_search("ttl-test")
        assert result == "No results found. Try a different search query."
        # Expired entry removed, new result cached with fresh TTL
        assert "ttl-test" in _search_cache
        cached_val, expiry = _search_cache["ttl-test"]
        assert cached_val == "No results found. Try a different search query."
        assert expiry == fake_time[0] + _search_cache_ttl

    def test_search_cache_max_eviction(self, monkeypatch):
        """When cache exceeds max, oldest entry is evicted."""
        from src.tools import web_search, _search_cache, _search_cache_max
        from unittest.mock import MagicMock

        _search_cache.clear()
        import src.tools

        fake_time = [100.0]
        monkeypatch.setattr(src.tools, "time", lambda: fake_time[0])
        mock_client = MagicMock()
        mock_client.search.return_value = {"results": []}
        monkeypatch.setattr(src.tools, "TavilyClient", lambda api_key: mock_client)
        monkeypatch.setenv("TAVILY_API_KEY", "fake-key")

        # Fill cache to max (each call increments fake_time for ordering)
        for i in range(_search_cache_max):
            web_search(f"query-{i}")
            fake_time[0] += 1

        assert len(_search_cache) == _search_cache_max

        # Add one more — oldest ("query-0") should be evicted
        fake_time[0] += 1
        web_search("new-query")

        assert len(_search_cache) == _search_cache_max
        assert "new-query" in _search_cache
        assert "query-0" not in _search_cache  # oldest evicted


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

    def test_scrape_page_truncates_at_1500(self, monkeypatch):
        """Scrape output should be limited to ~1500 characters."""
        from unittest.mock import MagicMock
        from src.tools import scrape_page

        # Mock requests.get to return a response with long content
        mock_resp = MagicMock()
        mock_resp.headers = {"Content-Type": "text/html"}
        mock_resp.__enter__.return_value = mock_resp
        mock_resp.iter_content.return_value = [b"<p>test</p>"]
        monkeypatch.setattr("src.tools.requests.get", lambda *a, **kw: mock_resp)

        # Mock BeautifulSoup to return long text content
        long_text = "word " * 800  # ~4000 chars
        mock_soup = MagicMock()
        mock_soup.get_text.return_value = long_text
        mock_soup.__getitem__.return_value = []
        monkeypatch.setattr("src.tools.BeautifulSoup", lambda t, p: mock_soup)

        result = scrape_page("https://example.com")
        assert len(result) <= 1600, f"Expected <= 1600 chars, got {len(result)}"
        assert "truncated" in result.lower(), "Truncation marker missing"
        assert len(result) < 3000, "Output exceeded old 3000-char limit"


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
        """Two saves with different names must produce different filenames."""
        path1 = save_report.invoke({"content": "content1", "name": "first"})
        path2 = save_report.invoke({"content": "content2", "name": "second"})
        assert path1 != path2, f"Filenames must differ, got {path1!r} and {path2!r}"
        # Verify both files actually exist with the right content
        file1 = path1.replace("Report saved to ", "")
        file2 = path2.replace("Report saved to ", "")
        assert Path(file1).read_text(encoding="utf-8") == "content1"
        assert Path(file2).read_text(encoding="utf-8") == "content2"

    def test_save_report_with_name(self, tmp_reports_dir):
        """Passing a name should include the slugified name in the path."""
        result = save_report.invoke({"content": "# Test", "name": "AI Trends"})
        assert "ai-trends" in result
        assert result.startswith("Report saved to")

    def test_save_report_with_name_slugified(self, tmp_reports_dir):
        """Name should be slugified (lowercased, non-alphanumeric -> hyphens)."""
        result = save_report.invoke({"content": "# Test", "name": "  My  Report!!!  "})
        assert "my-report" in result

    def test_save_report_without_name_falls_back(self, tmp_reports_dir):
        """Without a name, the filename starts with report_<timestamp>."""
        result = save_report("# Test")
        assert result.startswith("Report saved to reports/report_2")


# ── scrape_pages ──────────────────────────────────────────────────────────────

class TestScrapePages:
    """Tests for the concurrent scrape_pages tool."""

    def test_scrape_pages_empty_input(self):
        """Empty input should return an error message."""
        from src.tools import scrape_pages
        result = scrape_pages("")
        assert "No valid URLs" in result

    def test_scrape_pages_single_url(self, monkeypatch):
        """A single valid URL should be scraped successfully."""
        from src.tools import scrape_pages
        monkeypatch.setattr("src.tools.scrape_page", lambda url: f"Content for {url}")
        result = scrape_pages("https://example.com")
        assert "https://example.com" in result
        assert "Content" in result

    def test_scrape_pages_max_three_urls(self, monkeypatch):
        """At most 3 URLs should be processed; extras are ignored."""
        from src.tools import scrape_pages
        scraped = []

        def mock_scrape(url):
            scraped.append(url)
            return f"Content for {url}"

        monkeypatch.setattr("src.tools.scrape_page", mock_scrape)
        urls = "https://a.com, https://b.com, https://c.com, https://d.com"
        result = scrape_pages(urls)
        assert len(scraped) == 3
        assert "https://d.com" not in result

    def test_scrape_pages_some_fail(self, monkeypatch):
        """If one URL fails, others should still be returned."""
        from src.tools import scrape_pages
        call_count = [0]

        def mock_scrape(url):
            call_count[0] += 1
            if call_count[0] == 2:
                raise Exception("boom")
            return f"Content for {url}"

        monkeypatch.setattr("src.tools.scrape_page", mock_scrape)
        result = scrape_pages("https://a.com, https://b.com")
        assert "https://a.com" in result
        assert "Error" in result

    def test_scrape_pages_in_tools_list(self):
        """scrape_pages must be registered in TOOLS list."""
        from src.tools import TOOLS
        names = [t.name for t in TOOLS]
        assert "scrape_pages" in names


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
