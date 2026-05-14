"""LLM factory - OpenRouter via ChatOpenAI."""

from __future__ import annotations

import logging
import os

from dotenv import load_dotenv
from langchain_openai import ChatOpenAI

load_dotenv()
logger = logging.getLogger(__name__)

OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "")
OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
DEFAULT_MODEL = "openrouter/owl-alpha"
LLM_MODEL = os.getenv("LLM_MODEL", DEFAULT_MODEL)

DEFAULT_FREE_FALLBACK_MODELS = (
    "inclusionai/ring-2.6-1t:free",
    "nvidia/nemotron-3-super-120b-a12b:free",
    "poolside/laguna-m.1:free",
    "poolside/laguna-xs.2:free",
    "baidu/cobuddy:free",
    "nvidia/nemotron-3-nano-omni-30b-a3b-reasoning:free",
)

DEFAULT_PAID_FALLBACK_MODELS = (
    "deepseek/deepseek-v4-flash",
    "google/gemini-3-flash-preview",
    "moonshotai/kimi-k2.6",
    "anthropic/claude-sonnet-4.6",
    "openai/gpt-5.4",
)

LEGACY_MODEL_ALIASES = {
    "meta-llama/llama-3.3-70b-instruct:free": DEFAULT_MODEL,
    "meta-llama/llama-3.1-8b-instruct:free": DEFAULT_MODEL,
    "nvidia/llama-3.1-nemotron-70b-instruct:free": "nvidia/nemotron-3-super-120b-a12b:free",
    "baidu/qianfan-cobuddy:free": "baidu/cobuddy:free",
    "owl/alpha:free": "openrouter/owl-alpha",
    "nvidia/nemotron-3-nano-omni:free": "nvidia/nemotron-3-nano-omni-30b-a3b-reasoning:free",
    "poolside/laguna-xs-2:free": "poolside/laguna-xs.2:free",
    "poolside/laguna-m-1:free": "poolside/laguna-m.1:free",
    "deepseek/deepseek-v4-flash:free": DEFAULT_MODEL,
}


def _truthy(value: str | None) -> bool:
    return (value or "").strip().lower() in {"1", "true", "yes", "on"}


def _split_model_list(value: str | None) -> list[str]:
    return [item.strip() for item in (value or "").split(",") if item.strip()]


def normalize_model(model: str | None) -> str:
    """Normalize stale UI/env model IDs to current OpenRouter IDs."""
    chosen = (model or LLM_MODEL or DEFAULT_MODEL).strip()
    return LEGACY_MODEL_ALIASES.get(chosen, chosen)


def get_model_candidates(model: str | None = None) -> list[str]:
    """Return ordered OpenRouter models to try for one request."""
    configured_fallbacks = _split_model_list(os.getenv("LLM_FALLBACK_MODELS"))
    fallback_models = configured_fallbacks or list(DEFAULT_FREE_FALLBACK_MODELS)

    if _truthy(os.getenv("ALLOW_PAID_MODEL_FALLBACKS")):
        fallback_models.extend(DEFAULT_PAID_FALLBACK_MODELS)

    candidates = [normalize_model(model), DEFAULT_MODEL]
    candidates.extend(normalize_model(candidate) for candidate in fallback_models)

    unique: list[str] = []
    for candidate in candidates:
        if candidate and candidate not in unique:
            unique.append(candidate)
    return unique


def get_llm(model: str | None = None) -> ChatOpenAI:
    """Return a ChatOpenAI instance wired to OpenRouter."""
    chosen = normalize_model(model)
    logger.info("Using OpenRouter model: %s", chosen)
    return ChatOpenAI(
        base_url=OPENROUTER_BASE_URL,
        api_key=OPENROUTER_API_KEY or "missing-key",
        model=chosen,
        temperature=0.4,
        max_tokens=2048,
        max_retries=0,
        timeout=60,
        default_headers={
            "HTTP-Referer": "https://madvibe.app",
            "X-Title": "MadVibe Maddy Agent",
        },
    )
