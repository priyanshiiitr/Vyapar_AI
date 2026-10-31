from app.services.voice_intent import interpret_voice_command, normalize_route


def test_allowlisted_navigation_english():
    r = interpret_voice_command("Open reconciliation")
    assert r["action"] == "navigate"
    assert r["route"] == "/reconciliation"


def test_allowlisted_navigation_hinglish():
    r = interpret_voice_command("Collections page kholo")
    assert r["action"] == "navigate"
    assert r["route"] == "/collections"


def test_overview_alias():
    assert normalize_route("/overview") == "/"
    r = interpret_voice_command("Go to overview")
    assert r["action"] == "navigate"
    assert r["route"] == "/"


def test_reject_arbitrary_url():
    assert normalize_route("https://evil.example") is None
    assert normalize_route("/admin") is None


def test_sensitive_needs_confirmation():
    r = interpret_voice_command("Prepare a Hinglish reminder for invoice R-104")
    assert r["action"] == "needs_confirmation"
    assert r["requires_confirmation"] is True


def test_sensitive_confirmed_becomes_agent():
    r = interpret_voice_command(
        "Prepare a Hinglish reminder for invoice R-104", confirmed=True
    )
    assert r["action"] == "agent_query"


def test_read_query_goes_to_agent():
    r = interpret_voice_command("Show me overdue invoices")
    assert r["action"] == "agent_query"
