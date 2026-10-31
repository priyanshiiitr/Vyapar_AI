from app.services.matching import name_similarity, select_fuzzy_auto_match


class FakeCustomer:
    def __init__(self, name: str):
        self.name = name


class FakeInvoice:
    def __init__(self, id: int, number: str, name: str, amount: int, outstanding: int):
        self.id = id
        self.invoice_number = number
        self.customer = FakeCustomer(name)
        self.amount_paise = amount
        self.outstanding_paise = outstanding


def test_abc_stores_fuzzy_score_is_high():
    score = name_similarity("ABC Stores", "A.B.C. Store")
    assert score >= 85


def test_fuzzy_auto_match_requires_exact_amount():
    invoices = [
        FakeInvoice(1, "R-204", "ABC Stores", 1_250_000, 1_250_000),
        FakeInvoice(2, "R-205", "XYZ Traders", 4_000_000, 4_000_000),
    ]
    winner, ranked, reason = select_fuzzy_auto_match(
        txn_customer_name="A.B.C. Store",
        txn_amount_paise=1_250_000,
        invoices=invoices,
    )
    assert winner is not None
    assert winner.invoice_number == "R-204"
    assert "fuzzy_name" in reason

    winner2, _, reason2 = select_fuzzy_auto_match(
        txn_customer_name="A.B.C. Store",
        txn_amount_paise=999_000,  # not exact
        invoices=invoices,
    )
    assert winner2 is None
    assert "amount_not_exact" in reason2
