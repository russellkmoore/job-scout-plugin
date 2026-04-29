# Workday Fixture Provenance

Per D-4 (Phase 4 locked decision): wd5 fixture is live-verified; wd1 and wd3 fixtures are SYNTHETIC because live wd1/wd3 probes returned 422 during research. Parsing logic is identical across data centers (only URL components vary), so synthetic fixtures adequately exercise to_listing() field mapping + postedOn parsing.

| Fixture | Source | Date | Notes |
|---------|--------|------|-------|
| workday_wd5.json | Live probe: workday.wd5.myworkdayjobs.com/Workday, searchText="a", POST /wday/cxs/{tenant}/{site}/jobs | 2026-04-28 | Sliced to 2 representative jobs; sanitized — no real candidate PII captured |
| workday_synthetic_wd1.json | Synthetic — modeled on wd5 live shape | 2026-04-28 | wd1 live probes returned 422 during research; D-4 locked synthetic acceptable. "Posted Today" string exercises today-parsing branch |
| workday_synthetic_wd3.json | Synthetic — modeled on wd5 live shape | 2026-04-28 | Same rationale as wd1. "Posted 30+ Days Ago" exercises bounded-stale branch |

## Re-capture command (wd5 only)

```bash
curl -s -X POST 'https://workday.wd5.myworkdayjobs.com/wday/cxs/workday/Workday/jobs' \
  -H 'Content-Type: application/json' \
  -d '{"appliedFacets":{},"limit":20,"offset":0,"searchText":"a"}' | python3 -m json.tool > /tmp/wd5_full.json
```

Then slice to first 2 entries from `jobPostings` array, redact any candidate-identifying tokens that appear in `bulletFields`.

## Sanitization log

No redactions required — Workday public CXS endpoint returns no candidate-identifying data.
