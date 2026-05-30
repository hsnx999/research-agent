import argparse
import re
import sys
import threading
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv
load_dotenv()

from langchain_core.callbacks import BaseCallbackHandler

from src.agent_builder import build_agent

_tool_counts = {}
_tool_stats_lock = threading.Lock()


class LiveThoughtHandler(BaseCallbackHandler):
    def on_agent_action(self, action, **kwargs):
        try:
            tool_name = action.tool
            print(f"\n🔧 Tool: {tool_name}")
            print(f"📥 Input: {action.tool_input}")
            with _tool_stats_lock:
                _tool_counts[tool_name] = _tool_counts.get(tool_name, 0) + 1
        except Exception as e:
            print(f"⚠️  Warning: on_agent_action callback failed: {e}", file=sys.stderr)

    def on_tool_end(self, output, **kwargs):
        try:
            preview = str(output)[:200]
            print(f"📤 Result: {preview}{'...' if len(str(output)) > 200 else ''}")
        except Exception as e:
            print(f"⚠️  Warning: on_tool_end callback failed: {e}", file=sys.stderr)

    def on_agent_finish(self, finish, **kwargs):
        try:
            print("\n✅ Agent finished")
        except Exception as e:
            print(f"⚠️  Warning: on_agent_finish callback failed: {e}", file=sys.stderr)


def _spin(stop_event, message="Thinking"):
    """Print a spinner animation until stop_event is set."""
    chars = "⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏"
    i = 0
    while not stop_event.is_set():
        sys.stdout.write(f"\r{chars[i % len(chars)]} {message}...")
        sys.stdout.flush()
        i += 1
        stop_event.wait(0.1)
    sys.stdout.write("\r" + " " * 40 + "\r")
    sys.stdout.flush()


def run(task: str, instructions="", report_name="", max_iterations=15, system_prompt=None) -> str:
    stripped = task.strip()
    if not stripped:
        raise ValueError("Task cannot be empty.")
    if len(stripped) > 10000:
        raise ValueError("Task is too long (max 10,000 characters).")

    with _tool_stats_lock:
        _tool_counts.clear()

    stop_event = threading.Event()
    spinner = threading.Thread(target=_spin, args=(stop_event,), daemon=True)
    spinner.start()

    try:
        executor = build_agent(
            callbacks=[LiveThoughtHandler()],
            instructions=instructions,
            report_name=report_name,
            max_iterations=max_iterations,
            system_prompt=system_prompt,
        )
        result = _invoke_with_retry(executor, {"input": stripped})
        return result["output"]
    finally:
        stop_event.set()
        spinner.join()


def list_reports() -> None:
    """List all markdown reports in the reports/ directory."""
    reports_dir = Path("reports")
    if not reports_dir.is_dir():
        print("No reports directory found.")
        return

    files = list(reports_dir.glob("*.md"))
    if not files:
        print("No reports found.")
        return

    files.sort(key=lambda f: f.stat().st_mtime, reverse=True)

    header = f"{'Name':<50} {'Size':>8} {'Date':<20}"
    print(header)
    print("-" * len(header))
    for f in files:
        stat = f.stat()
        size = stat.st_size
        mtime = datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M")
        print(f"{f.name:<50} {size:>8} {mtime:<20}")
    print(f"\nTotal: {len(files)} report(s)")


def print_stats() -> None:
    """Print tool call statistics."""
    with _tool_stats_lock:
        if not _tool_counts:
            print("\n📊 No tool calls were made.")
            return
        print(f"\n{'📊 Tool Call Stats':=^50}")
        for tool, count in sorted(_tool_counts.items()):
            print(f"  {tool:<25} {count:>3} call(s)")
        print(f"  {'─' * 33}")
        print(f"  {'Total':<25} {sum(_tool_counts.values()):>3} call(s)")


def search_reports(keyword: str) -> None:
    """Search report contents for a keyword (case-insensitive)."""
    reports_dir = Path("reports")
    if not reports_dir.is_dir():
        print("No reports directory found.")
        return

    files = sorted(reports_dir.glob("*.md"), key=lambda f: f.stat().st_mtime, reverse=True)
    if not files:
        print("No reports found.")
        return

    matches = []
    for f in files:
        text = f.read_text(encoding="utf-8")
        for i, line in enumerate(text.splitlines(), 1):
            if keyword.lower() in line.lower():
                matches.append((f.name, i, line.strip()))

    if not matches:
        print(f'No matches found for "{keyword}".')
        return

    print(f'\nSearch results for "{keyword}":\n')
    for name, lineno, line in matches:
        display = line[:200]
        print(f"  {name}:{lineno}: {display}")
    unique_files = len(set(m[0] for m in matches))
    print(f"\n{len(matches)} match(es) in {unique_files} file(s)")


