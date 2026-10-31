# Evaluation metrics (Track 03)

We do **not** invent Paytm’s unpublished weights. Metrics are computed from labelled synthetic runs.

| Metric | Formula | Target |
|--------|---------|--------|
| Payment-match precision | correct auto matches / all auto matches × 100 | ≥ 95% |
| False payment closures | invoices marked paid without match evidence | 0 |
| Correct next-action rate | correct labelled exception actions / scenarios × 100 | ≥ 90% |
| Time per case | median ms in harness | ≤ 5000 ms |
| Workflow completion | successful demo workflow / attempted × 100 | ≥ 90% |
| Tool reliability | successful tool runs / attempts × 100 | ≥ 95% |
| Human escalation quality | correct escalations / escalation scenarios × 100 | ≥ 90% |

Corpus: ~60 invoices, ~60 transactions, ~40 exception scenarios.

UI shows **TARGET** vs **MEASURED**, plus numerator/denominator. `N/A` when not measurable.
