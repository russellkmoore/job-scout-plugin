#!/usr/bin/env bash
# _verify_06_04_task2.sh — acceptance checks for Plan 06-04 Task 2
# Exits 0 if all pass, 1 if any fail.

set -euo pipefail
SKILL="skills/scout-run/SKILL.md"
PASS=0
FAIL=0

check() {
    local desc="$1"
    local expected="$2"
    local actual="$3"
    local op="${4:-eq}"
    if [ "$op" = "ge" ]; then
        if [ "$actual" -ge "$expected" ]; then
            echo "PASS: $desc ($actual)"
            PASS=$((PASS+1))
        else
            echo "FAIL: $desc (expected >=$expected, got $actual)"
            FAIL=$((FAIL+1))
        fi
    else
        if [ "$actual" = "$expected" ]; then
            echo "PASS: $desc ($actual)"
            PASS=$((PASS+1))
        else
            echo "FAIL: $desc (expected $expected, got $actual)"
            FAIL=$((FAIL+1))
        fi
    fi
}

check "ab_tier_counts >= 2" "2" "$(grep -c 'ab_tier_counts' "$SKILL")" "ge"
check "Run Summary >= 1" "1" "$(grep -c 'Run Summary' "$SKILL")" "ge"
check "## Step 7.5 == 1" "1" "$(grep -c '## Step 7.5' "$SKILL")"
check "post-run validation failed >= 1" "1" "$(grep -c 'post-run validation failed' "$SKILL")" "ge"
check "milestone-bar >= 2" "2" "$(grep -c 'milestone-bar' "$SKILL")" "ge"
check "tier == 'A' check >= 1" "1" "$(grep -c "tier.*==.*'A'" "$SKILL")" "ge"
check "Stdout summary mirror >= 1" "1" "$(grep -ci 'stdout summary mirror' "$SKILL")" "ge"
check "ATS-fetch only >= 1" "1" "$(grep -c 'ATS-fetch only' "$SKILL")" "ge"
check "C-tier listings are excluded >= 1" "1" "$(grep -c 'C-tier listings are excluded' "$SKILL")" "ge"
check "### Header == 1" "1" "$(grep -c '^### Header' "$SKILL")"
check "### A-tier == 1" "1" "$(grep -c '^### A-tier' "$SKILL")"
check "### B-tier == 1" "1" "$(grep -c '^### B-tier' "$SKILL")"
check "### C-tier == 1" "1" "$(grep -c '^### C-tier' "$SKILL")"
check "### Honest notes == 1" "1" "$(grep -c '^### Honest notes' "$SKILL")"
check "### ATS regression suspects == 1" "1" "$(grep -c '^### ATS regression suspects' "$SKILL")"
check "### Pass-2 board-broken warnings == 1" "1" "$(grep -c '^### Pass-2 board-broken warnings' "$SKILL")"
check "### Dedup decisions == 1" "1" "$(grep -c '^### Dedup decisions' "$SKILL")"
check "### Generate-on-demand packets == 1" "1" "$(grep -c '^### Generate-on-demand packets' "$SKILL")"
check "Counts: companies checked >= 1" "1" "$(grep -c 'Counts: companies checked' "$SKILL")" "ge"
check "greenhouse/lever/ashby/sr/workday/jsonld per-provider line >= 1" "1" "$(grep -c 'greenhouse=.*lever=.*ashby=.*smartrecruiters=.*workday=.*jsonld=' "$SKILL")" "ge"

echo ""
echo "Results: $PASS passed, $FAIL failed"
[ "$FAIL" -eq 0 ]
