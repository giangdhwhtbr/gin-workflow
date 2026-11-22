# gin-qa keeps a run history per case

Epic: gin-workflow-g2gx
Kind: capability
Points: 5 (3 stories, 1 new CLI module, 4 callers of one writer, 2 skills, 3 docs; low risk: git union merge; same size as gin-workflow-05e5)
Status: draft for user review.

## Goal and scope

`gin-qa cases result` overwrites `Result`, `Run`, `Bug`, and `Checked` in the case file, so only the latest result of a case exists. e2e and tests runs keep their per-run data in the gitignored `qa/evidence/` folder (`e2e.ignore_evidence`, `plugins/gin-qa/src/scripts/gin_qa/e2e.py:199`). gin-console plans QA trends (`gin-console-rm-test-trends`: pass rate per capability over runs, flaky cases, median time from a failed run to the next pass), which need every result, not the latest.

Every result reaches the case file through one function, `record_result` (`cases.py:431`), called by `cases result` (`cli.py:238`), `cases bug` (`bugs.py:208`, `bugs.py:240`), `e2e run` (`e2e.py:364`), and `tests run` (`tests.py:315`). It takes no actor, time, or evidence today.

This epic makes `record_result` also append one run record per result to a tracked JSONL file that merges without conflicts, and adds `gin-qa runs export`. The case file keeps the latest result as today.

In scope:

- The run record, its file layout, and the `.gitattributes` union merge entry.
- `--actor` on `cases result`, `cases bug`, `e2e run`, `tests run`; `--evidence` on `cases result`.
- `gin-qa runs export` and its JSON contract.
- The `run` and `e2e` skills commit the run files with the case files.
- `docs/reference/cli.md`, `docs/guides/qa.md`, `docs/guides/qa.vi.md`.

Out of scope:

- Backfilling history from existing case files or git log.
- Trends, flaky detection, or history in `gin-qa report`; gin-console computes them.
- gin-console itself.
- Pruning or rotating old run files.
- `docs/changelog.md`, written at release time.

Assumptions:

- The actor defaults to `git config user.email`, the identity gin team mode already uses (`plugins/gin-workflow/src/scripts/workflow_core/team.py:191`); `unknown` when it is unset.
- `cases to-manual` writes `Result: not run` without a run (`cases.py:480`) and appends no record.
- `runs export` reads the working tree only, not other branches or git history.
- The record adds `capability` to the keys the epic lists, so a per-capability trend still works after a case is deleted or renamed.

## Requirements

### R1: Run record on every result

- `record_result` takes `actor` and `evidence` (a list of paths) and appends one record per call, under the lock it already holds, before it writes the case file. When the append fails, the case file is not written and the call raises an error that names the run file.
- The record is one line of JSON with sorted keys and no spaces after separators:

  ```json
  {"actor":"a@x.com","at":"2026-11-22T10:15:03Z","bug":"gin-workflow-abc","capability":"auth","case":"TC-AUTH-005","evidence":["qa/evidence/2026-11-22T10-15-03/tc-auth-005"],"hash8":"1a2b3c4d","result":"failed","run":"manual 2026-11-22"}
  ```

  - `at`: UTC time of the call, ISO 8601 to the second with `Z`.
  - `case`, `capability`: the case id and its capability, as `cases export` reports them.
  - `hash8`: `hash8(case)` (`cases.py:292`) of the case as recorded.
  - `result`: the status written to the case.
  - `run`, `bug`: the values the case file holds after the call; `""` when absent.
  - `evidence`: the evidence references as given (repository-relative folders for e2e and tests runs, the `--evidence` values, paths or links, for `cases result` and `cases bug`), `[]` when none.
- Callers:
  - `cases result <id> <status> [--run REF] [--bug REF] [--actor ID] [--evidence PATH]...`; `--evidence` is repeatable.
  - `cases bug ... [--actor ID]` passes its existing `--evidence` values.
  - `e2e run [--actor ID]` passes `<run folder>/<tc-id lowercase>` per case.
  - `tests run [--actor ID]` passes the run folder.
- `--actor` defaults per the assumption above.

### R2: File layout and merge

- The run directory is `runs` next to the cases directory (the parent of `qa.cases` plus `/runs`, default `qa/runs`), the way `evidence_root` sits next to the e2e directory.
- A record goes to `<runs>/<yyyy-mm of at>/<slug(actor)>.jsonl`. `slug` lowercases the actor and replaces each run of characters outside `[a-z0-9._-]` with `-` (`a@x.com` → `a-x.com`).
- The first append in a repository adds the line `/<runs>/** merge=union` to `.gitattributes` (creating it when missing) and never adds it twice.
- Two testers never write the same file, so their branches merge without conflicts on any host. One tester appending on two branches merges by union in a local `git merge`.

