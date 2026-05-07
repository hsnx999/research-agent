import re
import requests
from datetime import datetime
from pathlib import Path

from langchain.tools import tool
from tavily import TavilyClient
from bs4 import BeautifulSoup


# ── Tool 1: Web Search ─────────────────────────────────────────────────────
@tool
def web_search(query: str) -> str:
    """Search the web for current information on any topic.
    Use this when you need recent news, facts, or information
    that may not be in your training data. Returns titles,
    URLs and snippets of the top results."""
    import os
    try:
        client = TavilyClient(api_key=os.getenv("TAVILY_API_KEY"))
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
        
# ── Tool 2: Scrape Page ────────────────────────────────────────────────────
@tool
def scrape_page(url: str) -> str:
    """Fetch and read the full text content of a web page.
    Use this after web_search to get complete information from
    a specific URL. Strips HTML and returns clean readable text.
    Do not use on URLs that require login."""
    try:
        headers = {"User-Agent": "Mozilla/5.0"}
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()

        soup = BeautifulSoup(response.text, "html.parser")

        # Remove noise: scripts, styles, nav, footers
        for tag in soup(["script", "style", "nav", "footer", "header"]):
            tag.decompose()

        text = soup.get_text(separator="\n")

        # Clean up excessive whitespace
        lines  = [line.strip() for line in text.splitlines()]
        cleaned = "\n".join(line for line in lines if line)

        # Cap at 3000 chars to avoid blowing the context window
        if len(cleaned) > 3000:
            cleaned = cleaned[:3000] + "\n\n[Content truncated to 3000 chars]"

        return cleaned
    except Exception as e:
        return f"Could not scrape {url}: {str(e)}"


# ── Tool 3: Save Report ────────────────────────────────────────────────────
@tool
def save_report(content: str) -> str:
    """Save a research report to a markdown file in the reports/ folder.
    Use this as the final step when you have finished researching
    and want to persist the findings. The content should be a
    well-structured markdown document with headers and sections.
    Returns the file path where the report was saved."""
    try:
        Path("reports").mkdir(exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filepath  = f"reports/report_{timestamp}.md"
        Path(filepath).write_text(content, encoding="utf-8")
        return f"Report saved to {filepath}"
    except Exception as e:
        return f"Failed to save report: {str(e)}"


# ── Tool 4: Calculate ──────────────────────────────────────────────────────
@tool
def calculate(expression: str) -> str:
    """Evaluate a mathematical expression and return the result.
    Use this for any numerical calculations, percentages, or
    arithmetic needed during research.
    Example inputs: '150 * 0.43', '(2024 - 2017) / 7', '100 / 3'
    Only supports basic arithmetic — no imports or function calls."""
    try:
        # Whitelist only safe characters
        if not re.match(r'^[\d\s\+\-\*\/\.\(\)\%]+$', expression):
            return "Invalid expression — only basic arithmetic is supported."
        result = eval(expression)
        return f"{expression} = {result}"
    except Exception as e:
        return f"Calculation failed: {str(e)}"


# ── Export all tools as a list ─────────────────────────────────────────────
TOOLS = [web_search, scrape_page, save_report, calculate]