def _invoke_with_retry(executor, input_data, max_retries=3):
    """Invoke executor with exponential backoff on rate limit errors."""
    import time
    for attempt in range(max_retries):
        try:
            return executor.invoke(input_data)
        except Exception as e:
            if "rate limit" in str(e).lower() or "429" in str(e):
                if attempt < max_retries - 1:
                    wait = min(2 ** attempt * 10, 30)
                    print(f"\n⏳ Rate limited. Retrying in {wait}s...")
                    time.sleep(wait)
                    continue
            raise
    raise RuntimeError("Max retries exceeded")


def run_interactive():
    """Interactive REPL loop with in-memory conversation history."""
    print("Research Agent — interactive mode. Type 'exit' or 'quit' to stop.")
    history = []  # list of (role, message) tuples

    while True:
        try:
            task = input("\nResearch task: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nGoodbye!")
            break

        if not task:
            continue
        if task.lower() in ("exit", "quit"):
            print("Goodbye!")
            break

        # Build context from recent history (last 5 exchanges)
        context = ""
        if history:
            context = "Previous conversation:\n"
            for role, msg in history[-5:]:
                context += f"{role}: {msg}\n"
            context += "\n"

        full_task = context + task

        print("\n" + "=" * 55)
        try:
            answer = run(full_task)
            print("=" * 55)
            print("Final Answer:")
            print(answer)
            history.append(("User", task))
            history.append(("Assistant", answer[:500]))
        except Exception as e:
            print(f"\nError: {e}")


def run_cli() -> None:
    parser = argparse.ArgumentParser(
        description="Research Agent — autonomous web research"
    )
    parser.add_argument(
        "task",
        nargs="?",
        help="Research task to execute",
    )
    parser.add_argument(
        "--list-reports",
        action="store_true",
        help="List saved reports",
    )
    parser.add_argument(
        "--quick",
        action="store_true",
        help="Quick mode — 1 search, 1 scrape max",
    )
    parser.add_argument(
        "--deep",
        action="store_true",
        help="Deep mode — 5+ searches, 3+ scrapes",
    )
    parser.add_argument(
        "-i",
        "--interactive",
        action="store_true",
        help="Interactive multi-turn mode",
    )
    parser.add_argument(
        "--name",
        type=str,
        help="Custom name for the saved report",
    )
    parser.add_argument(
        "--stats",
        action="store_true",
        help="Show tool call statistics after execution",
    )
    parser.add_argument(
        "--search",
        type=str,
        help="Search reports for a keyword",
    )
    parser.add_argument(
        "--prompt",
        type=str,
        help="Path to a custom prompt file (replaces SYSTEM_PROMPT)",
    )
    args = parser.parse_args()

    if args.list_reports:
        list_reports()
        return

    if args.search:
        search_reports(args.search)
        return

    if args.interactive:
        # Interactive mode ignores --name since it spans multiple queries
        run_interactive()
        return

    # Determine depth instructions
    instructions = ""
    if args.quick:
        instructions = "Be brief — limit to 1 search and 1 scrape maximum. Keep responses concise."
    elif args.deep:
        instructions = "Be thorough — search at least 5 times and scrape at least 3 pages. Take your time to get comprehensive coverage."

    # Determine max iterations based on depth
    max_iter = 10 if args.quick else 30 if args.deep else 15

    # Slugify report name
    report_name = ""
    if args.name:
        report_name = re.sub(r'[^a-z0-9]+', '-', args.name.lower()).strip('-')

    task = args.task or "Search for the latest developments in AI agents and summarize the top 3 findings. Save a report of your findings."
    print(f"Task: {task}\n")
    if instructions:
        print(f"Mode: {'Quick' if args.quick else 'Deep'}")
    if report_name:
        print(f"Report name: {report_name}")
    print("=" * 55)

    # Load custom prompt if specified
    system_prompt = None
    if args.prompt:
        prompt_path = Path(args.prompt)
        if prompt_path.is_file():
            system_prompt = prompt_path.read_text(encoding="utf-8")
            print(f"📝 Using custom prompt from {args.prompt}")
        else:
            print(f"⚠️  Custom prompt file not found: {args.prompt}. Using default.", file=sys.stderr)

    try:
        executor = build_agent(
            callbacks=[LiveThoughtHandler()],
            instructions=instructions,
            report_name=report_name,
            max_iterations=max_iter,
            system_prompt=system_prompt,
        )

        result = _invoke_with_retry(executor, {"input": task})
        print("\n" + "=" * 55)
        print("Final Answer:")
        print(result["output"])
        if args.stats:
            print_stats()
    except Exception as e:
        print(f"\nError: {e}")
        if args.stats:
            print_stats()
        sys.exit(1)


if __name__ == "__main__":
    run_cli()
