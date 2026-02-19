# Plan Phase Workflow

Research + plan + verify for a phase. Creates executable plans that achieve phase goals.

## Output Files

- `.planning/{phase}-RESEARCH.md` — domain research findings
- `.planning/{phase}-{N}-PLAN.md` — executable task plans (2-3 tasks each)

## Process

### 1. Read Context

Load:
- `PROJECT.md` — project vision
- `REQUIREMENTS.md` — what's being built
- `ROADMAP.md` — phase description
- `{phase}-CONTEXT.md` — user decisions (if exists)

### 2. Research (Optional)

If enabled in config, spawn researchers:
- **Stack researcher**: Libraries, frameworks, tools
- **Pattern researcher**: Implementation approaches
- **Pitfall researcher**: Common mistakes to avoid

Research is guided by CONTEXT.md decisions.

### 3. Create Plans

Break phase into 2-3 atomic plans:

**Each plan should:**
- Be completable in a fresh context window
- Have clear dependencies
- Include verification steps
- Be parallelizable where possible

**Plan structure (PLAN.md):**
```markdown
# Plan X: [Name]

## Objective
What this plan achieves and why

## Context
@file references needed

## Tasks

### Task 1: [Name]
**Files:** `src/...`
**Action:**
- Step 1
- Step 2
**Verify:** How to confirm it works
**Done:** Success criteria

### Task 2: [Name]
...

## Dependencies
- Requires: Plan Y, Task Z
- Blocks: Plan A

## Success Criteria
- [ ] Criterion 1
- [ ] Criterion 2
```

### 4. Verify Plans

Check each plan against:
- Phase goals (does it achieve them?)
- Requirements (does it satisfy them?)
- Context decisions (does it honor them?)

If plans fail verification, revise and re-check.

## Plan Sizing

**Target:** Each plan completes within ~50% context usage

| Context Usage | Quality |
|---------------|---------|
| 0-30% | Peak — thorough, comprehensive |
| 30-50% | Good — confident, solid |
| 50-70% | Degrading — efficiency mode |
| 70%+ | Poor — rushed, minimal |

More plans with smaller scope = consistent quality.

## Dependency Analysis

Group plans into waves:

```
Wave 1 (parallel): Plans with no dependencies
Wave 2 (parallel): Plans depending on Wave 1
Wave 3 (parallel): Plans depending on Wave 2
...
```

**Vertical slices** (feature end-to-end) parallelize better than **horizontal layers** (all models, then all APIs).

## After This Workflow

User should run `/gsd execute-phase X` or say "execute phase X" to run the plans.
