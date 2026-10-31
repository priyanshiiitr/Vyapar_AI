"""Faker (en_IN) synthetic invoice/transaction generators for demos and evaluation."""

from __future__ import annotations

import csv
import io
from datetime import date, timedelta
from typing import Any

from faker import Faker

fake = Faker("en_IN")
Faker.seed(42)


def _business_name() -> str:
    # Mix company-style and store-style Indian SME names
    patterns = [
        lambda: f"{fake.last_name()} Stores",
        lambda: f"{fake.last_name()} Traders",
        lambda: f"{fake.last_name()} Mart",
        lambda: f"{fake.company()}",
        lambda: f"{fake.last_name()} & Sons",
        lambda: f"{fake.city()} Wholesale",
    ]
    return fake.random_element(patterns)()


def generate_invoice_rows(count: int = 60, *, today: date | None = None) -> list[dict[str, Any]]:
    today = today or date.today()
    rows = []
    for i in range(1, count + 1):
        name = _business_name()
        amount = fake.random_int(min=2500, max=85000)
        inv_date = today - timedelta(days=fake.random_int(min=5, max=40))
        due = inv_date + timedelta(days=fake.random_int(min=7, max=21))
        rows.append(
            {
                "invoice_id": f"F-{1000 + i}",
                "customer_name": name,
                "customer_phone": fake.numerify("9#########"),
                "amount": amount,
                "invoice_date": inv_date.isoformat(),
                "due_date": due.isoformat(),
                "description": fake.sentence(nb_words=6),
            }
        )
    return rows


def generate_transaction_rows(
    invoices: list[dict[str, Any]],
    *,
    today: date | None = None,
) -> list[dict[str, Any]]:
    """Create matching txns with occasional fuzzy/noisy names for RapidFuzz demos."""
    today = today or date.today()
    rows = []
    for i, inv in enumerate(invoices, start=1):
        name = inv["customer_name"]
        # Every 5th: noisy spelling / punctuation for fuzzy matching demos
        if i % 5 == 0:
            noisy = name.replace(" ", ".").replace("Stores", "Store").replace("Traders", "Trader")
            if noisy == name:
                noisy = f"{name} Pvt"
            name = noisy
        # Every 4th: partial payment
        amount = inv["amount"] // 2 if i % 4 == 0 else inv["amount"]
        # Every 7th: missing reference (forces name/fuzzy path)
        reference = "" if i % 7 == 0 else inv["invoice_id"]
        rows.append(
            {
                "transaction_id": f"FTX-{i}",
                "reference": reference,
                "amount": amount,
                "transaction_date": today.isoformat(),
                "customer_name": name,
                "notes": "faker_synthetic",
                "label_correct_auto": bool(reference) or i % 5 != 0,
            }
        )
    return rows


def rows_to_csv(rows: list[dict[str, Any]], fieldnames: list[str]) -> str:
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=fieldnames, extrasaction="ignore")
    writer.writeheader()
    for row in rows:
        writer.writerow(row)
    return buf.getvalue()


def build_faker_corpus(invoice_count: int = 60) -> dict[str, Any]:
    invoices = generate_invoice_rows(invoice_count)
    transactions = generate_transaction_rows(invoices)
    return {
        "invoices": invoices,
        "transactions": transactions,
        "invoice_csv": rows_to_csv(
            invoices,
            [
                "invoice_id",
                "customer_name",
                "customer_phone",
                "amount",
                "invoice_date",
                "due_date",
                "description",
            ],
        ),
        "transaction_csv": rows_to_csv(
            transactions,
            [
                "transaction_id",
                "reference",
                "amount",
                "transaction_date",
                "customer_name",
                "notes",
            ],
        ),
    }
