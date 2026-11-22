# Run history per case: one JSONL file per tester and month

**Context**
Epic `gin-workflow-g2gx` (2026-11-22, spec `.planning/specs/2026-11-22-qa-run-history-design.md`). `record_result` overwrote `Result`, `Run`, `Bug`, `Checked`, so only the latest result of a case existed; gin-console's QA trends (`gin-console-rm-test-trends`: pass rate, flaky cases, time to fix) need every result. The capability is exported as `qa-run-history`.

**Decision/Solution**
- `cases.record_result` stays the one writer: it appends the run record (`runs.append`) under the `.gin-qa.lock` it already holds, after building the new case text and before `write_atomic`. A failed append raises `ValueError` naming the run file and the case file is not written. `cases result`, `cases bug`, `e2e run`, and `tests run` all get history from this one place.
- Layout: `runs/<yyyy-mm>/<actor slug>.jsonl` next to the cases folder (`runs.runs_dir`, like `e2e.evidence_root`). One file per tester and month, so two testers never write the same file and their branches merge on any host. The first append adds `/<runs>/** merge=union` to `.gitattributes` for one tester on two branches; checked by hand that union also merges the add/add case where both branches create the same new file. GitHub's merge button may not apply the driver, so the per-tester file is the real guarantee.
- The actor defaults to `git config user.email` (the identity team mode uses), else `unknown`. `--actor` and `--evidence` go into the record only, never into the case file.
- `gin-qa runs export` reads the working tree only, sorts by `at`, then file, then line, and lists bad lines in `problems` with exit 0. Its key table in `docs/reference/cli.md` (`gin-qa runs export`) is the contract gin-console reads: keys are added, never renamed.
- `cases renumber` leaves records unchanged (a record keeps the TC-ID it ran under); rewriting other testers' lines would break append-only and the conflict-free merge. `cases to-manual` appends nothing.

**Consequences**
- Two branches that record different results for one case still conflict in the case file; only the run files are conflict-free.
- Skills that save QA work (`run`, `e2e`, `tests`) commit the `runs` folder and `.gitattributes` with the case files.
- Open notes from review: `runs export` exits 2 when a `runs/*/*.jsonl` path is a directory or unreadable; `_AT` uses `\d`, which accepts Unicode digits; `e2e._record` catches only `ValueError`, so an `OSError` from writing a case file (older behaviour) stops the remaining cases.

**References**
- `plugins/gin-qa/src/scripts/gin_qa/runs.py`, `cases.py` (`record_result`), `bugs.py` (`file_bug`), `e2e.py` (`_record`), `tests.py` (`run`), `cli.py` (`runs export`)
- `docs/reference/cli.md` (`gin-qa runs export`), `docs/guides/qa.md` (Run history)
- Beads: `gin-workflow-g2gx.1`, `.2`, `.3`
- Related: [gin-qa-due-runs](gin-qa-due-runs.md) (the `Checked` stamp of `record_result`), [gin-qa-utilities](gin-qa-utilities.md) (case writers re-parse under the lock)

**Scope**
gin-qa result recording, the run history files, and `gin-qa runs export`.
