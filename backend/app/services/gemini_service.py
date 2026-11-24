"""Gemini LLM service built on the official Google Gen AI SDK (`google-genai`).

Reads GEMINI_API_KEY and GEMINI_MODEL from .env (never hardcodes a model name),
with timeout handling, retries for transient errors, and clear error messages.
"""

import time
from typing import Any

from app.config.settings import settings
from app.utils.logger import get_logger

logger = get_logger(__name__)

# HTTP status codes worth retrying with exponential backoff
_RETRYABLE_STATUS_CODES: frozenset[int] = frozenset({429, 500, 502, 503, 504})


class GeminiServiceError(Exception):
    """Base error raised for Gemini configuration or API failures."""

    status_code: int = 502

    def __init__(self, message: str, status_code: int = 502) -> None:
        super().__init__(message)
        self.message = message
        self.status_code = status_code


class GeminiConfigError(GeminiServiceError):
    """Raised when GEMINI_API_KEY or GEMINI_MODEL is missing in backend/.env."""

    def __init__(self, message: str) -> None:
        super().__init__(message, status_code=500)


def _create_client(api_key: str, timeout_seconds: int) -> Any:
    """Instantiate the official google-genai Client with an HTTP timeout."""
    from google import genai
    from google.genai import types

    # google-genai HttpOptions.timeout expects milliseconds; disable SDK internal retries
    # so our own backoff loop controls total latency cleanly.
    timeout_ms = max(1, timeout_seconds) * 1000
    http_options = types.HttpOptions(
        timeout=timeout_ms,
        retry_options=types.HttpRetryOptions(attempts=1),
    )
    return genai.Client(api_key=api_key, http_options=http_options)


def _extract_status_code(error: Exception) -> int | None:
    """Pull an HTTP status code from google-genai APIError if present."""
    code = getattr(error, "code", None)
    if isinstance(code, int):
        return code
    status = getattr(error, "status_code", None)
    if isinstance(status, int):
        return status
    return None


def _is_retryable(error: Exception) -> bool:
    """Return True for transient network/timeout/rate-limit/5xx errors."""
    code = _extract_status_code(error)
    if code in _RETRYABLE_STATUS_CODES:
        return True
    msg = str(error).lower()
    transient_markers = ("timed out", "timeout", "temporarily unavailable", "connection reset", "rate limit", "429")
    return any(marker in msg for marker in transient_markers)


def _format_user_error(error: Exception, model_name: str) -> GeminiServiceError:
    """Convert raw SDK exceptions into clean, actionable messages."""
    code = _extract_status_code(error)
    msg = str(error)

    if code in {401, 403} or "api key" in msg.lower():
        return GeminiServiceError(
            "Gemini API authentication failed. Check GEMINI_API_KEY in backend/.env.",
            status_code=502,
        )
    if code == 404 or "not found" in msg.lower():
        return GeminiServiceError(
            f"Gemini model '{model_name}' was not found. Update GEMINI_MODEL in backend/.env.",
            status_code=502,
        )
    if code == 429 or "quota" in msg.lower() or "rate limit" in msg.lower():
        return GeminiServiceError(
            "Gemini API rate limit or quota exceeded. Wait a moment and try again.",
            status_code=503,
        )
    if code == 503 or "unavailable" in msg.lower() or "high demand" in msg.lower():
        return GeminiServiceError(
            f"Gemini model '{model_name}' is temporarily overloaded (503). Wait a moment and try again.",
            status_code=503,
        )
    if "timeout" in msg.lower() or "timed out" in msg.lower():
        return GeminiServiceError(
            "Gemini API request timed out. Please try again.",
            status_code=504,
        )
    return GeminiServiceError(f"Gemini API error: {msg}", status_code=502)


def generate_text(
    prompt: str,
    system_instruction: str | None = None,
    temperature: float = 0.2,
    max_retries: int | None = None,
    timeout_seconds: int | None = None,
) -> str:
    """Send a prompt to Gemini and return the generated text.

    Retries transient failures with exponential backoff (1s, 2s, 4s...).
    """
    api_key = settings.GEMINI_API_KEY.strip()
    model_name = settings.GEMINI_MODEL.strip()

    if not api_key:
        raise GeminiConfigError(
            "GEMINI_API_KEY is not set. Add your Gemini API key to backend/.env."
        )
    if not model_name:
        raise GeminiConfigError(
            "GEMINI_MODEL is not set. Add a model name (e.g. gemini-2.5-flash) to backend/.env."
        )

    retries = settings.GEMINI_MAX_RETRIES if max_retries is None else max(1, max_retries)
    timeout = settings.GEMINI_TIMEOUT_SECONDS if timeout_seconds is None else max(1, timeout_seconds)

    from google.genai import types

    config = types.GenerateContentConfig(
        temperature=temperature,
        system_instruction=system_instruction if system_instruction else None,
    )
    client = _create_client(api_key=api_key, timeout_seconds=timeout)

    last_error: Exception | None = None
    for attempt in range(1, retries + 1):
        try:
            response = client.models.generate_content(
                model=model_name,
                contents=prompt,
                config=config,
            )
            text = (getattr(response, "text", None) or "").strip()
            if not text:
                raise GeminiServiceError("Gemini returned an empty response.", status_code=502)
            return text
        except GeminiServiceError:
            raise
        except Exception as error:
            last_error = error
            if attempt < retries and _is_retryable(error):
                backoff = float(2 ** (attempt - 1))
                logger.warning(
                    "Gemini call failed (attempt %d/%d): %s. Retrying in %.1fs...",
                    attempt,
                    retries,
                    error,
                    backoff,
                )
                time.sleep(backoff)
                continue
            logger.error("Gemini call failed permanently on attempt %d/%d: %s", attempt, retries, error)
            raise _format_user_error(error, model_name) from error

    assert last_error is not None
    raise _format_user_error(last_error, model_name) from last_error
