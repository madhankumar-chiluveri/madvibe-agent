"""MadVibe AI Agent - FastAPI service powered by LangGraph + OpenRouter."""

from __future__ import annotations

import logging
import os
import uuid
from typing import Any

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Security
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from langchain_core.messages import AIMessage, HumanMessage
from pydantic import BaseModel

from agent.graph import build_graph
from agent.llm import DEFAULT_MODEL, get_model_candidates
from agent.memory import ConversationMemory
from agent.convex_client import convex_token_var

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

AGENT_API_KEY = os.getenv("AGENT_API_KEY", "")
CORS_ORIGINS = [
    origin.strip()
    for origin in os.getenv("CORS_ORIGINS", "http://localhost:3000").split(",")
    if origin.strip()
]

MODEL_RETRY_STATUS_CODES = {400, 402, 404, 408, 409, 429, 500, 502, 503, 504}
MODEL_RETRY_MARKERS = (
    "temporarily rate-limited",
    "rate limit",
    "rate-limited",
    "no endpoints",
    "model not found",
    "provider returned error",
    "upstream",
    "unsupported parameter",
)

app = FastAPI(
    title="MadVibe Agent",
    description="Maddy AI powered by LangGraph ReAct + OpenRouter",
    version="1.0.0",
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

security = HTTPBearer()
memory = ConversationMemory()


@app.get("/health")
async def health() -> dict:
    """Health-check endpoint used by Docker and Railway."""
    return {"status": "ok"}


def verify_api_key(
    credentials: HTTPAuthorizationCredentials = Security(security),
) -> str:
    if credentials.credentials != AGENT_API_KEY:
        raise HTTPException(status_code=401, detail="Invalid API key")
    return credentials.credentials


class ChatMessage(BaseModel):
    role: str
    content: str


class ChatRequest(BaseModel):
    messages: list[ChatMessage]
    workspace_id: str
    user_id: str
    model: str = DEFAULT_MODEL
    conversation_id: str | None = None
    convex_token: str | None = None


class ChatResponse(BaseModel):
    response: str
    conversation_id: str
    tools_used: list[str]
    model_used: str


def _collect_tools_used(messages: list[Any]) -> list[str]:
    names: list[str] = []
    for msg in messages:
        for tc in getattr(msg, "tool_calls", None) or []:
            if n := tc.get("name"):
                names.append(n)
    return list(dict.fromkeys(names))


def _openrouter_status_code(exc: Exception) -> int | None:
    status = getattr(exc, "status_code", None) or getattr(exc, "status", None)
    if isinstance(status, int):
        return status

    response = getattr(exc, "response", None)
    response_status = getattr(response, "status_code", None)
    return response_status if isinstance(response_status, int) else None


def _openrouter_retry_after(exc: Exception) -> str | None:
    response = getattr(exc, "response", None)
    headers = getattr(response, "headers", None)
    if headers:
        retry_after = headers.get("retry-after") or headers.get("Retry-After")
        if retry_after:
            return str(retry_after)

    body = getattr(exc, "body", None)
    if isinstance(body, dict):
        error = body.get("error")
        if isinstance(error, dict):
            metadata = error.get("metadata")
            if isinstance(metadata, dict):
                retry_after = metadata.get("retry_after_seconds") or metadata.get(
                    "retry_after_seconds_raw"
                )
                if retry_after is not None:
                    return str(int(float(retry_after)))
    return None


def _should_try_next_model(exc: Exception) -> bool:
    status = _openrouter_status_code(exc)
    if status in MODEL_RETRY_STATUS_CODES:
        return True

    text = str(exc).lower()
    return any(marker in text for marker in MODEL_RETRY_MARKERS)


async def _invoke_agent_with_model_fallback(
    *,
    messages: list[Any],
    requested_model: str,
    workspace_id: str,
    user_id: str,
) -> tuple[dict[str, Any], str]:
    candidates = get_model_candidates(requested_model)
    last_exc: Exception | None = None

    for index, candidate in enumerate(candidates):
        graph = build_graph(
            model=candidate,
            workspace_id=workspace_id,
            user_id=user_id,
        )

        try:
            result = await graph.ainvoke({"messages": messages})
            if index > 0:
                logger.info("Agent recovered with fallback model: %s", candidate)
            return result, candidate
        except Exception as exc:
            last_exc = exc
            next_model = candidates[index + 1] if index + 1 < len(candidates) else None
            if next_model and _should_try_next_model(exc):
                status = _openrouter_status_code(exc)
                retry_after = _openrouter_retry_after(exc)
                status_note = f" status={status}" if status else ""
                retry_note = f" retry_after={retry_after}s" if retry_after else ""
                logger.warning(
                    "OpenRouter model %s failed%s%s; trying fallback %s. Error: %s",
                    candidate,
                    status_note,
                    retry_note,
                    next_model,
                    exc,
                )
                continue
            raise

    raise last_exc or RuntimeError("Agent model fallback exhausted")


@app.post("/chat", response_model=ChatResponse)
async def chat(
    request: ChatRequest, _: str = Security(verify_api_key)
) -> ChatResponse:
    """Multi-turn chat with the MadVibe Maddy agent."""
    if request.convex_token:
        convex_token_var.set(request.convex_token)
        
    conversation_id = request.conversation_id or str(uuid.uuid4())
    history = memory.get(conversation_id)

    lc_messages: list[Any] = []
    new_user_messages: list[dict[str, str]] = []

    for msg in history:
        if msg["role"] == "user":
            lc_messages.append(HumanMessage(content=msg["content"]))
        elif msg["role"] == "assistant":
            lc_messages.append(AIMessage(content=msg["content"]))

    for msg in request.messages:
        if msg.role == "user":
            lc_messages.append(HumanMessage(content=msg.content))
            new_user_messages.append({"role": "user", "content": msg.content})

    try:
        result, model_used = await _invoke_agent_with_model_fallback(
            messages=lc_messages,
            requested_model=request.model,
            workspace_id=request.workspace_id,
            user_id=request.user_id,
        )
    except Exception as exc:
        logger.exception("Agent error after model fallback: %s", exc)
        status = _openrouter_status_code(exc)
        retry_after = _openrouter_retry_after(exc)
        headers = {"Retry-After": retry_after} if retry_after else None

        if status in {429, 500, 502, 503, 504}:
            raise HTTPException(
                status_code=503,
                detail="OpenRouter is rate-limiting or has no healthy upstream for the configured models. Try again shortly or choose another model.",
                headers=headers,
            ) from exc

        if status in {400, 402, 404}:
            raise HTTPException(
                status_code=502,
                detail="The selected OpenRouter model is unavailable for this key. Maddy tried its configured fallbacks but could not complete the request.",
                headers=headers,
            ) from exc

        raise HTTPException(
            status_code=500,
            detail="Agent encountered an error. Try rephrasing.",
            headers=headers,
        ) from exc

    final_messages = result.get("messages", [])
    response_text = ""
    for msg in final_messages:
        if isinstance(msg, AIMessage) and msg.content:
            response_text = msg.content

    if not response_text:
        response_text = "I wasn't able to generate a response. Please try again."

    for msg in new_user_messages:
        memory.append(conversation_id, msg)
    memory.append(conversation_id, {"role": "assistant", "content": response_text})

    return ChatResponse(
        response=response_text,
        conversation_id=conversation_id,
        tools_used=_collect_tools_used(final_messages),
        model_used=model_used,
    )


@app.get("/health")
async def health() -> dict[str, Any]:
    """Health check."""
    return {
        "status": "healthy",
        "service": "madvibe-agent",
        "default_model": DEFAULT_MODEL,
    }


if __name__ == "__main__":
    import uvicorn

    port = int(os.getenv("PORT", "8000"))
    uvicorn.run("main:app", host="0.0.0.0", port=port, reload=True)
