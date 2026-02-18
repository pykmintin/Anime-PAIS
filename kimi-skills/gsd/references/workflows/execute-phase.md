# Execute Phase Workflow

Execute all plans in parallel waves with clean contexts and atomic commits.

## Process

### 1. Load Plans

Read all `{phase}-{N}-PLAN.md` files for the phase.

### 2. Build Dependency Graph

Analyze dependencies between plans:
- Independent plans → Same wave
- Dependent plans → Later waves
- File conflicts → Sequential or same plan

### 3. Execute Waves

For each wave:

**Parallel Execution:**
- Spawn executor agents for each plan
- Each gets fresh 200k context
- No accumulated garbage from previous work

**Sequential Within Plan:**
- Tasks within a plan run in order
- Each task gets atomic git commit

### 4. Commit Per Task

Every task gets its own commit immediately after completion:

```bash
abc123f docs(08-02): complete user registration plan
def456g feat(08-02): add email confirmation flow
hij789k feat(08-02): implement password hashing
```

Benefits:
- Git bisect finds exact failing task
- Each task independently revertable
- Clear history for future sessions

### 5. Verify Results

After all waves complete:
- Check deliverables against plan success criteria
- Run any automated tests
- Update STATE.md with progress

## Wave Execution Example

```
PHASE EXECUTION

WAVE 1 (parallel)          WAVE 2 (parallel)          WAVE 3
┌─────────┐ ┌─────────┐    ┌─────────┐ ┌─────────┐    ┌─────────┐
│ Plan 01 │ │ Plan 02 │ →  │ Plan 03 │ │ Plan 04 │ →  │ Plan 05 │
│         │ │         │    │         │ │         │    │         │
│ User    │ │ Product │    │ Orders  │ │ Cart    │    │ Checkout│
│ Model   │ │ Model   │    │ API     │ │ API     │    │ UI      │
└─────────┘ └─────────┘    └─────────┘ └─────────┘    └─────────┘
     │           │              ↑           ↑              ↑
     └───────────┴──────────────┴───────────┘              │
            Dependencies: Plan 03 needs Plan 01
                        Plan 04 needs Plan 02
                        Plan 05 needs Plans 03 + 04
```

## Output Files

- `.planning/{phase}-{N}-SUMMARY.md` — What happened, what changed
- `.planning/{phase}-VERIFICATION.md` — Automated verification results

## After This Workflow

User should run `/gsd:verify-work X` or say "verify phase X" for manual acceptance testing.
