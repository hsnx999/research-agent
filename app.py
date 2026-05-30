import streamlit as st
from dotenv import load_dotenv
load_dotenv()

from pathlib import Path
from langchain_core.callbacks import BaseCallbackHandler

from src.agent_builder import build_agent

REPORTS_DIR = Path(__file__).parent / "reports"


class StreamlitCallbackHandler(BaseCallbackHandler):
    def __init__(self, thought_container):
        self.container = thought_container
        self.thoughts = []

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


st.set_page_config(page_title="Research Agent", page_icon="🤖")
st.title("🤖 Research Agent")
st.caption("Autonomous AI agent — searches, reads, reasons, and saves reports")

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
    if REPORTS_DIR.exists():
        reports = sorted(REPORTS_DIR.glob("*.md"), key=lambda p: p.stat().st_mtime, reverse=True)
        if reports:
            for r in reports[:5]:
                with st.expander(r.name):
                    try:
                        MAX_REPORT_BYTES = 10 * 1024 * 1024
                        size = r.stat().st_size
                        if size > MAX_REPORT_BYTES:
                            st.caption(
                                f"Report too large ({size / 1024 / 1024:.1f} MB) to display."
                            )
                        else:
                            st.markdown(r.read_text(encoding="utf-8"))
                    except Exception:
                        st.caption("Could not read report.")
        else:
            st.caption("No reports saved yet.")
    else:
        st.caption("No reports saved yet.")

task = st.text_area(
    "Research task:",
    value=st.session_state.get("task", ""),
    placeholder="What do you want to research?",
    height=100,
)

if st.button("Run agent", type="primary", disabled=not task.strip()):
    output_placeholder = st.empty()

    with output_placeholder.container():
        st.divider()

        with st.expander("Agent thought process", expanded=True):
            thought_container = st.empty()

        handler = StreamlitCallbackHandler(thought_container)

        with st.spinner("Agent is working..."):
            try:
                executor = build_agent(callbacks=[handler])
                result = executor.invoke({"input": task})
                st.divider()
                st.subheader("Final answer")
                st.markdown(result["output"])
            except Exception as e:
                thought_container.markdown("")  # clear partial thoughts
                st.error(f"Agent execution failed: {e}")
