"""Typed AgentState for the MadVibe LangGraph agent."""

from __future__ import annotations

from typing import Annotated, Any, Sequence, TypedDict

from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages


class AgentState(TypedDict):
    """Single source of truth passed through every graph node."""

    # LangGraph message list (deduplicated via add_messages reducer)
    messages: Annotated[Sequence[BaseMessage], add_messages]

    # User / workspace context injected by the API layer
    workspace_id: str
    user_id: str
    conversation_id: str
    model: str  # e.g. "meta-llama/llama-3.3-70b-instruct:free"

    # Accumulated tool call info for the response
    tools_used: list[str]
