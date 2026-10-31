# Hackathon demo script (reproducible)

Prereq: `start.bat` running; Sarvam key in `backend/.env`.

Voice browse: teal mic (bottom-right) → English/Hindi → speak or type → edit transcript → Run.  
Navigation is allowlisted only. Reminder/promise drafts need Confirm. Chrome/Edge recommended for Web Speech.

1. Open http://127.0.0.1:5173 — Overview.  
2. Click **Load demo data**.  
3. Confirm outstanding **₹33,000.00** (3 invoices: paid 1 / partial 1 / unpaid 1).  
4. Go to **AI Teammate**. Ask: `Analyze my overdue invoices.`  
5. Show tool cards (`get_dashboard_summary`, `list_overdue_invoices`, …).  
6. Ask: `Prepare a Hinglish reminder for invoice R-104.`  
7. Open **Approvals** — edit if needed — **Approve → WhatsApp mock**.  
8. Phone UI opens: green bubble = merchant reminder (sandbox).  
   - Promise (“I will pay tomorrow” / “2 days later”) → **auto-records payment promise** + follow-up (no manual Record button).  
   - “I already paid” → escalates; use **+** to upload screenshot (evidence only); close only via CSV match.  
   - Refusal (“Okay I cannot pay it”) → **auto-escalates to merchant**; see **Collections → Merchant escalations**.  
9. **Collections** → confirm promise / escalation / follow-up appeared automatically.  
 
10. Show promise + pending follow-up.  
11. **Reconciliation** → **Import TXN-803 (demo)**.  
12. Confirm TXN-803 matched to R-104.  
13. **Invoices**: R-104 outstanding ₹0 / paid.  
14. **Collections**: case closed; pending reminders/follow-ups cancelled.  
15. Overview refreshes to lower outstanding.  
16. **Activity Log** shows match + close + cancel events.  
17. **Evaluation** → **Run evaluation** — show measured metrics with numerators/denominators (Faker en_IN corpus).  
18. **Settings** — show Sarvam / Inngest / Langfuse configured.  
19. **Reconciliation** → **Complex GST overdue PDF** → **Extract invoice fields** → review total ₹25,000 / paid ₹10,000 / balance ₹15,000 → **Confirm → create ledger invoice** (opens overdue case).  
20. Mention RapidFuzz: messy names like `A.B.C. Store` can auto-match when amount is exact; otherwise human review.

Reset anytime: load demo again (idempotent reset+seed).
