# gin-qa due runs: stamped results, outdated results, and a regression set by priority

**Context**
Epic `gin-workflow-4706` (2026-11-19). A user asked whether QA must re-run every manual case of a capability after a change. `/gin-qa:run` walked every manual case, and a case kept its old `Result: passed` after its requirement changed, after a re-pin, or after its steps were edited, so the export and the report showed passed for something never run against the current text.

**Decision/Solution**
- Every recorded result is stamped: `cases.record_result` (the one writer, used by `cases result`, `cases bug`, `e2e run`, and `tests run`) writes `Checked: <stamp8>`, where `stamp8` hashes the case's `hash8` and its pins (or `Source:`). `Checked` is in `RESULT_FIELDS`, so `_with_result` replaces it, `move_to_manual` drops it, and `KNOWN_FIELDS` keeps it out of `hash8` (e2e headers and test markers stay current).
- `cases.effective_result(case, current)` is computed at read time and never written: a `passed`/`failed`/`blocked` result reads `outdated` when a pin differs from the requirement's current hash or the requirement is gone, or when `Checked` differs from the current `stamp8`. Results recorded before the stamp read outdated only when stale. `reqs.current_hashes(eff)` is None in the legacy layout, which skips the requirement check. Resetting `Result` on `pin` was rejected at discuss: it misses hand edits of a case.
- `cases export` adds `checked` and `effective_result` (raw `result` kept); `/gin-qa:report` charts, filters, and shows the effective result and the last recorded one.
- `gin-qa cases due <capability> [--change <epic>] [--all]` lists the manual cases to run with a reason: `todo` (not run, outdated, failed, blocked; with `--change`, only cases pinned to added or modified requirements, via `cli._scope`), `regression` (by the guidelines' `- Regression: none | high | high+medium` under `## Manual runs`, priority compared ignoring case, independent of `--change`), or `all`. `/gin-qa:run` walks that list.

**Consequences**
- An outdated case outside `--change` still appears as regression when its priority matches the level.
- Changes that touch no requirement (code-only fixes) select no case by themselves; QA uses the regression set or `--all`.
- Open MINOR items: an empty `- Regression:` value reads as `none` without a finding; report markup tests use substring checks; no report-level legacy-layout test.

**References**
- `plugins/gin-qa/src/scripts/gin_qa/cases.py`, `reqs.py`, `cli.py`, `report.py`; `plugins/gin-qa/src/templates/report.html`, `guidelines.md`; `plugins/gin-qa/src/skills/run/SKILL.md`
- Tests: `tests/gin_qa/test_cases_cli.py`, `test_cases_bug.py`, `test_cases_to_manual.py`, `test_e2e_cli.py`, `test_tests_cli.py`, `test_report.py`
- Docs: `docs/guides/qa.md` (and `.vi.md`), `docs/reference/cli.md`
- `.planning/specs/2026-11-19-qa-rerun-design.md`, `.planning/plans/2026-11-19-qa-rerun.md`
- Beads: `gin-workflow-4706`, `.1` to `.4`
- Related: [gin-qa-case-files](gin-qa-case-files.md), [qa-lifecycle](qa-lifecycle.md), [qa-evidence](qa-evidence.md)

**Scope**
gin-qa manual runs, case results, export, and report.
