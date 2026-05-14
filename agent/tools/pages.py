"""MadVibe pages tools for the LangGraph agent."""

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
async def list_pages(workspace_id: str, search: str = "") -> str:
    """List pages in the workspace. Pass search to filter by title keyword."""
    try:
        if search:
            data = await convex.query(
                "pages:search",
                {"workspaceId": workspace_id, "query": search},
            )
        else:
            data = await convex.query(
                "pages:listAll",
                {"workspaceId": workspace_id},
            )
        return _ok(data)
    except ConvexError as e:
        return _err(e)


@tool
async def get_page_content(page_id: str) -> str:
    """Get the title and content preview of a specific page by its ID."""
    try:
        data = await convex.query("maddy:getPageForMaddy", {"pageId": page_id})
        return _ok(data)
    except ConvexError as e:
        return _err(e)


def _text_to_blocknote(text: str) -> list:
    """Convert plain text into a BlockNote document array.

    The editor stores a SINGLE Convex 'blocks' row whose `content` field is a
    BlockNote document: a list of block objects with this shape:
      { id, type, props, content: [inlineNode, ...], children: [] }
    """
    import uuid

    blocknote_blocks = []
    for line in text.split("\n"):
        stripped = line.rstrip()
        inline = [{"type": "text", "text": stripped, "styles": {}}] if stripped else []
        blocknote_blocks.append({
            "id": str(uuid.uuid4()),
            "type": "paragraph",
            "props": {
                "textColor": "default",
                "backgroundColor": "default",
                "textAlignment": "left",
            },
            "content": inline,
            "children": [],
        })

    if not blocknote_blocks:
        blocknote_blocks = [{
            "id": str(uuid.uuid4()),
            "type": "paragraph",
            "props": {"textColor": "default", "backgroundColor": "default", "textAlignment": "left"},
            "content": [],
            "children": [],
        }]
    return blocknote_blocks


@tool
async def update_page(page_id: str, content: str, title: str = "") -> str:
    """Overwrite the content of an existing page. Provide the page_id and the
    new content as plain text (newlines become separate paragraphs).
    Optionally supply a new title to rename the page."""
    try:
        blocknote_doc = _text_to_blocknote(content)
        # Store as one DB block of type 'document' — same format as the editor
        await convex.mutation("blocks:replaceAll", {
            "pageId": page_id,
            "blocks": [{
                "type": "document",
                "content": blocknote_doc,
                "sortOrder": 1000,
                "properties": {},
            }],
        })
        if title:
            await convex.mutation("pages:update", {"id": page_id, "title": title})
        return f"Page updated successfully ({len(blocknote_doc)} paragraphs written)."
    except ConvexError as e:
        return _err(e)


@tool
async def create_page(workspace_id: str, title: str, content: str = "", parent_id: str = "") -> str:
    """Create a new page in the workspace with the given title and optional content.
    Returns the new page's ID."""
    try:
        args: dict = {"workspaceId": workspace_id, "title": title}
        if parent_id:
            args["parentId"] = parent_id
        page_id = await convex.mutation("pages:create", args)
        if content:
            blocknote_doc = _text_to_blocknote(content)
            await convex.mutation("blocks:replaceAll", {
                "pageId": page_id,
                "blocks": [{
                    "type": "document",
                    "content": blocknote_doc,
                    "sortOrder": 1000,
                    "properties": {},
                }],
            })
        return f"Created page '{title}' with ID: {page_id}"
    except ConvexError as e:
        return _err(e)




@tool
async def semantic_search(workspace_id: str, query: str) -> str:
    """Semantically search the knowledge base using vector similarity.
    Returns the most relevant pages for the given query text."""
    try:
        import os
        gemini_key = os.getenv("GEMINI_API_KEY", "")
        data = await convex.action(
            "maddy:semanticSearch",
            {
                "workspaceId": workspace_id,
                "query": query,
                "geminiApiKey": gemini_key,
                "limit": 5,
            },
        )
        return _ok(data)
    except ConvexError as e:
        return _err(e)
