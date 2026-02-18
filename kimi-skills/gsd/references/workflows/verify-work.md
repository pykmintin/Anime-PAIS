# Verify Work Workflow

Manual user acceptance testing — confirm the feature actually works as expected.

## Purpose

Automated verification checks that code exists and tests pass. But does the feature *work* the way you expected? This is your chance to use it.

## Process

### 1. Extract Testable Deliverables

From the phase plans and requirements, identify:
- What should the user be able to do now?
- What should they see/interact with?
- What should happen when they try X?

### 2. Walk Through Each Deliverable

Present one at a time:

```
"Can you log in with email?"
→ User tests: tries to log in
→ User responds: Yes / No / Here's what happened
```

### 3. Diagnose Failures

If something doesn't work:
- Spawn debug agents to find root cause
- Create verified fix plans
- Queue for re-execution

### 4. Create Fix Plans (if needed)

For each issue:
- Document the problem
- Root cause analysis
- Fix approach
- Verification steps

## Output Files

- `.planning/{phase}-UAT.md` — User acceptance test results
- `.planning/{phase}-FIX-{N}-PLAN.md` — Fix plans (if issues found)

## UAT Structure

```markdown
# Phase X User Acceptance Test

## Test Results

### Test 1: [Description]
**Expected:** What should happen
**Actual:** What user observed
**Status:** ✅ PASS / ❌ FAIL

### Test 2: [Description]
...

## Issues Found

### Issue 1: [Description]
**Symptom:** What user saw
**Likely Cause:** Debug agent analysis
**Fix Plan:** {phase}-FIX-1-PLAN.md

## Summary
- Tests passed: X
- Tests failed: Y
- Overall: PASS / NEEDS_FIX
```

## After This Workflow

**If all tests pass:**
- Update ROADMAP.md to mark phase complete
- User moves to next phase: "plan phase X+1"

**If issues found:**
- Run `/gsd:execute-phase X` again with fix plans
- Or say "execute phase X fixes"

## Philosophy

The user is the final arbiter of "does this work." Automated tests verify code correctness; user testing verifies the right thing was built.
