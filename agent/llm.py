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

# Best free models with confirmed tool/function-calling support on OpenRouter
DEFAULT_MODEL = "meta-llama/llama-3.3-70b-instruct:free"
LLM_MODEL = os.getenv("LLM_MODEL", DEFAULT_MODEL)

# Free models known to support tool calling well
DEFAULT_FREE_FALLBACK_MODELS = (
    "meta-llama/llama-3.1-8b-instruct:free",      # fast, tool calling ok
    "deepseek/deepseek-v3-0324:free",              # good tool calling
    "qwen/qwen3-30b-a3b:free",                     # good tool calling
    "mistralai/mistral-7b-instruct:free",           # basic tool calling
    "google/gemma-3-12b-it:free",                  # decent tool calling
)

DEFAULT_PAID_FALLBACK_MODELS = (
    "deepseek/deepseek-chat",
    "google/gemini-flash-1.5",
    "anthropic/claude-3-haiku",
)

LEGACY_MODEL_ALIASES = {
    # Map any stale/non-tool-calling models to safe defaults
    "openrouter/owl-alpha": DEFAULT_MODEL,
    "owl/alpha:free": DEFAULT_MODEL,
    "inclusionai/ring-2.6-1t:free": DEFAULT_MODEL,
    "baidu/qianfan-cobuddy:free": DEFAULT_MODEL,
    "baidu/cobuddy:free": DEFAULT_MODEL,
    "nvidia/nemotron-3-nano-omni:free": "meta-llama/llama-3.1-8b-instruct:free",
    "nvidia/nemotron-3-nano-omni-30b-a3b-reasoning:free": "meta-llama/llama-3.1-8b-instruct:free",
    "nvidia/nemotron-3-super-120b-a12b:free": DEFAULT_MODEL,
    "nvidia/llama-3.1-nemotron-70b-instruct:free": DEFAULT_MODEL,
    "poolside/laguna-xs-2:free": "deepseek/deepseek-v3-0324:free",
    "poolside/laguna-xs.2:free": "deepseek/deepseek-v3-0324:free",
    "poolside/laguna-m-1:free": "deepseek/deepseek-v3-0324:free",
    "poolside/laguna-m.1:free": "deepseek/deepseek-v3-0324:free",
    "deepseek/deepseek-v4-flash:free": "deepseek/deepseek-v3-0324:free",
    "deepseek/deepseek-r1:free": "deepseek/deepseek-v3-0324:free",
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
