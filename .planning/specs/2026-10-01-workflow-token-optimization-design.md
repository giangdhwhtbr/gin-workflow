# Workflow Token Optimization (Sub-project A) — Design

Date: 2026-10-01
Status: awaiting user confirmation
Scope: plugin `plugins/gin-workflow/src` (skills, commands, agents, references, setup defaults, lifecycle CLI, tests)

## Context and decomposition

The v-next request has four parts, split into separate spec → plan cycles in this order:

1. **A — Token/workflow optimization** (this spec).
2. **B+C — Project-type bootstrap** (greenfield, brownfield, …) with frontend-only as a profile. Separate spec.
3. **D — Best-practice rules** (TypeScript, React, Python, …), loaded selectively by profile/stack detected in B. Separate spec.

A lands first so B, C and D attach to a smaller, budgeted base.

## Problem (verified in repository)

- Each lifecycle stage loads 3+ instruction layers: command → stage skill → methodology skill(s) → references.
- The "Wrapper boundary" paragraph (`load_effective_config`, `capabilities: {}` is not missing setup, …) is duplicated across 16 command/skill files (32 mentions of `load_effective_config`).
- Skills are written against abstract Python contracts (`ContextManifest`, `ArtifactRegistry`, `ApprovalDecision`, `route_next_stage`, `WorkflowEventStore`) that agents cannot call. The CLI exposes only `setup`, `state`, `unblock`.
- No CLI writes the events that `gin-workflow state` reads for process gates (`requirement.confirmed`, `approval.recorded` with `action=plan_approved`, `orchestration.ready`; see `scripts/workflow_core/lifecycle_cli.py:_process_gate_state`). Agents are told to persist evidence without a tool to do so.
- Large skills forked from superpowers (≈150K chars total: `systematic-debugging`, `writing-plans`, `finishing-a-development-branch`, `using-git-worktrees`, `receiving-code-review`, `dispatching-parallel-agents`, `verification-before-completion`, `discovering-work`) collide by name/description with the installed superpowers plugin.
- Defaults run `verify` and `review` at `high_reasoning`, with up to 3 review cycles.

### Baseline (direct load chain: command + stage skill + skills/references it names directly; chars)

| Stage | Baseline |
|---|---|
| discuss | 12,045 |
| plan | 13,636 |
| orchestrate | 19,581 |
| execute | 15,108 |
| verify | 16,117 |
| ship | 22,433 |
| review | 4,683 |
| workflow | 31,528 |
| progress | 3,222 |
| Sum of frontmatter `description` (skills + agents + commands) | 4,909 |

Measured with a throwaway script; the budget test's `--report` mode re-measures the baseline on the pre-change tree before any edit. Methodology skills reached in a second hop (e.g. `execute` → `bead-worker` → `worker-dispatch`) add more in practice; the budget test measures the direct chain after restructuring, where second hops no longer exist for lifecycle stages.

## Decisions

- Change level: **medium** — restructure layers and replace abstract contracts with concrete CLI; lifecycle stages and gates unchanged.
- Forked superpowers skills: **kept in plugin, rewritten compactly, renamed with `gin-` prefix** (Codex/Antigravity have no superpowers).
- Layer approach: **thin command + self-contained stage skill + one shared reference**.
- Success measured by a **token budget test** with baseline and before/after table in handoff.

## Design

### (a) Skill map (32 → ~17)

| Group | Result | Absorbs |
|---|---|---|
| Stage skills | `discuss` | `discovering-work` |
| | `plan` | `writing-plans` (keep `plan-schema.md` as reference) |
| | `orchestrate` | `bead-orchestrator` |
| | `execute` | `executing-plans`, `bead-worker`, core of `worker-dispatch` |
| | `verify` | `verification-before-completion` |
| | `ship` | `finishing-a-development-branch` |
| | `review` (new, matches `/review`) | `cross-agent-code-review`, `requesting-code-review` |
| | `workflow`, `progress`, `setup`, `tech-doc` | kept, shortened |
| Shared, `gin-` prefix | `gin-debugging` | `systematic-debugging` |
| | `gin-worktrees` | `using-git-worktrees` |
| | `gin-review-response` | `receiving-code-review` |
| | `gin-parallel-agents` | `dispatching-parallel-agents` |
| | `gin-knowledge` | `knowledge-capture`, `knowledge-reconciliation` |
| Optional | `telegram-notify`, `beads-migration` | kept; loaded only when configured or explicitly invoked |
| Reference | `references/stage-contract.md` | `approval-manager`, `evidence-manager`, `context-manager`, `context-retrieval`, all Wrapper boundary copies |

