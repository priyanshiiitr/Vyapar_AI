"""Classify simulated debtor WhatsApp replies + extract promise dates."""

from __future__ import annotations

import json
import re
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeout
from datetime import date, timedelta
from typing import Any, Literal

Intent = Literal["refusal", "dispute", "promise", "payment_claim", "neutral"]

_REFUSAL = re.compile(
    r"("
    r"can\s*n['’]?t\s*pay|cannot\s*pay|can\s*not\s*pay|unable\s*to\s*pay|"
    r"\bpaay\b|won't\s*pay|will\s*not\s*pay|no\s*money|paisa\s*nahi|"
    r"nahi\s*(de|bhej)\s*sakt|nahi\s*ho\s*payega|abhi\s*nahi\s*(de|pay)|"
    r"refuse|hardship|bankrupt"
    r")",
    re.I,
)

_PAYMENT_CLAIM = re.compile(
    r"("
    r"already\s*paid|i\s*(have\s*)?paid|payment\s*(done|sent|completed)|"
    r"paid\s*(just\s*)?now|bhej\s*diya|transfer\s*(ho\s*)?gaya|"
    r"upi\s*(done|sent)|neft\s*(done|sent)|paid\s*(the\s*)?(bill|invoice|amount)|"
    r"screenshot|utr|payment\s*proof"
    r")",
    re.I,
)

_DISPUTE = re.compile(
    r"("
    r"galat\s*invoice|wrong\s*invoice|dispute|"
    r"not\s*my\s*(invoice|bill)|never\s*ordered|quality\s*issue|"
    r"double\s*charge|incorrect\s*amount"
    r")",
    re.I,
)

_PROMISE = re.compile(
    r"("
    r"will\s*(be\s*)?pay|going\s*to\s*pay|pay\s*(it\s*)?(by|on|tomorrow|tommorow)|"
    r"paying\s*.*\s*(day|days|later|tomorrow|tommorow)|"
    r"friday|monday|tuesday|wednesday|thursday|saturday|sunday|"
    r"\bkal\b|\bparso\b|next\s*week|in\s*\d+\s*days?|\d+\s*days?\s*later|"
    r"tak\s*clear|clear\s*kar|bhej\s*dung|promise|de\s*dung"
    r")",
    re.I,
)

_WEEKDAYS = {
    "monday": 0,
    "tuesday": 1,
    "wednesday": 2,
    "thursday": 3,
    "friday": 4,
    "saturday": 5,
    "sunday": 6,
}


def classify_debtor_reply(body: str) -> Intent:
    text = (body or "").strip()
    if not text:
        return "neutral"
    if _REFUSAL.search(text):
        return "refusal"
    if _PAYMENT_CLAIM.search(text):
        return "payment_claim"
    if _DISPUTE.search(text):
        return "dispute"
    if _PROMISE.search(text):
        return "promise"
    return "neutral"


def parse_promise_date(body: str, *, today: date | None = None) -> date | None:
    """Best-effort relative date from debtor language. Returns None if unclear."""
    text = (body or "").lower()
    today = today or date.today()

    if re.search(r"\b(tom+or+ow|kal)\b", text):
        return today + timedelta(days=1)
    if re.search(r"\b(day\s*after\s*tomorrow|parso)\b", text):
        return today + timedelta(days=2)
    if re.search(r"\bnext\s*week\b", text):
        return today + timedelta(days=7)

    m = re.search(r"(?:in\s*)?(\d+)\s*days?\s*(?:later|mein|me)?", text)
    if m:
        return today + timedelta(days=int(m.group(1)))

    m = re.search(r"after\s*(\d+)\s*days?", text)
    if m:
        return today + timedelta(days=int(m.group(1)))

    for name, wd in _WEEKDAYS.items():
        if re.search(rf"\b{name}\b", text):
            delta = (wd - today.weekday()) % 7
            if delta == 0:
                delta = 7
            return today + timedelta(days=delta)

    # "will pay" with no date → default +2 business-ish days for demo
    if re.search(r"will\s*(be\s*)?pay|paying|bhej\s*dung|clear\s*kar", text):
        return today + timedelta(days=2)
    return None


def analyze_debtor_reply(body: str, *, use_sarvam: bool = True) -> dict[str, Any]:
    """
    Rules first (fast/reliable), then optional Sarvam enrichment for ambiguous text.
    Never marks invoices paid.
    """
    rules_intent = classify_debtor_reply(body)
    promise_date = parse_promise_date(body) if rules_intent == "promise" else None
    result: dict[str, Any] = {
        "intent": rules_intent,
        "promise_date": promise_date.isoformat() if promise_date else None,
        "source": "rules",
        "confidence": "high" if rules_intent != "neutral" else "low",
    }

    if not use_sarvam:
        return result
    if rules_intent != "neutral":
        # Still ask Sarvam only when promise date missing but looks like promise
        if not (rules_intent == "promise" and not promise_date):
            return result

    enriched = _sarvam_classify(body)
    if not enriched:
        return result

    intent = enriched.get("intent") or rules_intent
    if intent not in {"refusal", "dispute", "promise", "payment_claim", "neutral"}:
        intent = rules_intent
    pd = enriched.get("promise_date") or result["promise_date"]
    if intent == "promise" and not pd:
        fallback = parse_promise_date(body) or (date.today() + timedelta(days=2))
        pd = fallback.isoformat()
    return {
        "intent": intent,
        "promise_date": pd,
        "source": "sarvam+rules",
        "confidence": enriched.get("confidence") or "medium",
        "sarvam_note": enriched.get("note"),
    }


def _sarvam_classify(body: str) -> dict[str, Any] | None:
    from app.config import get_settings

    settings = get_settings()
    if not settings.sarvam_configured:
        return None

    prompt = (
        "Classify this debtor WhatsApp reply for Indian SME collections. "
        "Return ONLY JSON with keys: intent (refusal|dispute|promise|payment_claim|neutral), "
        "promise_date (YYYY-MM-DD or null), confidence (high|medium|low), note (short).\n"
        "payment_claim = customer says they already paid (do NOT mark paid).\n"
        "promise = will pay in future — set promise_date relative to today.\n"
        f"Today: {date.today().isoformat()}\n"
        f"Reply: {body.strip()[:500]}"
    )

    def _call() -> dict[str, Any] | None:
        try:
            from sarvamai import SarvamAI

            client = SarvamAI(api_subscription_key=settings.SARVAM_API_KEY)
            response = client.chat.completions(
                model=settings.SARVAM_CHAT_MODEL,
                messages=[
                    {"role": "system", "content": "You extract collection intents as JSON only."},
                    {"role": "user", "content": prompt},
                ],
                temperature=0.1,
                max_tokens=256,
            )
            text = response.choices[0].message.content or ""
            return _extract_json(text)
        except Exception:  # noqa: BLE001
            return None

    try:
        with ThreadPoolExecutor(max_workers=1) as pool:
            fut = pool.submit(_call)
            return fut.result(timeout=12)
    except FuturesTimeout:
        return None


def _extract_json(text: str) -> dict[str, Any] | None:
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        m = re.search(r"\{.*\}", text, re.S)
        if not m:
            return None
        try:
            return json.loads(m.group(0))
        except json.JSONDecodeError:
            return None
