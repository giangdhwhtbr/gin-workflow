# gin-qa utilities: flaky e2e cases move to manual, re-run notes, and tester chores as commands

**Context**
Epic `gin-workflow-uj96` (2026-11-07/08). Testers did file and shell chores by hand around gin-qa. A failed re-run on an open bug dropped the tester's actual result and evidence. QA had no supported way to take a flaky e2e case off the pipeline.

**Decision/Solution**
- `gin-qa cases to-manual <TC-ID> --reason <why>` renames `.e2e.md` to `.manual.md` and writes `Moved from e2e: <date>: <reason>`. It sets `Result: not run`, removes `Run:`, keeps `Bug:`, and deletes the spec last. QA decides when; gin-qa does not count pipeline failures. Moving back is by hand.
- `Moved from e2e` is in `KNOWN_FIELDS`, so `hash8` does not change. `as_dict` exposes `moved_from_e2e`, and the report has a "Moved from e2e to manual" section and a `moved` count.
- `gin-qa cases bug` on an open bug appends one notes line (`Re-run <date>; Run: ...; Actual: ...; Evidence: ...`) with `gin task update --append-notes`, before the case changes; json gains `appended`.
- `gin-qa cases new` writes a case file with the next ID and the pin (`--req` with SDD, `--source` with legacy). `gin-qa report --zip` writes `<folder>.zip`. `gin-qa e2e init --install` installs Playwright and chromium with the lockfile's manager. `e2e init` merges step snapshots into an older `evidence.ts` only on an exact anchor match.

**Consequences**
- A case writer must re-parse the case under `_lock` and run every file-state check there, as `record_result` does; a parse before the lock used stale line numbers (review F1 of `.1`).
- Write before rename, and validate before the first side effect: a refused command leaves no file or folder behind. `cases new` creates the capability folder inside the lock, because an empty `qa/cases/<cap>/` next to a flat `<cap>.md` fails `cases check` (review F1 of `.2`); `init --install` reads `package.json` before writing anything.
- A value passed to `gin` as an argument holds no newline and no double quote: a Windows `.cmd` shim cuts at the first newline and re-parses quotes.
- Open notes: docs say a type "not listed under `## Types`" is refused, but without that section any valid type is accepted; `report --zip` overwrites an older archive of the same name; the merge has no test on the real old fixture (checked by hand in review).

**References**
- `plugins/gin-qa/src/scripts/gin_qa/cases.py` (`move_to_manual`, `new_case`, `moved_from_e2e`), `e2e.py` (`to_manual`, `ignore_evidence`, `init`, `_install`, `_merge_snapshot`), `bugs.py` (`rerun_note`), `report.py` (`_archive`), `templates/report.html`
- `.planning/specs/2026-11-07-qa-utilities-design.md`, `.planning/plans/2026-11-07-qa-utilities.md`
- Beads: `gin-workflow-uj96`, `.1` to `.4`
- Related: [gin-qa-automated-types](gin-qa-automated-types.md), [gin-qa-case-files](gin-qa-case-files.md)

**Scope**
The gin-qa CLI, its report template, skills, and the QA guide.
