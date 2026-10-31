"""Integer-paise money helpers. Never use float as source of truth."""

from __future__ import annotations

from decimal import Decimal, InvalidOperation, ROUND_HALF_UP


def parse_amount_to_paise(value: str | int | float | Decimal) -> int:
    if isinstance(value, int):
        return value
    text = str(value).strip().replace(",", "").replace("₹", "").replace("Rs.", "").replace("Rs", "")
    if not text:
        raise ValueError("Amount is empty")
    try:
        dec = Decimal(text)
    except InvalidOperation as exc:
        raise ValueError(f"Invalid amount: {value}") from exc
    paise = (dec * Decimal(100)).quantize(Decimal("1"), rounding=ROUND_HALF_UP)
    return int(paise)


def format_inr(paise: int) -> str:
    rupees = Decimal(paise) / Decimal(100)
    quantized = rupees.quantize(Decimal("0.01"))
    negative = quantized < 0
    quantized = abs(quantized)
    whole, _, frac = f"{quantized:.2f}".partition(".")
    # Indian grouping
    if len(whole) <= 3:
        grouped = whole
    else:
        last3 = whole[-3:]
        rest = whole[:-3]
        parts = []
        while rest:
            parts.append(rest[-2:])
            rest = rest[:-2]
        grouped = ",".join(reversed(parts)) + "," + last3
    formatted = f"₹{grouped}.{frac}"
    return f"-{formatted}" if negative else formatted
