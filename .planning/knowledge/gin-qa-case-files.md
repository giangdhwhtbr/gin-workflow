# gin-qa case files: line splitting, IDs in file names, and numbering

**Context**
Epic `gin-workflow-qa-case-folders` (2026-11-04) added per-case files `qa/cases/<cap>/<TC-ID>[-<slug>].<type>.md` and writers that edit case files in place (`cases result`, `cases split`, `cases pin`, `e2e run` recording). Review found two defects that recur whenever a parser and a writer address the same file by line number or name.

**Decision/Solution**
- The parser and every writer split a case file the same way: `read_text().split("\n")` (`cases._lines`). `str.splitlines()` also breaks on `\x0b`, `\x0c`, `\x1c`-`\x1e`, `\x85`, `\u2028`, `\u2029`, so line numbers from a `splitlines()` parser drift from a `split("\n")` writer and `result` rewrote the wrong lines while `split` deleted `Priority:` instead of `Type:`. `read_text()` already turns `\r\n` and `\r` into `\n`.
- `TC_ID` and `_CASE_FILE` use a lazy capability group (`TC-([A-Z][A-Z0-9-]*?)-(\d{3,})`), so a slug starting with digits stays a slug: `TC-AUTH-005-2024-tax.e2e.md` is `TC-AUTH-005`. A greedy group read it as capability `AUTH-005`, number 2024, and `next-id` could reuse 005.
- Values written into a case line (`--run`, `--bug`) must be `str.isprintable()`; a check for `ord < 32` lets `\u2028`, `\x85`, and `\x7f` through and corrupts the file for the next parse.
- Since `gin-workflow-ixc2` (2026-11-19) `next-id` and `new` give the lowest free number of the capability, read from files on disk only; git history no longer counts, so testers get numbers without gaps. A number an e2e spec (file name or `// TC:` header) or an automated test marker still names stays taken (`numbering.held`), so a leftover spec or test never attaches to a new case. `gin-qa cases renumber <cap> [--dry-run]` closes existing gaps to 001..N and rewrites case files, e2e specs, test markers and names (four forms: `TC-AUTH-005`, `tc-auth-005`, `tc_auth_005`, `TC_AUTH_005`), and the e2e evidence named on `Run:`, in one regex pass with renames through temporary names.
- `tc.load` returns `(cases, errors)`; a caller that takes only `[0]` silently skips unparseable case files. A command that numbers or rewrites cases must refuse on the errors under its capability: review of `renumber` found it left two `TC-AUTH-003-*` files when one case file did not parse.

**Consequences**
- A capability whose name has an all-digit segment of three or more digits (`api-100`) is not recognised in case file names or by `next-id`; `check` reports the mismatch, so it is not silent.
- Because `read_text()` normalises line endings, every writer rewrites a CRLF file with LF (case files, e2e specs, and test files under `tests pin`); bead `gin-workflow-kbzn` tracks keeping them.
- `split` and `pin` do not take the `.gin-qa.lock` that `record_result` holds; revisit if several processes write the same cases file.
- A deleted case's number can come back on another case; bug bead titles and exported reports keep the old meaning. `renumber` does not rewrite bug bead titles, `gin-qa tests run` folders, or exported reports, and refuses on a flat file, an unparseable or duplicate case, an orphan spec or marker, an uncommitted file it would change, or an existing target. It reads git in the C locale because it matches git's "not a git repository" text.

**References**
- `plugins/gin-qa/src/scripts/gin_qa/cases.py` (`_lines`, `TC_ID`, `_CASE_FILE`, `record_result`, `split`, `next_id`)
- `plugins/gin-qa/src/scripts/gin_qa/numbering.py` (`held`, `renumber`)
- `tests/gin_qa/test_cases_cli.py` (`test_odd_line_breaks_keep_writes_on_their_lines`, `TestCaseFiles`)
- `tests/gin_qa/test_cases_renumber.py`
- Beads: `gin-workflow-qa-case-folders.1`, `gin-workflow-qa-case-folders.2`, `gin-workflow-ixc2.1`, `gin-workflow-ixc2.2`

**Scope**
gin-qa code that reads or writes test case files.
