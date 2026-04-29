# Greenhouse fixture — provenance

**Source URL:** `https://boards-api.greenhouse.io/v1/boards/airbnb/jobs?content=true`
**Captured:** 2026-04-29
**Public board:** Airbnb (a public Greenhouse customer; their job board is publicly indexed and intended for third-party scraping per Greenhouse's published API contract — research/STACK.md HIGH confidence)
**Slice:** First 3 jobs from the response (full response was 224 jobs at capture time; slice is plenty for the canonical Listing shape exercise)

## Sanitization log

Greenhouse's public Job Board API (`boards-api.greenhouse.io/v1/boards/{slug}/jobs`)
is documented as containing only public-facing job postings — there are no
internal recruiter notes or candidate PII in the response shape. The slice
captured here was checked field-by-field; no redactions were necessary.

The `metadata` array contains only public-facing job-listing labels
("Workplace Type", "Is this job part of ACC?") with no employee or candidate
identifiers. `internal_job_id` is a numeric Greenhouse-internal ID with no
PII; left intact for fixture realism. `data_compliance` is GDPR boilerplate.

If a future re-capture surfaces non-public fields (e.g., internal `metadata`
entries with employee IDs), redact them in this file by replacing the value
with `"REDACTED"` and add a row to the table below.

| Field path | Original value | Replacement | Reason |
|-----------|---------------|-------------|--------|
| (none — fixture as captured) | | | |

## How to re-capture

```bash
curl -sS -H "User-Agent: job-scout/0.4 (+claude-code-plugin)" \
  "https://boards-api.greenhouse.io/v1/boards/airbnb/jobs?content=true" \
  | python3 -c "
import json, sys
data = json.load(sys.stdin)
sliced = {
    'jobs': data.get('jobs', [])[:3],
    'meta': {'total': len(data.get('jobs', [])), 'fixture_slice': 3},
}
print(json.dumps(sliced, indent=2, ensure_ascii=False))
" > tests/fixtures/ats/greenhouse/airbnb.json
```

Then re-run the smoke-test from `.planning/phases/02-provider-protocol-greenhouse-dispatcher-observability/02-02-greenhouse-PLAN.md` to confirm the new shape still parses.

## Why airbnb specifically

- Public Greenhouse customer (verified live by research/STACK.md probe 2026-04-27 — 221 jobs returned; recaptured 2026-04-29 — 224 jobs)
- Large response → wide variety of job shapes (full-time/intern/contract, remote/onsite, multiple departments, multiple locations)
- Stable customer (unlikely to migrate ATS overnight; if they do, re-capture against another HIGH-confidence Greenhouse customer like `stripe` or `figma`)
