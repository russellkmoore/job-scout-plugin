# Profile Extraction Guide

How to read a candidate's resume and LinkedIn data export, then produce a structured candidate_profile.json. This runs during `/scout-setup`.

## Input Sources

### Resume (PDF or DOCX)
The primary source of truth. Read using the Read tool.

Extract:
- Job titles and companies with dates
- Quantified accomplishments (revenue, team size, P&L, scale metrics)
- Technologies and platforms mentioned
- Education and certifications
- Summary/headline positioning

### LinkedIn Data Export (ZIP)
Optional but recommended. Contains CSVs that supplement the resume.

Key files inside the ZIP:
- `Profile.csv` — headline, summary, location
- `Positions.csv` — work history (may have entries not on resume)
- `Skills.csv` — endorsed skills (shows what peers validate)
- `Connections.csv` — full connection list (processed by mine_connections.py)
- `Education.csv` — degrees and schools
- `Certifications.csv` — professional certifications

### User Questionnaire Answers
From the setup questionnaire. Fills gaps the resume doesn't answer:
- Where they've gotten interviews (reveals true positioning)
- Where they've been rejected (reveals where market says no)
- Self-identified weaknesses
- Target compensation and location preferences

## Extraction Process

### Step 1: Parse the Resume

Read the PDF/DOCX and extract structured data:

```
For each work experience entry:
  - title: exact title held
  - company: company name
  - years: start-end or start-present
  - type: classify as executive/founder/senior_ic/solo_consulting/management/early_career
  - notable: 2-3 most impressive quantified accomplishments
```

**Classification rules for experience.type:**
| Type | Criteria |
|------|----------|
| executive | C-suite, VP, SVP, EVP, or equivalent at company with 100+ employees |
| founder | Founded or co-founded a company |
| senior_ic | Principal, Distinguished, Staff, Fellow — no direct reports |
| solo_consulting | Independent consultant, freelancer, own LLC with no employees |
| management | Director, Senior Manager, Manager with direct reports |
| early_career | First 5 years of career |

### Step 2: Categorize Skills

This is the most important step for honest scoring. Divide all mentioned skills into three buckets:

**Strongest** — Skills where the resume shows clear, quantified outcomes:
- "Led migration of $2B platform to microservices" → platform architecture is STRONGEST
- "Grew team from 20 to 200" → team scaling is STRONGEST
- "P&L responsibility for $30M business unit" → P&L management is STRONGEST

**Credible** — Skills the candidate has used but without headline-level outcomes:
- "Implemented AI-driven recommendation engine" → AI is CREDIBLE (not strongest unless outcomes are shown)
- "AWS certified, managed cloud infrastructure" → cloud architecture is CREDIBLE
- "Led digital transformation initiative" → digital transformation is CREDIBLE

**Aspirational** — Skills the candidate lists or implies but the resume doesn't substantiate:
- Claims "AI strategy" but no AI-specific outcomes or roles → ASPIRATIONAL
- Lists "data science" in skills but no data science work in experience → ASPIRATIONAL
- Summary says "thought leader in X" but no speaking/publishing/outcomes in X → ASPIRATIONAL

**Why this matters:** The scoring engine penalizes roles that require aspirational skills as core requirements. Honest skill categorization prevents the scout from recommending roles the candidate can't substantiate in an interview.

### Step 3: Identify Unique Differentiators

Look for things that make this candidate stand out from typical applicants:
- Security clearances (TS/SCI, Secret, etc.)
- Language skills (especially non-European languages)
- Founder/exit experience
- Specific industry depth that transfers
- Military background
- Patents, publications, speaking history
- Board or advisory positions
- IPO/M&A experience
- International work experience

### Step 4: Assess Education & Credential Gaps

Be honest about credential screening:

- Top-tier MBA (Harvard, Stanford, Wharton, etc.) → note as strong credential
- MBA from state/mid-tier school → note that this satisfies "MBA required" but won't impress credential-conscious companies
- No MBA → note that some companies will screen on this
- Non-elite undergrad → note if this creates bias at certain companies
- Online/non-traditional degree → be honest about perception while noting it doesn't reflect actual capability
- Certifications → note which are industry-recognized vs. vendor-specific

Write a `credential_gap_note` that's honest: "No MBA from a top-tier institution. This creates screening bias at prestige-conscious companies like McKinsey, Goldman, and FAANG leadership roles."

### Step 5: Determine Positioning

Based on all the above, identify:

**Sweet spot roles:** Where experience + connections + market position align. These are the roles the candidate should prioritize. Maximum 3-5.

**Stretch roles:** Where the candidate could land with a strong referral or unique angle, but there's a meaningful gap. Maximum 2-3.

**Underutilized assets:** Skills or credentials that open doors the candidate hasn't considered. Maximum 2-3.

**Market challenges:** Honest assessment of what's working against them. Maximum 3-5. Be specific — "the market is tough" is not a market challenge.

### Step 6: Network Analysis

If LinkedIn data is available:

1. Count total connections
2. Calculate percentage in senior leadership (Director+, VP+, C-suite)
3. Identify top companies by connection count
4. Cross-reference with target companies from the pipeline
5. Identify industries where the candidate has the strongest network

## Output Schema

Write the completed candidate_profile.json following the template in `templates/candidate_profile.json`. Every field must be populated — use empty strings or arrays for missing data, not null.

## Quality Checks

Before saving candidate_profile.json:

1. **Skills categorization is honest** — aspirational skills are not in the strongest bucket
2. **Positioning is realistic** — sweet spot roles match proven experience, not aspirations
3. **Market challenges are specific** — each one names a concrete barrier, not a platitude
4. **Differentiators are real** — only include things substantiated by the resume or LinkedIn data
5. **Credential gap note exists** — even if the candidate has strong credentials, note what's relevant
6. **Experience entries have quantified accomplishments** — if a role has no numbers, note this as a resume gap
