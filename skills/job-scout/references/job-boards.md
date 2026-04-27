# Job Board Reference

Pass 2 of `/scout-run` casts a wider net beyond LinkedIn. These boards each have different signal profiles — use them in combination, not as redundancies.

Each section tells you: **the URL pattern, the right filter, what to grab from a listing, and known parsing gotchas.** Stick to the spec. Do not invent search URLs.

---

## 1. Wellfound (formerly AngelList Talent)

**Why it matters for this candidate:** Founder/early-stage VP Eng and Director roles, equity-heavy. Strong fit for the "underutilized assets" positioning (founder experience, 0-to-1 builder).

**Search URL pattern:**
```
https://wellfound.com/jobs?role=engineering-manager&role=vp-engineering&role=cto&remote=true
```

**Filters to apply:**
- Role: VP of Engineering, Engineering Manager, CTO, Director of Engineering
- Remote: yes (or US-remote)
- Company size: Seed, Series A, Series B (skip late-stage growth — comp drops off)
- Equity: included (Wellfound shows equity %)

**What to extract per listing:**
- Company name + Wellfound company page URL
- Stage (Seed / Series A / etc.)
- Comp range AND equity range (Wellfound is unusual in showing both)
- Founder names — try to match against `connection_names` in `master_targets.csv`

**Parsing gotchas:**
- Wellfound listings often need login to view full JD. If the page text returned by `get_page_text` cuts off mid-description, prompt the user to log in via Claude in Chrome and retry.
- "Active" badge on listings is a real freshness signal — use it.

**When to skip Wellfound:**
- Candidate's salary minimum is firm and the company is pre-revenue.

---

## 2. Built In Seattle

**Why it matters:** Local Seattle/Pacific Northwest tech curation. Higher hit rate than LinkedIn for Seattle-area Director/VP roles because LinkedIn buries them under generic national hits.

**Search URL pattern:**
```
https://builtin.com/jobs/seattle/dev-engineering?experience=expert&job=executive
```

**Filters to apply:**
- Experience level: Expert (10+ years) or Executive
- Category: Dev + Engineering, Operations, Product
- Job type: Director, VP, Head of, Chief

**What to extract per listing:**
- Company + Built In company profile URL (companies often have richer Built In profiles than LinkedIn pages — use these for `what_they_do` in `master_targets.csv`)
- Comp range (Built In requires comp transparency for WA listings — these are reliable)
- Tech stack tags (Built In tags every listing — use for ATS keyword extraction)

**Parsing gotchas:**
- Built In has location filters that include "Remote in WA" — this catches US-remote roles open to WA residents that LinkedIn often misses.
- The "Apply" button often redirects to the company's ATS — capture the final URL, not the Built In one, for `Job URL` in the tracker.

**When to skip Built In Seattle:**
- Candidate is targeting roles outside the PNW with no Seattle anchor.

---

## 3. Hacker News "Who is Hiring" (monthly thread)

**Why it matters:** First business day of every month, a moderator (`whoishiring`) posts a thread. High signal for technical leadership at smaller, technically-rigorous companies. Comments are unstructured, so parsing matters.

**URL pattern (current month):**
```
https://hn.algolia.com/?dateRange=pastMonth&query=Ask+HN%3A+Who+is+hiring%3F&sort=byDate&type=story
```
Pick the most recent thread. Then read the actual thread:
```
https://news.ycombinator.com/item?id=<thread_id>
```

**How to parse:**
- Each top-level comment is one company posting.
- First line typically reads: `Acme Corp | Senior/Staff Engineer, VP Eng | Remote (US) | Full-Time | $200-280k`
- Look for keywords: `VP`, `Director`, `Head of`, `CTO`, `Chief Architect`, `Engineering Manager`
- Filter for `REMOTE`, `Remote (US)`, `WFH`, or candidate's location.

**What to extract per match:**
- Company name (from first line)
- Role title (also first line)
- Comp (often listed inline)
- Apply URL (usually a `mailto:` or company careers page link in the comment body)
- Free-form description — use this verbatim as `Match Notes`

**Parsing gotchas:**
- HN posters use inconsistent formats. If first-line parsing fails, fall back to keyword-scanning the whole comment.
- Comments edited days after posting still appear — don't double-count if a company posts in two consecutive monthly threads.

**When to skip HN Who is Hiring:**
- Last thread is more than 5 weeks old (means the new one hasn't dropped yet — re-check).

---

## 4. Y Combinator — Work at a Startup

**Why it matters:** YC portfolio companies, often 0-to-1 leadership roles where founder/builder positioning wins. Curated, no spam.

**URL pattern:**
```
https://www.workatastartup.com/jobs?role_types=eng_manager&role_types=eng_director&remote=yes
```

**Filters to apply:**
- Role types: Eng Manager, Eng Director, VP Eng, CTO/Founder
- Remote: yes (or specific timezone)
- Company stage: any (YC ranges from Seed to public)

**What to extract per listing:**
- YC batch (e.g., `W24`, `S23`) — proxy for company stage
- Comp + equity range (similar to Wellfound)
- Founder bio links — high warm-path-discovery value (small founder pool, often shared connections)

**Parsing gotchas:**
- Requires YC login for full JDs. If `get_page_text` returns a teaser only, surface to the user that they need to log in.
- "Closed" listings can linger in search results — check the "Apply" button is active before adding to tracker.

**When to skip YC Work at a Startup:**
- Candidate has hard deal-breaker on equity-heavy compensation.

---

## Cross-board deduplication

The same role may appear on multiple boards. Dedup logic:

1. Normalize company name (strip Inc/LLC, lowercase) AND
2. Compare role title fuzzy (e.g., "VP Eng" ≈ "VP of Engineering" ≈ "Vice President, Engineering")

If a match is found, prefer the listing with the most direct apply URL (company ATS > Built In > Wellfound > LinkedIn).

---

## Per-board signal quality (rough ranking, for budget allocation)

| Board | Signal/listing | Volume/run | Recommended budget |
|---|---|---|---|
| Company career pages (Pass 1) | Highest | Medium | 60% |
| Built In Seattle (Pass 2) | High | Low–medium | 8% |
| Wellfound (Pass 2) | High | Medium | 7% |
| YC Work at a Startup (Pass 2) | High | Low | 5% |
| HN Who is Hiring (Pass 2, monthly) | Medium–high | Variable | 5% |
| LinkedIn keyword search (Pass 3) | Medium–low | High | 15% |

The budget percentages map to the `max_listings_per_run` cap in `config.json` — if the cap is 50, Pass 1 can produce up to ~30 listings, Pass 2 ~12, Pass 3 ~8.
