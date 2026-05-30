import os
import re
import requests
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse

from langchain.tools import tool
from tavily import TavilyClient
from bs4 import BeautifulSoup


@tool
def web_search(query: str) -> str:
    """Search the web for current information on any topic.
    Use this when you need recent news, facts, or information
    that may not be in your training data. Returns up to 5
    results with title, URL and snippet for each."""
    api_key = os.getenv("TAVILY_API_KEY")
    if not api_key:
        return "Search failed: TAVILY_API_KEY is not set. Add it to your .env file."
    try:
        client = TavilyClient(api_key=api_key)
        response = client.search(query, max_results=5)
        results = []
        for r in response["results"]:
            results.append(
                f"Title: {r['title']}\n"
                f"URL:   {r['url']}\n"
                f"Info:  {r['content']}\n"
            )
        if not results:
            return "No results found. Try a different search query."
        return "\n---\n".join(results)
    except Exception as e:
        return f"Search failed: {str(e)}"


@tool
def scrape_page(url: str) -> str:
    """Fetch and read the full text content of a web page.
    Use this after web_search to get complete information from
    a specific URL. Returns clean readable text up to 3000
    characters. Has a 10-second timeout and caps downloads at
    5 MB. Do not use on URLs that require login."""
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https") or not parsed.netloc:
        return f"Could not scrape {url}: invalid URL (must start with http:// or https://)"
    try:
        headers = {"User-Agent": "Mozilla/5.0"}
        with requests.get(url, headers=headers, timeout=10, stream=True) as response:
            response.raise_for_status()

            max_bytes = 5 * 1024 * 1024
            content_bytes = b""
            for chunk in response.iter_content(chunk_size=65536, decode_unicode=False):
                content_bytes += chunk
                if len(content_bytes) >= max_bytes:
                    content_bytes = content_bytes[:max_bytes]
                    break

        text = content_bytes.decode("utf-8", errors="replace")

        soup = BeautifulSoup(text, "html.parser")

        for tag in soup(["script", "style", "nav", "footer", "header"]):
            tag.decompose()

        text = soup.get_text(separator="\n")

        lines = [line.strip() for line in text.splitlines()]
        cleaned = "\n".join(line for line in lines if line)

        if not cleaned:
            return f"Could not scrape {url}: page has no readable text content"

        if len(cleaned) > 3000:
            cleaned = cleaned[:3000]
            last_space = cleaned.rfind(" ")
            if last_space > 2000:
                cleaned = cleaned[:last_space]
            cleaned += "\n\n[Content truncated to 3000 chars]"

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
def save_report(content: str) -> str:
    """Save a research report to a markdown file in the reports/ folder.
    Use this as the final step when you have finished researching
    and want to persist the findings. The content should be a
    well-structured markdown document with headers and sections.
    Files are auto-named as report_YYYYMMDD_HHMMSS.md.
    Returns the file path where the report was saved."""
    try:
        Path("reports").mkdir(exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
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

        if not re.match(r'^[\d \+\-\*\/\.\(\)\%]+$', expression):
            return "Invalid expression — only basic arithmetic is supported."

        if expression.count("**") > 1:
            return "Expression contains repeated exponentiation which is not allowed."

        result = eval(expression)
        return f"{expression} = {result}"
    except Exception as e:
        return f"Calculation failed: {str(e)}"


TOOLS = [web_search, scrape_page, save_report, calculate]
