# Merge Strategy

Phase 6 of the orchestrator: merge completed worktree branches into the integration
branch, close the epic, and hand off to `/ship`.

`mode=shared` workers have already committed to `integration_branch` directly — skip
all merge steps for those tracks. This document applies to `mode=worktree` tracks.

---

## Order

Iterate `complete_tracks` in the order they appear in `exec-plan.tracks` (Phase 2
produced this order from `bv --robot-plan`, which respects bd cross-track dependencies
via topological sort over the issue graph).

When tracks have no cross-deps, any order is correct; we use exec-plan order for
determinism.

Skip tracks where `track_status != "complete"` — they route to `needs_human` handling.

---

## Per-track merge

`mode=worktree` only. For each complete track in exec-plan order:

```bash
# track.worktree_branch shape: orchestrate-wt/<epic_id>-<agent_name>
# (flat sibling, NOT <integration_branch>/<agent_name> which causes git ref hierarchy conflict)
git merge <track.worktree_branch> \
  --no-ff \
  -m "Merge track <agent_name> (<bead_count> beads)"
```

On success:

```bash
git worktree remove <track.worktree_path>
```

---

## Conflict policy

On `git merge` conflict:

1. Abort the merge immediately:
   ```bash
   git merge --abort
   ```

2. Notify the track worker and `$HUMAN_NAME` (the user's auto-generated mail identity; printed at orchestration start):
   ```python
   mcp__mcp-agent-mail__send_message(
       sender_name  = coordinator_name,
       sender_token = load_token(coordinator_name),   # from agent-tokens.json
       to           = [agent_name, human_name],        # $HUMAN_NAME — auto-generated user identity
       thread_id    = epic_id,
       subject      = "[<agent_name>] Merge conflict",
       body_md      = "Conflicted files:\n<list>\n\nDiff summary:\n<diff excerpt>",
       importance   = "high",
       ack_required = True
   )
   ```

3. Mark the track `next_action = "needs_human"` in the final report.

4. **KEEP the worktree** — do NOT remove it. The human needs to inspect and resolve
   the conflict manually. Removing it would discard the work.

5. Continue with the next track. Do not block the merge loop on one conflict.

---

## After all merges

**If all complete and no `needs_human` tracks:**

```bash
bd close "$epic_id" --reason "Orchestrate complete" --actor "$COORDINATOR_NAME"
```

Per-track thread summary:
```python
for track in complete_tracks:
    mcp__mcp-agent-mail__summarize_thread(
        project_key = project_key,
        thread_id   = f"track-{track.agent_name}-{epic_id}"  # dashes, NOT colons
    )
```

**If any partial or failed tracks:**

```bash
bd update "$epic_id" --status blocked \
  --description "Partial: <failed/partial track list>" \
  --actor "$COORDINATOR_NAME"
```

**Final summary mail to all workers + `$HUMAN_NAME`:**

```python
mcp__mcp-agent-mail__send_message(
    sender_name  = coordinator_name,
    sender_token = load_token(coordinator_name),    # from agent-tokens.json
    to           = all_agent_names + [human_name],  # $HUMAN_NAME — auto-generated user identity
    thread_id    = epic_id,
    subject      = "Orchestration complete — <epic_id>",
    body_md      = (
        "## Track outcomes\n"
        "<track-by-track summary table>\n\n"
        "## Integration branch\n"
        f"`{integration_branch}`\n\n"
        "Run `/ship` when ready."
    ),
    importance = "normal"
)
```

---

## Push (optional)

The orchestrator does NOT auto-push to the remote. Handoff to `/ship`:

```
Integration branch: <integration_branch>. Run /ship when ready.
```

Print this to the user and stop. Do NOT invoke `/ship` automatically.
