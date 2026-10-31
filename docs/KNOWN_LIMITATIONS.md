# Known limitations

- Not a production Paytm Payments / bank feed integration — CSV sandbox evidence only.
- No real WhatsApp, SMS, or email delivery.
- Single demo merchant tenant for the hackathon UI.
- Inngest Free pauses at monthly quota; DB scheduler remains available.
- Langfuse Hobby has monthly unit limits; local logs always work.
- Free Supabase/Render hosting intentionally not used (pause / expiry / ephemeral disk risks).
- Sarvam outages block AI chat only; ledger workflows continue.
- Playwright E2E requires a separate browser install (`npx playwright install`) when you run UI tests.
