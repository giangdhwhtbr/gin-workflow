# Worker Return Schema

Normative definition of the JSON the worker subagent emits as its final message.

> Worker emits this JSON as the FINAL assistant message — no prose before or after.
> Orchestrator parses with `jq`.

---

## Schema

```jsonc
{
  "track":         "<agent_name>",
  "epic_id":       "<bd-...>",
  "mode":          "shared" | "worktree",
  "bead_outcomes": [
    {
      "bead_id": "<bd-...>",
      "status":  "closed" | "failed" | "skipped",
      "commit":  "<sha>" | null,
      "reason":  "<short one-line description>"
    }
  ],
  "worktree_path":   "<absolute_path>" | null,
  "worktree_branch": "<branch_name>" | null,
  "track_status":    "complete" | "partial" | "failed",
  "next_action":     "merge" | "nothing" | "needs_human" | "abort",
  "mail_sent":       true | false   // OPTIONAL. Absent = false. When false (or absent),
                                    // orchestrator Phase 4 translates bead_outcomes into
                                    // per-bead mail messages on the worker's behalf.
                                    // Workers with MCP access should set true if they
                                    // sent their own bead/track mail.
}
```

---

## track_status rule

| Value      | Condition |
|------------|-----------|
| `complete` | All beads in `bead_outcomes` have `status = "closed"` |
| `partial`  | At least one `"closed"` AND at least one `"failed"` or `"skipped"` |
| `failed`   | Zero `"closed"` beads (all failed or skipped) |

---

## next_action by mode + status

| mode       | track_status   | next_action    |
|------------|----------------|----------------|
| `shared`   | `complete`     | `nothing`      |
| `worktree` | `complete`     | `merge`        |
| any        | `partial`      | `needs_human`  |
| any        | `failed`       | `needs_human`  |
| any        | (pre-flight)   | `abort`        |

`pre-flight` means the worker aborted before executing any bead (e.g. failed to acquire
file reservation, invalid inputs, MCP initialization failure). Zero bead_outcomes entries.

`worktree_path` and `worktree_branch` are non-null only when `mode = "worktree"`. They
MUST be set when mode is worktree — the orchestrator uses them for `git merge` and
`git worktree remove`.
