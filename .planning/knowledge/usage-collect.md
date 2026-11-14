# Usage collect: one bd list, one history per bead

**Context**
Bead `gin-workflow-y8g6` (2026-11-12). `usage.collect` on an epic ran `bd show` per bead, a parent-child `dep list`, and per bead `bd history` twice plus a discovered-from `dep list`: about 4 bd calls per child, around 30s for 10 tracks on Linux and far more on Windows.

**Decision/Solution**
- `collect` runs `bd list --all -n 0 --json` once. Its rows carry `parent`, `started_at`, `closed_at`, `issue_type`, and `dependencies` (`{issue_id, depends_on_id, type}`), so they replace `bd show`, the parent-child `dep list` (children are rows whose `parent` is the epic), and the discovered-from `dep list` (bug rows with a `discovered-from` dependency on the bead).
- `bd history` runs once per bead per collect and is shared by `_span` and `quality`. A bead or parent missing from the rows raises `UsageError("bd show <id>: no such bead")`.
- `quality(..., history=None, rows=None)` keeps its own bd calls when called without them.

**Consequences**
- An epic with N children costs 1 list + (N + 1) history + 1 update; `tests/workflow_core/test_usage.py` asserts the exact call list.
- The lower-priority call sites the bead named (`review_ledger/cleanup.py`, `team_beads.deps`, `specs.py`) still call bd per bead.
- `gin-workflow-4sa5` (`gin task ready` runs bd twice) needs a decision on rendering ready output; its evaluation is in the bead notes.
- Summaries cannot be merged across machines: each `collect` overwrites `ai_usage` from local logs and stores no record identity, so adding a child's summary to its epic's can double count (gin-console's `own_share` subtracts children instead). `gin usage report` marks such totals `partial` with reasons ([team-progress](team-progress.md)).

**References**
- `plugins/gin-workflow/src/scripts/workflow_core/usage.py` (`collect`, `quality`, `_span`, `_row`); `tests/workflow_core/test_usage.py`, `tests/workflow_core/test_usage_cli.py`
- Beads: `gin-workflow-y8g6`, `gin-workflow-4sa5`

**Scope**
Bead lookups in `gin usage collect`.
