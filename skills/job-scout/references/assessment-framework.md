# Assessment Framework

How to generate an honest career assessment during setup. This runs once after profile extraction and produces a candid analysis of the candidate's positioning.

## Purpose

The assessment tells the candidate where they actually stand in the market — not where they wish they stood. It identifies their sweet spot roles, stretch roles, underutilized assets, and market challenges. It should be useful, not cruel.

## Assessment Structure

### 1. Profile Summary (1 paragraph)
Summarize who this person is in market terms. Not a resume summary — a positioning statement.

Example: "You're a 15-year technology executive with deep SaaS platform experience, a track record of leading 100+ person orgs, and a career gap that recruiters will question. Your strongest positioning is as a VP/CTO at a mid-market software company, not at FAANG where credential screening will filter you."

### 2. Sweet Spot Roles
Roles where the candidate's experience, connections, and market position align. These are the roles they should spend 60%+ of their application effort on.

Criteria for sweet spot:
- Experience directly matches 80%+ of typical JD requirements
- Companies at this level don't have extreme credential screening
- Compensation range is realistic for this level/company size
- The candidate has connections or warm paths into some of these companies

### 3. Stretch Roles
Roles the candidate could potentially land but where there's a meaningful gap. They should apply selectively — only when there's a connection or unique angle.

Criteria for stretch:
- Experience matches 50-70% of requirements
- Gap is identifiable but not disqualifying
- Would need a strong referral or unique differentiator to get past screening

### 4. Underutilized Assets
Skills, experiences, or credentials the candidate has that they're not leveraging in their current search strategy. These often open doors the candidate hasn't considered.

Common underutilized assets:
- Security clearances (open defense/intelligence sector)
- Language skills (open international roles, specific-country companies)
- Founder experience (valued at startups/growth companies, sometimes underplayed)
- Industry-specific knowledge that transfers to adjacent sectors
- Board/advisory experience
- Published work, patents, speaking history

### 5. Market Challenges
Honest assessment of what's working against the candidate. These should be specific and actionable — not just "the market is tough."

Common challenges to assess:
- **Consulting gaps:** 2+ years of solo consulting reads as "unemployed" to some recruiters. Longer gaps amplify this.
- **Technology depreciation:** Skills that were hot 5-10 years ago but have been superseded. Note the specific technologies and what's replaced them.
- **Credential bias:** No top-tier MBA/MS in a market where competitors have one. Be honest about which companies/roles care about this.
- **Competition:** Who else is applying for the same roles? Displaced FAANG leaders with fresher big-company experience? Consultants from McKinsey/BCG? Be specific.
- **Resume positioning:** Is the resume trying to be too many things? Does it lead with the wrong experience for target roles?
- **Network gaps:** Lots of connections but few at target companies? Senior connections but in the wrong industry?

### 6. Recommended Paths (3-5)
Concrete strategies the candidate should consider. Each path should include:
- What roles to target
- What changes to make (resume, network, credentials)
- Realistic timeline
- Why this path makes sense given their profile

## Tone Calibration

The assessment style is set in `config.json → assessment_style`:

### Honest (Default)
Direct and specific. Names the problems. Doesn't sugarcoat but isn't cruel.

Example: "Your consulting gap is the #1 barrier. Recruiters see '2021-present: Solo Consulting' and assume you couldn't find a full-time role. This isn't fair, but it's reality. You need to either position the consulting work with named clients and specific outcomes, or lean into companies that value entrepreneurial experience."

### Balanced
Still identifies issues but frames them more diplomatically. Slightly softer on delivery.

Example: "The transition from consulting back to full-time will require careful positioning. Companies may have questions about the consulting period — having strong client references and specific project outcomes ready will help address this."

### Encouraging
Focuses more on strengths while still noting areas for improvement. Appropriate for candidates who are already demoralized and need momentum.

Example: "Your consulting work shows strong client relationships and real outcomes. For the full-time transition, let's make sure those client stories are front and center so hiring managers see the depth of work you've been doing."

## What Good Assessments Look Like

**Good:** "You're competing against displaced VP-level leaders from major tech companies who have 3-5 years of recent big-company experience. Your career gap means you can't match their 'currently managing 500-person org' claims. Your edge is domain-specific expertise and founder experience — lean into companies that value depth over brand."

**Bad:** "The market is very competitive right now and you should keep applying!" (Not actionable, not specific, sycophantic)

**Bad:** "You don't have the right credentials for any of these roles and should probably lower your expectations significantly." (Cruel, not constructive, no paths forward)

**Good:** "Your security clearance is a differentiator that almost none of your competitors have. Defense and intelligence sector technology leadership roles pay well and have far less competition from FAANG refugees. This is your strongest non-obvious path."

**Bad:** "Have you considered government work?" (Vague, dismissive)

## Process

1. Read the full candidate_profile.json
2. Read config.json for preferences and targets
3. Read master_targets.csv for network analysis
4. Compare stated targets against actual profile
5. Identify the gaps between where they're applying and where they're competitive
6. Write the assessment following the structure above
7. Present to the candidate and ask for feedback
8. Incorporate feedback — the candidate often knows things the profile doesn't capture

## Important Rules

- Never tell someone to give up or leave their field entirely unless the data overwhelmingly supports it AND you can suggest a concrete alternative
- Always provide at least 3 actionable paths forward
- Be specific about timelines — "This will take 6-12 months" is more useful than "be patient"
- If the candidate's salary expectations are unrealistic for their profile, say so with data
- If the candidate is applying for roles well above their market position, quantify the gap
- Acknowledge that the job market has structural problems (credential bias, ageism, algorithm filtering) — it's not always the candidate's fault
