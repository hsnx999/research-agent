import ipaddress
import os
import re
import requests
from datetime import datetime
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
from threading import Lock
from time import time
from urllib.parse import urlparse


from langchain.tools import tool
from tavily import TavilyClient
from bs4 import BeautifulSoup

_search_cache = {}
_search_cache_ttl = 300  # 5 minutes
_search_cache_max = 50
_search_cache_lock = Lock()


@tool
def web_search(query: str) -> str:
    """Search the web for current information on any topic.
    Use this when you need recent news, facts, or information
    that may not be in your training data. Returns up to 5
    results with title, URL and snippet for each.

    Results are cached in memory for 5 minutes (TTL) to avoid
    repeated API calls for the same query. The cache holds up
    to 50 entries; when full, the oldest entry is evicted."""
    # Check cache first
    now = time()
    with _search_cache_lock:
        if query in _search_cache:
            result, expiry = _search_cache[query]
            if now < expiry:
                return result
            del _search_cache[query]

    # Cache miss — perform actual search
    api_key = os.getenv("TAVILY_API_KEY")
    if not api_key:
        return "Search failed: TAVILY_API_KEY is not set. Add it to your .env file."
    try:
        client = TavilyClient(api_key=api_key)
        response = client.search(query, max_results=5, timeout=15)
        results = []
        for r in response["results"]:
            results.append(
                f"Title: {r['title']}\n"
                f"URL:   {r['url']}\n"
                f"Info:  {r['content']}\n"
            )
        if not results:
            result_str = "No results found. Try a different search query."
        else:
            result_str = "\n---\n".join(results)

        # Store in cache
        with _search_cache_lock:
            if len(_search_cache) >= _search_cache_max:
                oldest = min(
                    _search_cache.keys(), key=lambda k: _search_cache[k][1]
                )
                del _search_cache[oldest]
            _search_cache[query] = (result_str, now + _search_cache_ttl)

        return result_str
    except Exception as e:
        return f"Search failed: {str(e)}"


@tool
def scrape_page(url: str) -> str:
    """Fetch and read the full text content of a web page.
    Use this after web_search to get complete information from
    a specific URL. Returns clean readable text up to 1500
    characters. Has a 10-second timeout and caps downloads at
    5 MB. Do not use on URLs that require login."""
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https") or not parsed.netloc:
        return f"Could not scrape {url}: invalid URL (must start with http:// or https://)"

    # SSRF protection: reject private/loopback/link-local IPs
    hostname = parsed.hostname
    if hostname is None:
        return f"Could not scrape {url}: could not parse hostname from URL"
    try:
        addr = ipaddress.ip_address(hostname)
        if addr.is_private or addr.is_loopback or addr.is_link_local:
            return f"Could not scrape {url}: cannot access private or internal addresses"
    except ValueError:
        pass  # hostname is a domain name, not a raw IP — safe to proceed

    try:
        headers = {"User-Agent": "Mozilla/5.0"}
        # Note: redirects are unlimited by default (requests follows up to 30)
        with requests.get(url, headers=headers, timeout=10, stream=True) as response:
            response.raise_for_status()

            max_bytes = 5 * 1024 * 1024
            content_bytes = b""
            for chunk in response.iter_content(chunk_size=65536, decode_unicode=False):
                content_bytes += chunk
                if len(content_bytes) >= max_bytes:
                    content_bytes = content_bytes[:max_bytes]
                    break

        # Charset sniffing from Content-Type header
        content_type = response.headers.get("Content-Type", "")
        charset = "utf-8"
        if "charset=" in content_type:
            charset = content_type.split("charset=")[-1].split(";")[0].strip()
        text = content_bytes.decode(charset, errors="replace")

        soup = BeautifulSoup(text, "lxml")

        for tag in soup(["script", "style", "nav", "footer", "header"]):
            tag.decompose()

        text = soup.get_text(separator="\n")

        lines = [line.strip() for line in text.splitlines()]
        cleaned = "\n".join(line for line in lines if line)

        if not cleaned:
            return f"Could not scrape {url}: page has no readable text content"

        if len(cleaned) > 1500:
            cleaned = cleaned[:1500]
            last_space = cleaned.rfind(" ")
            if last_space > 1000:
                cleaned = cleaned[:last_space]
            cleaned += "\n\n[Content truncated to 1500 chars]"

        return cleaned
    except requests.exceptions.Timeout:
        return f"Could not scrape {url}: request timed out after 10 seconds"
    except requests.exceptions.ConnectionError:
        return f"Could not scrape {url}: failed to connect"
    except requests.exceptions.HTTPError as e:
        return f"Could not scrape {url}: HTTP {e.response.status_code}"
    except Exception as e:
        return f"Could not scrape {url}: {str(e)}"


