"""Async HTTP client for Convex HTTP API.

Convex exposes every query/mutation/action as:
  POST /api/query      → { path, args } → { value }
  POST /api/mutation   → { path, args } → { value }
  POST /api/action     → { path, args } → { value }

Auth strategy:
  - If a user JWT (convex_token) is available in the request context, use it.
    This gives the Convex function a real user identity so getAuthUserId() works.
  - Fall back to the deploy key only when no user token is available.
"""

from __future__ import annotations

import logging
import os
from contextvars import ContextVar
from typing import Any

import httpx
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger(__name__)

CONVEX_URL = os.getenv("CONVEX_URL", "").rstrip("/")
CONVEX_DEPLOY_KEY = os.getenv("CONVEX_DEPLOY_KEY", "")

# Per-request user JWT token — set by main.py from the incoming request body
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

    def _build_headers(self) -> dict[str, str]:
        """Return auth headers.

        Prefer the user JWT (gives Convex functions a real getAuthUserId),
        fall back to the deploy key for system-level operations.
        """
        user_token = convex_token_var.get()
        if user_token:
            logger.debug("Convex: using user JWT token for auth")
            return {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {user_token}",
            }

        logger.debug("Convex: using deploy key for auth (no user token in context)")
        return {
            "Content-Type": "application/json",
            "Authorization": f"Convex {CONVEX_DEPLOY_KEY}",
        }

    async def _post(self, endpoint: str, path: str, args: dict[str, Any]) -> Any:
        url = f"{self.base_url}/{endpoint}"
        payload = {"path": path, "args": args, "format": "json"}
        headers = self._build_headers()
        logger.info("Convex %s %s (auth=%s)", endpoint.upper(), path,
                    "jwt" if "Bearer" in headers.get("Authorization", "") else "deploy_key")
        try:
            async with httpx.AsyncClient(timeout=20.0) as client:
                r = await client.post(url, json=payload, headers=headers)
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
