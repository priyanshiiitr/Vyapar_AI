# Environment variables

File location: `backend/.env` (gitignored). Template: `.env.example`.

| Variable | Required? | Purpose | Where to get it | Features that need it |
|----------|-----------|---------|-----------------|------------------------|
| `SARVAM_API_KEY` | Yes for AI | Auth to Sarvam Chat Completions | Sarvam dashboard API keys | AI Teammate tool calling |
| `SARVAM_CHAT_MODEL` | No (default `sarvam-105b`) | Model id | Docs | AI Teammate |
| `SARVAM_TIMEOUT_SECONDS` | No (60) | Client timeout hint | — | AI Teammate |
| `SARVAM_MAX_TOKENS` | No (4096) | Max completion tokens | — | AI Teammate |
| `DATABASE_URL` | No | SQLAlchemy URL | Local default SQLite | Entire app |
| `APP_ENV` | No | Environment label | — | Logging |
| `CORS_ORIGINS` | No | Allowed frontend origins | — | Browser API calls |
| `DEMO_MERCHANT_ID` | No | Demo tenant id | — | Demo seed |
| `INNGEST_EVENT_KEY` | No | Send Inngest events | Inngest app keys | Cloud follow-up events |
| `INNGEST_SIGNING_KEY` | No | Verify Inngest requests | Inngest app keys | Inngest serve endpoint |
| `INNGEST_DEV` | No (1) | Dev mode flag | — | Local Inngest |
| `LANGFUSE_PUBLIC_KEY` | No | Langfuse project public key | Langfuse project settings | Trace export |
| `LANGFUSE_SECRET_KEY` | No | Langfuse secret | Langfuse project settings | Trace export |
| `LANGFUSE_HOST` | No | Langfuse API host | Default cloud URL | Trace export |

Without optional keys, the app uses SQLite + local scheduler + local structured logs.