Rules for rewriting:
- Keep only behavior tied to gin-workflow (Beads, review-ledger, gates, worktrees, handoff options). Drop long rationale, anti-rationalization tables, and generic advice.
- Each command is a thin entry (purpose + "use the `<stage>` skill"), ≤ 1.2K chars.
- Each stage skill begins with `Follow references/stage-contract.md.` and contains only stage-specific steps.
- Agent files (`agents/*.md`) point to stage skills instead of restating them; ≤ 4K each.
- References whose content moves into `stage-contract.md` or a stage skill are deleted from `src/references/` only when no remaining file points to them.
- Files outside the plugin (`docs/*.md` duplicates of `src/references/*.md`, root `review.md`, `Plan.md`) do not affect consumer token cost; they are listed in the handoff for the user to decide and are not changed by this work.

### (b) Stage contract and concrete CLI

New lifecycle CLI subcommand, reusing `WorkflowEvent`/`WorkflowEventStore` and emitting exactly the events `_process_gate_state` reads (router unchanged):

```
gin-workflow record requirement-confirmed --evidence <spec-path> --actor <id>
gin-workflow record plan-approved        --evidence <plan-path> --actor <id>
gin-workflow record orchestration-ready  --evidence <bead-ids>  --actor <id>
```

- `plan-approved` is invoked only after explicit user confirmation in the harness; the CLI never manufactures approval.
- Later gates (`implementation_complete`, `verification_passed`, `shipped`) keep their current sources (Beads, review-ledger, git).

`references/stage-contract.md` (~1.5K chars) contains:
- Input: missing `.agent-workflow/generated/effective-config.yaml` → stop, tell user to run `/setup`; `capabilities: {}` is valid.
- State: `gin-workflow state --format json`.
- Gates: `gin-workflow record …`; unblock: `gin-workflow unblock …`.
- Evidence: test output, review-ledger state, bead IDs, spec/plan paths; self-assessment is never evidence.
- Approval: explicit user confirmation before `plan-approved`, production-impacting parallel work, and disabling worktree isolation.
- Context: load requirement, file scope, validation intent only; look up symbols/tests/knowledge on demand, codegraph first when `.codegraph/` exists.
- Commit/push only with explicit authorization.

### (c) Model tiers and review cycles

Defaults in `scripts/workflow_core/configuration.py`:

| Stage | Before | After |
|---|---|---|
| brainstorm, design, plan | high_reasoning | high_reasoning |
| implement | standard_impl | standard_impl; plan tasks marked `complexity: low` dispatch at `cheap_simple` |
| verify | high_reasoning | **standard_impl** (escalate via `gin-debugging` on failure) |
| review | high_reasoning | high_reasoning |
| docs | cheap_simple | cheap_simple |

`routing.review.max_cycles` default: 3 → **2**; after that, escalate to the user.

Only defaults change. Existing `.agent-workflow/config.yaml` values are preserved; `/setup update` shows a diff for the user to opt in.

### (d) Token budget test

`tests/workflow_core/test_token_budget.py`, over `plugins/gin-workflow/src`:
- Stage chain = `commands/<stage>.md` + `skills/<stage>/SKILL.md` + every `references/*.md` either file references directly. Unit: characters (~4 chars ≈ 1 token); no tokenizer dependency.
- Budgets:
  - each lifecycle stage chain (`discuss`, `plan`, `orchestrate`, `execute`, `verify`, `ship`, `review`, `workflow`, `progress`) ≤ 12,000
  - each `commands/*.md` ≤ 1,200
  - each `gin-*` shared skill ≤ 6,000
  - each `agents/*.md` ≤ 4,000
  - sum of frontmatter `description` ≤ 4,000
  - zero occurrences in skills/commands of `ContextManifest`, `ArtifactRegistry`, `ApprovalDecision`, `load_effective_config`
- `--report` mode prints the table used for baseline and handoff.
- Budgets are constants; raising them (e.g. for sub-project D) is an explicit test change.

Related tests:
- Update `tests/workflow_providers/test_harness_packaging.py` to the new file list.
- New test: `gin-workflow record <gate>` then `gin-workflow state --format json` reports that gate `satisfied`.
- Existing suite (`tests/test_all.py`, install smoke tests) passes; `dist/` regenerated for all three harnesses.

## Out of scope

- Lifecycle changes (merging stages, fast path for small changes).
- Project-type bootstrap, frontend profile, best-practice rules (sub-projects B+C, D).
- Router/gate semantics changes beyond the new `record` writer.

## Acceptance criteria

1. Skill count reduced per map (a); no lifecycle skill references another methodology skill for core behavior.
2. `gin-workflow record` writes the three process-gate events and `state` reflects them.
3. Defaults updated per (c); existing configs untouched.
4. Token budget test passes; before/after table included in handoff.
5. Full test suite and install smoke tests pass for claude-code, codex, antigravity.
