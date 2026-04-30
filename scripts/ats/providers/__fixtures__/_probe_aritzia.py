#!/usr/bin/env python3
"""One-off probe for Aritzia Workday API. Captures a real response as a fixture
for the DSP-02 fix. Run via: python3 _probe_aritzia.py
"""
import httpx
import json
import os
import sys

URL = "https://aritzia.wd3.myworkdayjobs.com/wday/cxs/aritzia/External/jobs"
BODY = {"appliedFacets": {}, "limit": 20, "offset": 0, "searchText": ""}
HEADERS = {
    "Content-Type": "application/json",
    "Accept": "application/json",
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
}

OUT_DIR = os.path.dirname(os.path.abspath(__file__))
OUT_PATH = os.path.join(OUT_DIR, "aritzia_workday_sample.json")

try:
    resp = httpx.post(URL, json=BODY, headers=HEADERS, timeout=20.0)
except Exception as e:
    print(f"REQUEST FAILED: {type(e).__name__}: {e}", file=sys.stderr)
    sys.exit(1)

print(f"HTTP {resp.status_code}")
if resp.status_code != 200:
    print("Body (first 800 chars):", resp.text[:800])
    sys.exit(1)

data = resp.json()
with open(OUT_PATH, "w") as f:
    json.dump(data, f, indent=2)
print(f"Saved fixture to {OUT_PATH}")
print()

jobs = data.get("jobPostings") or data.get("jobs") or []
print(f"Total jobs in response: {len(jobs)} (response 'total' field: {data.get('total', '?')})")
if not jobs:
    print("No jobs in response — top-level keys:", list(data.keys()))
    sys.exit(0)

j0 = jobs[0]
print()
print("First job KEYS:", list(j0.keys()))
print()
print("First job (formatted):")
for k, v in j0.items():
    vs = str(v)[:150]
    print(f"  {k!r}: {vs}")
print()

# Hunt for date-shaped fields across first 3 jobs
import re
DATE_PAT = re.compile(r"(post|date|day|time|start|since|created|updated)", re.I)
print("Date-shaped fields across first 3 jobs:")
for j in jobs[:3]:
    title = (j.get("title") or "?")[:50]
    print(f"  {title}:")
    for k, v in j.items():
        if DATE_PAT.search(k):
            print(f"    {k}: {v!r}")
