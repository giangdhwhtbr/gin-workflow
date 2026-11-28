# Beads call costs and output shapes (bd 1.3.4)

**Context**
Measured while building the state card (track `gin-workflow-context-boundaries.2`, 2026-11-28), where every Beads call counts against a 15-second hook timeout.

**Decision/Solution**
- `bd show id1 id2 ...` costs about 1 s per id (48 ids: 50.9 s). `bd list --status closed --limit 0 --id a,b,...` answers the same 48 ids in 1.4 s. For many ids, use `bd list --id`.
- Concurrent `bd` calls in one repository serialize: 4 calls took 5.0 s together against 5.4 s summed alone (another run: about 7.5 s together against 5.1 s in a row). A per-call timeout must cover the queue, not one call; running the calls in a row on one thread is as fast and easier to bound.
- `bd list --json --skip-labels` returns an object `{"issues": [...], "meta", "schema_version"}`, not the plain list that gin parsers expect. Do not pass `--skip-labels` through `tasks.query_result`.

**Consequences**
- Batch reads by id with `bd list --id`, or read the whole list once (see [usage-collect](usage-collect.md), [team-lanes](team-lanes.md)).
- Do not parallelize Beads calls to save time; order them by importance within one budget ([state-card](state-card.md)).

**References**
- `plugins/gin-workflow/src/scripts/workflow_core/prime.py` (`bounded`, `shipped_among`), `tasks.py` (`query_result`)
- Beads: `gin-workflow-context-boundaries.2`; epic `[gin learn]` comments on `gin-workflow-context-boundaries`

**Scope**
Any gin command that calls `bd` more than a few times, on bd 1.3.4; measure again after a bd upgrade.
