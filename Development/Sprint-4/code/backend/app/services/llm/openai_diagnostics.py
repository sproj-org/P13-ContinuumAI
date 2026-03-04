"""Safe OpenAI failure diagnostics helpers."""

from __future__ import annotations

from typing import Any, TypedDict


class OpenAIDiagnostics(TypedDict):
    openai_error_type: str
    openai_status_code: int | None
    openai_error_hint: str | None


def _coerce_int(value: Any) -> int | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _extract_status_code(exc: Exception) -> int | None:
    direct = _coerce_int(getattr(exc, "status_code", None))
    if direct is not None:
        return direct

    http_status = _coerce_int(getattr(exc, "http_status", None))
    if http_status is not None:
        return http_status

    response = getattr(exc, "response", None)
    if response is not None:
        response_status = _coerce_int(getattr(response, "status_code", None))
        if response_status is not None:
            return response_status
        response_status = _coerce_int(getattr(response, "status", None))
        if response_status is not None:
            return response_status

    return None


def _text_fingerprint(exc: Exception) -> str:
    parts: list[str] = [exc.__class__.__name__]
    for attr in ("type", "code", "message"):
        value = getattr(exc, attr, None)
        if isinstance(value, str) and value.strip():
            parts.append(value.strip())
    rendered = str(exc).strip()
    if rendered:
        parts.append(rendered)
    return " ".join(parts).lower()


def classify_openai_exception(exc: Exception) -> OpenAIDiagnostics:
    status_code = _extract_status_code(exc)
    fingerprint = _text_fingerprint(exc)
    class_name = exc.__class__.__name__.lower()

    if status_code in {401, 403} or "authentication" in class_name:
        return {
            "openai_error_type": "authentication_error",
            "openai_status_code": status_code,
            "openai_error_hint": "Authentication failed (check OPENAI_API_KEY permissions)",
        }
    if status_code == 429 or "ratelimit" in class_name or "rate limit" in fingerprint:
        return {
            "openai_error_type": "rate_limit",
            "openai_status_code": status_code,
            "openai_error_hint": "Rate limited (wait or reduce requests)",
        }
    if status_code == 404 or "notfound" in class_name:
        return {
            "openai_error_type": "not_found",
            "openai_status_code": status_code,
            "openai_error_hint": "Model not found or endpoint not available (check model name)",
        }
    if status_code == 400 or "badrequest" in class_name:
        return {
            "openai_error_type": "bad_request",
            "openai_status_code": status_code,
            "openai_error_hint": "Bad request (check model/tool schema/payload)",
        }
    if status_code is not None and status_code >= 500:
        return {
            "openai_error_type": "server_error",
            "openai_status_code": status_code,
            "openai_error_hint": "OpenAI server error (retry)",
        }

    timeout_tokens = ("timeout", "timed out", "read timeout", "connect timeout")
    if any(token in fingerprint for token in timeout_tokens):
        return {
            "openai_error_type": "timeout",
            "openai_status_code": status_code,
            "openai_error_hint": "Request timed out (retry or increase timeout)",
        }

    network_tokens = (
        "connection",
        "network",
        "dns",
        "socket",
        "unreachable",
        "ssl",
        "proxy",
        "apiconnection",
    )
    if any(token in fingerprint for token in network_tokens):
        return {
            "openai_error_type": "network",
            "openai_status_code": status_code,
            "openai_error_hint": "Network/connectivity issue reaching OpenAI",
        }

    return {
        "openai_error_type": "unknown",
        "openai_status_code": status_code,
        "openai_error_hint": "OpenAI request failed (see backend diagnostics)",
    }


def log_openai_failure(
    logger: Any,
    correlation_id: str,
    diagnostics: OpenAIDiagnostics,
    *,
    enable_debug: bool = False,
    exception_class_name: str | None = None,
) -> None:
    if enable_debug:
        logger.warning(
            "openai_failure correlation_id=%s openai_error_type=%s openai_status_code=%s openai_error_hint=%s exception_class=%s",
            correlation_id,
            diagnostics.get("openai_error_type"),
            diagnostics.get("openai_status_code"),
            diagnostics.get("openai_error_hint"),
            exception_class_name or "-",
        )
        return

    logger.warning(
        "openai_failure correlation_id=%s openai_error_type=%s openai_status_code=%s openai_error_hint=%s",
        correlation_id,
        diagnostics.get("openai_error_type"),
        diagnostics.get("openai_status_code"),
        diagnostics.get("openai_error_hint"),
    )
