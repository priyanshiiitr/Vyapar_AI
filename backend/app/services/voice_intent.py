"""Voice-to-browse intent parsing — allowlisted navigation only; no arbitrary URLs/JS."""

from __future__ import annotations

import re
from typing import Any, Literal

# Frontend-navigable routes only. "/overview" maps to app root "/".
ALLOWED_ROUTES: dict[str, str] = {
    "/": "/",
    "/overview": "/",
    "/invoices": "/invoices",
    "/reconciliation": "/reconciliation",
    "/collections": "/collections",
    "/approvals": "/approvals",
    "/activity": "/activity",
    "/evaluation": "/evaluation",
    "/settings": "/settings",
    "/ai": "/ai",
    "/whatsapp": "/whatsapp",
}

ActionType = Literal["navigate", "agent_query", "needs_confirmation", "unsupported"]

# Phrases that imply mutating / customer-facing actions → merchant must confirm
_SENSITIVE = re.compile(
    r"("
    r"remind|reminder|yaad\s*dila|bhej|send\s*(message|reminder)|"
    r"promise\s*record|record\s*(a\s*)?promise|payment\s*promise|"
    r"approve|reject|mark\s*paid|close\s*case|schedule\s*follow|"
    r"create\s*reminder|draft\s*reminder|prepare\s*(a\s*)?(payment\s*)?reminder"
    r")",
    re.I,
)

_NAV_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"\b(overview|dashboard|home|command\s*center|मुख्य|डैशबोर्ड)\b", re.I), "/"),
    (re.compile(r"\b(invoices?|इनवॉइस|बिल)\b", re.I), "/invoices"),
    (re.compile(r"\b(reconciliation|reconcile|मैच|मिलान|transaction\s*match)\b", re.I), "/reconciliation"),
    (re.compile(r"\b(collections?|कलेक्शन|वसूली)\b", re.I), "/collections"),
    (re.compile(r"\b(approvals?|approve\s*section|अप्रूवल)\b", re.I), "/approvals"),
    (re.compile(r"\b(activity(\s*log)?|audit\s*log|लॉग)\b", re.I), "/activity"),
    (re.compile(r"\b(evaluation|eval|मूल्यांकन)\b", re.I), "/evaluation"),
    (re.compile(r"\b(settings?|सेटिंग)\b", re.I), "/settings"),
    (re.compile(r"\b(ai\s*teammate|teammate|chat|एआई)\b", re.I), "/ai"),
    (re.compile(r"\b(whatsapp|व्हाट्सऐप)\b", re.I), "/whatsapp"),
]

_OPEN_NAV = re.compile(
    r"("
    r"\b(open|go\s*to|take\s*me\s*to|navigate|switch\s*to|open\s*up)\b|"
    r"\b(show|dikhao|dikha\s*do|kholo|chalo)\b.{0,40}\b"
    r"(overview|invoices?|reconciliation|collections?|approvals?|activity|evaluation|settings?|whatsapp|teammate|dashboard)\b|"
    r"\b(overview|invoices?|reconciliation|collections?|approvals?|activity|evaluation|settings?|whatsapp)\b"
    r".{0,20}\b(page|section|screen|tab|kholo|dikhao)\b|"
    r"खोलो|जाओ|दिखाओ"
    r")",
    re.I,
)


def normalize_route(candidate: str) -> str | None:
    path = (candidate or "").strip()
    if not path.startswith("/"):
        path = "/" + path
    path = path.rstrip("/") or "/"
    # Only exact allowlist keys / values
    if path in ALLOWED_ROUTES:
        return ALLOWED_ROUTES[path]
    if path in ALLOWED_ROUTES.values():
        return path
    return None


def interpret_voice_command(transcript: str, *, confirmed: bool = False) -> dict[str, Any]:
    """
    Map spoken transcript → safe action.
    Never returns arbitrary URLs or executable code.
    """
    text = (transcript or "").strip()
    if not text:
        return {
            "ok": False,
            "action": "unsupported",
            "error": "Empty transcript",
        }

    lower = text.lower()

    # Pure navigation (open X / go to X) — not data questions like "show overdue invoices"
    _queryish = re.search(
        r"\b(overdue|outstanding|total|balance|history|promise|find|search|kitna|baki|due\s*list)\b",
        text,
        re.I,
    )
    if not _queryish and (
        _OPEN_NAV.search(text)
        or re.search(r"^(invoices|collections|approvals|settings|overview)\s*$", lower)
    ):
        for pattern, route in _NAV_PATTERNS:
            if pattern.search(text):
                safe = normalize_route(route)
                if safe:
                    return {
                        "ok": True,
                        "action": "navigate",
                        "route": safe,
                        "label": _route_label(safe),
                        "transcript": text,
                        "requires_confirmation": False,
                        "note": "Allowlisted in-app navigation only.",
                    }

    # Sensitive mutations need explicit confirm unless already confirmed
    if _SENSITIVE.search(text) and not confirmed:
        return {
            "ok": True,
            "action": "needs_confirmation",
            "agent_message": text,
            "transcript": text,
            "requires_confirmation": True,
            "confirm_reason": (
                "This may draft a reminder, record a promise, or otherwise change collections state. "
                "Voice alone cannot approve customer messages or mark payments."
            ),
            "note": "Review the transcript, then confirm to send to the existing AI teammate.",
        }

    # Default: pass through to existing Sarvam agent (read tools / draft after confirm)
    return {
        "ok": True,
        "action": "agent_query",
        "agent_message": text,
        "transcript": text,
        "requires_confirmation": False,
        "suggested_routes": _suggest_routes(text),
        "note": "Forwarding to existing /api/agent/chat (Sarvam tools + ledger).",
    }


def _route_label(route: str) -> str:
    return {
        "/": "Overview",
        "/invoices": "Invoices",
        "/reconciliation": "Reconciliation",
        "/collections": "Collections",
        "/approvals": "Approvals",
        "/activity": "Activity Log",
        "/evaluation": "Evaluation",
        "/settings": "Settings",
        "/ai": "AI Teammate",
        "/whatsapp": "WhatsApp mock",
    }.get(route, route)


def _suggest_routes(text: str) -> list[str]:
    out: list[str] = []
    for pattern, route in _NAV_PATTERNS:
        if pattern.search(text):
            safe = normalize_route(route)
            if safe and safe not in out:
                out.append(safe)
    return out[:3]
