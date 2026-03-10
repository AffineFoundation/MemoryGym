"""Global API configuration.

Single source of truth for API URL and key resolution.
All modules should use get_api_config() instead of reading env vars directly.

Environment variables (in priority order):
    MEMORYGYM_API_KEY  — project-specific key
    CHUTES_API_KEY     — Chutes platform key (backward compat)
    OPENAI_API_KEY     — OpenAI key (fallback)

    MEMORYGYM_API_URL  — custom API endpoint
    (default: https://llm.chutes.ai/v1)
"""

from __future__ import annotations

import os
from dataclasses import dataclass

_DEFAULT_API_URL = "https://llm.chutes.ai/v1"


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
    key = (
        api_key
        or os.environ.get("MEMORYGYM_API_KEY")
        or os.environ.get("CHUTES_API_KEY")
        or os.environ.get("OPENAI_API_KEY")
    )
    if not key:
        raise RuntimeError(
            "No API key found. Set MEMORYGYM_API_KEY, CHUTES_API_KEY, "
            "or OPENAI_API_KEY environment variable."
        )

    url = (
        api_url
        or os.environ.get("MEMORYGYM_API_URL")
        or _DEFAULT_API_URL
    )

    return APIConfig(api_key=key, api_url=url)
