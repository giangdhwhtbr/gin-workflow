# gin-qa: re-run only what a change needs, and never show an old result as current

Epic: gin-workflow-4706
Workflow: gin-workflow-4706
Kind: capability
Status: confirmed by the user on 2026-11-19.

## Goal and scope

After a change, QA should re-run the affected manual cases plus a risk-based regression set, not every manual case of a capability. gin-qa pins each case to `REQ-ID@hash8` and `gin-qa cases plan` lists `missing`, `stale`, and `obsolete` cases, but:

- `/gin-qa:run <capability>` walks every manual case of the capability (`plugins/gin-qa/src/skills/run/SKILL.md` step 2); the tester answers `skip` case by case to leave the rest out.
- A case's `Result:` stays as it was when the case turns stale, when it is re-pinned after its requirement changed, or when its steps are edited (`cases.hash8` covers the title, free fields, and sections, not the pins or the result). The export and `/gin-qa:report` then show `passed` for a case never run against what it now says.

Confirmed decisions (2026-11-19):

- Every recorded result is stamped with the case's state at the time; an old result whose case changed since, or whose requirement changed since, reads as `outdated`.
- `/gin-qa:run` runs only what needs running by default (not run, outdated, failed, blocked, plus the regression set); `--all` runs everything as today; `--change <epic>` narrows to the cases pinned to that change's requirements.
- The regression set is declared in the guidelines by priority.

Assumptions (defaults, not asked):

- The stamp is a new case field `Checked: <stamp8>`, written by the same code path that writes `Result`, `Run`, and `Bug` (`cases.record_result`), so manual results, `gin-qa e2e run`, and `gin-qa tests run` are all stamped. `Checked` joins `KNOWN_FIELDS`, so it never changes a case's `hash8`.
- `stamp8` is the first 8 hex characters of the SHA-256 of the case's `hash8` followed by its `REQ` pins (`REQ-ID@hash8`, in file order) or, for a legacy-layout case, its `Source:` value.
- A result recorded before this change has no `Checked`; it reads as `outdated` only when the case is stale.
- `outdated` is a read-time value: nothing rewrites case files when a requirement or case changes.
- `move_to_manual` keeps writing `Result: not run` and drops `Checked`.
- The regression levels are `none`, `high`, `high+medium`, read from `Priority:`; a case without priority is never in the regression set.

Out of scope:
- Automatic selection of cases for changes that touch no requirement (code-only fixes); QA picks those with `--all` or by priority.
- Changing how `gin-qa e2e` or `gin-qa tests` choose what to run.
- gin-console.

## Requirements

### R1. Result stamp

`cases.record_result` writes `Checked: <stamp8>` next to `Result` and `Run` (the existing `_with_result` helper), where `stamp8 = cases.stamp8(case)`. `Checked` is in `KNOWN_FIELDS`. `gin-qa cases check` accepts the field and reports a value that is not 8 lowercase hex characters: `<file>:<line>: <TC-ID>: Checked must be 8 hex characters`.

### R2. Effective result

`cases.effective_result(case, reqs) -> str`, where `reqs` maps REQ-ID to its current hash (the same data `cases plan` uses), returns:
- `outdated` when `Result` is `passed`, `failed`, or `blocked` and either a pinned requirement's current hash differs from its pin (the case is stale) or `Checked` is present and differs from `stamp8(case)`;
- otherwise the `Result` value (`not run` when absent).

A requirement that no longer exists (an obsolete pin) also makes the result `outdated`.

### R3. Export and report

- `gin-qa cases export --format json` rows gain `effective_result` and `checked`; `result` keeps the raw value.
- `/gin-qa:report` (`report.build` and its page) uses `effective_result` for the result chart, the result filter, and the result shown in the table and the case detail; `outdated` is a value of each, and the detail shows the raw result as "last recorded".

### R4. Cases due

`gin-qa cases due <capability> [--change <epic>] [--all] [--format json]` lists the manual cases (`Type: manual`) of the capability to run, sorted by ID, each with its reason:
- default: cases whose effective result is `not run`, `outdated`, `failed`, or `blocked` (`todo`), plus the regression set (`regression`) for the rest;
- `--change <epic>`: the same rule, limited to cases pinned to a requirement the change adds or modifies (from `gin specs reqs --change`); the regression set is still added. Cases pinned only to removed requirements are obsolete and never due;
- `--all`: every manual case of the capability (`all`).

