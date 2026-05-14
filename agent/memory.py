"""In-memory conversation memory with a Redis-ready interface."""

from __future__ import annotations

import os
from typing import Any

MAX_HISTORY = int(os.getenv("MAX_HISTORY", "30"))


class ConversationMemory:
    """Simple dict-backed memory store keyed by conversation_id."""

    def __init__(self, max_history: int = MAX_HISTORY) -> None:
        self._store: dict[str, list[dict[str, Any]]] = {}
        self._max = max_history

    def get(self, conversation_id: str) -> list[dict[str, Any]]:
        return list(self._store.get(conversation_id, []))

    def append(self, conversation_id: str, message: dict[str, Any]) -> None:
        history = self._store.setdefault(conversation_id, [])
        history.append(message)
        self._store[conversation_id] = history[-self._max :]

    def clear(self, conversation_id: str) -> None:
        self._store.pop(conversation_id, None)
