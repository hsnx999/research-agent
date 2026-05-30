from functools import lru_cache

from langchain import hub
from langchain.agents import create_react_agent, AgentExecutor
from langchain.prompts import PromptTemplate
from langchain_groq import ChatGroq

from src.tools import TOOLS
from src.prompts import SYSTEM_PROMPT

_FALLBACK_PROMPT = """Answer the following questions as best you can. You have access to the following tools:

{tools}

Use the following format:

Question: the input question you must answer
Thought: you should always think about what to do
Action: the action to take, should be one of [{tool_names}]
Action Input: the input to the action
Observation: the result of the action
... (this Thought/Action/Action Input/Observation can repeat N times)
Thought: I now know the final answer
Final Answer: the final answer to the original input question

Begin!

Question: {input}
{agent_scratchpad}"""


@lru_cache(maxsize=1)
def _get_base_prompt():
    try:
        return hub.pull("hwchase17/react")
    except Exception:
        return PromptTemplate.from_template(_FALLBACK_PROMPT)


def build_agent(callbacks=None) -> AgentExecutor:
    try:
        llm = ChatGroq(
            model="llama-3.3-70b-versatile",
            temperature=0.0,
            max_tokens=4096,
        )
    except Exception as e:
        raise RuntimeError(
            f"Failed to initialise LLM. Check your GROQ_API_KEY is set and valid.\n{e}"
        ) from e

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