A case in several groups is listed once, with the first reason in the order todo, regression, all. Text output: `<TC-ID> <reason> <effective result> <title>` per line; JSON: `{"capability", "change", "cases": [{"id", "title", "reason", "effective_result", "priority"}]}`. An unknown capability gives an empty list, as `cases plan` does; an unknown change exits 2 with gin's message.

### R5. Regression set

The guidelines' `## Manual runs` section may hold `Regression: none | high | high+medium`. `none` (the default when the line is missing) adds no case; `high` adds manual cases with `Priority: high`; `high+medium` adds `high` and `medium`. Another value makes `gin-qa cases check` report `<guidelines>:<line>: Regression must be none, high, or high+medium`, like its other guidelines findings. The guidelines template gains the line with `none`.

### R6. Run skill

`/gin-qa:run <capability> [--change <epic>] [--all]` takes its cases from `gin-qa cases due` instead of the whole export, shows each case's reason and effective result with it, and otherwise works as today (one case at a time, results through `cases result`, bugs through `cases bug`). With no case due it says so and stops. The skill stays within its character budget.

### R7. Documentation

`docs/guides/qa.md` and `.vi.md` (manual runs: what is due, outdated results, the regression line), `docs/reference/cli.md` (`cases due`, `cases export` fields, `cases check` messages).

## User Stories

### US-1: Re-run only what a change needs
As a tester, I want `/gin-qa:run` to offer only the cases that need running after a change, so that I do not walk every manual case of the capability again.

Acceptance criteria:
- With three manual cases, one `passed` and current, one `outdated`, one `not run`, `gin-qa cases due <cap>` lists the outdated and not-run cases with reason `todo`, and not the current passed one.
- With `Regression: high` and the current passed case at `Priority: high`, it is listed with reason `regression`.
- `--all` lists all three with reason `all`.
- `--change <epic>` lists only the due cases pinned to requirements the change adds or modifies, plus the regression set.

### US-2: Never read an old result as current
As a QA lead, I want a result recorded before its case or requirement changed to read as outdated, so that the report never shows passed for something not run against the current text.

Acceptance criteria:
- After `cases result TC-X passed`, editing a step of TC-X makes its `effective_result` `outdated` in `cases export`; its `result` stays `passed`.
- After its requirement changes and `cases pin TC-X`, the effective result is `outdated` until `cases result` is run again.
- A stale case (requirement changed, not re-pinned) reads `outdated` with or without a `Checked` line.
- `/gin-qa:report` counts and filters `outdated` and shows the last recorded result in the case detail.
- `cases result`, `e2e run`, and `tests run` all write `Checked`; `move_to_manual` drops it.

## Errors and compatibility

- Case files written before this change have no `Checked`; they parse, check, and export as before, and only stale ones read `outdated`.
- `Checked` does not change a case's `hash8`, so e2e spec headers and test markers stay current.
- `cases check` reports a malformed `Checked` and an unknown `Regression` value (exit 1).
- `cases due` with an unknown capability lists nothing; an unknown `--change` exits 2.
- Export keeps every existing key; `effective_result` and `checked` are added.
- `dist/` is regenerated by the build; no hand edits there.

## Testing

- gin-qa unit tests (the existing `tests/gin_qa/` files for cases, cli, report): `stamp8`, `Checked` written by `cases result`, `e2e run`, and `tests run`, dropped by `move_to_manual`; `effective_result` for an edited case, a re-pinned case, a stale case with and without `Checked`, an obsolete pin, a not-run case; `cases check` on a malformed `Checked` and a bad `Regression`; `cases due` default, `--change`, `--all`, each regression level, ordering and reasons; export fields; report chart, filter, and detail with `outdated`.
- Skill routing or budget test for the run skill when one covers it.
- `gin docs check` on the changed pages; full suite through the pre-push hook.

## Open Technical Questions
