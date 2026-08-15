"""OpenAI-compatible asynchronous chat completion adapter."""

from collections.abc import Sequence
from typing import Any

from openai import AsyncOpenAI

from app.core.config import settings


class LLMConfigurationError(RuntimeError):
    """Raised when the LLM cannot be called with the configured settings."""


def get_llm_client(client: Any | None = None) -> Any:
    if client is not None:
        return client
    if not settings.LLM_API_KEY:
        raise LLMConfigurationError("LLM API key is not configured")
    return AsyncOpenAI(
        api_key=settings.LLM_API_KEY,
        base_url=settings.LLM_BASE_URL or None,
    )


async def complete_chat(messages: Sequence[dict[str, str]], *, client: Any | None = None) -> str:
    response = await get_llm_client(client).chat.completions.create(
        model=settings.LLM_MODEL,
        messages=list(messages),
        max_tokens=settings.LLM_MAX_TOKENS,
        temperature=0.2,
    )
    content = response.choices[0].message.content if response.choices else None
    if not content or not content.strip():
        raise LLMConfigurationError("LLM returned an empty completion")
    return content.strip()
