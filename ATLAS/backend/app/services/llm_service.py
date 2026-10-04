"""All provider-specific LLM code lives here (Groq / OpenAI-compatible API)."""
import logging

import httpx

from app.config import PLACEHOLDER_KEY, settings

logger = logging.getLogger("atlas.llm")


class LLMError(Exception):
    """Application-level LLM failure. `user_message` is safe to show to users."""

    def __init__(self, user_message: str):
        super().__init__(user_message)
        self.user_message = user_message


class LLMNotConfiguredError(LLMError):
    pass


def is_configured() -> bool:
    return bool(settings.llm_api_key) and settings.llm_api_key != PLACEHOLDER_KEY and bool(settings.llm_base_url)


def generate_response(messages: list[dict], system_prompt: str | None = None) -> str:
    """Send chat messages to the LLM and return the reply text.

    messages: [{"role": "user" | "assistant", "content": "..."}]
    Raises LLMError (never leaks the API key or raw provider traces).
    """
    if not is_configured():
        raise LLMNotConfiguredError(
            "The AI model isn't configured yet. Add LLM_API_KEY to the .env file and restart "
            "the backend. Task features still work without it."
        )

    payload_messages = ([{"role": "system", "content": system_prompt}] if system_prompt else []) + messages
    try:
        resp = httpx.post(
            f"{settings.llm_base_url.rstrip('/')}/chat/completions",
            headers={"Authorization": f"Bearer {settings.llm_api_key}"},
            json={"model": settings.llm_model, "messages": payload_messages, "max_tokens": 1024, "temperature": 0.3},
            timeout=settings.llm_timeout_seconds,
        )
    except httpx.TimeoutException:
        raise LLMError("The AI model took too long to respond. Please try again.")
    except httpx.HTTPError:
        raise LLMError("Couldn't reach the AI provider. Check your internet connection and try again.")

    if resp.status_code != 200:
        logger.warning("LLM provider returned HTTP %s", resp.status_code)
        if resp.status_code in (401, 403):
            raise LLMError("The AI provider rejected the API key. Check LLM_API_KEY in your .env file.")
        if resp.status_code == 429:
            raise LLMError("The AI provider's rate limit was reached. Wait a moment and try again.")
        if resp.status_code in (400, 404):
            raise LLMError("The AI provider rejected the request. Check that LLM_MODEL is a valid model name.")
        raise LLMError("The AI provider had a problem. Please try again shortly.")

    try:
        return resp.json()["choices"][0]["message"]["content"].strip()
    except (ValueError, KeyError, IndexError, AttributeError, TypeError):
        raise LLMError("The AI provider sent an unexpected response. Please try again.")
