from __future__ import annotations

import json
from datetime import date, datetime, timedelta
from typing import Any, Callable

from pydantic import BaseModel, Field, ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.models import (
    AuditLog,
    CollectionCase,
    Customer,
    FollowUp,
    Invoice,
    Message,
    PaymentPromise,
    Transaction,
)
from app.services.collections import create_reminder_draft, list_pending_approvals, record_payment_promise
from app.services.dashboard import get_dashboard_summary
from app.services.money import format_inr
from app.services.reconciliation import run_reconciliation
from app.scheduler.service import list_followups, schedule_followup


class EmptyArgs(BaseModel):
    pass


class MinDaysArgs(BaseModel):
    minimum_days: int = Field(default=1, ge=0)


class ListInvoicesArgs(BaseModel):
    status: str | None = None
    search_query: str | None = None


class InvoiceIdArgs(BaseModel):
    invoice_id: str


class ReminderArgs(BaseModel):
    invoice_id: str
    language: str = "hinglish"
    tone: str = "polite"
    message_text: str | None = None


class PromiseArgs(BaseModel):
    invoice_id: str
    promise_date: str
    customer_statement: str = ""
    promised_amount: str | int | None = None


class FollowupArgs(BaseModel):
    invoice_id: str
    followup_date: str
    reason: str


class FlagArgs(BaseModel):
    record_id: str
    reason: str


class CustomerArgs(BaseModel):
    customer_id: str


class FollowupStatusArgs(BaseModel):
    status: str | None = None


def _parse_date(value: str) -> date:
    value = value.strip().lower()
    today = date.today()
    if value in ("friday", "this friday", "next friday"):
        # upcoming Friday (or today if Friday)
        days_ahead = (4 - today.weekday()) % 7
        if days_ahead == 0 and value.startswith("next"):
            days_ahead = 7
        if "next" in value and days_ahead == 0:
            days_ahead = 7
        return today + timedelta(days=days_ahead or 0)
    for fmt in ("%Y-%m-%d", "%d-%m-%Y", "%d/%m/%Y"):
        try:
            return datetime.strptime(value, fmt).date()
        except ValueError:
            continue
    raise ValueError(f"Could not parse date: {value}")


def _invoice_dict(inv: Invoice) -> dict:
    today = date.today()
    return {
        "invoice_id": inv.invoice_number,
        "customer": inv.customer.name if inv.customer else None,
        "customer_id": inv.customer_id,
        "amount": format_inr(inv.amount_paise),
        "amount_paise": inv.amount_paise,
        "paid": format_inr(inv.paid_paise),
        "outstanding": format_inr(inv.outstanding_paise),
        "outstanding_paise": inv.outstanding_paise,
        "status": inv.status,
        "due_date": inv.due_date.isoformat(),
        "days_overdue": max(0, (today - inv.due_date).days) if inv.outstanding_paise > 0 else 0,
        "description": inv.description,
    }


