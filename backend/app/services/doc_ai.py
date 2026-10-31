"""Sarvam Document AI demo — extract invoice fields from PDF/photo."""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

from app.config import get_settings
from app.services.money import parse_amount_to_paise
from app.services.observability import structured_log

INVOICE_EXTRACT_SCHEMA = {
    "type": "object",
    "properties": {
        "invoice_id": {
            "type": "string",
            "description": "Invoice number or invoice ID printed on the document",
        },
        "customer_name": {
            "type": "string",
            "description": "Customer or buyer business name",
        },
        "customer_phone": {
            "type": "string",
            "description": "Customer phone number if present, else empty string",
        },
        "amount": {
            "type": "number",
            "description": "Invoice TOTAL / grand total in INR as a number (before subtracting payments)",
        },
        "amount_paid": {
            "type": "number",
            "description": "Payments already received / amount paid in INR if shown, else 0",
        },
        "balance_due": {
            "type": "number",
            "description": "BALANCE DUE / outstanding amount in INR if shown, else same as amount",
        },
        "invoice_date": {
            "type": "string",
            "description": "Invoice date in YYYY-MM-DD if possible",
        },
        "due_date": {
            "type": "string",
            "description": "Due date in YYYY-MM-DD if possible",
        },
        "description": {
            "type": "string",
            "description": "Short description of goods or services",
        },
    },
}

TERMINAL = {"completed", "partially_completed", "failed", "rejected"}


def extract_invoice_fields(
    *,
    filename: str,
    content: bytes,
    content_type: str | None = None,
    poll_seconds: float = 5.0,
    max_wait_seconds: float = 90.0,
) -> dict[str, Any]:
    settings = get_settings()
    if not settings.sarvam_configured:
        return {
            "ok": False,
            "error": "SARVAM_API_KEY missing. Document AI needs the same Sarvam credits as chat.",
        }

    mime = content_type or _guess_mime(filename)
    try:
        from sarvamai import SarvamAI

        client = SarvamAI(api_subscription_key=settings.SARVAM_API_KEY)
        # SDK expects a file-like object in a list of tuples
        import io

        bio = io.BytesIO(content)
        job = client.doc_ai.extract(
            file=[(filename, bio, mime)],
            schema=json.dumps(INVOICE_EXTRACT_SCHEMA),
            output_format="json",
        )
        job_id = job.job_id
        status = getattr(job, "status", "pending")
        started = time.time()
        while str(status).lower() not in TERMINAL:
            if time.time() - started > max_wait_seconds:
                return {
                    "ok": False,
                    "error": "Document AI timed out while polling. Try a smaller file.",
                    "job_id": job_id,
                    "status": status,
                }
            time.sleep(poll_seconds)
            st = client.doc_ai.get_status(job_id=job_id)
            status = st.status
            structured_log("doc_ai_poll", job_id=job_id, status=status)

        if str(status).lower() not in {"completed", "partially_completed"}:
            return {
                "ok": False,
                "error": f"Document AI job ended with status={status}",
                "job_id": job_id,
                "status": status,
            }

        results = client.doc_ai.get_results(job_id=job_id)
        raw = getattr(results, "result", None) or {}
        if hasattr(raw, "model_dump"):
            raw = raw.model_dump()
        elif not isinstance(raw, dict):
            raw = json.loads(json.dumps(raw, default=str))

        normalized = _normalize_extracted(raw)
        return {
            "ok": True,
            "job_id": job_id,
            "status": status,
            "raw": raw,
            "normalized": normalized,
            "note": (
                "Demo extraction only. Review fields before importing into the ledger. "
                "This uses Sarvam Document AI credits (per page)."
            ),
        }
    except Exception as exc:  # noqa: BLE001
        structured_log("doc_ai_error", error=str(exc), filename=filename)
        msg = str(exc)
        if "402" in msg or "quota" in msg.lower():
            msg = "Sarvam credits insufficient for Document AI (402). Chat may still work."
        return {"ok": False, "error": msg}


def _guess_mime(filename: str) -> str:
    ext = Path(filename).suffix.lower()
    return {
        ".pdf": "application/pdf",
        ".png": "image/png",
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".webp": "image/webp",
        ".tif": "image/tiff",
        ".tiff": "image/tiff",
    }.get(ext, "application/octet-stream")


