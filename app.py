# Run with: streamlit run app.py

import streamlit as st
from dotenv import load_dotenv
load_dotenv()

import os
import time
from pathlib import Path
from langchain_groq import ChatGroq
from langchain.agents import create_react_agent, AgentExecutor
from langchain import hub
from langchain_core.callbacks import BaseCallbackHandler

from src.tools import TOOLS


# ── Streamlit callback — streams thoughts into the UI ──────────────────────
class StreamlitCallbackHandler(BaseCallbackHandler):
    """
    Same idea as LiveThoughtHandler but writes to Streamlit
    containers instead of the terminal.
    """
    def __init__(self, thought_container):
        self.container  = thought_container
        self.thoughts   = []

    def on_agent_action(self, action, **kwargs):
        self.thoughts.append(
            f"🔧 **Tool:** `{action.tool}`\n\n"
            f"📥 **Input:** {action.tool_input}\n"
        )
        self.container.markdown("\n---\n".join(self.thoughts))

    def on_tool_end(self, output, **kwargs):
        preview = str(output)[:300]
        self.thoughts.append(
            f"📤 **Result:** {preview}{'...' if len(str(output)) > 300 else ''}\n"
        )
        self.container.markdown("\n---\n".join(self.thoughts))

    def on_agent_finish(self, finish, **kwargs):
        self.thoughts.append("✅ **Agent finished**")
        self.container.markdown("\n---\n".join(self.thoughts))


def build_agent(callback_handler) -> AgentExecutor:
    llm = ChatGroq(
        model="llama-3.3-70b-versatile",
        temperature=0.0,
        max_tokens=4096,
    )
    prompt   = hub.pull("hwchase17/react")
    agent    = create_react_agent(llm=llm, tools=TOOLS, prompt=prompt)
    executor = AgentExecutor(
        agent=agent,
        tools=TOOLS,
        verbose=False,
        max_iterations=15,
        handle_parsing_errors=True,
        callbacks=[callback_handler],
    )
    return executor


# ── Page config ────────────────────────────────────────────────────────────
st.set_page_config(page_title="Research Agent", page_icon="🤖")
st.title("🤖 Research Agent")
st.caption("Autonomous AI agent — searches, reads, reasons, and saves reports")

# ── Sidebar — example tasks ────────────────────────────────────────────────
with st.sidebar:
    st.header("Example tasks")
    examples = [
        "Research the latest developments in AI agents and summarize the top 3 findings",
        "Compare LangChain and LlamaIndex for building RAG applications",
        "Research the current state of open source LLMs in 2026",
        "Find the top 5 Python libraries for machine learning in 2026",
    ]
    for example in examples:
        if st.button(example, use_container_width=True):
            st.session_state.task = example

    st.divider()
    st.header("Saved reports")
    reports = sorted(Path("reports").glob("*.md"), reverse=True)
    if reports:
        for r in reports[:5]:
            with st.expander(r.name):
                st.markdown(r.read_text())
    else:
        st.caption("No reports saved yet.")


# ── Main area ──────────────────────────────────────────────────────────────
task = st.text_area(
    "Research task:",
    value=st.session_state.get("task", ""),
    placeholder="What do you want to research?",
    height=100,
)

if st.button("Run agent", type="primary", disabled=not task.strip()):
    st.divider()

    # Thought process expander
    with st.expander("Agent thought process", expanded=True):
        thought_container = st.empty()

    handler  = StreamlitCallbackHandler(thought_container)
    executor = build_agent(handler)

    with st.spinner("Agent is working..."):
        result = executor.invoke({"input": task})

    st.divider()
    st.subheader("Final answer")
    st.markdown(result["output"])