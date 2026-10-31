# Architecture

```
Merchant UI (React)
    │ HTTP /api
FastAPI
    ├─ Ledger services (paise math, CSV, reconcile, cases)
    ├─ Collections (draft → approve → sandbox)
    ├─ Scheduler (DB + optional Inngest)
    ├─ Agent (Sarvam-105b tool loop)
    └─ Evaluation harness
         │
      SQLite (source of truth)
```

## Four stages

1. **INGEST** — invoice/transaction CSV uploads with validation + upload batch audit  
2. **RECONCILE** — exact unique invoice reference → high-confidence auto-match; else human review  
3. **TAKE ACTION** — reminder drafts, promises, follow-ups (human approval for messages)  
4. **CLOSE LOOP** — verified payment allocates, outstanding→0 closes case, cancels reminders/follow-ups  

## Safety rules

- Integer **paise** only for money.
- Agent tools are allowlisted; cannot mutate amounts or force-pay invoices.
- Customer claims do not close invoices; CSV match evidence does.
- Sandbox messaging never leaves the machine.
