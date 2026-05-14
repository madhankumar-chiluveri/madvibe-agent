"""MadVibe ledger (finance) tools — read-only summaries."""

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
async def list_finance_accounts(user_id: str) -> str:
    """List all finance accounts (bank, savings, credit) for the user."""
    try:
        data = await convex.query(
            "ledger:listAccounts",
            {"userId": user_id},
        )
        return _ok(data)
    except ConvexError as e:
        return _err(e)


@tool
async def get_recent_transactions(user_id: str, limit: int = 20) -> str:
    """Get the most recent financial transactions for the user."""
    try:
        data = await convex.query(
            "ledger:getRecentTransactions",
            {"userId": user_id, "limit": limit},
        )
        return _ok(data)
    except ConvexError as e:
        return _err(e)
