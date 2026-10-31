# No-credit-card setup guide (beginner)

You only need accounts for services this project actually uses:

1. **Sarvam AI** (required for the AI Teammate)
2. **Inngest** (optional — delayed follow-ups in the cloud)
3. **Langfuse** (optional — AI tracing dashboard)

SQLite is built-in. Supabase and Render are **not required**.

**Never paste secret API keys into chat or GitHub.** Put them only in `backend/.env`.

---

## SERVICE: SARVAM AI (required for chat)

### What it is
Indian LLM provider. We use model `sarvam-105b` with native function calling so the agent can call ledger tools.

### Why we use it
Hackathon credits from Paytm. Primary AI brain for Vyapar AI.

### Links
- Docs: https://docs.sarvam.ai/
- Quickstart: https://docs.sarvam.ai/api/getting-started/quickstart
- Dashboard: use the Sarvam / Paytm hackathon dashboard where your credits were issued

### Credit card?
Use your **free hackathon credits**. Do not buy paid plans.

### Steps
1. Open the Sarvam dashboard linked from your Paytm hackathon email / portal.
2. Sign in with the same account that received credits.
3. Open **API Keys** (or Developers → API Keys).
4. Create a key (or copy an existing one).
5. Copy the key value once. It usually starts with something like `sk_...`.
6. On your PC, open the file: `E:\Vyapar_AI\backend\.env`
7. Find the line `SARVAM_API_KEY=`
8. Paste the key after the `=` with no spaces.
9. Save the file.
10. Restart the backend window (Ctrl+C, then run uvicorn again, or re-run `start.bat`).
11. Open the app → **Settings**. Sarvam should show **Configured**.
12. Open **AI Teammate**, ask: `Show me overdue invoices.`
13. Success = real tool cards appear (`list_overdue_invoices`, etc.) and an answer that matches the ledger.
14. If you see “SARVAM_API_KEY is not configured”, the `.env` path or restart is wrong.
15. If you see 401/403, regenerate the key in the dashboard and update `.env`.
16. If Sarvam is down, invoices/reconciliation/approvals still work; only AI chat fails gracefully.

Other Sarvam variables (usually leave defaults):

```
SARVAM_CHAT_MODEL=sarvam-105b
SARVAM_TIMEOUT_SECONDS=60
SARVAM_MAX_TOKENS=4096
```

---

## SERVICE: INNGEST (optional)

### What it is
Background job / durable workflow platform for delayed follow-ups.

### Why we use it
Can schedule promise-date follow-ups with retries. **Every follow-up is still saved in SQLite.** If Inngest keys are missing, the local “Process due follow-ups now” button and DB scheduler still work.

### Links
- Site: https://www.inngest.com/
- Docs: https://www.inngest.com/docs
- Pricing: https://www.inngest.com/pricing

### Free plan (verified from official pricing)
- Free: $0 / month
- **No credit card required**
- ~50,000 executions / month, 5 seats, 5 concurrent steps
- When free quota is hit, executions pause (no surprise card charge on Free)

### Steps
1. Open https://www.inngest.com/pricing and click **Start Free**.
2. Create an account (GitHub/email). Do **not** enter a card. Stay on Free.
3. Create or open an app named something like `vyapar-ai`.
4. Open **Manage** → **Keys** (or Settings → Keys).
5. Copy the **Event Key** → paste into `backend/.env` as `INNGEST_EVENT_KEY=`
6. Copy the **Signing Key** → paste as `INNGEST_SIGNING_KEY=`
7. Keep `INNGEST_DEV=1` for local development.
8. Restart backend.
9. Open **Settings** in the app — Inngest should show **Configured**.
10. Record a payment promise; a follow-up row may show an `inngest_event_id`.
11. If keys are wrong, the app falls back to the DB scheduler automatically.
12. To disable: clear the two keys in `.env` and restart.

### Key types
- **Event Key** — used to *send* events into Inngest (keep secret).
- **Signing Key** — used so Inngest can *verify* requests to your app (keep secret).

---

## SERVICE: LANGFUSE (optional)

### What it is
AI observability: traces of model calls and tool runs.

### Why we use it
Helps debug agent tool loops for the hackathon. If unset, Vyapar writes structured local logs instead.

### Links
- Site: https://langfuse.com/
- Docs: https://langfuse.com/docs
- Pricing: https://langfuse.com/pricing

### Free plan (verified)
- Hobby: free
- **No credit card required**
- 50k units / month, 30 days data, 2 users

### Steps
1. Open https://langfuse.com/pricing → sign up for **Hobby**.
2. Do **not** enter a card.
3. Create a project, e.g. `vyapar-ai`.
4. Open project **Settings** → **API Keys**.
5. Create keys.
6. Copy **Public Key** → `LANGFUSE_PUBLIC_KEY=` in `backend/.env`
7. Copy **Secret Key** → `LANGFUSE_SECRET_KEY=` in `backend/.env`
8. Leave `LANGFUSE_HOST=https://cloud.langfuse.com` unless you self-host.
9. Restart backend.
10. Use AI Teammate once.
11. Success = a new trace appears in the Langfuse project (phones are redacted).
12. If Langfuse is down, local logs continue; ledger is unaffected.
13. To disable: clear the two keys and restart.

### Key types
- **Public key** — identifies the project (still don’t commit it).
- **Secret key** — full access to send traces (never share publicly).

---

## What you do NOT need

| Service | Why skipped for accounts |
|---------|--------------------------|
| Supabase | SQLite is default and reliable offline; free cloud pauses after inactivity |
| Render | Free web spins down; free Postgres expires in 30 days; local demo is safer |

---

## Checklist after setup

- [ ] `SARVAM_API_KEY` in `backend/.env`
- [ ] (Optional) Inngest event + signing keys
- [ ] (Optional) Langfuse public + secret keys
- [ ] Backend restarted
- [ ] Settings page shows expected statuses
- [ ] AI Teammate returns real tool executions
