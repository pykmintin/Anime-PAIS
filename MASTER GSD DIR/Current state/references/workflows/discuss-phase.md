# Discuss Phase Workflow

Capture implementation decisions before planning. This is where you shape the implementation.

## Purpose

Your roadmap has a sentence or two per phase. That's not enough context to build something the way the user imagines it. This step captures preferences before anything gets researched or planned.

## Process

### 1. Analyze the Phase

Read the phase from `ROADMAP.md` and identify gray areas:

**Visual features → Ask about:**
- Layout preferences (card vs list vs table)
- Density (compact vs spacious)
- Interactions (modal vs inline vs page)
- Empty states and loading states

**APIs/CLIs → Ask about:**
- Response format (JSON vs structured text)
- Flags and options style
- Error handling approach
- Verbosity levels

**Content systems → Ask about:**
- Content structure
- Tone and voice
- Depth and detail level
- Flow and organization

**Organization tasks → Ask about:**
- Grouping criteria
- Naming conventions
- Duplicate handling
- Exception handling

### 2. Ask Until Satisfied

For each gray area:
- Present options with tradeoffs
- Ask user's preference
- Lock in the decision
- Note any deferred ideas

### 3. Create CONTEXT.md

Output: `.planning/{phase_num}-CONTEXT.md`

Structure:
```markdown
# Phase X Context

## Decisions (LOCKED)
- Decision 1: What was chosen
- Decision 2: What was chosen

## Deferred Ideas
- Idea 1: Why deferred
- Idea 2: Why deferred

## Kimi's Discretion
- Areas where reasonable choices are fine

## References
- Related files
- External resources
```

## Why This Matters

The CONTEXT.md feeds directly into:

1. **Researcher reads it** — Knows what patterns to investigate
2. **Planner reads it** — Knows what decisions are locked

**Skip this step** → Get reasonable defaults  
**Use this step** → Get the user's actual vision

## After This Workflow

User should run `/gsd plan-phase X` or say "plan phase X" to continue.
