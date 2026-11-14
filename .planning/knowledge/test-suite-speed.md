# Test suite speed: where the time goes and how to keep it down

**Context**
Bead `gin-workflow-a21c` (2026-11-14). Every track runs the full suite at least once (`gin evidence run`), and the pre-push hook runs it again; it took 342 s on this 4-CPU host (`python3 -m pytest -n auto`), with 245,521 subtests. The user asked to drop verbose tests while every feature keeps a behaviour test, and to keep one suite (no markers that skip tests in `gin evidence run`).

**Decision/Solution**
- Measured costs on this host:
  - A `bd` call costs about 0.27 s for `list` and 0.4 to 0.5 s for a write, because each one starts embedded Dolt.
  - A `gin` call costs about 0.48 s as a subprocess and about 0.016 s in-process once warm.
  - A `gin-qa` call costs about 0.28 s, of which about 0.2 s is its nested `gin specs reqs` subprocess.
  - pytest reports every `subTest`. One subtest per scanned line in `tests/workflow_core/test_rename_sweep.py` made 243,828 subtests and about 17 s; one subtest per file (first offending line in the message) takes 0.7 s.
- Patterns now in the suite:
  - Run the CLI in-process through `team_fixtures.run_cli_in_process` and `qa_fixtures.qa_in_process`. Keep one subprocess test per CLI subcommand, so the launcher, argument parsing, and exit codes stay covered.
  - Build expensive fixtures (bd databases, Dolt remotes, git origins, approved review-ledger tracks) once per class and give each test a `shutil.copytree` copy. Do not copy a linked git worktree: `git worktree repair` on a copy rewrote the template's links. Re-point copied Dolt remotes with `bd dolt remote remove/add`.
  - To prove that a refused command wrote nothing, compare a byte snapshot of `.beads/embeddeddolt/*/.dolt/noms` instead of running `bd list` twice. Reads leave it unchanged; any write changes the manifest and journal. `temptf/dolt_embedded_metrics` changes on the first read, so it is excluded.
- Result: 342 s to 195 s wall (-43%), 2193 to 2186 tests (7 redundant tests merged or removed, each with its covering test listed in the review), 3,054 subtests. No production code changed.

**Consequences**
- What remains slow is real bd and Dolt work that no other test covers: `tests/workflow_core/test_milestone_cli.py` (about 72 s single-process) and `tests/workflow_core/test_team_beads.py` (about 85 s).
- `gin task ready` hands bd's output straight to the terminal when nothing is held, so an in-process run cannot capture it; those tests stay subprocesses.
- A new test that runs `gin` or `gin-qa` should use the in-process helpers unless it is the subcommand's one subprocess test. A new line-by-line scan should report one subtest per file.
- Wall-clock scheduler tests flaked under parallel load (`gin-workflow-2o6e`, `gin-workflow-mj2c`, `gin-workflow-el1d`); each fix widened the window a timer must hit. To prove such a fix, shift the timer delay in a scratch copy of the test: CPU-burning processes do not reproduce a race between threads of one Python process (el1d: 0/200 failures with 4 burners and 0/100 with 16, while a 40 ms later timer reproduced the failure). Loops under artificial load cost most of el1d's 42 minutes; do not use them.
- Copied fixtures keep `core.hooksPath` and the Dolt backup URL of the template. This has no effect today, but it would matter if a test ran hooks or a Dolt backup.

**References**
- `tests/workflow_core/team_fixtures.py`, `tests/gin_qa/qa_fixtures.py`; `tests/workflow_core/test_milestone_cli.py`, `test_team_beads.py`, `test_team_gates.py`, `test_tasks.py`, `test_rename_sweep.py`; `tests/gin_qa/test_cases_cli.py`, `test_e2e_cli.py`; `tests/review_ledger/test_sequential_tracks.py`
- Beads: `gin-workflow-a21c`, `gin-workflow-el1d`

**Scope**
Writing or changing tests in this repository, and judging suite time.
