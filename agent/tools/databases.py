"""MadVibe database tools — lets Maddy read and write workspace databases."""

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
async def get_database_by_page(page_id: str) -> str:
    """Get the database schema (columns/properties) attached to a database page.
    Use this first to understand what columns exist before reading rows."""
    try:
        data = await convex.query("databases:getByPage", {"pageId": page_id})
        if not data:
            return "No database found for this page."
        return _ok(data)
    except ConvexError as e:
        return _err(e)


@tool
async def list_database_rows(database_id: str) -> str:
    """List all rows in a database. Each row has a 'data' field mapping
    column property IDs to values. Use get_database_by_page first to
    understand what the property IDs mean."""
    try:
        data = await convex.query("databases:listRows", {"databaseId": database_id})
        if not data:
            return "No rows found in this database."
        # Return up to 100 rows to avoid token overflow
        rows = data[:100]
        summary = f"Total rows: {len(data)} (showing {len(rows)})\n\n"
        return summary + _ok(rows)
    except ConvexError as e:
        return _err(e)


@tool
async def get_database_with_rows(page_id: str) -> str:
    """Get a database and ALL its rows in one call, with column names resolved.
    This is the most useful tool for reading a database — pass the page ID
    of a database page (type='database') from list_pages.
    Returns a human-readable table with column names and values."""
    try:
        # Step 1: Get the database schema
        db = await convex.query("databases:getByPage", {"pageId": page_id})
        if not db:
            return "No database found for this page."

        database_id = db.get("_id")
        properties: list[dict] = db.get("properties", [])
        prop_map = {p["id"]: p.get("name", p["id"]) for p in properties}

        # Step 2: Get all rows
        rows = await convex.query("databases:listRows", {"databaseId": database_id})
        if not rows:
            return f"Database '{db.get('name', 'Unnamed')}' has no rows yet."

        # Step 3: Build a readable table
        output_rows = []
        for row in rows[:100]:
            row_data = row.get("data", {})
            readable = {prop_map.get(k, k): v for k, v in row_data.items() if v not in (None, "", [])}
            if readable:
                output_rows.append(readable)

        result = {
            "database_name": db.get("name", "Unnamed"),
            "database_id": database_id,
            "columns": [p.get("name", p["id"]) for p in properties],
            "total_rows": len(rows),
            "rows": output_rows[:100],
        }
        return _ok(result)
    except ConvexError as e:
        return _err(e)