def _money_fields(value: Any) -> tuple[Any, int | None, str | None]:
    if value is None or str(value).strip() == "":
        return None, None, None
    try:
        from app.services.money import format_inr

        paise = parse_amount_to_paise(str(value))
        return value, paise, format_inr(paise)
    except Exception:  # noqa: BLE001
        return value, None, None


def _normalize_extracted(raw: dict[str, Any]) -> dict[str, Any]:
    # Prefer nested result payloads if Doc AI wraps fields
    if isinstance(raw.get("extracted_data"), dict):
        raw = {**raw, **raw["extracted_data"]}
    if isinstance(raw.get("data"), dict) and not raw.get("invoice_id"):
        raw = {**raw, **raw["data"]}

    amount, amount_paise, amount_display = _money_fields(raw.get("amount"))
    amount_paid, amount_paid_paise, amount_paid_display = _money_fields(raw.get("amount_paid"))
    balance_due, balance_due_paise, balance_due_display = _money_fields(raw.get("balance_due"))

    # If balance shown but paid missing, derive paid from total - balance
    if (
        amount_paise is not None
        and balance_due_paise is not None
        and amount_paid_paise is None
        and balance_due_paise <= amount_paise
    ):
        amount_paid_paise = max(0, amount_paise - balance_due_paise)
        from app.services.money import format_inr

        amount_paid = amount_paid_paise / 100
        amount_paid_display = format_inr(amount_paid_paise)

    return {
        "invoice_id": (raw.get("invoice_id") or "").strip() or None,
        "customer_name": (raw.get("customer_name") or "").strip() or None,
        "customer_phone": (raw.get("customer_phone") or "").strip() or None,
        "amount": amount,
        "amount_paise": amount_paise,
        "amount_display": amount_display,
        "amount_paid": amount_paid,
        "amount_paid_paise": amount_paid_paise,
        "amount_paid_display": amount_paid_display,
        "balance_due": balance_due,
        "balance_due_paise": balance_due_paise,
        "balance_due_display": balance_due_display,
        "invoice_date": (raw.get("invoice_date") or "").strip() or None,
        "due_date": (raw.get("due_date") or "").strip() or None,
        "description": (raw.get("description") or "").strip() or None,
    }


def write_sample_invoice_pdf(path: Path) -> Path:
    """Write a minimal one-page demo invoice PDF (no extra deps)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    # Simple PDF with visible invoice text for Document AI / human demo
    lines = [
        "BT /F1 12 Tf 50 750 Td (PAYTM VYAPAR AI - DEMO INVOICE) Tj ET",
        "BT /F1 11 Tf 50 720 Td (Invoice ID: R-204) Tj ET",
        "BT /F1 11 Tf 50 700 Td (Customer: A.B.C. Stores) Tj ET",
        "BT /F1 11 Tf 50 680 Td (Phone: 9876543210) Tj ET",
        "BT /F1 11 Tf 50 660 Td (Amount: 12500.00 INR) Tj ET",
        "BT /F1 11 Tf 50 640 Td (Invoice Date: 2026-10-01) Tj ET",
        "BT /F1 11 Tf 50 620 Td (Due Date: 2026-10-15) Tj ET",
        "BT /F1 11 Tf 50 600 Td (Description: Grocery wholesale stock) Tj ET",
    ]
    content = "\n".join(lines) + "\n"
    objects = []
    objects.append("1 0 obj<< /Type /Catalog /Pages 2 0 R >>endobj\n")
    objects.append("2 0 obj<< /Type /Pages /Kids [3 0 R] /Count 1 >>endobj\n")
    objects.append(
        "3 0 obj<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
        "/Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>endobj\n"
    )
    objects.append(f"4 0 obj<< /Length {len(content)} >>stream\n{content}endstream\nendobj\n")
    objects.append("5 0 obj<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>endobj\n")

    pdf = ["%PDF-1.4\n"]
    offsets = [0]
    for obj in objects:
        offsets.append(sum(len(x.encode("latin-1")) for x in pdf))
        pdf.append(obj)
    xref_pos = sum(len(x.encode("latin-1")) for x in pdf)
    pdf.append(f"xref\n0 {len(objects) + 1}\n")
    pdf.append("0000000000 65535 f \n")
    for off in offsets[1:]:
        pdf.append(f"{off:010d} 00000 n \n")
    pdf.append(f"trailer<< /Size {len(objects) + 1} /Root 1 0 R >>\n")
    pdf.append(f"startxref\n{xref_pos}\n%%EOF\n")
    path.write_bytes("".join(pdf).encode("latin-1"))
    return path
