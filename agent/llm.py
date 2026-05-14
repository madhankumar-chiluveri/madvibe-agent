"""LLM factory — supports OpenRouter (default) and NVIDIA NIM via OpenAI-compatible API."""

from __future__ import annotations

import logging
import os

from dotenv import load_dotenv
from langchain_openai import ChatOpenAI

load_dotenv()
logger = logging.getLogger(__name__)

# ── OpenRouter config ────────────────────────────────────────────────────────
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "")
OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"

# ── NVIDIA NIM config (OpenAI-compatible) ────────────────────────────────────
NVIDIA_API_KEY = os.getenv("NVIDIA_API_KEY", "")
NVIDIA_BASE_URL = "https://integrate.api.nvidia.com/v1"

# ── Defaults ─────────────────────────────────────────────────────────────────
# If NVIDIA_API_KEY is set, default to a NVIDIA model; otherwise use OpenRouter
_DEFAULT_NVIDIA_MODEL = "minimaxai/minimax-m2.7"
_DEFAULT_OPENROUTER_MODEL = "meta-llama/llama-3.3-70b-instruct:free"

DEFAULT_MODEL = (
    _DEFAULT_NVIDIA_MODEL if NVIDIA_API_KEY else _DEFAULT_OPENROUTER_MODEL
)
LLM_MODEL = os.getenv("LLM_MODEL", DEFAULT_MODEL)

# ── Free OpenRouter fallbacks (tool-calling capable) ─────────────────────────
DEFAULT_FREE_FALLBACK_MODELS = (
    "meta-llama/llama-3.1-8b-instruct:free",
    "deepseek/deepseek-v3-0324:free",
    "qwen/qwen3-30b-a3b:free",
    "mistralai/mistral-7b-instruct:free",
    "google/gemma-3-12b-it:free",
)

DEFAULT_PAID_FALLBACK_MODELS = (
    "deepseek/deepseek-chat",
    "google/gemini-flash-1.5",
    "anthropic/claude-3-haiku",
)

# ── NVIDIA NIM free models with good tool-calling ────────────────────────────
NVIDIA_FREE_MODELS = (
    "stepfun-ai/step-3.5-flash",
    "mistralai/mistral-large-3-675b-instruct-2512",
    "qwen/qwen3-coder-480b-a35b-instruct",
    "mistralai/magistral-small-2506",
    # Extra safety fallbacks
    "meta/llama-3.3-70b-instruct",
    "meta/llama-3.1-8b-instruct",
)

LEGACY_MODEL_ALIASES: dict[str, str] = {
    # stale / non-tool-calling models → safe NVIDIA defaults
    "openrouter/owl-alpha": "stepfun-ai/step-3.5-flash",
    "owl/alpha:free": "stepfun-ai/step-3.5-flash",
    "minimaxai/minimax-m2.7": "stepfun-ai/step-3.5-flash",
    "inclusionai/ring-2.6-1t:free": "stepfun-ai/step-3.5-flash",
    "baidu/cobuddy:free": "stepfun-ai/step-3.5-flash",
    "nvidia/nemotron-3-super-120b-a12b:free": "stepfun-ai/step-3.5-flash",
    "nvidia/llama-3.1-nemotron-70b-instruct:free": "meta/llama-3.3-70b-instruct",
    "poolside/laguna-xs.2:free": "mistralai/magistral-small-2506",
    "poolside/laguna-m.1:free": "mistralai/mistral-large-3-675b-instruct-2512",
    "deepseek/deepseek-v3-0324:free": "qwen/qwen3-coder-480b-a35b-instruct",
    "deepseek/deepseek-r1:free": "qwen/qwen3-coder-480b-a35b-instruct",
    "meta-llama/llama-3.3-70b-instruct:free": "meta/llama-3.3-70b-instruct",
    "meta-llama/llama-3.1-8b-instruct:free": "meta/llama-3.1-8b-instruct",
}


def _truthy(value: str | None) -> bool:
    return (value or "").strip().lower() in {"1", "true", "yes", "on"}


def _split_model_list(value: str | None) -> list[str]:
    return [item.strip() for item in (value or "").split(",") if item.strip()]


def _is_nvidia_model(model: str) -> bool:
    """Return True if this model should be routed to NVIDIA NIM."""
    # NVIDIA NIM orgs (no :free suffix, no openrouter/ prefix)
    nvidia_orgs = {
        "minimaxai", "meta", "mistralai", "microsoft", "nvidia",
        "google", "stepfun-ai", "qwen", "deepseek", "01-ai",
    }
    org = model.split("/")[0] if "/" in model else ""
    return (
        org in nvidia_orgs
        and ":free" not in model
        and not model.startswith("openrouter/")
        and not model.startswith("openai/")
        and not model.startswith("anthropic/")
    )


def normalize_model(model: str | None) -> str:
    """Normalize stale UI/env model IDs to current supported IDs."""
    chosen = (model or LLM_MODEL or DEFAULT_MODEL).strip()
    return LEGACY_MODEL_ALIASES.get(chosen, chosen)


def get_model_candidates(model: str | None = None) -> list[str]:
    """Return ordered models to try for one request."""
    primary = normalize_model(model)

    # If NVIDIA key exists and the primary is a NVIDIA model, use NVIDIA fallbacks
    if NVIDIA_API_KEY and _is_nvidia_model(primary):
        candidates = [primary] + list(NVIDIA_FREE_MODELS)
    else:
        configured_fallbacks = _split_model_list(os.getenv("LLM_FALLBACK_MODELS"))
        fallback_models = configured_fallbacks or list(DEFAULT_FREE_FALLBACK_MODELS)

        if _truthy(os.getenv("ALLOW_PAID_MODEL_FALLBACKS")):
            fallback_models.extend(DEFAULT_PAID_FALLBACK_MODELS)

        candidates = [primary, _DEFAULT_OPENROUTER_MODEL] + fallback_models

    # Deduplicate while preserving order
    unique: list[str] = []
    for candidate in candidates:
        if candidate and candidate not in unique:
            unique.append(candidate)
    return unique


def get_llm(model: str | None = None) -> ChatOpenAI:
    """Return a ChatOpenAI instance wired to the correct provider.

    - If NVIDIA_API_KEY is set AND the model looks like a NVIDIA model → NVIDIA NIM
    - Otherwise → OpenRouter
    """
    chosen = normalize_model(model)

    if NVIDIA_API_KEY and _is_nvidia_model(chosen):
        logger.info("Using NVIDIA NIM model: %s", chosen)
        return ChatOpenAI(
            base_url=NVIDIA_BASE_URL,
            api_key=NVIDIA_API_KEY,
            model=chosen,
            temperature=0.6,
            max_tokens=4096,
            max_retries=0,
            timeout=60,
        )

    # Default: OpenRouter
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
