# gin-qa automated types: the declared Run command and test markers

**Context**
Epic `gin-workflow-qa-test-types` (2026-11-04) added `gin-qa tests {plan,pin,check,run}` for case types other than e2e, declared in `qa/guidelines.md` under `## Automated types` with `- Tests:` globs and a `- Run:` command. Review found defects at the boundary between the declaration and the files and processes it reaches.

**Decision/Solution**
- `Tests:` globs are repository-relative: an absolute glob (POSIX or Windows) or one with a `..` segment is a declaration error. Without it, marker scanning read files outside the repository and `pin` could rewrite them.
- The Run command is split with `shlex` and runs without a shell from the repository root; the program is resolved with `shutil.which` before the run folder exists, so "not found" exits 2 and leaves nothing behind. `{files}` expands to repository-root-relative paths, so a runner option that changes folder breaks it: `uv run --directory backend` changes the working folder, `uv run --project backend` does not (checked with `os.getcwd()`). Docs and the skill use `--project`.
- A JUnit test case belongs to a case when its `classname name`, upper-cased with `_` read as `-`, holds the TC-ID followed by a non-digit (`(?<![A-Z0-9])ID(?!\d)`), so `TC-AUTH-001` does not match `TC-AUTH-0012`.
- Writers that touch several files (`tests pin`) read and edit all of them in memory first and write only when every file succeeded; an unreadable JUnit file or a failed result write is a finding, not an abort.

**Consequences**
- `tests pin`, like `e2e pin` and the case writers, rewrites CRLF files with LF (bead `gin-workflow-kbzn`).
- `tests plan <TC-ID>` treats the TC-ID as a capability and finds nothing (bead `gin-workflow-w9et`); the skill runs `plan` per capability instead.
- `qa/evidence/` is git-ignored only by `gin-qa e2e init`; a tests-only project adds the entry itself.

**References**
- `plugins/gin-qa/src/scripts/gin_qa/tests.py` (`declared`, `_files`, `markers`, `pin`, `_junit`, `run`)
- `plugins/gin-qa/src/skills/tests/SKILL.md`, `docs/reference/cli.md` (`gin-qa tests`)
- `tests/gin_qa/test_tests_cli.py`
- Beads: `gin-workflow-qa-test-types.1`, `.2`, `.3`

**Scope**
gin-qa code and docs for declared automated types and their test files.
