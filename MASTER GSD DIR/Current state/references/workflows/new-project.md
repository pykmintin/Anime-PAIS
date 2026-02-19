# New Project Workflow

Initialize a new project through unified flow: questioning → research → requirements → roadmap.

## Output Files

- `.planning/PROJECT.md` — project context
- `.planning/config.json` — workflow preferences
- `.planning/research/` — domain research (optional)
- `.planning/REQUIREMENTS.md` — scoped requirements
- `.planning/ROADMAP.md` — phase structure
- `.planning/STATE.md` — project memory

## Process

### 1. Questioning Phase

Ask the user until you understand their idea completely:

**Core Questions:**
- What are you building? (elevator pitch)
- Who is it for? (target users)
- What problem does it solve?
- What does success look like?

**Technical Questions:**
- Any tech preferences or constraints?
- Existing codebase or greenfield?
- Timeline/deadline pressures?
- Integration requirements?

**Scope Questions:**
- What's the minimum viable version?
- What can wait for v2?
- What's definitely out of scope?

**Edge Cases:**
- What could go wrong?
- Unusual use cases to consider?
- Performance/scaling concerns?

### 2. Research Phase (Optional)

If user wants research, spawn parallel researchers:
- Stack researcher: Best tech choices
- Feature researcher: What similar tools offer
- Architecture researcher: Patterns and pitfalls
- Pitfall researcher: Common mistakes

### 3. Requirements Extraction

From answers, extract:

**v1 Must-Haves:**
- Core features for MVP
- Critical functionality
- User-facing deliverables

**v2 Nice-to-Haves:**
- Features for next iteration
- Improvements and polish

**Out of Scope:**
- Explicitly excluded features
- Future considerations

### 4. Roadmap Creation

Create phases that:
- Map to requirements
- Can be built sequentially
- Deliver working software at each step
- Are sized for ~1-3 days of work each

## After This Workflow

User should run `/gsd plan-phase 1` or say "plan phase 1" to start execution.
