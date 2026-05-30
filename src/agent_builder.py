from functools import lru_cache

from langchain import hub
from langchain.agents import create_react_agent, AgentExecutor
from langchain.prompts import PromptTemplate
from langchain_groq import ChatGroq

from src.tools import TOOLS
from src.prompts import SYSTEM_PROMPT


@lru_cache(maxsize=1)
def _get_base_prompt():
    return hub.pull("hwchase17/react")


def build_agent(callbacks=None) -> AgentExecutor:
    llm = ChatGroq(
        model="llama-3.3-70b-versatile",
        temperature=0.0,
        max_tokens=4096,
    )

    base = _get_base_prompt()
    combined = SYSTEM_PROMPT + "\n\n" + base.template
    prompt = PromptTemplate.from_template(combined)

    agent = create_react_agent(llm=llm, tools=TOOLS, prompt=prompt)

    executor = AgentExecutor(
        agent=agent,
        tools=TOOLS,
        verbose=False,
        max_iterations=15,
        handle_parsing_errors=True,
        callbacks=callbacks or [],
    )
    return executor
