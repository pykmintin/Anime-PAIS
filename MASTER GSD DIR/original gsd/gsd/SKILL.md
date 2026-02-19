---
name: gsd
description: Get Shit Done - A spec-driven development system for structured project planning and execution. Invoke via /skill:gsd or /gsd followed by subcommand (new-project, discuss-phase, plan-phase, execute-phase, verify-work, status). Use when starting new projects with "start a new project", planning phases with "plan phase X", executing with "execute phase X", or managing complex multi-phase development workflows with persistent planning documentation.
---

# GSD (Get Shit Done)

A spec-driven development system that prevents context rot through structured documentation, parallel execution, and verification.

## Slash Commands

Invoke with `/skill:gsd <command>` or `/gsd <command>`:

| Command | Arguments | Purpose |
|---------|-----------|---------|
| `new-project` | none | Initialize new project with planning documents |
| `discuss-phase` | `<phase-number>` | Capture implementation decisions before planning |
| `plan-phase` | `<phase-number>` | Research and create executable plans |
| `execute-phase` | `<phase-number>` | Execute all plans in parallel waves |
| `verify-work` | `<phase-number>` | Manual user acceptance testing |
| `status` | none | Check current position and progress |

**Examples:**
- `/skill:gsd new-project`
- `/gsd plan-phase 1`
- `/gsd execute-phase 2`

## Core Workflow

```
/gsd new-project
       ↓
/gsd discuss-phase 1
       ↓
/gsd plan-phase 1
       ↓
/gsd execute-phase 1
       ↓
/gsd verify-work 1
       ↓
(repeat for next phase)
```

## Command Routing

When this skill triggers, examine the user's input to determine intent:

**If input starts with `/skill:gsd` or `/gsd`:**
Parse the subcommand that follows:
- `/skill:gsd new-project` → Run new-project workflow
- `/skill:gsd discuss-phase 1` → Run discuss-phase for phase 1
- `/skill:gsd plan-phase 2` → Run plan-phase for phase 2
- `/skill:gsd execute-phase 1` → Run execute-phase for phase 1
- `/skill:gsd verify-work 1` → Run verify-work for phase 1
- `/skill:gsd status` → Run status check

**If natural language input:**
Infer intent from phrases:
- "start a new project", "I want to build..." → new-project
- "discuss phase X", "shape phase X" → discuss-phase
- "plan phase X" → plan-phase
- "execute phase X", "run phase X", "build phase X" → execute-phase
- "verify the work", "check phase X", "did it work" → verify-work
- "check progress", "where are we", "what's next" → status

Route to the appropriate workflow section below.

### `new-project` command
**Slash:** `/skill:gsd new-project` or `/gsd new-project`
**Natural:** "start a new project", "I want to build..."
1. Read `references/workflows/new-project.md`
2. Ask user questions until idea is clear
3. Create `.planning/` directory with:
   - `PROJECT.md` - project vision
   - `REQUIREMENTS.md` - scoped requirements
   - `ROADMAP.md` - phase structure
   - `STATE.md` - project memory
   - `config.json` - workflow preferences

### `discuss-phase` command
**Slash:** `/skill:gsd discuss-phase <n>` or `/gsd discuss-phase <n>`
**Natural:** "discuss phase N", "what should phase N include"
1. Read `ROADMAP.md` to understand phase goals
2. Read `references/workflows/discuss-phase.md`
3. Ask user about implementation preferences
4. Create `.planning/{phase}-CONTEXT.md` with locked decisions

### `plan-phase` command
**Slash:** `/skill:gsd plan-phase <n>` or `/gsd plan-phase <n>`
**Natural:** "plan phase N", "create a plan for phase N"
1. Read context files:
   - `PROJECT.md`
   - `REQUIREMENTS.md`
   - `ROADMAP.md`
   - `{phase}-CONTEXT.md` (if exists)
2. Read `references/workflows/plan-phase.md`
3. Optionally spawn researchers from `references/agents/researcher.md`
4. Create:
   - `.planning/{phase}-RESEARCH.md` (if research performed)
   - `.planning/{phase}-{N}-PLAN.md` files (2-3 tasks each)

### `execute-phase` command
**Slash:** `/skill:gsd execute-phase <n>` or `/gsd execute-phase <n>`
**Natural:** "execute phase N", "run phase N", "build phase N"
1. Read all `.planning/{phase}-{N}-PLAN.md` files
2. Read `references/workflows/execute-phase.md`
3. Build dependency graph, group into waves
4. For each wave, spawn executors from `references/agents/executor.md`
5. Each task gets atomic git commit
6. Create `.planning/{phase}-{N}-SUMMARY.md` for each plan

### `verify-work` command
**Slash:** `/skill:gsd verify-work <n>` or `/gsd verify-work <n>`
**Natural:** "verify the work", "check phase N", "did it work"
1. Read plan files and summaries
2. Read `references/workflows/verify-work.md`
3. Walk user through each deliverable
4. Create `.planning/{phase}-UAT.md` with results
5. If issues found, create `.planning/{phase}-FIX-{N}-PLAN.md`

### `status` command
**Slash:** `/skill:gsd status` or `/gsd status`
**Natural:** "check progress", "where are we", "what's next"
1. Read `STATE.md` and `ROADMAP.md`
2. Report current position, blockers, next steps

## File Structure

GSD creates and manages files in `.planning/`:

| File | Purpose |
|------|---------|
| `PROJECT.md` | Project vision and context |
| `REQUIREMENTS.md` | Scoped v1/v2 requirements |
| `ROADMAP.md` | Phase structure and progress |
| `STATE.md` | Decisions, blockers, position |
| `config.json` | Workflow preferences |
| `{phase}-CONTEXT.md` | Implementation decisions |
| `{phase}-RESEARCH.md` | Domain research findings |
| `{phase}-{N}-PLAN.md` | Executable task plans |
| `{phase}-{N}-SUMMARY.md` | Execution results |
| `{phase}-UAT.md` | User acceptance test results |
| `{phase}-FIX-{N}-PLAN.md` | Fix plans for failed verification |

## Agent Spawning

Spawn subagents for parallel work:

**Researchers** (`references/agents/researcher.md`):
```
Spawn Task subagent:
  - subagent_name: coder
  - prompt: "You are a GSD researcher. Read references/agents/researcher.md, 
             then research [topic] and append findings to {phase}-RESEARCH.md"
```

**Executors** (`references/agents/executor.md`):
```
For each plan in wave:
  Spawn Task subagent:
    - subagent_name: coder
    - prompt: "You are a GSD executor. Read references/agents/executor.md 
               and {phase}-{N}-PLAN.md, then execute all tasks with atomic commits"
```

**Verifiers** (`references/agents/verifier.md`):
```
Spawn Task subagent:
  - subagent_name: coder
  - prompt: "You are a GSD verifier. Read references/agents/verifier.md,
             plans, and code, then create {phase}-VERIFICATION.md"
```

## Principles

1. **Plans are prompts** - PLAN.md IS the prompt, not a document that becomes one
2. **Fresh context per task** - Each plan runs in a new session
3. **Atomic commits** - Every task gets its own commit
4. **Ship fast** - Plan → Execute → Ship → Learn → Repeat
5. **No enterprise theater** - No sprints, story points, or ceremonies

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
