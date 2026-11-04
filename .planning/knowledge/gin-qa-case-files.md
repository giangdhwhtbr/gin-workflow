# gin-qa case files: line splitting and IDs in file names

**Context**
Epic `gin-workflow-qa-case-folders` (2026-11-04) added per-case files `qa/cases/<cap>/<TC-ID>[-<slug>].<type>.md` and writers that edit case files in place (`cases result`, `cases split`, `cases pin`, `e2e run` recording). Review found two defects that recur whenever a parser and a writer address the same file by line number or name.

**Decision/Solution**
- The parser and every writer split a case file the same way: `read_text().split("\n")` (`cases._lines`). `str.splitlines()` also breaks on `\x0b`, `\x0c`, `\x1c`-`\x1e`, `\x85`, `\u2028`, `\u2029`, so line numbers from a `splitlines()` parser drift from a `split("\n")` writer and `result` rewrote the wrong lines while `split` deleted `Priority:` instead of `Type:`. `read_text()` already turns `\r\n` and `\r` into `\n`.
- `TC_ID` and `_CASE_FILE` use a lazy capability group (`TC-([A-Z][A-Z0-9-]*?)-(\d{3,})`), so a slug starting with digits stays a slug: `TC-AUTH-005-2024-tax.e2e.md` is `TC-AUTH-005`. A greedy group read it as capability `AUTH-005`, number 2024, and `next-id` could reuse 005.
- Values written into a case line (`--run`, `--bug`) must be `str.isprintable()`; a check for `ord < 32` lets `\u2028`, `\x85`, and `\x7f` through and corrupts the file for the next parse.

**Consequences**
- A capability whose name has an all-digit segment of three or more digits (`api-100`) is not recognised in case file names or by `next-id`; `check` reports the mismatch, so it is not silent.
- Because `read_text()` normalises line endings, every writer rewrites a CRLF file with LF (case files, e2e specs, and test files under `tests pin`); bead `gin-workflow-kbzn` tracks keeping them.
- `split` and `pin` do not take the `.gin-qa.lock` that `record_result` holds; revisit if several processes write the same cases file.

**References**
- `plugins/gin-qa/src/scripts/gin_qa/cases.py` (`_lines`, `TC_ID`, `_CASE_FILE`, `record_result`, `split`)
- `tests/gin_qa/test_cases_cli.py` (`test_odd_line_breaks_keep_writes_on_their_lines`, `TestCaseFiles`)
- Beads: `gin-workflow-qa-case-folders.1`, `gin-workflow-qa-case-folders.2`

**Scope**
gin-qa code that reads or writes test case files.
