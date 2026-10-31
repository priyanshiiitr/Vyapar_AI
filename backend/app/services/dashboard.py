from __future__ import annotations

from collections import defaultdict
from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.models import (
    AuditLog,
    CollectionCase,
    FollowUp,
    Invoice,
    Message,
    PaymentPromise,
    Transaction,
)
from app.services.money import format_inr


def get_dashboard_summary(db: Session, merchant_id: str) -> dict:
    invoices = list(
        db.scalars(
            select(Invoice)
            .options(joinedload(Invoice.customer))
            .where(Invoice.merchant_id == merchant_id)
        ).unique()
    )
    txns = list(db.scalars(select(Transaction).where(Transaction.merchant_id == merchant_id)))
    today = date.today()

    total_receivables = sum(i.amount_paise for i in invoices)
    outstanding = sum(i.outstanding_paise for i in invoices)
    overdue = sum(
        i.outstanding_paise for i in invoices if i.outstanding_paise > 0 and i.due_date < today
    )
    paid = sum(1 for i in invoices if i.status == "paid")
    partial = sum(1 for i in invoices if i.status == "partial")
    unpaid = sum(1 for i in invoices if i.status == "unpaid")

    pending_promises = db.scalar(
        select(PaymentPromise).where(
            PaymentPromise.merchant_id == merchant_id, PaymentPromise.status == "active"
        ).limit(1)
    )
    promise_count = len(
        list(
            db.scalars(
                select(PaymentPromise).where(
                    PaymentPromise.merchant_id == merchant_id, PaymentPromise.status == "active"
                )
            )
        )
    )
    pending_approvals = len(
        list(
            db.scalars(
                select(Message).where(
                    Message.merchant_id == merchant_id, Message.status == "pending_approval"
                )
            )
        )
    )
    unmatched = sum(1 for t in txns if t.status in ("unmatched", "ambiguous", "overpayment"))

    aging = {"0_7": 0, "8_15": 0, "16_30": 0, "30_plus": 0}
    for inv in invoices:
        if inv.outstanding_paise <= 0:
            continue
        days = (today - inv.due_date).days
        if days <= 0:
            continue
        if days <= 7:
            aging["0_7"] += inv.outstanding_paise
        elif days <= 15:
            aging["8_15"] += inv.outstanding_paise
        elif days <= 30:
            aging["16_30"] += inv.outstanding_paise
        else:
            aging["30_plus"] += inv.outstanding_paise

    customer_balances: dict[str, int] = defaultdict(int)
    for inv in invoices:
        if inv.outstanding_paise > 0:
            customer_balances[inv.customer.name] += inv.outstanding_paise

    payment_trend = []
    by_day: dict[str, int] = defaultdict(int)
    for t in txns:
        if t.status == "matched":
            by_day[t.transaction_date.isoformat()] += t.amount_paise
    for d, amt in sorted(by_day.items()):
        payment_trend.append({"date": d, "amount_paise": amt, "amount": format_inr(amt)})

    recent = list(
        db.scalars(
            select(AuditLog)
            .where(AuditLog.merchant_id == merchant_id)
            .order_by(AuditLog.id.desc())
            .limit(15)
        )
    )

    open_cases = len(
        list(
            db.scalars(
                select(CollectionCase).where(
                    CollectionCase.merchant_id == merchant_id,
                    CollectionCase.status.in_(["open", "promised", "escalated"]),
                )
            )
        )
    )
    pending_followups = len(
        list(
            db.scalars(
                select(FollowUp).where(
                    FollowUp.merchant_id == merchant_id, FollowUp.status == "pending"
                )
            )
        )
    )

    return {
        "total_invoices": len(invoices),
        "total_receivables_paise": total_receivables,
        "total_receivables": format_inr(total_receivables),
        "outstanding_paise": outstanding,
        "outstanding": format_inr(outstanding),
        "overdue_paise": overdue,
        "overdue": format_inr(overdue),
        "fully_paid": paid,
        "partially_paid": partial,
        "unpaid": unpaid,
        "pending_promises": promise_count,
        "pending_approvals": pending_approvals,
        "unmatched_transactions": unmatched,
        "open_collection_cases": open_cases,
        "pending_followups": pending_followups,
        "aging": {k: {"paise": v, "display": format_inr(v)} for k, v in aging.items()},
        "customer_balances": [
            {"customer": k, "outstanding_paise": v, "outstanding": format_inr(v)}
            for k, v in sorted(customer_balances.items(), key=lambda x: -x[1])
        ],
        "payment_trend": payment_trend,
        "recent_activity": [
            {
                "id": a.id,
                "action": a.action,
                "entity_type": a.entity_type,
                "entity_id": a.entity_id,
                "detail": a.detail,
                "actor": a.actor,
                "created_at": a.created_at.isoformat() if a.created_at else None,
            }
            for a in recent
        ],
        "has_active_promise_sample": pending_promises is not None,
    }
