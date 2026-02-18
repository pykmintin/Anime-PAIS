---
name: gsd
description: Get Shit Done - A spec-driven development system for Kimi Code. Use when starting new projects, planning features, executing development phases, or managing complex coding workflows. Triggers on phrases like "plan this project", "start new project", "execute phase", "discuss implementation", "verify work", or any structured development workflow needs.
---

# GSD (Get Shit Done)

A lightweight, powerful spec-driven development system for solo developers using Kimi Code.

## What GSD Solves

**Context rot** - The quality degradation that happens as AI fills its context window. GSD fixes this through:
- Context engineering with structured documentation
- Multi-agent orchestration with fresh contexts
- Atomic git commits with clear history
- Spec-driven development with verification

## Core Workflow

```
new-project → discuss-phase → plan-phase → execute-phase → verify-work
                                    ↓              ↓
                              (repeat phases)  (fix if needed)
```

## Commands

### Project Initialization
- **Start new project**: Create `PROJECT.md`, `REQUIREMENTS.md`, `ROADMAP.md`, `STATE.md`
- **Map existing codebase**: Analyze current code before planning

### Phase Workflow (repeat for each phase)
1. **Discuss phase**: Capture implementation decisions before planning
2. **Plan phase**: Research + create executable plans
3. **Execute phase**: Run plans in parallel waves
4. **Verify work**: Confirm deliverables work as expected

### Utilities
- **Check progress**: See where you are, what's next
- **Add todo**: Capture ideas for later
- **Debug**: Systematic debugging with persistent state
- **Quick mode**: Fast path for small tasks

## File Structure

GSD creates and manages these files in `.planning/`:

| File | Purpose |
|------|---------|
| `PROJECT.md` | Project vision and context |
| `REQUIREMENTS.md` | Scoped v1/v2 requirements |
| `ROADMAP.md` | Phase structure and progress |
| `STATE.md` | Decisions, blockers, position |
| `{phase}-CONTEXT.md` | Implementation decisions |
| `{phase}-RESEARCH.md` | Domain research findings |
| `{phase}-{N}-PLAN.md` | Executable task plans |
| `{phase}-{N}-SUMMARY.md` | Execution results |

## Usage Patterns

### Starting a New Project

```
User: "I want to build a task management app"
→ Read references/workflows/new-project.md
→ Ask questions until idea is clear
→ Create PROJECT.md, REQUIREMENTS.md, ROADMAP.md
→ Run /gsd:plan-phase 1
```

### Working on a Phase

```
User: "Plan phase 2"
→ Check for {phase}-CONTEXT.md
→ If missing: run discuss-phase workflow
→ Read references/workflows/plan-phase.md
→ Create research and plan files
```

### Executing Plans

```
→ Read references/workflows/execute-phase.md
→ Group plans into waves by dependencies
→ Spawn executors for each wave
→ Verify results
```

## Principles

1. **Plans are prompts** - PLAN.md IS the prompt, not a document that becomes one
2. **Fresh context per task** - Each plan runs in a new session
3. **Atomic commits** - Every task gets its own commit
4. **Ship fast** - Plan → Execute → Ship → Learn → Repeat
5. **No enterprise theater** - No sprints, story points, or ceremonies

## References

- **Workflows**: See `references/workflows/` for detailed process guides
- **Templates**: See `references/templates/` for document templates
- **Agents**: See `references/agents/` for sub-agent definitions

## Differences from Claude Code GSD

| Aspect | Claude Code | Kimi Code |
|--------|-------------|-----------|
| Commands | `/gsd:new-project` | Natural language triggers |
| Agent spawning | `Task` tool | Kimi's agent system |
| Config dir | `~/.claude/` | `~/.kimi/` |
| Slash commands | Yes | Use natural language |

## Quick Start

1. Say "start a new project" or "I want to build..."
2. Answer questions about your idea
3. Review generated roadmap
4. Say "plan phase 1" to begin
5. Say "execute phase 1" when ready

The system guides you through each step.
