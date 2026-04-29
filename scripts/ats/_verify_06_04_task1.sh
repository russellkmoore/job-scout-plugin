#!/usr/bin/env bash
# _verify_06_04_task1.sh — acceptance checks for Plan 06-04 Task 1
# Exits 0 if all pass, 1 if any fail.

set -euo pipefail
SKILL="skills/scout-run/SKILL.md"
PASS=0
FAIL=0

check() {
    local desc="$1"
    local expected="$2"
    local actual="$3"
    local op="${4:-eq}"  # eq or ge
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

check "[ATS-PREVIEW] == 0" "0" "$(grep -c '\[ATS-PREVIEW\]' "$SKILL" || true)"
check "version: 0.4.0 == 1" "1" "$(grep -c '^version: 0.4.0' "$SKILL")"
check "Career page read directly == 0" "0" "$(grep -c 'Career page.*read directly' "$SKILL" || true)"
check "Items 1+2 deleted == 0" "0" "$(grep -cE '[12]\. \*\*Career page\*\*|[12]\. \*\*ATS board\*\*' "$SKILL" || true)"
check "f_C= >= 1" "1" "$(grep -c 'f_C=' "$SKILL")" "ge"
check "linkedin.com/jobs/search/ >= 1" "1" "$(grep -c 'linkedin.com/jobs/search/' "$SKILL")" "ge"
check "f_TPR=r604800 >= 1" "1" "$(grep -c 'f_TPR=r604800' "$SKILL")" "ge"
check "verified 2026-04-27 run >= 1" "1" "$(grep -c 'verified 2026-04-27 run' "$SKILL")" "ge"
check "ATS sourcing runs in Step 2.5 >= 1" "1" "$(grep -c 'ATS sourcing runs in \*\*Step 2.5\*\*' "$SKILL")" "ge"
check "ATS-first sourcing >= 1" "1" "$(grep -c 'ATS-first sourcing' "$SKILL")" "ge"
check "broad sourcing deleted == 0" "0" "$(grep -c 'broad sourcing across LinkedIn, career pages' "$SKILL" || true)"

echo ""
echo "Results: $PASS passed, $FAIL failed"
[ "$FAIL" -eq 0 ]
