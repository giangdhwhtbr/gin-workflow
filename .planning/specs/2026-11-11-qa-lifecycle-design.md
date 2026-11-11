# QA tracks and acceptance cases in the lifecycle

Epic: gin-workflow-qa-lifecycle
Status: confirmed by the user on 2026-11-11.

## Goal and scope

A plan can route a track to the `qa` provider role, and `/gin:execute` then runs it through the matching gin-qa skill, validates it with gin-qa, and commits it like any track; `/gin:ship` stops when gin-qa reports missing or stale acceptance cases; the reviewer sees gin-qa's coverage rows; and the QA and git-flow checklists cover testability per pull request kind.

The process review (`.planning/reviews/2026-11-07-process-review/synthesis.md`, cluster "QA tracks and acceptance cases in the lifecycle") found (QA-6, QA-7, QA-13, QA-14, QA-20):
- `/gin:execute` sends every track to `gin:developer` and never mentions gin-qa (`plugins/gin-workflow/src/skills/execute/SKILL.md:35`); gin-qa skills never commit (`plugins/gin-qa/src/skills/cases/SKILL.md:21`), so a QA track has no path to a commit and a review.
- `/gin:ship` runs no QA check (`plugins/gin-workflow/src/skills/ship/SKILL.md:16-18`), so an epic can ship with missing or stale cases; `gin-qa cases check --change <epic>` already reports them under the SDD layout.
- The reviewer does not consult `gin-qa cases plan` (`plugins/gin-workflow/src/skills/review/SKILL.md:23`).
- The ship approval checklist (`docs/guides/qa.md`, "Ship approval checklist") asks a green e2e run on every pull request, impossible for a contract or service pull request; the BA spec checklist has no testability item (`docs/guides/git-flow.md`).
- Provider roles have no `qa` preset (`plugins/gin-workflow/src/scripts/workflow_core/project.py:81-84`).
- Stage budgets: execute 11,970 and review 11,971 of 12,000 characters, ship 10,682.

`gin-workflow-qa-workspace` shipped (merge 531a3a6b): gin-qa resolves a QA home, so a QA track can run in a worktree of the `qa` child.

In scope:
- A1 the `qa` role and the execute QA-track path.
- A2 the ship gate.
- A3 reviewer coverage input.
- A4 checklists.

Out of scope:
- Evidence publishing and bug beads from automated failures (QA-8, QA-9, QA-17): a separate roadmap epic.
- Legacy parity testing (QA-10, BE-LEAD-24): a separate roadmap epic.
- Checking case `Result:` fields.
- Host CODEOWNERS for `qe` (documented as advice only).

Confirmed summary (user, 2026-11-11): this epic covers only cluster A; B and C become separate roadmap epics at the next `/gin:roadmap`. A QA track is marked by the `qa` provider role, available by default.

Comments considered: 1, latest 2026-11-11T08:10:59Z

## Requirements

R1. The provider role `qa` is available by default: the routing presets of every project shape include it, routed to the main harness like `docs` and `general`. Existing configs that define their own roles keep them; a missing `qa` role in an existing effective config is added by `gin setup refresh` the way other preset roles are.

R2. A new on-demand skill `plugins/gin-workflow/src/skills/qa-track/SKILL.md` (`qa-track`) describes the QA track: it is dispatched to `gin:developer` like any track, with the gin-qa skill that matches its files (`gin-qa:cases`, `gin-qa:tests`, or `gin-qa:e2e`) as the instructions and `gin rules --files` for the case files; it is validated with `gin-qa cases check --change <epic>`, plus `gin-qa e2e check` or `gin-qa tests check` when it changed e2e specs or tests; the developer commits in the track's worktree (the `qa` child's worktree in a workspace) because gin-qa skills do not commit; review and close follow the normal execute steps.

R3. `execute/SKILL.md` names the `qa-track` skill for tracks routed to `qa` in one sentence (a named skill loads on demand, so it does not count toward the execute chain). The execute stage chain stays within 12,000 characters; any characters added are cut elsewhere without dropping a rule.

R4. `ship/SKILL.md` step 1 adds: with `gin-qa` on PATH and `project.layout: sdd`, run `gin-qa cases check --change <epic> --format json` and stop on exit 1, reporting the findings; with the legacy layout or without gin-qa, say the QA check was skipped. The ship stage chain stays within 12,000 characters.

R5. The `sdd` skill adds: with gin-qa installed, the reviewer runs `gin-qa cases plan --change <epic> --format json` and treats `missing` or `stale` rows for the track's REQ-IDs as missing tests. The review stage chain size does not grow.

R6. `docs/guides/qa.md` splits the ship approval checklist by pull request kind (contract: contract or schema tests; service: `api` cases; app: e2e against mocks) and adds an integration sign-off at the milestone integration point. `docs/guides/git-flow.md` adds a testability item to the BA spec review checklist and recommends a non-gating `qe` review of spec pull requests. The team pull request template and `design-spec.md` template add one testability line. `references/way-of-working.md` names the integration sign-off. `docs/concepts/lifecycle.md` states the QA track and the ship QA check. The `.vi.md` pairs of changed pages follow.

## User Stories

### US-1: A QA track runs like any track
As a QA engineer, I want my case and test tracks executed, reviewed, and closed through `/gin:execute`, so that QA work is not closed by hand.

Acceptance criteria:
- A plan track with `Provider role: qa` resolves without configuring a role.
- `execute/SKILL.md` names the `qa-track` skill for `qa` tracks, and that skill names the gin-qa skills, the validation commands, and the commit in the track worktree.
- The execute stage chain is at most 12,000 characters.

### US-2: Ship stops on missing acceptance cases
As a QA engineer, I want ship to stop when a REQ of the epic has no case or a stale case, so that untested requirements do not ship.

Acceptance criteria:
- `ship/SKILL.md` runs `gin-qa cases check --change <epic>` under the SDD layout with gin-qa installed and stops on exit 1.
- Without gin-qa or with the legacy layout, ship states that the QA check was skipped.

### US-3: Review sees acceptance coverage
As a reviewer, I want gin-qa's coverage rows for the track's REQs, so that "each REQ has a test" includes acceptance cases.

Acceptance criteria:
- The `sdd` skill tells the reviewer to read `gin-qa cases plan --change <epic>` rows for the track's REQ-IDs.

### US-4: Checklists fit the pull request
As a tester, I want a ship checklist per pull request kind and a testability item in spec review, so that a contract or service pull request is not asked for an e2e run it cannot have.

Acceptance criteria:
- `docs/guides/qa.md` has checklists for contract, service, and app pull requests and an integration sign-off.
- `docs/guides/git-flow.md` has the testability item and the `qe` review note.

## Errors and compatibility

- Configs with their own provider roles are not overwritten; the `qa` preset is only added where presets apply.
- Projects without gin-qa or with the legacy layout see no new failure, only a skipped-check line at ship.
- No JSON output or Beads metadata changes.

## Testing

- `tests/workflow_core/test_token_budget.py` for the execute, review, ship, and sdd skills.
- A skill text test: execute names the `qa-track` skill; ship names `gin-qa cases check`.
- A test that the `qa` role is in the presets and resolves in `gin routes resolve`.
- `gin docs check` on changed docs.

## Open Technical Questions

## Assumptions

- The skill that matches a QA track's files is chosen by the developer from the file paths (`cases/`, test globs, `e2e/` of the QA home).
- The `qa` preset routes to the main harness with no model override; plans still set `Model:` and `Effort:`.
