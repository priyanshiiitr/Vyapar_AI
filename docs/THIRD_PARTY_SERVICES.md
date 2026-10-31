# Third-party service evaluation

| Service | Purpose | Free plan | Card required? | Credentials? | Effort | Benefits | Limitations | Decision |
|---------|---------|-----------|----------------|--------------|--------|----------|-------------|----------|
| Sarvam AI | LLM + tool calling | Hackathon credits | No (credits) | Yes | Medium | Native Hindi/Hinglish + function calling | Needs key / network | **SELECTED** |
| SQLite | Ledger DB | Free local | No | No | Low | Offline durable demo | Single-machine | **SELECTED** |
| Inngest | Delayed follow-ups | Free 50k exec, no card | No | Optional | Medium | Durable delayed jobs | Needs account; Free pauses at quota | **SELECTED (optional)** |
| Langfuse | Agent traces | Hobby 50k units, no card | No | Optional | Low–Med | Debug tool loops for judges | Optional cloud | **SELECTED (optional)** |
| shadcn/ui patterns | UI speed | OSS | No | No | Low | Consistent UI | — | **SELECTED** |
| Recharts | Charts | OSS | No | No | Low | Live analytics | — | **SELECTED** |
| PapaParse | CSV preview | OSS | No | No | Low | Frontend preview | Not financial truth | **SELECTED** |
| Playwright | E2E tests | OSS local | No | No | Med | Demo regression | Install browsers | **SELECTED for tests** |
| Supabase | Hosted Postgres | Free 500MB | No for Free | Would need | Med | Hosted DB | Pauses after 1 week inactivity | **SKIPPED** (SQLite default) |
| Render | Hosting | Free web | No initially | Would need | Med | Public URL | Spin-down, ephemeral FS, Postgres expires 30d | **SKIPPED** (local first) |

## Fallbacks

- No Inngest → DB `FollowUps` + `/api/scheduler/process-due`
- No Langfuse → structured local logs (`vyapar.ai`)
- No Sarvam → ledger/CSV/approvals still work; AI returns clear error
- No Supabase/Render → intentional; local SQLite demo
