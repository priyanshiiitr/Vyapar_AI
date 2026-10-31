"""Langfuse optional tracing (v5 SDK) + structured local logging fallback."""

from __future__ import annotations

import json
import logging
import re
from contextlib import contextmanager
from typing import Any, Iterator

from app.config import get_settings

logger = logging.getLogger("vyapar.ai")
PHONE_RE = re.compile(r"\b[6-9]\d{9}\b")


def redact(value: Any) -> Any:
    if isinstance(value, str):
        return PHONE_RE.sub("[REDACTED_PHONE]", value)
    if isinstance(value, dict):
        return {k: redact(v) for k, v in value.items()}
    if isinstance(value, list):
        return [redact(v) for v in value]
    return value


def structured_log(event: str, **payload: Any) -> None:
    safe = redact(payload)
    logger.info("%s %s", event, json.dumps(safe, default=str))


def get_langfuse_client():
    settings = get_settings()
    if not settings.langfuse_configured:
        return None
    try:
        from langfuse import Langfuse

        return Langfuse(
            public_key=settings.LANGFUSE_PUBLIC_KEY,
            secret_key=settings.LANGFUSE_SECRET_KEY,
            host=settings.LANGFUSE_HOST,
        )
    except Exception as exc:  # noqa: BLE001
        structured_log("langfuse_init_failed", error=str(exc))
        return None


@contextmanager
def trace_span(name: str, metadata: dict[str, Any] | None = None) -> Iterator[dict[str, Any]]:
    """Yield a mutable span dict. Uses Langfuse v5 when configured, else local logs."""
    meta = redact(metadata or {})
    span: dict[str, Any] = {"name": name, "metadata": meta, "events": []}
    client = get_langfuse_client()
    observation = None
    if client is not None:
        try:
            # Langfuse Python SDK v5
            observation = client.start_observation(
                name=name,
                as_type="span",
                metadata=meta,
            )
        except Exception as exc:  # noqa: BLE001
            structured_log("langfuse_trace_failed", error=str(exc))
            client = None
            observation = None
    try:
        yield span
        if observation is not None:
            try:
                observation.update(metadata={"events": redact(span.get("events", []))})
                observation.end()
            except Exception as exc:  # noqa: BLE001
                structured_log("langfuse_end_failed", error=str(exc))
        if client is not None:
            try:
                client.flush()
            except Exception:  # noqa: BLE001
                pass
        structured_log("span_ok", name=name, metadata=meta, events=span.get("events", []))
    except Exception as exc:
        span["error"] = str(exc)
        structured_log("span_error", name=name, error=str(exc), metadata=meta)
        if observation is not None:
            try:
                observation.update(level="ERROR", status_message=str(exc))
                observation.end()
            except Exception:  # noqa: BLE001
                pass
        raise
