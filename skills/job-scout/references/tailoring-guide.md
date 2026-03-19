# Tailoring Guide

How to generate ATS-focused tailoring briefs for A-tier matches. These are specific, actionable resume changes — not generic advice and not full rewrites.

## What a Tailoring Brief IS

A tailoring brief tells the candidate exactly what to change on their resume for a specific role:
- Which keywords to add and where
- Which bullets to reorder
- Which section to lead with
- What to emphasize vs. de-emphasize

## What a Tailoring Brief IS NOT

- A full resume rewrite
- Generic advice ("emphasize your leadership experience")
- A list of skills to add that the candidate doesn't have
- Keyword stuffing instructions

## Step 1: Extract Keywords from the JD

Read the full job description and extract:

1. **Hard requirements** — technologies, certifications, specific experiences mentioned as "required"
2. **Soft requirements** — skills mentioned as "preferred" or "nice to have"
3. **Action verbs** — what the company says the person will "do" (build, scale, lead, transform, optimize)
4. **Domain terms** — industry-specific language the company uses
5. **Cultural signals** — words that indicate what kind of person they want (entrepreneurial, data-driven, collaborative)

## Step 2: Compare Against the Resume

For each extracted keyword:
1. Is this term (or a close synonym) already on the candidate's resume?
2. If yes: note where it appears and whether it's prominent enough
3. If no: does the candidate have this skill/experience? (check candidate_profile.json)
   - If they have it but it's not on the resume: recommend adding it
   - If they don't have it: do NOT recommend adding it (that's fabrication)

## Step 3: Generate the Brief

Structure the brief as 3-5 specific changes:

### ATS Keywords to Add
List terms from the JD that the candidate legitimately possesses but their resume doesn't currently contain. Format: comma-separated, ready to inject.

Example:
> **Add:** composable commerce, headless architecture, microservices migration, CI/CD pipeline optimization, OKR framework

### Section to Lead With
Based on the role type, recommend which resume section should come first after the header:

| Role Type | Lead With |
|-----------|-----------|
| Executive/VP at large company | Enterprise-scale experience section with team size and P&L |
| Startup/growth CTO | Founder experience and buildout accomplishments |
| Consulting/advisory | Client portfolio and engagement outcomes |
| Technical leadership | Platform/architecture achievements with scale metrics |
| Managed services | Operational metrics, SLA performance, cost optimization |
| AI/digital transformation | Transformation outcomes with revenue/efficiency impact |

### Bullet Reordering
Identify 2-3 existing resume bullets that should be promoted to the top of their respective sections. Be specific:

Good: "Move the bullet about $50M annual revenue to position 1 under that role"
Bad: "Emphasize revenue impact"

Good: "Promote the bullet about leading 150-person org through M&A integration to position 1 under the previous employer section"
Bad: "Highlight team leadership"

### Specific Wording Changes
If the JD uses particular phrasing the candidate should mirror:

Good: "The JD says 'digital-first transformation' — your resume says 'digital modernization.' Change to match their language."
Bad: "Use similar wording to the job description"

## Quality Checks

Before finalizing a tailoring brief, verify:

1. **Every recommended keyword addition is legitimate** — the candidate actually has this skill or experience
2. **No fabrication** — never recommend adding experience the candidate doesn't have
3. **Specificity** — every instruction references a specific bullet, section, or phrase on the resume
4. **Actionable** — the candidate can implement every change in under 15 minutes
5. **ATS-safe** — keywords are woven into natural language, not listed as a keyword block

## Anti-Patterns

Reject these patterns in tailoring briefs:

| Anti-Pattern | Why It's Bad |
|-------------|-------------|
| "Add a skills section with these keywords" | Keyword blocks are ATS-detectable and look unprofessional |
| "Rewrite your summary to emphasize X" | Too vague — what specific words to change? |
| "Add experience in [technology you don't know]" | Fabrication — will be caught in interviews |
| "Make your resume more relevant" | Not actionable |
| "Tailor your resume for this role" | This IS the tailoring — be specific |

## Example: Full Tailoring Brief

**Role:** VP Technology, E-Commerce — Acme Corp
**Score:** 82/100 (A-tier)

**ATS Keywords to Add:** composable commerce, headless CMS, MACH architecture, progressive web apps, conversion rate optimization, A/B testing at scale

**Lead With:** Enterprise platform section — Acme is mid-market scaling up, they want someone who's done it at larger scale

**Bullet Reordering:**
1. Under most recent role: Move "$50M annual revenue platform" bullet to position 1 (JD emphasizes revenue scale)
2. Under consulting section: Move the B2B commerce platform buildout bullet above the AI strategy bullet (they care about commerce execution first)
3. Under enterprise role: Promote the 150-person team leadership bullet (JD mentions "scaling engineering teams")

**Wording Changes:**
- Resume says "platform modernization" → JD says "platform transformation" — match their language
- Resume says "AI/ML optimization" → JD says "data-driven optimization" — use their framing, it's broader and more honest
- Add "composable commerce" to the platform description (legitimate — this is what they built)
