# Search Configuration

## Candidate Profile Summary

Loaded from `candidate_profile.json` at runtime. The config below provides the search strategy framework — the candidate's actual data is injected from their setup files.

### Reality Check
This search system must be brutally honest about fit — no wishful thinking. Prioritize roles where:
- The candidate has LinkedIn connections at the company (this is the #1 predictor of getting an interview)
- The role matches their proven experience, not aspirational positioning
- The JD doesn't require credentials they don't have

## Search Queries

Run these in order. Adapt keywords based on the candidate's `candidate_profile.json` strongest skills.

### Query 1: Primary Sweet Spot
- **Keywords:** `VP technology [candidate's primary domain]`
- **Location:** Based on config.json preferences
- **Experience Level:** Director, Executive
- **Date Posted:** Past 24 hours (daily) / Past week (first run)

### Query 2: Engineering Leadership + Domain
- **Keywords:** `"director of engineering" OR "VP engineering" [candidate's domain] OR platform`
- **Location:** Based on config.json
- **Experience Level:** Director, Executive
- **Date Posted:** Past 24 hours (daily) / Past week (first run)
- **Note:** Use OR operators to broaden without losing relevance.

### Query 3: CTO at Growth Companies
- **Keywords:** `CTO [candidate's domain] OR SaaS OR platform`
- **Location:** Based on config.json
- **Experience Level:** Director, Executive
- **Date Posted:** Past 24 hours (daily) / Past week (first run)

### Query 4: Transformation / Modernization
- **Keywords:** `VP "digital transformation" OR "platform modernization" technology`
- **Location:** Based on config.json
- **Experience Level:** Director, Executive
- **Date Posted:** Past 24 hours (daily) / Past week (first run)

### Query 5: Domain Intersection
- **Keywords:** Build from candidate's credible + strongest skill intersections
- **Location:** Based on config.json
- **Experience Level:** Director, Executive
- **Date Posted:** Past 24 hours (daily) / Past week (first run)

### Query 6: Managed Services / Service Leadership
- **Keywords:** `VP "managed services" OR "service delivery" technology`
- **Location:** Based on config.json
- **Experience Level:** Director, Executive
- **Date Posted:** Past 24 hours (daily) / Past week (first run)

### Query 7: Target Companies (rotate 3-5 per day from master list)

**IMPORTANT:** Before running keyword searches, always check the Target Company list first:

1. Read `master_targets.csv` and select companies with the highest connection counts that haven't been checked recently
2. Also check any supplemental company lists the candidate provided during setup (pipeline spreadsheets, saved company lists, etc.)
3. For each target company, navigate directly to their LinkedIn company page → Jobs tab
4. Look for roles matching the candidate's target level

**Priority order for company-specific searches:**
1. Companies where the candidate has 3+ named connections (warm path = highest ROI)
2. Companies on any pipeline/target list the candidate provided
3. Domain-specific companies (commerce platforms, SaaS, etc.)
4. Underutilized asset companies (defense/intelligence if clearance, APAC if language skills, etc.)

### Query 8: Underutilized Asset Search
- **Keywords:** Based on candidate's `unique_differentiators` from profile
- **Location:** Broader (may include DC/Virginia for defense, international for language skills)
- **Experience Level:** Director, Executive
- **Date Posted:** Past week
- **Also suggest:** Specialized job boards if relevant (ClearanceJobs, AngelList, Built In, etc.)

## Stale Listing Detection

Before adding any job to the report, check:
- Has the candidate already applied to this company? (check master_targets.csv `already_applied` and `application_status`)
- Extract the LinkedIn job ID from the URL. IDs below 4,200,000,000 are likely 6+ months old → flag as stale
- Was the job posted more than 30 days ago? (likely stale/reposted)
- Has the job been reposted multiple times? (flag as potentially unrealistic expectations)
- If "Over 200 applicants" and posted weeks ago → deprioritize, window has likely passed

**Stale listings should NOT be scored or included in A/B tiers.** List them in a separate section.

## Scoring Rubric

| Category | Weight | What to evaluate |
|----------|--------|-----------------|
| **Connection Leverage** | 30 pts | Does the candidate have LinkedIn connections at this company? 1-2 connections = 15 pts. 3-5 = 20 pts. 6+ = 25 pts. Someone who could refer = 30 pts. No connections = 0 pts. THIS IS THE MOST IMPORTANT FACTOR. |
| **Experience Match** | 25 pts | Does the JD describe what the candidate has actually done? Deduct heavily if JD requires credentials they don't have. |
| **Domain Fit** | 20 pts | Is this in the candidate's industry sweet spot? |
| **Compensation** | 15 pts | Is total comp likely at or above their minimum? Full points if clearly above, partial if range includes it, zero if below. |
| **Realistic Shot** | 10 pts | Gut check: would this company actually interview this person? Consider competition level, credential screening, etc. |

### Bonus Points
- +10 warm introduction possible (named connection who could refer)
- +5 role mentions founder/startup/entrepreneurial experience as a plus
- +5 role mentions military veteran preference (if applicable)
- +5 company is on the candidate's target pipeline list
- +3 role involves building a team from scratch

### Penalty Points
- -15 requires PhD, elite MBA, or deep ML research background (unless candidate has these)
- -10 clearly individual contributor role with no leadership component
- -10 JD language suggests they want someone from FAANG/Big 3 consulting specifically
- -5 role has been reposted multiple times

### Match Tiers
- **A-tier (75-100):** Strong match + connection leverage — prioritize and tailor resume
- **B-tier (55-74):** Decent match — include in report, worth applying especially if connections exist
- **C-tier (40-54):** Stretch but possible — note in report briefly
- **Below 40:** Skip

**Hard cap:** Never more than 10 A-tier matches per run.

## Resume Tailoring Guidelines

When tailoring for A-tier matches, lead with what matches the JD. Generate specific, actionable briefs — not generic advice. See `references/tailoring-guide.md` for the full framework.

Key principle: every tailoring instruction should name a specific bullet, section, or phrase on the resume. "Emphasize your leadership" is never acceptable. "Move the $X revenue bullet to position 1 under the [Company] section" is.
