# agent.py

import os
from dotenv import load_dotenv
load_dotenv()

from langchain import hub
from langchain_groq import ChatGroq
from langchain.agents import create_react_agent, AgentExecutor
from langchain.prompts import PromptTemplate
from langchain_core.callbacks import BaseCallbackHandler

from src.tools import TOOLS
from src.prompts import SYSTEM_PROMPT


# ── Callback handler — prints agent thoughts live ──────────────────────────
class LiveThoughtHandler(BaseCallbackHandler):
    """
    Intercepts the agent's internal reasoning and prints it to the terminal
    as it happens. This makes the agent's thought process transparent —
    critical for debugging and impressive in demos.
    """
    def on_agent_action(self, action, **kwargs):
        print(f"\n🔧 Tool: {action.tool}")
        print(f"📥 Input: {action.tool_input}")

    def on_tool_end(self, output, **kwargs):
        preview = str(output)[:200]
        print(f"📤 Result: {preview}{'...' if len(str(output)) > 200 else ''}")

    def on_agent_finish(self, finish, **kwargs):
        print("\n✅ Agent finished")


def build_agent() -> AgentExecutor:
    """
    Assemble the agent: LLM + tools + prompt + executor.

    AgentExecutor is the runtime that:
    - Feeds the LLM the current state
    - Parses which tool to call
    - Calls the tool
    - Feeds the result back to the LLM
    - Repeats until the LLM says "Final Answer"
    """
    llm = ChatGroq(
        model="llama-3.3-70b-versatile",  # much better at following ReAct format
        temperature=0.0,
        max_tokens=4096,
    )

    # ReAct prompt format — {tools}, {tool_names}, {input}, {agent_scratchpad}
    # are required placeholders that LangChain fills in automatically
    prompt = hub.pull("hwchase17/react")

    agent = create_react_agent(llm=llm, tools=TOOLS, prompt=prompt)

    executor = AgentExecutor(
        agent=agent,
        tools=TOOLS,
        verbose=False,           # we use our own callback instead
        max_iterations=15,       # safety cap — stops runaway agents
        handle_parsing_errors=True,  # recover from malformed LLM output
        callbacks=[LiveThoughtHandler()],
    )
    return executor


def run(task: str) -> str:
    """Run a task through the agent and return the final answer."""
    executor = build_agent()
    result = executor.invoke({"input": task})
    return result["output"]


if __name__ == "__main__":
    task = "Search for the latest developments in AI agents and summarize the top 3 findings. Save a report of your findings."
    print(f"Task: {task}\n")
    print("=" * 55)
    answer = run(task)
    print("\n" + "=" * 55)
    print("Final Answer:")
    print(answer)