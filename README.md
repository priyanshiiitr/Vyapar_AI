# Paytm Vyapar AI

Autonomous AI teammate for SME receivables and collections (Paytm Build for India — Track 03).

**Design principle:** the model writes language and selects tools; the ledger establishes payment facts.

## Quick start (Windows)

1. Ensure Python 3.10+ and Node.js 20+ are installed.
2. Install backend packages:

```bat
cd backend
py -3 -m pip install -r requirements.txt --user
```

3. Copy env template and add your Sarvam key (already prepared locally if you followed the agent setup):

```bat
copy ..\.env.example .env
```

Edit `backend/.env` and set `SARVAM_API_KEY=` (do not paste keys into chat).

4. Optional: add Inngest and Langfuse keys (free, no credit card). See [docs/NO_CARD_SETUP_GUIDE.md](docs/NO_CARD_SETUP_GUIDE.md).

5. Install frontend:

```bat
cd ..\frontend
npm install
```

6. Launch both servers:

```bat
cd ..
start.bat
```

- Frontend: http://127.0.0.1:5173  
- Backend docs: http://127.0.0.1:8000/docs  

## Demo in 2 minutes

1. Open Overview → **Load demo data** (outstanding ₹33,000).
2. AI Teammate → ask “Analyze my overdue invoices.”
3. Collections → draft Hinglish reminder for R-104 → Approvals → approve (sandbox).
4. Record Friday promise for R-104.
5. Reconciliation → **Import TXN-803** → R-104 closes, reminders cancel.
6. Evaluation → **Run evaluation** for measured metrics.

Full script: [docs/DEMO_SCRIPT.md](docs/DEMO_SCRIPT.md)

## Stack

| Layer | Choice |
|-------|--------|
| Frontend | React, TypeScript, Vite, Tailwind, shadcn-style UI, Recharts, PapaParse, TanStack Query |
| Backend | FastAPI, Pydantic, SQLAlchemy, SQLite |
| AI | Sarvam AI `sarvam-105b` native function calling |
| Jobs | Inngest when configured + DB-backed scheduler fallback |
| Observability | Langfuse when configured + structured local logs |

## Tests

```bat
cd backend
set PYTHONPATH=.
py -3 -m pytest -q
```

## Important

- No production Paytm/bank integration — CSV evidence sandbox only.
- No real WhatsApp/SMS/email sending.
- Local app works without Inngest/Langfuse.
- Never commit `.env`.
