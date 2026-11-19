# Gap-free TC-ID numbering in gin-qa

Workflow: tc-id-numbering
Kind: capability
Status: draft for user review.

## Goal and scope

Testers want the test case IDs of a capability to run without gaps (TC-AUTH-001, 002, 003, …): the cases folder and the `/gin-qa:report` output read better. Today `next_id` (`plugins/gin-qa/src/scripts/gin_qa/cases.py:255`) takes one past the highest number found in the flat cases file, the case file names, and the `git log` of both, so a number is never given out again: every deleted case leaves a permanent gap, and history from other branches makes numbers jump.

In scope:

- `gin-qa cases next-id <cap>` and `gin-qa cases new` give the lowest free number, read from the files on disk only; git history is no longer read.
- A new command `gin-qa cases renumber <cap> [--dry-run]` that closes the gaps of a capability that already has them, and rewrites every reference gin-qa owns.
- The `cases` skill, `docs/reference/cli.md`, and `docs/guides/qa.md` / `qa.vi.md` updated for both.

Out of scope:

- Collisions between parallel branches that each take the same new number. They stay as today: `gin-qa cases check` reports `duplicate` after the merge.
- Rewriting bug bead titles, external tracker entries, JUnit files of `gin-qa tests run` folders, or reports already exported.
- `gin specs next-id` for REQ-IDs (gin-workflow): unchanged.

Assumptions:

- A number that a deleted case used may be given to a new case. Bug beads stay linked through the case's `Bug:` line, which goes away with the deleted file, so no bead is re-linked.
- `renumber` is run when no other branch is adding cases to the same capability; otherwise the merge conflicts or produces duplicates.
- Renumbering keeps the order: the case with the smaller number keeps the smaller number.

## Requirements

### R1: Lowest free number

- `next_id(root, cases_dir, cap)` returns `TC-<CAP>-NNN` with the smallest `NNN ≥ 1` that is not taken. A number is taken when, for this capability:
  - a case uses it: a file name in `<cases>/<cap>/`, or a TC-ID in the flat `<cases>/<cap>.md`;
  - an e2e spec uses it: a file `<e2e>/<cap>/tc-<cap>-NNN.spec.ts`, or the TC-ID on its `// TC:` header;
  - an automated test marker uses it: `TC: TC-<CAP>-NNN@<hash8>` in a file matched by the `Tests:` globs of `## Automated types` in the guidelines.
- No `git` process is started; the result is the same inside and outside a git repository, on any branch with the same files.
- `gin-qa cases new` keeps taking the cases lock around `next_id` and the file write.
- Example: cases 001, 002, 004 give 003; when an orphan e2e spec `tc-auth-003.spec.ts` still exists, they give 005.

### R2: `gin-qa cases renumber <cap>`

- Mapping: the capability's cases sorted by number get 001..N; cases whose number does not change are left alone. With no gap, it prints `nothing to renumber` and exits 0.
- Every rewrite applies the whole mapping in one regex pass, and renames go through temporary names, so `003 -> 002` never collides with `002 -> 001`. TC-IDs match with boundaries (`TC-AUTH-005` never matches inside `TC-AUTH-0050`).
- Rewrites, for each renumbered case:
  - the case file: renamed `<old-ID>-<slug>.<type>.md` → `<new-ID>-<slug>.<type>.md`, heading `# <old-ID>:` → `# <new-ID>:`;
  - its e2e spec: renamed `tc-<cap>-<old>.spec.ts` → `tc-<cap>-<new>.spec.ts`; the TC-ID in the `// TC:` header and in `test('<ID>: …')` rewritten;
  - automated test files matched by the `Tests:` globs: the TC-ID in `TC:` markers, and in test names in the forms `TC-AUTH-005`, `tc-auth-005`, `tc_auth_005`, `TC_AUTH_005`;
  - evidence: for each run folder named on a renumbered case's `Run:` line that is an e2e run folder under the evidence folder, `<run>/<old-id>/` → `<run>/<new-id>/`, the `tc` field of each `result.json` under it, and the renamed spec paths in that run's `run.json` `specs` list.
