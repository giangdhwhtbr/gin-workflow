# Docs Rewrite Design

Status: confirmed 2026-10-04

## Goal

Replace the drifted documentation set with a layered one that matches the code on `master` (rules and lean pack, SDD living specs, team mode, gin-qa, `quick`, usage report), has exactly one copy of each document, explains the plugin architecture with Mermaid diagrams, and fails a test when a skill, CLI subcommand, or relative link goes undocumented or dead.

## Global Constraints

- Docs are written in English. One Vietnamese quickstart (`docs/huong-dan.md`) mirrors `docs/getting-started.md` and links to the English pages for detail.
- Every statement is checked against the current code (`--help`, `SKILL.md`, config schema, `plugins/gin-workflow/src/examples/config.full.yaml`), never copied from an old doc without checking.
- Each page has one job; other pages link to it instead of repeating it. Diagrams live only in `docs/concepts/architecture.md`.
- Historical docs are deleted; git history keeps them.
- `docs/` is the only copy. The plugin bundle ships only references that skills read (`stage-contract.md`, `shape-*.md`).
- `AGENTS.md` and `CLAUDE.md` stay a pointer layer.
- No new runtime dependency; the docs test uses the Python standard library only.

## Structure

```
README.md                      what it is, install (Claude Code, Codex, Antigravity, gin-qa), quickstart, docs map; target <= ~6 KB
docs/getting-started.md        one worked example: /setup -> discuss -> plan -> orchestrate -> execute -> verify -> ship, plus quick and report
docs/huong-dan.md              Vietnamese version of getting-started
docs/concepts/architecture.md  entry point: six Mermaid diagrams with short explanations
docs/concepts/lifecycle.md     stages, gates, gate CLI (record, state), waivers, quick path, verification and handoff checklist
docs/concepts/state-model.md   Beads (parent vs track beads), review ledger and cleanup, .planning/ (specs, plans, worktrees), .agent-workflow/
docs/concepts/providers.md     capability contracts, provider roles, reasoning and model classes, routing, worker context and evidence policy
docs/guides/rules.md           rule packs (core, lean default-on), `gin-workflow rules`, how review grades lean findings
docs/guides/sdd.md             project.layout sdd, living specs, REQ-IDs, specs lint/trace, migrate-specs
docs/guides/team.md            opt-in team mode, team-setup, team ready/claim, PR-based gates; solo unchanged
docs/guides/qa.md              gin-qa add-on: cases and e2e skills
docs/guides/usage-report.md    usage collect/report, /report, usage-prices.yaml, limits (agy not measured, parallel root sessions, review interval)
docs/guides/use-cases.md       merged quick-debug, large-task, resume-in-progress
docs/reference/cli.md          every gin-workflow subcommand: synopsis, options, exit codes; review-ledger.py commands
docs/reference/config.md       setup system, versioning and migration, effective config keys
docs/reference/skills.md       every skill of gin-workflow and gin-qa with one-line purpose and when to use it
docs/reference/troubleshooting.md  moved from README, plus Codex marketplace install has no CLI launchers
docs/contributing.md           build, local install (Linux/macOS, Windows), tests and smoke tests, release (version bump, reinstall snapshots), benchmark protocol
```

## Content Map