@tool
def scrape_pages(urls: str) -> str:
    """Fetch multiple web pages at the same time for faster research.
    Pass URLs as a comma-separated list (up to 3 URLs).
    Use this when you have multiple URLs from a search and want
    to read them all at once. Each page is capped at 1000 characters.

    Example: 'https://example.com/page1, https://example.com/page2'
    Returns combined content from all successfully scraped pages."""
    url_list = [u.strip() for u in urls.split(",") if u.strip()][:3]
    if not url_list:
        return "No valid URLs provided. Pass comma-separated URLs."

    def _scrape_single(url: str) -> tuple[str, str]:
        try:
            result = scrape_page(url)
            return (url, result)
        except Exception as e:
            return (url, f"Error: {e}")

    results = []
    with ThreadPoolExecutor(max_workers=3) as executor:
        for url, result in executor.map(_scrape_single, url_list):
            results.append(f"=== {url} ===\n{result[:1000]}")

    return "\n\n".join(results)


@tool
def save_report(content: str, name: str = None) -> str:
    """Save a research report to a markdown file in the reports/ folder.
    Use this as the final step when you have finished researching
    and want to persist the findings. The content should be a
    well-structured markdown document with headers and sections.

    Optionally pass a descriptive `name` to give the file a custom name
    instead of using just an auto-generated timestamp. The name will be
    slugified for the filesystem (e.g. 'AI Trends' becomes 'ai-trends').

    Files are named: report_{slug}_{timestamp}.md when a name is given,
    or report_{timestamp}.md when no name is given.
    Returns the file path where the report was saved."""
    try:
        Path("reports").mkdir(exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        if name:
            slug = re.sub(r'[^a-z0-9]+', '-', name.lower()).strip('-')
            filepath = f"reports/report_{slug}_{timestamp}.md"
        else:
            filepath = f"reports/report_{timestamp}.md"
        Path(filepath).write_text(content, encoding="utf-8")
        return f"Report saved to {filepath}"
    except Exception as e:
        return f"Failed to save report: {str(e)}"


@tool
def calculate(expression: str) -> str:
    """Evaluate a mathematical expression and return the result.
    Use this for any numerical calculations, percentages, or
    arithmetic needed during research.
    Supported operators: +, -, *, /, ** (exponent), % (modulo), ( )
    Do NOT use % for percentages — use decimal multiplication instead
    (e.g., '150 * 0.43' for 43% of 150).
    Example inputs: '150 * 0.43', '(2024 - 2017) / 7', '100 / 3', '2 ** 10'
    Only supports basic arithmetic — no imports or function calls."""
    try:
        if len(expression) > 200:
            return "Expression too long (max 200 characters)."

        if not re.fullmatch(r'[0-9+\-*/.()% ]+', expression):
            return "Invalid expression — only basic arithmetic is supported."

        if expression.count("**") > 1:
            return "Expression contains repeated exponentiation which is not allowed."

        result = eval(expression)
        return f"{expression} = {result}"
    except Exception as e:
        return f"Calculation failed: {str(e)}"


TOOLS = [web_search, scrape_pages, scrape_page, save_report, calculate]