TOOL_SPECS: list[dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "get_dashboard_summary",
            "description": "Get merchant receivables KPIs, aging, and pending actions.",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_overdue_invoices",
            "description": "List overdue invoices with outstanding balance.",
            "parameters": {
                "type": "object",
                "properties": {
                    "minimum_days": {"type": "integer", "description": "Minimum days past due"}
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_invoices",
            "description": "List invoices filtered by status or search query.",
            "parameters": {
                "type": "object",
                "properties": {
                    "status": {"type": "string"},
                    "search_query": {"type": "string"},
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_invoice_details",
            "description": "Get detailed invoice, payments, and collection case.",
            "parameters": {
                "type": "object",
                "properties": {"invoice_id": {"type": "string"}},
                "required": ["invoice_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_unmatched_transactions",
            "description": "List unmatched, ambiguous, or overpayment transactions.",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "run_reconciliation",
            "description": "Run payment reconciliation for unmatched transactions.",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "create_reminder_draft",
            "description": "Create a customer reminder draft for merchant approval. Never invent fees or payment links.",
            "parameters": {
                "type": "object",
                "properties": {
                    "invoice_id": {"type": "string"},
                    "language": {"type": "string", "enum": ["hindi", "hinglish", "english"]},
                    "tone": {
                        "type": "string",
                        "enum": ["polite", "professional", "friendly", "firm"],
                    },
                    "message_text": {"type": "string"},
                },
                "required": ["invoice_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "record_payment_promise",
            "description": "Record a customer payment promise and schedule follow-up. Does not mark invoice paid.",
            "parameters": {
                "type": "object",
                "properties": {
                    "invoice_id": {"type": "string"},
                    "promise_date": {"type": "string"},
                    "customer_statement": {"type": "string"},
                    "promised_amount": {"type": "string"},
                },
                "required": ["invoice_id", "promise_date"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "schedule_followup",
            "description": "Schedule a follow-up task for an invoice.",
            "parameters": {
                "type": "object",
                "properties": {
                    "invoice_id": {"type": "string"},
                    "followup_date": {"type": "string"},
                    "reason": {"type": "string"},
                },
                "required": ["invoice_id", "followup_date", "reason"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_collection_case",
            "description": "Get collection case status for an invoice.",
            "parameters": {
                "type": "object",
                "properties": {"invoice_id": {"type": "string"}},
                "required": ["invoice_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_pending_approvals",
            "description": "List reminder drafts awaiting merchant approval.",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_activity_log",
            "description": "Get recent audit activity.",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "flag_for_human_review",
            "description": "Escalate a record for human review.",
            "parameters": {
                "type": "object",
                "properties": {
                    "record_id": {"type": "string"},
                    "reason": {"type": "string"},
                },
                "required": ["record_id", "reason"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_missed_promises",
            "description": "List payment promises that are past due and still active.",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_customer_history",
            "description": "Get invoices and promises for a customer (id or name).",
            "parameters": {
                "type": "object",
                "properties": {"customer_id": {"type": "string"}},
                "required": ["customer_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_followup_tasks",
            "description": "List follow-up tasks optionally filtered by status.",
            "parameters": {
                "type": "object",
                "properties": {"status": {"type": "string"}},
            },
        },
    },
]


def build_tool_handlers(db: Session, merchant_id: str) -> dict[str, Callable[[dict], Any]]:
    def get_dashboard_summary_tool(_: dict) -> Any:
        return get_dashboard_summary(db, merchant_id)

    def list_overdue_invoices_tool(args: dict) -> Any:
        parsed = MinDaysArgs.model_validate(args or {})
        today = date.today()
        rows = []
        for inv in db.scalars(
            select(Invoice)
            .options(joinedload(Invoice.customer))
            .where(Invoice.merchant_id == merchant_id)
        ).unique():
            if inv.outstanding_paise <= 0:
                continue
            days = (today - inv.due_date).days
            if days >= parsed.minimum_days:
                rows.append(_invoice_dict(inv))
        return {"count": len(rows), "invoices": rows}

    def list_invoices_tool(args: dict) -> Any:
        parsed = ListInvoicesArgs.model_validate(args or {})
        q = (
            select(Invoice)
            .options(joinedload(Invoice.customer))
            .where(Invoice.merchant_id == merchant_id)
        )
        invoices = list(db.scalars(q).unique())
        if parsed.status:
            invoices = [i for i in invoices if i.status == parsed.status]
        if parsed.search_query:
            s = parsed.search_query.lower()
            invoices = [
                i
                for i in invoices
                if s in i.invoice_number.lower()
                or s in (i.customer.name.lower() if i.customer else "")
            ]
        return {"count": len(invoices), "invoices": [_invoice_dict(i) for i in invoices]}

    def get_invoice_details_tool(args: dict) -> Any:
        parsed = InvoiceIdArgs.model_validate(args)
        inv = db.scalar(
            select(Invoice)
            .options(joinedload(Invoice.customer), joinedload(Invoice.collection_case))
            .where(Invoice.merchant_id == merchant_id, Invoice.invoice_number == parsed.invoice_id)
        )
        if not inv:
            return {"ok": False, "error": "Invoice not found"}
        matches = [
            {
                "transaction_pk": m.transaction_id,
                "allocated": format_inr(m.allocated_paise),
                "confidence": m.confidence,
                "reason": m.match_reason,
            }
            for m in inv.matches
        ]
        case = inv.collection_case
        return {
            "ok": True,
            "invoice": _invoice_dict(inv),
            "matches": matches,
            "collection_case": None
            if not case
            else {
                "id": case.id,
                "status": case.status,
                "outstanding": format_inr(case.outstanding_paise),
            },
        }

    def list_unmatched_transactions_tool(_: dict) -> Any:
        rows = []
        for t in db.scalars(
            select(Transaction).where(
                Transaction.merchant_id == merchant_id,
                Transaction.status.in_(["unmatched", "ambiguous", "overpayment"]),
            )
        ):
            rows.append(
                {
                    "transaction_id": t.transaction_id,
                    "reference": t.reference,
                    "amount": format_inr(t.amount_paise),
                    "status": t.status,
                    "customer_name": t.customer_name,
                    "date": t.transaction_date.isoformat(),
                    "evidence_source": t.evidence_source,
                }
            )
        return {"count": len(rows), "transactions": rows}

    def run_reconciliation_tool(_: dict) -> Any:
        return run_reconciliation(db, merchant_id)

    def create_reminder_draft_tool(args: dict) -> Any:
        parsed = ReminderArgs.model_validate(args)
        return create_reminder_draft(
            db,
            merchant_id=merchant_id,
            invoice_id=parsed.invoice_id,
            language=parsed.language,
            tone=parsed.tone,
            message_text=parsed.message_text,
        )

    def record_payment_promise_tool(args: dict) -> Any:
        parsed = PromiseArgs.model_validate(args)
        return record_payment_promise(
            db,
            merchant_id=merchant_id,
            invoice_id=parsed.invoice_id,
            promise_date=_parse_date(parsed.promise_date),
            customer_statement=parsed.customer_statement,
            promised_amount=parsed.promised_amount,
        )

    def schedule_followup_tool(args: dict) -> Any:
        parsed = FollowupArgs.model_validate(args)
        result = schedule_followup(
            db,
            merchant_id=merchant_id,
            invoice_id=parsed.invoice_id,
            followup_date=_parse_date(parsed.followup_date),
            reason=parsed.reason,
        )
        db.commit()
        return result

    def get_collection_case_tool(args: dict) -> Any:
        parsed = InvoiceIdArgs.model_validate(args)
        inv = db.scalar(
            select(Invoice).where(
                Invoice.merchant_id == merchant_id, Invoice.invoice_number == parsed.invoice_id
            )
        )
        if not inv:
            return {"ok": False, "error": "Invoice not found"}
        case = db.scalar(select(CollectionCase).where(CollectionCase.invoice_id == inv.id))
        if not case:
            return {"ok": True, "case": None}
        return {
            "ok": True,
            "case": {
                "id": case.id,
                "status": case.status,
                "outstanding": format_inr(case.outstanding_paise),
                "close_reason": case.close_reason,
            },
        }

    def get_pending_approvals_tool(_: dict) -> Any:
        return {"approvals": list_pending_approvals(db, merchant_id)}

    def get_activity_log_tool(_: dict) -> Any:
        rows = list(
            db.scalars(
                select(AuditLog)
                .where(AuditLog.merchant_id == merchant_id)
                .order_by(AuditLog.id.desc())
                .limit(25)
            )
        )
        return {
            "events": [
                {
                    "id": a.id,
                    "action": a.action,
                    "entity_type": a.entity_type,
                    "entity_id": a.entity_id,
                    "detail": a.detail,
                    "created_at": a.created_at.isoformat() if a.created_at else None,
                }
                for a in rows
            ]
        }

    def flag_for_human_review_tool(args: dict) -> Any:
        parsed = FlagArgs.model_validate(args)
        from app.services.audit import log_audit

        log_audit(
            db,
            merchant_id=merchant_id,
            entity_type="review",
            entity_id=parsed.record_id,
            action="flagged_for_human_review",
            detail=parsed.reason,
            actor="agent",
        )
        # escalate case if invoice-like
        inv = db.scalar(
            select(Invoice).where(
                Invoice.merchant_id == merchant_id, Invoice.invoice_number == parsed.record_id
            )
        )
        if inv and inv.collection_case:
            inv.collection_case.status = "escalated"
        db.commit()
        return {"ok": True, "record_id": parsed.record_id, "reason": parsed.reason}

    def get_missed_promises_tool(_: dict) -> Any:
        today = date.today()
        rows = []
        for p in db.scalars(
            select(PaymentPromise).where(
                PaymentPromise.merchant_id == merchant_id, PaymentPromise.status == "active"
            )
        ):
            if p.promise_date < today:
                inv = db.get(Invoice, p.invoice_id)
                rows.append(
                    {
                        "promise_id": p.id,
                        "invoice_id": inv.invoice_number if inv else None,
                        "promise_date": p.promise_date.isoformat(),
                        "promised": format_inr(p.promised_paise),
                        "statement": p.customer_statement,
                    }
                )
                p.status = "missed"
        db.commit()
        return {"count": len(rows), "missed_promises": rows}

    def get_customer_history_tool(args: dict) -> Any:
        parsed = CustomerArgs.model_validate(args)
        key = parsed.customer_id.strip()
        customer = None
        if key.isdigit():
            customer = db.get(Customer, int(key))
        if not customer:
            customer = db.scalar(
                select(Customer).where(
                    Customer.merchant_id == merchant_id, Customer.name.ilike(f"%{key}%")
                )
            )
        if not customer or customer.merchant_id != merchant_id:
            return {"ok": False, "error": "Customer not found"}
        invoices = list(
            db.scalars(
                select(Invoice)
                .options(joinedload(Invoice.customer))
                .where(Invoice.customer_id == customer.id)
            ).unique()
        )
        return {
            "ok": True,
            "customer": {
                "id": customer.id,
                "name": customer.name,
                "opted_out": customer.opted_out,
                "dispute_active": customer.dispute_active,
            },
            "invoices": [_invoice_dict(i) for i in invoices],
        }

    def get_followup_tasks_tool(args: dict) -> Any:
        parsed = FollowupStatusArgs.model_validate(args or {})
        return {"followups": list_followups(db, merchant_id, parsed.status)}

    return {
        "get_dashboard_summary": get_dashboard_summary_tool,
        "list_overdue_invoices": list_overdue_invoices_tool,
        "list_invoices": list_invoices_tool,
        "get_invoice_details": get_invoice_details_tool,
        "list_unmatched_transactions": list_unmatched_transactions_tool,
        "run_reconciliation": run_reconciliation_tool,
        "create_reminder_draft": create_reminder_draft_tool,
        "record_payment_promise": record_payment_promise_tool,
        "schedule_followup": schedule_followup_tool,
        "get_collection_case": get_collection_case_tool,
        "get_pending_approvals": get_pending_approvals_tool,
        "get_activity_log": get_activity_log_tool,
        "flag_for_human_review": flag_for_human_review_tool,
        "get_missed_promises": get_missed_promises_tool,
        "get_customer_history": get_customer_history_tool,
        "get_followup_tasks": get_followup_tasks_tool,
    }


ALLOWED_TOOLS = {spec["function"]["name"] for spec in TOOL_SPECS}


def execute_tool(db: Session, merchant_id: str, name: str, arguments: dict | str) -> dict:
    handlers = build_tool_handlers(db, merchant_id)
    if name not in handlers:
        return {"ok": False, "error": f"Tool '{name}' is not allowlisted"}
    if isinstance(arguments, str):
        try:
            arguments = json.loads(arguments or "{}")
        except json.JSONDecodeError:
            return {"ok": False, "error": "Invalid tool arguments JSON"}
    try:
        result = handlers[name](arguments or {})
        return {"ok": True, "tool": name, "result": result}
    except ValidationError as exc:
        return {"ok": False, "tool": name, "error": exc.errors()}
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "tool": name, "error": str(exc)}
