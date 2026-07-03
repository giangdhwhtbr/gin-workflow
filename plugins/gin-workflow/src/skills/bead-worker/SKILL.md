---
name: bead-worker
description: |
  Subagent-only protocol for executing a track of bd beads using the
  bd + bv + agent-mail trio. Loaded by bead-orchestrator's spawned
  subagents. Not for main-session use. Supports two modes: shared
  (single checkout) or worktree (isolated per track).
---

# Bead Worker (subagent protocol)

Loop over an assigned list of bd beads using the bd + bv + agent-mail trio. Each bead → claim, work, commit, close, hand off self-notes. Return a single JSON message at the end.

---

## When NOT to invoke

If running in main session (orchestrator, user-facing assistant, any non-subagent context), STOP and surface the task to `bead-orchestrator`. This skill is meaningless in main session because parallel work is the orchestrator's job.

---

## Inputs

Common inputs, received in the subagent prompt:

| Variable | Notes |
|---|---|
| `epic_id` | Mail thread for orchestrator-worker comm. |
| `agent_name` | Worker mail identity (auto-assigned by orchestrator: `BlueLake`, `RedFox`, …). |
| `coordinator_name` | Orchestrator mail name (`Conductor-<epic_id_short>`). |
| `track_thread_id` | Mail thread for cross-bead self-context within this track. Format: `track-<agent_name>-<epic_id>` (dashes only — colons are rejected by the server). |
| `bead_ids` | Array, dependency order. |
| `file_scope` | Glob list — strict edit boundary. Worker MUST NOT edit outside these globs. |
| `project_key` | Mail invariant — absolute path of the original repo root. See "Project key invariant" below. |
| `mode` | `"shared"` or `"worktree"`. |
| `integration_branch` | Target branch name. |

`mode=worktree` adds: `worktree_path`, `worktree_branch`.

`mode=shared` adds: `test_cmd_template` (with `{path}` placeholder, e.g. `pnpm --filter {path} test`).

---

## Project key invariant

CRITICAL: Every `mcp__mcp-agent-mail__*` call (or curl shell-out per OV2 fallback) MUST pass `project_key = absolute path of the original repo root` (`git rev-parse --show-toplevel` run from OUTSIDE any worktree). Do NOT recompute from `pwd` — in worktree mode, `pwd` is `<worktree_path>`, not the repo root, and using it will create a phantom project in agent-mail.

---

## Working directory

| Mode | `cd` to |
|---|---|
| shared | inherited from orchestrator — repo root |
| worktree | `<worktree_path>` |

Use `git -C <WD>` for ALL git operations. Avoid bare `git ...` so the working directory is always explicit.

---

## Protocol

> Shell snippets use `$VAR_NAME` for inputs from the table above (e.g. `$BEAD_ID`, `$AGENT_NAME`, `$INTEGRATION_BRANCH`, `$WORKTREE_PATH`, `$FILE_SCOPE_REGEX`). The orchestrator passes these as the subagent prompt's input block; export them at the start of the run.

Loop steps 1–3 for each `bead_id` in `bead_ids` order. Step 4 = end-of-track (run once after the loop).

### 1. START BEAD

```bash
# Once per track only — guard with first-bead check.
if [ "$BEAD_ID" = "${bead_ids[0]}" ]; then
  mcp__mcp-agent-mail__register_agent(
    project_key, name=$AGENT_NAME, program="claude-code",
    model=<model_id>, task_description="track of $EPIC_ID"
  )
  # Read self-notes from previous bead in this track (only meaningful on first bead):
  mcp__mcp-agent-mail__summarize_thread(project_key, thread_id=$TRACK_THREAD_ID)
fi

# Advisory file lock (TTL 30 min):
mcp__mcp-agent-mail__file_reservation_paths(
  project_key, $AGENT_NAME, paths=$FILE_SCOPE,
  ttl_seconds=1800, exclusive=true, reason=$BEAD_ID
)
# If conflict reported: send_message(to=holder, ack_required=true).
# Wait ≤5 min. No reply → mail $HUMAN_NAME (the user's auto-generated mail identity, printed at orchestration start), mark bead skipped (skip 3a, do 3b with --status skipped — see fail/skipped path under step 3), continue.

bd update $BEAD_ID --status in_progress --actor "$AGENT_NAME"
# OR atomic claim form:
# bd update $BEAD_ID --claim --actor "$AGENT_NAME"
# If --claim exits non-zero, the bead is already claimed — log to track thread and skip.
```

**OV2 fallback:** per OV2 (verifications notes), workers may not have `mcp__mcp-agent-mail__*` tools in their toolset. If absent, use curl shell-out fallback (see `references/trio-cheatsheet.md` `## agent-mail (MCP)`). If even curl fails, skip the mail/reservation calls and rely on the JSON return contract (§ "Return contract") — orchestrator translates outcomes to mail.

### 2. WORK

- `bd show $BEAD_ID` → read body, implement.
- Edit ONLY paths matching `file_scope`. Use Read/Edit/Write.
- Test:
  - `mode=shared`: run `test_cmd_template` with `{path}` substituted by the bead's `file_scope` root. Examples: monorepo per-package via `pnpm --filter @org/sdk test`; single-package repo via `npm test -- {path}`; Go via `go test ./{path}/...`. The orchestrator derives `test_cmd_template` from repo signals at pre-flight; `{path}` is whatever scopes the test to the bead's edits.
  - `mode=worktree`: run repo's full test command.
