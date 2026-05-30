import argparse
import sys
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv
load_dotenv()

from langchain_core.callbacks import BaseCallbackHandler

from src.agent_builder import build_agent


class LiveThoughtHandler(BaseCallbackHandler):
    def on_agent_action(self, action, **kwargs):
        try:
            print(f"\n🔧 Tool: {action.tool}")
            print(f"📥 Input: {action.tool_input}")
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


def run(task: str) -> str:
    stripped = task.strip()
    if not stripped:
        raise ValueError("Task cannot be empty.")
    if len(stripped) > 10000:
        raise ValueError("Task is too long (max 10,000 characters).")
    executor = build_agent(callbacks=[LiveThoughtHandler()])
    result = executor.invoke({"input": stripped})
    return result["output"]


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
        description="Research Agent — single-task execution or interactive multi-turn mode"
    )
    parser.add_argument(
        "task",
        nargs="?",
        default=None,
        help="Research task to execute",
    )
    parser.add_argument(
        "--list-reports",
        action="store_true",
        help="List all saved reports",
    )
    parser.add_argument(
        "-i",
        "--interactive",
        action="store_true",
        help="Interactive multi-turn mode",
    )
    args = parser.parse_args()

    if args.interactive:
        run_interactive()
        return

    if args.list_reports:
        list_reports()
        return

    task = args.task or "Search for the latest developments in AI agents and summarize the top 3 findings. Save a report of your findings."
    print(f"Task: {task}\n")
    print("=" * 55)
    try:
        answer = run(task)
        print("\n" + "=" * 55)
        print("Final Answer:")
        print(answer)
    except Exception as e:
        print(f"\nError: {e}")
        sys.exit(1)


if __name__ == "__main__":
    run_cli()
