# Research Agent — Autonomous AI Agent

An autonomous AI agent that researches topics by searching the web,
reading pages, reasoning across multiple steps, and saving structured
reports — all without human intervention.

Built with LangChain's ReAct framework and LLaMA 3.3 70B via Groq.

---

## How it works

The agent uses a ReAct loop — Reason + Act — at every step:

    Thought    → decide what to do next
    Action     → call a tool (search, scrape, calculate, save)
    Observation → read the result
    Repeat     → until the task is complete

Example run:

    Task: "Research the current state of open source LLMs in 2026"

    Thought: I should search for recent information
    Action:  web_search("open source LLMs 2026")
    Thought: Let me read this article in full
    Action:  scrape_page("https://...")
    Thought: I have enough, let me save a report
    Action:  save_report("# Open Source LLMs...")
    Final Answer: Here are the key findings...

The CLI is built with `argparse` and supports the following flags:

    python agent.py                          # run the default research task
    python agent.py "your query"             # run a custom research task
    python agent.py --quick "query"          # quick mode (10 iterations max)
    python agent.py --deep "query"           # deep mode (30 iterations max)
    python agent.py --name "Title" "query"   # custom report name
    python agent.py --list-reports           # list saved reports
    python agent.py --stats "query"          # show tool call statistics
    python agent.py --search <keyword>       # search report contents
    python agent.py --prompt <file> "query"  # use a custom prompt file
    python agent.py -i                       # interactive REPL mode

---

## Tools

    web_search     Search the web via Tavily API (cached 5 min, 50 entries)
    scrape_pages   Fetch multiple pages concurrently (comma-separated, up to 3)
    scrape_page    Fetch and clean full page content from a single URL
    save_report    Persist findings as a markdown file in reports/
    calculate      Evaluate mathematical expressions safely

---

## Features

- **Web search cache** — Repeated queries return instantly (5 min TTL, 50 entry LRU)
- **Concurrent scraping** — `scrape_pages` fetches up to 3 URLs in parallel
- **SSRF protection** — Scraper blocks private, loopback, and link-local IPs
- **Rate-limit retry** — Automatic exponential backoff (10s → 20s → 30s) on 429 errors
- **Tool call stats** — `--stats` flag shows per-tool usage after each run
- **Report search** — `--search <keyword>` greps all saved reports (case-insensitive)
- **Custom prompts** — `--prompt <file>` overrides the system prompt
- **Quick / Deep modes** — `--quick` (10 iter) for fast answers, `--deep` (30 iter) for thorough research
- **Interactive REPL** — `-i` mode with conversation history (last 5 turns)

---

## Tech stack

    Library         Role
    LangChain       ReAct agent framework, tool orchestration, and prompt hub
    Groq            LLaMA 3.3 70B inference — fast and free
    Tavily          Web search API designed for AI agents
    BeautifulSoup   HTML parsing and content extraction
    lxml            Fast HTML/XML parser (2-3x vs html.parser)
    Streamlit       Live UI showing agent thought process
    pytest          Test suite (75+ tests)

---

## Configuration

Create a `.env` file in the project root (or copy `.env.example`):

    cp .env.example .env

| Variable         | Required | Default                     | Description                |
|------------------|----------|-----------------------------|----------------------------|
| GROQ_API_KEY     | Yes      | —                           | Groq API key               |
| TAVILY_API_KEY   | Yes      | —                           | Tavily search API key      |
| MODEL_NAME       | No       | llama-3.3-70b-versatile     | Groq model to use          |

---

## Run it locally

Prerequisites: Python 3.12+, free API keys from groq.com and tavily.com

    git clone https://github.com/hsnx999/research-agent.git
    cd research-agent
    python -m venv .venv
    source .venv/bin/activate
    pip install -r requirements.txt

Create a .env file:

    cp .env.example .env
    # then edit .env with your API keys

Run the terminal agent:

    python agent.py                          # default task
    python agent.py "your research query"    # custom task
    python agent.py --quick "query"          # quick mode (10 iterations)
    python agent.py --deep "query"           # deep mode (30 iterations)
    python agent.py --name "Title" "query"   # custom report name
    python agent.py --list-reports           # list saved reports
    python agent.py --stats "query"          # show tool call statistics
    python agent.py --search <keyword>       # search report contents
    python agent.py --prompt <file> "query"  # use a custom prompt file
    python agent.py -i                       # interactive REPL mode

Run the Streamlit UI:

    streamlit run app.py

---

## Run with Docker

    docker compose up cli              # terminal agent
    docker compose up ui               # Streamlit UI

Or with Podman:

    podman-compose up cli
    podman-compose up ui

---

## Run tests

    source .venv/bin/activate
    pytest -v

---

## Project structure

    research-agent/
    ├── agent.py               Terminal entry point with live thought printing
    ├── app.py                 Streamlit UI with streaming thought process
    ├── Dockerfile             Container image (python:3.12-slim)
    ├── docker-compose.yml     Multi-service orchestration (cli + ui)
    ├── .dockerignore          Docker build ignore rules
    ├── .env.example           Template for required API keys
    ├── pyproject.toml         Project metadata, pytest config, CLI entry stub
    ├── requirements.txt       Python dependencies
    ├── src/
    │   ├── __init__.py        Package init
    │   ├── agent_builder.py   Shared agent builder (LLM, prompt, executor)
    │   ├── tools.py           All agent tools — search, scrape, save, calculate
    │   └── prompts.py         Agent system prompt and behaviour rules
    ├── reports/               Saved research reports (git-ignored)
    └── tests/
        ├── conftest.py        Shared fixtures and test configuration
        ├── test_agent.py      CLI, validation, callbacks, stats, retry tests
        ├── test_app.py        Streamlit UI tests
        └── test_tools.py      Tool unit tests (75+ total)

---

