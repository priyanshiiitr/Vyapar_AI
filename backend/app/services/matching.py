"""RapidFuzz-assisted payment matching helpers.

Rules:
- Exact unique invoice reference → high-confidence auto-match.
- Fuzzy customer name → auto-match only when score is high, uniquely best,
  and the transaction amount exactly equals outstanding or invoice total.
- Everything else → human review (ambiguous / unmatched).
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from rapidfuzz import fuzz


NAME_AUTO_THRESHOLD = 85
NAME_UNIQUE_GAP = 8


def normalize_name(value: str) -> str:
    text = (value or "").lower()
    text = re.sub(r"[^a-z0-9\s]", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def compact_name(value: str) -> str:
    return re.sub(r"[^a-z0-9]", "", (value or "").lower())


def name_similarity(a: str, b: str) -> float:
    na, nb = normalize_name(a), normalize_name(b)
    if not na or not nb:
        return 0.0
    # token_set_ratio handles word order; compact ratio handles A.B.C. vs ABC
    token_score = float(fuzz.token_set_ratio(na, nb))
    compact_score = float(fuzz.ratio(compact_name(a), compact_name(b)))
    return max(token_score, compact_score)


@dataclass
class FuzzyCandidate:
    invoice_id: int
    invoice_number: str
    customer_name: str
    score: float
    outstanding_paise: int
    amount_paise: int


def rank_fuzzy_candidates(
    *,
    txn_customer_name: str,
    invoices: list,
) -> list[FuzzyCandidate]:
    ranked: list[FuzzyCandidate] = []
    for inv in invoices:
        cust = inv.customer.name if inv.customer else ""
        score = name_similarity(txn_customer_name, cust)
        ranked.append(
            FuzzyCandidate(
                invoice_id=inv.id,
                invoice_number=inv.invoice_number,
                customer_name=cust,
                score=score,
                outstanding_paise=inv.outstanding_paise,
                amount_paise=inv.amount_paise,
            )
        )
    ranked.sort(key=lambda c: c.score, reverse=True)
    return ranked


def select_fuzzy_auto_match(
    *,
    txn_customer_name: str,
    txn_amount_paise: int,
    invoices: list,
) -> tuple[FuzzyCandidate | None, list[FuzzyCandidate], str]:
    """Return (winner, ranked, reason). Winner is None if human review needed."""
    ranked = rank_fuzzy_candidates(txn_customer_name=txn_customer_name, invoices=invoices)
    if not ranked:
        return None, ranked, "no_open_invoices"

    best = ranked[0]
    second = ranked[1].score if len(ranked) > 1 else 0.0

    if best.score < NAME_AUTO_THRESHOLD:
        return None, ranked, f"name_score_below_threshold:{best.score:.1f}"

    if best.score - second < NAME_UNIQUE_GAP:
        return None, ranked, f"ambiguous_name_scores:{best.score:.1f}/{second:.1f}"

    amount_exact = txn_amount_paise in (best.outstanding_paise, best.amount_paise)
    if not amount_exact:
        return None, ranked, "amount_not_exact_for_fuzzy_auto"

    return best, ranked, "fuzzy_name_high_score_exact_amount"