- Pins stay valid: `hash8` of a case does not include its ID, and the `@<hash8>` part of headers and markers is not touched.
- Refuses with exit 1 and writes nothing when:
  - `<cases>/<cap>.md` exists (run `gin-qa cases split <cap>` first);
  - the capability has a duplicate TC-ID, an orphan e2e spec, or an orphan automated test marker (a TC-ID with no case), each listed;
  - a case file, e2e spec, or automated test file it would change or rename is modified, staged, or untracked in git, each listed, so that `git diff` after the run holds only the renumbering;
  - a target name already exists.
- `--dry-run` prints the mapping and the files it would change, and writes nothing.
- Output: `--format text` prints `old -> new` lines (ASCII, so a Windows console can print them), the changed files, and a closing line naming what is not rewritten (bug bead titles, `gin-qa tests run` folders, exported reports). `--format json` prints `{"mapping": {old: new}, "files": [...], "untouched": [...]}`.
- Runs under the same cases lock as `new`.
- The evidence folder is in `.gitignore` (`gin-qa e2e init`, `tests run`, and `report` add it, `e2e.py:198`), so the uncommitted-changes rule covers only tracked files.

### R3: Skill and docs

- `cases` skill: a step telling the agent to run `gin-qa cases renumber <cap>` only when the user asks to close the gaps, show the `--dry-run` mapping first, then run it and `gin-qa cases check`, `gin-qa e2e check`, `gin-qa tests check`.
- `next-id` documented as "lowest free number in the current files"; the "never reused" wording removed from the docstring and the docs.

## User Stories

### US-1: New cases fill the gaps
As a tester, I want a new test case to take the lowest free number of its capability, so that the case list has no gaps after cases are deleted.

Acceptance criteria:
- With cases TC-AUTH-001, 002, 004 and nothing else referencing 003, `gin-qa cases next-id auth` prints `TC-AUTH-003`.
- With an e2e spec `tc-auth-003.spec.ts` left from a deleted case, it prints `TC-AUTH-005`.
- With a `TC: TC-AUTH-003@<hash8>` marker left in an automated test file, it prints `TC-AUTH-005`.
- A case deleted in an earlier commit no longer blocks its number.
- `next-id` gives the same result in a folder that is not a git repository.

### US-2: Close existing gaps
As a tester, I want to renumber the cases of a capability to 001..N, so that a capability that already has gaps reads cleanly in the report.

Acceptance criteria:
- With cases 001, 002, 005, 009, `renumber auth --dry-run` prints `TC-AUTH-005 -> TC-AUTH-003` and `TC-AUTH-009 -> TC-AUTH-004` and changes no file.
- `renumber auth` renames the two case files and their headings, renames their e2e specs and rewrites header and test title, and rewrites matching markers and test names in automated test files.
- After `renumber`, `gin-qa cases check`, `gin-qa e2e check`, and `gin-qa tests check` report no new finding.
- A renumbered case whose `Run:` names an e2e run folder shows the same results and screenshots in `/gin-qa:report` as before.
- With no gap, `renumber auth` prints `nothing to renumber` and exits 0.
- With a flat `auth.md`, an orphan spec, a duplicate ID, or an uncommitted change in a file it would touch, `renumber auth` exits 1, names the cause, and changes no file.

## Errors and compatibility

- `next-id` output format is unchanged (`TC-<CAP>-NNN`); only the number chosen changes.
- `renumber` is a new subcommand; the `cases` usage line lists it.
- Bug beads filed under an old ID keep the old ID in their title; the case still links them through `Bug:`.
- A deleted case's number can come back on a different case. Old bug titles and old exported reports then name a number that now means another case; the output of `renumber` and the docs say so.

## Testing

- `tests/gin_qa/test_cases_cli.py`: replace `test_next_id_never_reuses_a_number` and `test_next_id_counts_file_names_and_their_history` with tests for gap filling, numbers held by an orphan e2e spec and by an automated test marker, deleted-in-history numbers reused, and a run outside git.
- `tests/gin_qa/test_workspace_root.py`: the `next_id` tests that rely on child history follow the new rule.
- New `tests/gin_qa/test_cases_renumber.py`: dry run writes nothing; case, e2e spec, marker, test name, and evidence rewrites; mapping applied in one pass (no chained replace); each refusal; nothing to renumber; JSON output.
- Run one file: see `docs/contributing.md`.

## Open Technical Questions
