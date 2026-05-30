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

## Tech stack

    Library         Role
    LangChain       ReAct agent framework, tool orchestration, and prompt hub
    Groq            LLaMA 3.3 70B inference — fast and free
    Tavily          Web search API designed for AI agents
    BeautifulSoup   HTML parsing and content extraction
    Streamlit       Live UI showing agent thought process

---

## Run it locally

Prerequisites: Python 3.12+, free API keys from groq.com and tavily.com

    git clone https://github.com/hsnx999/research-agent.git
    cd research-agent
    python -m venv .venv
    source .venv/bin/activate
    pip install -r requirements.txt

Create a .env file:

    GROQ_API_KEY=your_groq_key
    TAVILY_API_KEY=your_tavily_key

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

## Project structure

    research-agent/
    ├── agent.py               Terminal entry point with live thought printing
    ├── app.py                 Streamlit UI with streaming thought process
    ├── src/
    │   ├── __init__.py        Package init
    │   ├── agent_builder.py   Shared agent builder (LLM, prompt, executor)
    │   ├── tools.py           All agent tools — search, scrape, save, calculate
    │   └── prompts.py         Agent system prompt and behaviour rules
    ├── reports/               Saved research reports (git-ignored)
    └── requirements.txt

---


