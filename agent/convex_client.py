"""Async HTTP client for Convex HTTP API.

Convex exposes every query/mutation/action as:
  POST /api/query      → { path, args } → { value }
  POST /api/mutation   → { path, args } → { value }
  POST /api/action     → { path, args } → { value }

Auth: "Authorization: Convex <CONVEX_DEPLOY_KEY>"
The deploy key bypasses user auth and runs with full access.
"""

from __future__ import annotations

import logging
import os
from typing import Any

import httpx
from dotenv import load_dotenv
from contextvars import ContextVar

load_dotenv()
logger = logging.getLogger(__name__)

CONVEX_URL = os.getenv("CONVEX_URL", "").rstrip("/")
CONVEX_DEPLOY_KEY = os.getenv("CONVEX_DEPLOY_KEY", "")

_HEADERS = {
    "Content-Type": "application/json",
    "Authorization": f"Convex {CONVEX_DEPLOY_KEY}",
}

convex_token_var: ContextVar[str | None] = ContextVar("convex_token", default=None)


class ConvexError(Exception):
    def __init__(self, status: int, detail: str) -> None:
        self.status = status
        self.detail = detail
        super().__init__(f"Convex error {status}: {detail}")


class ConvexClient:
    """Thin async wrapper around Convex HTTP API."""

    def __init__(self, base_url: str = CONVEX_URL) -> None:
        self.base_url = base_url

    async def _post(self, endpoint: str, path: str, args: dict[str, Any]) -> Any:
        url = f"{self.base_url}/{endpoint}"
        payload = {"path": path, "args": args, "format": "json"}
        logger.info("Convex %s %s", endpoint.upper(), path)
        # Always use the deploy key — it has full server-side access.
        # The user token is NOT needed here; the agent acts on behalf of the workspace.
        try:
            async with httpx.AsyncClient(timeout=20.0) as client:
                r = await client.post(url, json=payload, headers=_HEADERS)
                r.raise_for_status()
                data = r.json()
                return data.get("value", data)
        except httpx.HTTPStatusError as exc:
            raise ConvexError(exc.response.status_code, exc.response.text[:300]) from exc
        except Exception as exc:
            raise ConvexError(0, str(exc)) from exc

    async def query(self, path: str, args: dict[str, Any] | None = None) -> Any:
        return await self._post("api/query", path, args or {})

    async def mutation(self, path: str, args: dict[str, Any] | None = None) -> Any:
        return await self._post("api/mutation", path, args or {})

    async def action(self, path: str, args: dict[str, Any] | None = None) -> Any:
        return await self._post("api/action", path, args or {})


# Singleton used by all tool modules
convex = ConvexClient()
