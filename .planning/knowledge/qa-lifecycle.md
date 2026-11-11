# QA tracks, the ship QA check, and the qa-track skill

**Context**
Epic `gin-workflow-qa-lifecycle` (2026-11-11), cluster A of the process review "QA tracks and acceptance cases in the lifecycle" (QA-6, QA-7, QA-13, QA-14, QA-20). `/gin:execute` never mentioned gin-qa and gin-qa skills never commit, so a QA track had no path to a commit and a review; `/gin:ship` ran no QA check; the reviewer ignored `gin-qa cases plan`; the ship checklist asked an e2e run of every pull request; no `qa` provider role existed.

**Decision/Solution**
- `qa` is a provider role in every preset of `ROLES_BY_SHAPE` (`project.py`), routed to the main harness like `docs` and `general`. Presets apply only when setup proposes assignments (`gin setup preset`); `gin setup refresh` does not add preset roles, so an existing project adds `qa` by re-running setup or configuring the role.
- `skills/qa-track/SKILL.md` is the single core file that names `gin-qa` (`tests/gin_qa/test_packaging.py::test_core_never_refers_to_gin_qa` exempts exactly it). It holds the QA track (dispatch to `gin:developer` with the matching `gin-qa:cases`/`tests`/`e2e` skill, validate with `gin-qa ... check`, commit in the track worktree), "Ship check", and "Review coverage".
- `execute/SKILL.md`, `ship/SKILL.md` step 1, and `sdd/SKILL.md` name the `qa-track` skill instead of gin-qa commands; a named skill loads on demand and does not count toward a stage chain.
- Ship check: with gin-qa on PATH and `project.layout: sdd`, `gin-qa cases check --change <epic> --format json`; exit 1 stops ship; exit 2 (usage or environment error) is reported and counts as skipped; without gin-qa or with the legacy layout ship says the QA check was skipped.
- Review coverage: `missing` or `stale` rows of `gin-qa cases plan --change <epic> --format json` for the track's REQs count as missing tests.
- `docs/guides/qa.md` splits the ship checklist by pull request kind (contract, service, app) plus an integration sign-off per milestone; `git-flow.md` adds a spec testability item and a non-gating `qe` review note.

**Consequences**
- The plan put `gin-qa` commands directly into ship and sdd; the full suite caught the core invariant, and the commands moved into `qa-track`. Check core-invariant tests when a plan names an add-on inside `plugins/gin-workflow/src` (templates too: the PR template says "QA cases check").
- Budgets are tight: execute chain 11,950 of 12,000, review 11,971, `sdd/SKILL.md` 5,987 of 6,000. New guidance belongs in on-demand skills.
- A post-approval fix needs the reviewer to move the ledger `review-approved` → `implementation-in-progress` (reviewer role only), then checkpoint, `review-requested`, and a new review.
- `gin-qa api run` does not exist; API cases run with `gin-qa tests run --type api`.

**References**
- `plugins/gin-workflow/src/skills/{qa-track,execute,ship,sdd}/SKILL.md`; `plugins/gin-workflow/src/scripts/workflow_core/project.py`
- Tests: `tests/workflow_core/test_token_budget.py`, `tests/workflow_core/test_project_settings.py`, `tests/gin_qa/test_packaging.py`
- Docs: `docs/guides/qa.md`, `docs/guides/git-flow.md`, `docs/concepts/lifecycle.md`, `docs/reference/skills.md`, and `.vi.md` pairs
- `.planning/specs/2026-11-11-qa-lifecycle-design.md`, `.planning/plans/2026-11-11-qa-lifecycle.md`
- Beads: `gin-workflow-qa-lifecycle`, `.1` to `.3`
- Related: [gin-qa-qa-home](gin-qa-qa-home.md), [process-review](process-review.md), [review-ledger-cycle-limit](review-ledger-cycle-limit.md)

**Scope**
How QA work runs through execute, review, and ship, and where the core may name gin-qa.
