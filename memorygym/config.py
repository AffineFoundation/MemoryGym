"""Global API configuration.

Single source of truth for API URL and key resolution.
All modules should use get_api_config() instead of reading env vars directly.

Environment variables (in priority order):
    DASHSCOPE_API_KEY  — DashScope key; preferred default provider
    CHUTES_API_KEY     — Chutes platform key
    OPENAI_API_KEY     — OpenAI key
    API_KEY            — project-specific fallback key

    API_URL            — custom API endpoint
    (default: DashScope when DASHSCOPE_API_KEY is set, else Chutes)
"""

from __future__ import annotations

import os
from dataclasses import dataclass

QWEN_FALLBACK_BASE_URL = "https://dashscope.aliyuncs.com/compatible-mode/v1"
QWEN_FALLBACK_MODEL = "qwen3.6-27b"

_DEFAULT_API_URL = "https://llm.chutes.ai/v1"


def _looks_like_dashscope(url: str | None) -> bool:
    return bool(url and "dashscope.aliyuncs.com" in url)


def _looks_like_chutes(url: str | None) -> bool:
    return bool(url and "chutes.ai" in url)


@dataclass(frozen=True)
class APIConfig:
    """Resolved API configuration."""

    api_key: str
    api_url: str


def get_api_config(
    *,
    api_key: str | None = None,
    api_url: str | None = None,
) -> APIConfig:
    """Resolve API key and URL from args or environment.

    Args:
        api_key: Explicit key override (highest priority).
        api_url: Explicit URL override (highest priority).

    Returns:
        APIConfig with resolved key and URL.

    Raises:
        RuntimeError: If no API key can be found.
    """
    requested_url = api_url or os.environ.get("API_URL")

    if api_key:
        key = api_key
    elif _looks_like_dashscope(requested_url):
        key = (
            os.environ.get("DASHSCOPE_API_KEY")
            or os.environ.get("API_KEY")
            or os.environ.get("OPENAI_API_KEY")
        )
    elif _looks_like_chutes(requested_url):
        key = (
            os.environ.get("CHUTES_API_KEY")
            or os.environ.get("API_KEY")
            or os.environ.get("OPENAI_API_KEY")
        )
    else:
        key = (
            os.environ.get("DASHSCOPE_API_KEY")
            or os.environ.get("CHUTES_API_KEY")
            or os.environ.get("OPENAI_API_KEY")
            or os.environ.get("API_KEY")
        )
    if not key:
        raise RuntimeError(
            "No API key found. Set DASHSCOPE_API_KEY, CHUTES_API_KEY, "
            "OPENAI_API_KEY, or API_KEY environment variable."
        )

    url = (
        api_url
        or os.environ.get("API_URL")
        or (QWEN_FALLBACK_BASE_URL if os.environ.get("DASHSCOPE_API_KEY") else None)
        or _DEFAULT_API_URL
    )

    return APIConfig(api_key=key, api_url=url)