### R3: `gin-qa runs export`

- `gin-qa runs export [--capability CAP] [--case TC-ID] [--since YYYY-MM-DD] [--format text|json]`; `json` prints an object with `runs` and `problems` through the existing `_emit`.
- `runs` holds every record of every `<runs>/*/*.jsonl` file that passes the filters, sorted by `at`, then file path, then line number. `--since` keeps records with `at` on or after that UTC date. Filters combine with AND.
- A line that is not a JSON object with the R1 keys adds `"<file>:<line>: <reason>"` to `problems` and is skipped; the other records are still returned.
- Exit codes: 0 for the export, with or without problems; 2 for a usage error (bad date, unknown format). No run directory gives `{"runs": [], "problems": []}`.
- Text output: one line per record, `<at> <case> <result> <actor> <run>`, then one line per problem.

### R4: Skills and docs

- `run` skill: the commit step names the run file(s) written in the session along with the case files.
- `e2e` skill: the commit after `gin-qa e2e run` includes the run files.
- `docs/reference/cli.md`: `cases result` documents `--actor` and `--evidence`; a new `gin-qa runs export` entry holds a table of every record key, which is the contract gin-console reads; the command list in the `gin-qa` section names `runs export`.
- `docs/guides/qa.md` and `docs/guides/qa.vi.md`: a short section on the run history (where it lives, why it merges cleanly, how to export it).

## User Stories

### US-1: Every result is kept
As a tester, I want every result I record to stay as a run record, so that a later run does not erase the earlier ones.

Acceptance criteria:
- `gin-qa cases result TC-AUTH-005 failed --run "manual 2026-11-22" --actor a@x.com` and then `... passed ...` leave two lines in `qa/runs/2026-11/a-x.com.jsonl`, `failed` first, each with the R1 keys.
- Without `--actor`, the file is named after `git config user.email`; with it unset, `unknown.jsonl`.
- `gin-qa cases bug TC-AUTH-005 --actual ... --evidence shot.png` appends a `failed` record whose `bug` is the new bead and whose `evidence` is `["shot.png"]`.
- `gin-qa e2e run` and `gin-qa tests run` append one record per recorded case, with the per-case folder or the run folder as `evidence`.
- The case file after these calls is byte-identical to what the same calls write today, and `gin-qa cases export` output is unchanged.
- When the run file cannot be written, `cases result` exits non-zero, names the file, and the case file is unchanged.

### US-2: Testers' histories merge cleanly
As a QA team member, I want run records from different testers and branches to merge without conflicts, so that nobody resolves conflicts in history files.

Acceptance criteria:
- Testers `a@x.com` and `b@x.com` each record a result for the same case on their own branch; `git merge` of both branches reports no conflict and both records are present.
- One tester records results on two branches; a local `git merge` reports no conflict and keeps both lines.
- After the first append, `.gitattributes` holds `/qa/runs/** merge=union` exactly once, also after further appends.

### US-3: Export for gin-console
As a gin-console maintainer, I want `gin-qa runs export --format json` with filters, so that the console can chart pass rate, flaky cases, and time to fix.

Acceptance criteria:
- Two runs of one case give two records in `runs`, sorted by `at`.
- `--capability auth`, `--case TC-AUTH-005`, and `--since 2026-11-22` each return only the matching records.
- A run file with a broken line returns the other records, lists `<file>:<line>: ...` in `problems`, and exits 0.
- A repository without `qa/runs` prints `{"problems": [], "runs": []}` and exits 0.
- `--since 2026-13-01` exits 2.

## Errors and compatibility

- The case file format, `cases export`, `cases due`, `e2e export`, and `report` are unchanged; existing callers without `--actor` or `--evidence` keep working.
- A failed append stops `cases result` and `cases bug` before the case file changes. In `e2e run` and `tests run` it joins the existing `<case>: result not recorded: <error>` findings for that case, and the other cases are still recorded.
- An existing `.gitattributes` keeps its lines; the entry is appended.
- Record keys are only ever added, never renamed or removed (the gin-console JSON rule of the roadmap constraints).

## Testing

- New `tests/gin_qa/test_runs_cli.py` (`unittest`, `qa_fixtures`, in-process `qa`; one subprocess test for `runs export`): R1 record keys and order, actor default and `unknown`, `--evidence`, failed-append leaves the case file unchanged, `.gitattributes` written once, export filters, sort order, problems, empty run directory, bad `--since`.
- A real-git test: two branches with different actors, and two branches with the same actor, each merged with `git merge`; no conflict and all records present.
- `test_cases_bug.py`, `test_e2e_cli.py`, `test_tests_cli.py`: each path appends records with the expected `evidence` and `actor`.
- Existing `cases export` and `cases result` tests pass unchanged.

## Open Technical Questions