- Test fail × 3 attempts → DONE-fail (skip 3a, mark `--status failed`, see step 3 fail-path below).
- Periodically (every few minutes for long beads): `fetch_inbox(agent_name, urgent_only=true, include_bodies=true)`. Heed urgent mail (especially file-reservation conflicts and orchestrator instructions).

### 3. DONE BEAD

**3a. Stage + commit.**

Capture `EDITED` files from `git status --porcelain` (uncommitted changes in the worker's WD, intersected with `file_scope` globs). Capture this list BEFORE staging so glob expansion is stable; never expand later globs that could pick up unrelated dirty state.

`mode=shared` (race-safe):
```bash
if git ls-remote --exit-code origin "$INTEGRATION_BRANCH" >/dev/null 2>&1; then
  git pull --ff-only origin "$INTEGRATION_BRANCH" || (sleep 1 && git pull --ff-only origin "$INTEGRATION_BRANCH")
fi
# If the integration branch doesn't exist on origin yet, this is the first push — nothing to pull.
EDITED=$(git status --porcelain | awk '{print $2}' | grep -E "$FILE_SCOPE_REGEX")
git add $EDITED                              # never `.` or `-A`
for attempt in 1 2 3; do
  git commit -m "$BEAD_ID: $TITLE" && break
  sleep $(awk "BEGIN{print 0.5 * 2^($attempt - 1)}")  # 0.5/1/2 backoff for index.lock
done
```

`mode=worktree`:
```bash
EDITED=$(git -C $WORKTREE_PATH status --porcelain | awk '{print $2}')
git -C $WORKTREE_PATH add $EDITED
git -C $WORKTREE_PATH commit -m "$BEAD_ID: $TITLE"
```

**3b. Capture commit + close bd:**
```bash
COMMIT=$(git rev-parse HEAD)   # or git -C $WORKTREE_PATH rev-parse HEAD
bd close $BEAD_ID --reason "<one-line>" --actor "$AGENT_NAME"
```

**3c. Report to coordinator (epic thread):**
```
send_message(to=[$COORDINATOR_NAME], thread_id=$EPIC_ID,
             subject="[$BEAD_ID] COMPLETE",
             body_md="commit: $COMMIT\nsummary: ...")
```

**3d. Self-note for next bead in track (track thread):**
```
send_message(to=[$AGENT_NAME], thread_id=$TRACK_THREAD_ID,
             subject="$BEAD_ID DONE — context",
             body_md="## Learnings\n…\n## Gotchas\n…\n## Next-bead notes\n…")
```

**3e. Release reservation:**
```
release_file_reservations(project_key, $AGENT_NAME, paths=$FILE_SCOPE)
```

**Fail-path** (test fail × 3, file-reservation timeout, or other unrecoverable): skip 3a (no commit). Do 3b as `bd update $BEAD_ID --status failed --actor "$AGENT_NAME"` (NOT `bd close`). 3c subject `[$BEAD_ID] FAILED` body with stderr or reason. Still do 3e.

**Skipped-path** (file reservation conflict, no holder reply within 5 min): same as fail-path but `--status skipped` and subject `[$BEAD_ID] SKIPPED`.

### 4. END OF TRACK

```
send_message(to=[$COORDINATOR_NAME], thread_id=$EPIC_ID,
             subject="[Track $AGENT_NAME] COMPLETE",
             body_md="<bead summary list>")
```

Then return JSON contract (see "Return contract" section below + `references/return-schema.md` for full schema) as the FINAL assistant message. **No prose before or after the JSON.** Orchestrator parses with `jq` and any prose pollutes the parse.

---

## Failure modes

| Symptom | Action |
|---|---|
| `bd update --claim` returns non-zero (another worker holds it) | Skip bead, log to track thread, continue. |
| File reservation conflict | Mail holder ack=true, 5 min timeout, escalate `$HUMAN_NAME` (auto-generated mail identity printed by orchestrator at run start), mark `--status skipped`. |
| Test fail × 3 | Mark `--status failed`, NO `bd close`, urgent mail with stderr. |
| `.git/index.lock` (shared mode) | Retry 3× backoff (0.5/1/2 s); persist → mark bead failed, halt track. |
| MCP transient error | Retry once; persist → return early `track_status="failed"`. |
| Token budget ≥ 80% | Stop after current bead, return `track_status="partial"`. |
| Worker has no MCP tools (OV2 fallback) | Use curl shell-out per `trio-cheatsheet.md`; if curl also fails, skip mail and rely on return JSON. |

---

## Return contract

```jsonc
{
  "track":         "<agent_name>",
  "epic_id":       "<bd-...>",
  "mode":          "shared" | "worktree",
  "bead_outcomes": [
    { "bead_id": "<bd-...>",
      "status":  "closed" | "failed" | "skipped",
      "commit":  "<sha>" | null,
      "reason":  "<short>" }
  ],
  "worktree_path":   "<path>" | null,
  "worktree_branch": "<branch>" | null,
  "track_status":    "complete" | "partial" | "failed",
  "next_action":     "merge" | "nothing" | "needs_human" | "abort",
  "mail_sent":       true | false   // optional; absent = false. If false, orchestrator
                                    // translates bead_outcomes into per-bead mail messages.
}
```

Full rules and the `next_action` decision matrix are in `references/return-schema.md` (which lives under `bead-orchestrator/references/` since it's primarily orchestrator-consumed; worker still reads it as the contract source-of-truth).

---

## References

- `references/trio-cheatsheet.md` — exact CLI/MCP signatures for bd, bv. Read on demand.
- Worker also defers to `bead-orchestrator/references/return-schema.md` for the JSON contract — but workers MUST emit the JSON exactly per the schema in this file's "Return contract" section.
