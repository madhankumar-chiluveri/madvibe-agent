"""LangGraph graph wiring for the MadVibe agent.

Graph topology:
  START → executor → END

We use a single ReAct executor node (tools + LLM loop).
This keeps complexity low while still being extensible —
add a planner or router node above executor when needed.
"""

from __future__ import annotations

from pathlib import Path

from langchain_core.messages import SystemMessage
from langgraph.prebuilt import create_react_agent

from agent.llm import get_llm
from agent.tools import ALL_TOOLS

# Load the co-located system prompt template
_PROMPT_TEMPLATE = (
    Path(__file__).parent / "nodes" / "executor" / "prompt.md"
).read_text(encoding="utf-8")


def build_graph(model: str | None = None, workspace_id: str = "", user_id: str = "", page_id: str | None = None):
    """Build and return a compiled LangGraph ReAct agent.

    We rebuild per-request only when workspace context differs.
    For production you'd cache this per (model, workspace_id).
    """
    llm = get_llm(model)
    system_prompt = _PROMPT_TEMPLATE.format(
        workspace_id=workspace_id,
        user_id=user_id,
        current_page_id=page_id or "none",
    )

    return create_react_agent(
        llm,
        ALL_TOOLS,
        prompt=SystemMessage(content=system_prompt),
    )
