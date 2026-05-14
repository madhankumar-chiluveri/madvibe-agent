"""MadVibe reminders & habits tools."""

from __future__ import annotations

import json
import logging

from langchain_core.tools import tool

from agent.convex_client import convex, ConvexError

logger = logging.getLogger(__name__)


def _ok(data: object) -> str:
    return json.dumps(data, indent=2, default=str)


def _err(e: ConvexError) -> str:
    return f"Error ({e.status}): {e.detail}"


@tool
async def list_reminders(workspace_id: str) -> str:
    """List all upcoming and scheduled reminders in the workspace."""
    try:
        data = await convex.query(
            "reminders:listByWorkspace",
            {"workspaceId": workspace_id},
        )
        return _ok(data)
    except ConvexError as e:
        return _err(e)


@tool
async def list_habits(user_id: str) -> str:
    """List the user's active habits and their current streaks."""
    try:
        data = await convex.query(
            "habits:listHabits",
            {"userId": user_id},
        )
        return _ok(data)
    except ConvexError as e:
        return _err(e)