| New page | Sources | Gaps to fill from code |
|---|---|---|
| README.md | README.md install sections | docs map, Codex launcher note (link to troubleshooting) |
| getting-started / huong-dan | huong-dan-workflow-v2.1.md | /setup, quick, /report |
| concepts/lifecycle.md | agent-task-lifecycle.md, verification-and-handoff-workflow.md | record/state, waivers, quick, usage collect at bead close |
| concepts/state-model.md | orchestration-state-model.md | review ledger, cleanup, .planning layout |
| concepts/providers.md | capability-provider-contracts.md, provider-routing.md, context-and-evidence-policy.md | model classes, agy |
| guides/rules.md | README Rule Packs | lean pack, lean finding grading |
| guides/sdd.md | gin-sdd, migrate-specs skills | living specs, REQ-IDs, lint/trace |
| guides/team.md | gin-team, team-setup skills | team commands, PR gates |
| guides/qa.md | README gin-qa section, gin-qa skills | cases, e2e |
| guides/usage-report.md | README usage paragraph, ai-usage spec | prices file, limits |
| guides/use-cases.md | docs/use-cases/*.md | none |
| reference/cli.md | CLI parsers | all subcommands |
| reference/config.md | setup-system.md, config.full.yaml | layout, team, rules, verify_commands |
| reference/skills.md | README skill tables | all skills |
| reference/troubleshooting.md | README Troubleshooting | Codex launcher note |
| contributing.md | README Local Development and Repository Structure, docs/benchmarks/README.md | release steps |

## Architecture Diagrams (`docs/concepts/architecture.md`)

Each diagram has two to four sentences of explanation and links to the page that covers it in detail. Every name in a diagram (file, function, command) exists in the code.

1. Components (`flowchart`): Claude Code, Codex, Antigravity invoke the plugin bundle (skills, agents, references, `gin-workflow` CLI over `workflow_core`, `review-ledger.py`), which reads and writes repository state (`.agent-workflow/` config and runtime events, `.planning/` specs, plans and worktrees, Beads, review ledgers).
2. Lifecycle (`stateDiagram-v2`): discuss -> plan -> orchestrate -> execute -> verify -> ship with the gate recorded at each transition; the quick path; waivers; where SDD and team mode change a step.
3. Track execution (`sequenceDiagram`): claim bead, worktree, rules, implement and test, review ledger with an independent reviewer, approve or changes requested, usage collect, `bd close` unblocking dependents.
4. Provider routing (`flowchart`): track role and reasoning, `resolve_all_assignments`, preferred and fallback routes with circuit, health and capacity checks, assignment manifest or `worker_routes_unavailable`.
5. Build and install (`flowchart`): `src/` -> build -> `dist/{claude-code,codex,antigravity}` -> marketplace or local installer -> per-harness snapshot, and why a reinstall is needed after shipping.
6. Usage collection (`flowchart`): Claude Code and Codex logs -> attribution by worktree or gate -> `ai_usage` bead metadata -> `usage report`.

## Deletions and Updates

Delete:
- `docs/agent-task-lifecycle.md`, `docs/orchestration-state-model.md`, `docs/verification-and-handoff-workflow.md`, `docs/setup-system.md`, `docs/capability-provider-contracts.md`, `docs/context-and-evidence-policy.md`, `docs/provider-routing.md`
- `docs/huong-dan-workflow-v2.1.md`, `docs/workflow-audit-2026-07-08.md`, `docs/workflow-validation-simulation-2026-07-09.md`, `docs/model-class-planning-metadata-design-2026-07-09.md`, `docs/simulated-workflow-smoke-task.md`
- `docs/superpowers/`, `docs/use-cases/`, `docs/benchmarks/` (content moves as mapped above)
- The seven copies in `plugins/gin-workflow/src/references/` of the files above (all except `stage-contract.md` and `shape-*.md`)

Update:
- `AGENTS.md`, `CLAUDE.md`: point to `docs/concepts/*` and `docs/reference/*`.
- `plugins/gin-workflow/src/scripts/workflow_core/waivers.py`: comment path `docs/agent-task-lifecycle.md` -> `docs/concepts/lifecycle.md`.
- `tests/workflow_providers/test_harness_packaging.py`: drop the seven references from `REQUIRED_ARTIFACTS`.
- `tests/install_smoke_test.sh` (and `.ps1` where present): drop the assertions on those references.
- `tests/workflow_core/test_assignments.py` `test_parent_deliverable_vs_track_bead_and_handoff_contracts`: drop the doc/reference equality and assert the handoff rules ("waiting for PR merge", the Vietnamese PR option) against `skills/execute/SKILL.md`, which enforces them.

## Docs Test (`tests/test_docs_coverage.py`)

1. Every directory in `plugins/*/src/skills/` appears as `` `<name>` `` in `docs/reference/skills.md`.
2. Every subcommand of the `gin-workflow` parser has a heading in `docs/reference/cli.md`.
3. Every relative Markdown link in `README.md`, `AGENTS.md`, `CLAUDE.md`, and `docs/**/*.md` resolves to an existing file.
4. Every ```` ```mermaid ```` block starts with a known diagram type (`flowchart`, `graph`, `sequenceDiagram`, `stateDiagram-v2`, `stateDiagram`, `classDiagram`, `erDiagram`).

## Verification

- Full unittest suite and `tests/install_smoke_test.sh` pass.
- The docs test passes.
- All six diagrams render with `npx @mermaid-js/mermaid-cli` (manual check at verify, not CI).
- Read-only commands shown in the docs (`--help`, `state`, `usage report`, `rules --files`) are run and their output matches the docs.
- README is at most about 6 KB.
- Independent review compares docs against code with no finding of severity important or higher left open.

## Non-goals

- Generated reference pages.
- A docs site or static site generator.
- Full Vietnamese translation beyond the quickstart.
- Changing plugin behavior; the only code change is the `waivers.py` comment.

## Risks

- Installed snapshots keep the removed references until reinstalled; harmless because no skill reads them.
- The Vietnamese quickstart can drift from the English one; accepted because it is short and links to the English pages.
