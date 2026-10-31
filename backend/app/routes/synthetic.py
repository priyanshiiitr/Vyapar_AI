from fastapi import APIRouter
from fastapi.responses import PlainTextResponse

from app.services.synthetic import build_faker_corpus

router = APIRouter(prefix="/synthetic")


@router.get("/preview")
def preview(count: int = 10):
    corpus = build_faker_corpus(max(5, min(count, 60)))
    return {
        "source": "faker_en_IN",
        "invoice_count": len(corpus["invoices"]),
        "transaction_count": len(corpus["transactions"]),
        "sample_invoices": corpus["invoices"][:5],
        "sample_transactions": corpus["transactions"][:5],
        "note": "Names/phones generated with Faker en_IN. Noisy names test RapidFuzz matching.",
    }


@router.get("/invoices.csv")
def invoices_csv():
    corpus = build_faker_corpus(40)
    return PlainTextResponse(corpus["invoice_csv"], media_type="text/csv")


@router.get("/transactions.csv")
def transactions_csv():
    corpus = build_faker_corpus(40)
    return PlainTextResponse(corpus["transaction_csv"], media_type="text/csv")
