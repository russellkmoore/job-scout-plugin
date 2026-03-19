# Scoring Rubric

Score every job listing against the candidate's actual profile using these 5 weighted categories. Weights are configurable in config.json but must sum to 100.

## Category 1: Connection Leverage (default 30 pts)

The single most important factor. Having a connection who can refer you is the #1 predictor of getting an interview.

| Points | Criteria |
|--------|----------|
| 30 | 3+ connections at the company, at least one senior enough to refer |
| 25 | 2+ connections, or 1 senior connection (Director+) |
| 20 | 1 connection at the company (any level) |
| 15 | No direct connections but warm path exists (mutual connection, shared alumni, industry contact) |
| 5 | Company is on the candidate's target list with some research done |
| 0 | No connections, no warm path, cold apply only |

**How to check:** Look up the company in master_targets.csv. Check `linkedin_connection_count` and `connection_names`. If connection_count > 0, also check if any named connections hold Director+ titles.

**Why this matters:** Cold applications at senior levels have a callback rate under 3%. With a referral, it jumps to 15-30%. Spending time on cold applications for stretch roles is usually wasted effort.

## Category 2: Experience Match (default 25 pts)

Does the JD describe what the candidate has actually done? Not what they want to do — what they've done.

| Points | Criteria |
|--------|----------|
| 25 | JD reads like the candidate's resume — 80%+ of requirements match proven experience |
| 20 | Strong match on core requirements, minor gaps on 1-2 nice-to-haves |
| 15 | Good match on 60-70% of requirements, some stretching needed |
| 10 | Matches on maybe half — candidate could do the job but resume doesn't prove it |
| 5 | Significant gaps — would need to heavily reframe experience |
| 0 | Fundamental mismatch — different career track entirely |

**Automatic deductions:**
- JD says "PhD required" and candidate has no PhD: -10
- JD says "MBA from top-tier program" and candidate doesn't have one: -8
- JD requires deep ML/AI research experience and candidate's AI experience is applied/strategic: -8
- JD requires Big 3/4 consulting background: -5
- JD requires specific technology the candidate has never used (named by version/platform): -3 per technology

**Automatic bonuses:**
- Candidate has done the exact role at a similar company: +5
- JD mentions building a team/function from scratch and candidate has done this: +3

## Category 3: Domain Fit (default 20 pts)

Is this in the candidate's industry/vertical sweet spot?

| Points | Criteria |
|--------|----------|
| 20 | Exact industry match — candidate has deep experience here |
| 15 | Adjacent industry — transferable and the company would see the connection |
| 10 | Related industry — candidate could make the case with effort |
| 5 | Different industry — candidate has some transferable skills |
| 0 | Complete mismatch — healthcare, biotech, finance when candidate is tech/commerce |

**How to assess:** Compare the company's industry against `config.json → preferences.industries_preferred` and the candidate's `candidate_profile.json → experience` entries.

## Category 4: Compensation (default 15 pts)

Does the listed (or estimated) compensation meet the candidate's minimum?

| Points | Criteria |
|--------|----------|
| 15 | Compensation range clearly exceeds the candidate's minimum |
| 12 | Top of range meets or slightly exceeds minimum |
| 8 | Range overlaps with minimum (candidate would be at the high end) |
| 4 | Compensation is below minimum but within 15% (negotiable) |
| 0 | Compensation is 20%+ below minimum or not listed at all at a company unlikely to pay at target |

**Notes:**
- Compare against `config.json → preferences.salary_minimum` and `salary_type`
- If no compensation listed: estimate based on company size, location, title level
- For startups, consider equity — note this in match notes but don't give full points for speculative equity

## Category 5: Realistic Shot (default 10 pts)

Honest gut check: would this company actually interview the candidate?

| Points | Criteria |
|--------|----------|
| 10 | Very likely — profile matches, reasonable company, no red flags |
| 7 | Probable — minor concerns but not disqualifying |
| 5 | Coin flip — could go either way depending on the hiring manager |
| 3 | Unlikely — significant barriers (credential bias, competitor preference, etc.) |
| 0 | Near zero — prestige company with known screening bias, or role clearly targets a different profile |

**Factors that reduce realistic shot:**
- FAANG/big tech with known credential screening (Stanford/MIT preference)
- JD language like "world-class" or "best in their field" signals looking for pedigree
- Company has been reposting the role for months (suggests very specific candidate in mind)
- Role requires specific regulatory/compliance experience the candidate doesn't have
- 200+ applicants already on the posting

**Factors that increase realistic shot:**
- Mid-market company that values execution over pedigree
- Startup/growth-stage that values founder experience
- Company has veteran hiring programs (for candidates with military background)
- Role has been open a while with low applicant count (urgency helps non-traditional candidates)

## Bonus/Penalty Adjustments

Apply after the base score. These are additive.

| Adjustment | Points | Trigger |
|------------|--------|---------|
| Warm introduction possible | +10 | Connection who can actively refer, not just a name in the system |
| Founder/startup experience valued | +5 | JD explicitly mentions entrepreneurial background |
| Military veteran preference | +5 | Company has veteran hiring programs or JD mentions military experience |
| Company on Target Pipeline | +5 | Company exists in master_targets.csv with pipeline_tier 1-3 |
| Role involves building team from scratch | +3 | JD describes greenfield team/function buildout |
| Requires PhD or elite MBA | -15 | "PhD required" or "MBA from top program required" |
| Clearly IC role | -10 | Senior IC with no team management despite executive title |
| Targets FAANG/Big 3 specifically | -10 | JD language clearly seeking Big Tech or McKinsey/BCG/Bain alumni |
| Reposted multiple times | -5 | Same role appears with different posting dates or "reposted" tag |
| Below minimum compensation | -5 | Comp range is clearly below candidate's minimum |

## Tier Thresholds

Configurable in config.json:

| Tier | Score Range | Action |
|------|-------------|--------|
| A | 75-100 (default) | Generate tailoring brief, prioritize application |
| B | 55-74 (default) | Include in report with notes |
| C | 40-54 | Mention briefly in report |
| Skip | Below 40 | Do not include |

**Hard cap:** Never produce more than 10 A-tier matches in a single run. If scoring yields more, raise the A-tier threshold by 5 until the count is 10 or fewer. Too many "top matches" dilutes focus.

## Scoring Examples

### Example 1: Strong Match
- Role: VP Technology at mid-market e-commerce company
- Connections: 2 at the company (1 Director-level)
- Experience: JD describes platform modernization, team scaling, P&L — all proven
- Domain: E-commerce / SaaS
- Comp: $280K-$350K (above minimum)
- Realistic: Mid-market company, execution-focused culture
- **Score:** 25 + 22 + 18 + 15 + 8 = 88 (A-tier)

### Example 2: Stretch Role
- Role: Director of AI Strategy at FAANG company
- Connections: 0
- Experience: AI experience is strategic not research, lacks FAANG pedigree
- Domain: Tech — adjacent
- Comp: $350K+ (above minimum)
- Realistic: Known credential screening, 400+ applicants
- **Score:** 0 + 10 + 15 + 15 + 1 - 10 = 31 (Skip)

### Example 3: Hidden Gem
- Role: CTO at Korean tech company expanding to US
- Connections: 1 (former colleague now there)
- Experience: Tech leadership matches, international experience
- Domain: Commerce/tech — fits
- Comp: Not listed but likely competitive
- Realistic: Korean language skill is a huge differentiator
- **Score:** 20 + 18 + 16 + 8 + 9 + 5 (veteran) = 76 (A-tier)
