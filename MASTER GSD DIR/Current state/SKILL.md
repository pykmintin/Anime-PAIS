---
name: gsd
description: Get Shit Done - A spec-driven development system for structured project planning and execution. Trigger with /gsd, then use :command syntax for subcommands (:new-project, :discuss-phase N, :plan-phase N, :execute-phase N, :verify-work N, :status).
---

# GSD (Get Shit Done)

A spec-driven development system that prevents context rot through structured documentation, parallel execution, and verification.

## Activation

**Primary trigger:** `/gsd`
- Loads all documentation and enters GSD mode
- Enables :command recognition

**Alternative:** Natural language
- "start a new project" → :new-project
- "plan phase 1" → :plan-phase 1
- "check status" → :status

## Command Syntax

Once activated, use `:` prefix for subcommands:

| Command | Arguments | Purpose |
|---------|-----------|---------|
| `:new-project` | none | Initialize new project with planning documents |
| `:discuss-phase` | `<n>` | Capture implementation decisions before planning |
| `:plan-phase` | `<n>` | Research and create executable plans |
| `:execute-phase` | `<n>` | Execute all plans in parallel waves |
| `:verify-work` | `<n>` | Manual user acceptance testing |
| `:status` | none | Check current position and progress |

**Examples:**
- `:new-project`
- `:plan-phase 1`
- `:execute-phase 2`
- `:status`

## Core Workflow

```
/gsd
   ↓
:new-project
   ↓
:discuss-phase 1
   ↓
:plan-phase 1
   ↓
:execute-phase 1
   ↓
:verify-work 1
   ↓
(repeat for next phase)
```

## Command Routing

When GSD is active, examine user input to determine intent:

**If input starts with `:`:**
Parse the subcommand that follows:
- `:new-project` → Run new-project workflow
- `:discuss-phase 1` → Run discuss-phase for phase 1
- `:plan-phase 2` → Run plan-phase for phase 2
- `:execute-phase 1` → Run execute-phase for phase 1
- `:verify-work 1` → Run verify-work for phase 1
- `:status` → Run status check

**If natural language input:**
Infer intent from phrases:
- "start a new project", "I want to build..." → :new-project
- "discuss phase X", "shape phase X" → :discuss-phase X
- "plan phase X" → :plan-phase X
- "execute phase X", "run phase X", "build phase X" → :execute-phase X
- "verify the work", "check phase X", "did it work" → :verify-work X
- "check progress", "where are we", "what's next" → :status

Route to the appropriate workflow section below.

---

## Workflow: `:new-project`

**Trigger:** `:new-project` or "start a new project"

1. Read `references/workflows/new-project.md`
2. Ask user questions until idea is clear
3. Create `.planning/` directory with:
   - `PROJECT.md` - project vision
   - `REQUIREMENTS.md` - scoped requirements
   - `ROADMAP.md` - phase structure
   - `STATE.md` - project memory
   - `config.json` - workflow preferences

---

## Workflow: `:discuss-phase <n>`

**Trigger:** `:discuss-phase 1` or "discuss phase 1"

1. Read `ROADMAP.md` to understand phase goals
2. Read `references/workflows/discuss-phase.md`
3. Ask user about implementation preferences
4. Create `.planning/phase-{n}-CONTEXT.md` with locked decisions

---

## Workflow: `:plan-phase <n>`

**Trigger:** `:plan-phase 1` or "plan phase 1"

1. Read context files:
   - `PROJECT.md`
   - `REQUIREMENTS.md`
   - `ROADMAP.md`
   - `phase-{n}-CONTEXT.md` (if exists)
2. Read `references/workflows/plan-phase.md`
3. Optionally spawn researchers using Task tool
4. Create:
   - `.planning/phase-{n}-RESEARCH.md` (if research performed)
   - `.planning/phase-{n}-{N}-PLAN.md` files (2-3 tasks each)

---

## Workflow: `:execute-phase <n>`

**Trigger:** `:execute-phase 1` or "execute phase 1"

