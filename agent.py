import sys
from dotenv import load_dotenv
load_dotenv()

from langchain_core.callbacks import BaseCallbackHandler

from src.agent_builder import build_agent


class LiveThoughtHandler(BaseCallbackHandler):
    def on_agent_action(self, action, **kwargs):
        print(f"\n🔧 Tool: {action.tool}")
        print(f"📥 Input: {action.tool_input}")

    def on_tool_end(self, output, **kwargs):
        preview = str(output)[:200]
        print(f"📤 Result: {preview}{'...' if len(str(output)) > 200 else ''}")

    def on_agent_finish(self, finish, **kwargs):
        print("\n✅ Agent finished")


def run(task: str) -> str:
    executor = build_agent(callbacks=[LiveThoughtHandler()])
    try:
        result = executor.invoke({"input": task})
        return result["output"]
    except Exception as e:
        return f"Agent execution failed: {e}"


if __name__ == "__main__":
    task = "Search for the latest developments in AI agents and summarize the top 3 findings. Save a report of your findings."
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