1. Read all `.planning/phase-{n}-{N}-PLAN.md` files
2. Read `references/workflows/execute-phase.md`
3. Build dependency graph, group into waves
4. For each wave, spawn executors using Task tool
5. Each task should be committed (ask user for git confirmation)
6. Create `.planning/phase-{n}-{N}-SUMMARY.md` for each plan

---

## Workflow: `:verify-work <n>`

**Trigger:** `:verify-work 1` or "verify phase 1"

1. Read plan files and summaries
2. Read `references/workflows/verify-work.md`
3. Walk user through each deliverable
4. Create `.planning/phase-{n}-UAT.md` with results
5. If issues found, create `.planning/phase-{n}-FIX-{N}-PLAN.md`

---

## Workflow: `:status`

**Trigger:** `:status` or "check progress"

1. Read `STATE.md` and `ROADMAP.md`
2. Report current position, blockers, next steps

---

## File Structure

GSD creates and manages files in `.planning/`:

| File | Purpose |
|------|---------|
| `PROJECT.md` | Project vision and context |
| `REQUIREMENTS.md` | Scoped v1/v2 requirements |
| `ROADMAP.md` | Phase structure and progress |
| `STATE.md` | Decisions, blockers, position |
| `config.json` | Workflow preferences |
| `phase-{n}-CONTEXT.md` | Implementation decisions |
| `phase-{n}-RESEARCH.md` | Domain research findings |
| `phase-{n}-{N}-PLAN.md` | Executable task plans |
| `phase-{n}-{N}-SUMMARY.md` | Execution results |
| `phase-{n}-UAT.md` | User acceptance test results |
| `phase-{n}-FIX-{N}-PLAN.md` | Fix plans for failed verification |

---

## Agent Spawning (Kimi Task Tool)

Spawn subagents for parallel work using the Task tool:

**Researchers** (`references/agents/researcher.md`):
```
Spawn Task subagent:
  - subagent_name: coder
  - prompt: "You are a GSD researcher. Read references/agents/researcher.md, 
             then research [topic] and append findings to phase-{n}-RESEARCH.md"
```

**Executors** (`references/agents/executor.md`):
```
For each plan in wave:
  Spawn Task subagent:
    - subagent_name: coder
    - prompt: "You are a GSD executor. Read references/agents/executor.md 
               and phase-{n}-{N}-PLAN.md, then execute all tasks. 
               Ask user before any git commits."
```

**Verifiers** (`references/agents/verifier.md`):
```
Spawn Task subagent:
  - subagent_name: coder
  - prompt: "You are a GSD verifier. Read references/agents/verifier.md,
             plans, and code, then create phase-{n}-VERIFICATION.md"
```

---

## Principles

1. **Plans are prompts** - PLAN.md IS the prompt, not a document that becomes one
2. **Fresh context per task** - Each plan runs in a new session via Task tool
3. **Atomic commits** - Every task gets its own commit (ask user first)
4. **Ship fast** - Plan → Execute → Ship → Learn → Repeat
5. **No enterprise theater** - No sprints, story points, or ceremonies

---

## Reference Files

**Workflows** (read when executing corresponding command):
- `references/workflows/new-project.md`
- `references/workflows/discuss-phase.md`
- `references/workflows/plan-phase.md`
- `references/workflows/execute-phase.md`
- `references/workflows/verify-work.md`

**Agents** (load into subagent prompts):
- `references/agents/planner.md`
- `references/agents/executor.md`
- `references/agents/researcher.md`
- `references/agents/verifier.md`

**Templates** (use when creating documents):
- `references/templates/PROJECT.md`
- `references/templates/REQUIREMENTS.md`
- `references/templates/ROADMAP.md`
- `references/templates/STATE.md`

---

## Kimi CLI Differences from Claude

| Feature | Claude | Kimi CLI |
|---------|--------|----------|
| Trigger | `/gsd new-project` | `:new-project` after `/gsd` |
| Subagents | Native | Task tool |
| Git commits | Automatic | Ask user first |
| Context | 200k tokens | Manage efficiently |

Always ask user before git mutations (commit, push, etc.).
