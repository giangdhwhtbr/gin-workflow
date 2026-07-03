---
name: bead-orchestrator
description: |
  Use when running /orchestrate to execute an approved plan via parallel
  subagents. Decomposes plan into bd issues + tracks, spawns one worker
  per track (mode: shared or worktree), monitors via agent-mail, merges
  into an integration branch. Requires bd, bv, mcp-agent-mail.
---

# Bead Orchestrator

Main-session skill that turns an approved plan markdown into bd issues organized into tracks, dispatches one subagent per track, monitors progress via agent-mail, and merges results into an integration branch. Hands off to `/ship` when done. Do NOT use this skill from a subagent — workers run `bead-worker` instead.

---

## When to invoke

User runs `/orchestrate` (or directly invokes this skill). Invoked from main session only.

**Required inputs:** an approved plan file matching `references/plan-input-contract.md`.

**Required tools:**
- `bd` — beads issue tracker CLI (Homebrew Go build, v1.0.3+)
- `bv` — beads viewer (robot-plan, robot-alerts, robot-next)
- MCP `mcp__mcp-agent-mail__*` (or curl-fallback access to the local MCP HTTP endpoint per OV2/spec §17)

Skill ABORTS pre-flight if any are missing.

---

## Inputs

`$ARGUMENTS` flags parsed from the slash-command invocation:

| Flag | Default | Meaning |
|---|---|---|
| `--plan <path>` | latest in `.planning/plans/` | Plan markdown to execute. |
| `--worktree` / `--no-worktree` | auto-detect | Force execution mode. |
| `--max-tracks <N>` | 4 | Cap parallel tracks; merge smallest if exceeded. |
| `--integration-branch <name>` | `orchestrate/<epic_id>` | Target branch for merged commits. |
| `--inject-agents-md` | off | Run `bv --agents-add` once at pre-flight. |

---

## Project key invariant

Same as worker. `project_key = git rev-parse --show-toplevel` run from the original repo root (NOT from any worktree). Orchestrator computes once at pre-flight and propagates to every worker prompt.

CRITICAL: Every `mcp__mcp-agent-mail__*` call (or curl shell-out fallback per OV2) MUST pass this exact `project_key`. Do NOT recompute inside worktree paths — they return the wrong value.

---

## Phase 1 — Pre-flight

1. **Tool detection**: probe all required tools before proceeding.

   ```bash
   command -v bd   # beads CLI
   command -v bv                    # beads viewer
   mcp__mcp-agent-mail__health_check  # main-session liveness probe
   ```

   Missing any tool → ABORT with install instructions:
   - `bd` missing → `brew install beads`.
   - `bv` missing → `go install github.com/Dicklesworthstone/beads_viewer/cmd/bv@latest` (or `brew install bv` if available).
   - MCP missing in main session AND no curl access to local MCP HTTP endpoint (`http://127.0.0.1:8765/api/`) → ABORT. Install: ensure mcp-agent-mail server is running and `~/.claude.json` has the server entry; restart Claude Code session. The subagent-side MCP availability is handled in step 2.

2. **Subagent capability probe**: spawn a foreground throw-away subagent that replies JSON `{skill_ok, mcp_ok}`.

   Decision matrix:
   - `skill_ok && mcp_ok` → `dispatch_mode="skill"` (Path A — subagent uses `Skill(skill="bead-worker")`).
   - `mcp_ok` only → `dispatch_mode="inline"` (Path B — paste verbatim worker SKILL body into prompt).
   - `!mcp_ok` but curl accessible → workers use curl-fallback per OV2/spec §17.
   - Hard ABORT only if MAIN session has no MCP AND no curl access to `http://127.0.0.1:8765/api/` either.

3. **Mode resolution** per spec §3 rules. Auto-detect:

   Monorepo signals (any one of):
   - `package.json` has `"workspaces"` key
   - `pnpm-workspace.yaml` exists
   - `turbo.json` exists
   - ≥2 `go.mod` files in tree
   - `Cargo.toml` with `[workspace]` section

   Scoped test command derivable: pnpm/turbo `--filter`, `go test ./...`, `pytest <path>`.

   Both signals satisfied → `mode=shared`. Else → `mode=worktree`.

   User confirms `y/n` before continuing. Do not proceed without confirmation.

4. **bd init + epic**:

   ```bash
   bd init --prefix mde_ainative_okr_v2  # idempotent — no-op if .beads/ exists
   bd export -o .beads/issues.jsonl  # export DB → JSONL (git-tracked snapshot)
   ```

   Register the project with agent-mail before creating the epic (idempotent upsert):
   ```
   mcp__mcp-agent-mail__ensure_project(project_key, name="<plan title>")
   ```

   ```bash
   EPIC_ID=$(bd create "<plan title>" -t epic -p 1 --silent --actor "$COORDINATOR_NAME")
   ```

   If `--inject-agents-md` flag set: run `bv --agents-add` once here before epic creation.
   `bv --agents-add` injects an AGENTS.md preamble at `<repo_root>/AGENTS.md`, pointing
   AI agents to the bd issue queue. The command is idempotent — if `AGENTS.md` already
   exists it is a no-op. Failure to write the file is non-fatal: log a warning and
   continue.

5. **Branching**:
   - `mode=shared`:
     ```bash
     git checkout -B "$INTEGRATION_BRANCH"
     if git remote get-url origin >/dev/null 2>&1; then
       git push -u origin "$INTEGRATION_BRANCH" 2>/dev/null || true
     fi
     # Push makes the integration branch available for worker-side `git pull --ff-only`.
     # Skip silently if no remote — local-only repos work fine without the push.
     ```
   - `mode=worktree`:
     ```bash
     git checkout -B "$INTEGRATION_BRANCH"  # create integration branch on the orchestrator's checkout
     # Per-track worktree branches are created in Phase 3 from this branch as base.
     # Branch naming: flat sibling form orchestrate-wt/<epic_id>-<agent_name>
     # (NOT <integration_branch>/<agent_name> — git refuses to create a child ref under a leaf branch).
     ```

6. **Coordinator identity**:

   ```bash
   # Use the suffix after the last '-' — unique across epics regardless of prefix length.
   EPIC_SUFFIX="${EPIC_ID##*-}"   # e.g. "l1e" from "mde_ainative_okr_v2-l1e"
   COORDINATOR_NAME="Conductor-${EPIC_SUFFIX}"

   # Register coordinator and capture token. project_key obtained in step 4 above.
   COORDINATOR_TOKEN=$(mcp__mcp-agent-mail__register_agent(
     project_key, name=$COORDINATOR_NAME, program="claude-code",
     model=<model_id>, task_description="orchestrator for $EPIC_ID"
   ).registration_token)

   # Allow all agents to mail coordinator without contact-approval handshake.
   mcp__mcp-agent-mail__set_contact_policy(
     project_key, agent_name=$COORDINATOR_NAME, policy="open",
     registration_token=$COORDINATOR_TOKEN
   )

   # Register the user as a mail recipient with an auto-generated identity.
   # Omit name → server returns an adjective+noun name like "BrightCat".
   HUMAN_NAME=$(mcp__mcp-agent-mail__register_agent(
     project_key, program="human", model="human"
   ).name)
   HUMAN_TOKEN=$(mcp__mcp-agent-mail__register_agent(
     project_key, program="human", model="human"
   ).registration_token)
   # NOTE: call register_agent once and capture both .name and .registration_token
   # from the single response. Above shows two captures for clarity only.
   mcp__mcp-agent-mail__set_contact_policy(
     project_key, agent_name=$HUMAN_NAME, policy="open",
     registration_token=$HUMAN_TOKEN
   )

   # Print the user's mail identity so they can receive directed messages.
   echo "Your mail identity for this run is '$HUMAN_NAME'. Replies addressed to that name will reach you."
   ```

   Save `COORDINATOR_TOKEN`, `HUMAN_NAME`, and `HUMAN_TOKEN` to `agent-tokens.json` (see step 7).

7. **State dir**:

   ```bash
   mkdir -p ".beads/orchestrator-runs/$EPIC_ID/"
   ```

   Files written here: `exec-plan.json` (Phase 2), `task-ids.json` (Phase 3), `final-report.json` (Phase 4–5), `agent-tokens.json` (Phase 1 step 6 + Phase 2 step 6).

   **`agent-tokens.json`** — persists `registration_token` for every registered agent (coordinator, human, and each worker). Required for `send_message(sender_token=...)`, `fetch_inbox`, and `set_contact_policy` calls on behalf of those agents. Format:
   ```jsonc
   {
     "<agent_name>": "<registration_token>",
     ...
   }
   ```
   NEVER commit this file. It contains session tokens. Add `.beads/orchestrator-runs/` to `.gitignore` or treat as ephemeral.

---

## Phase 2 — Decompose

1. Parse plan per `references/plan-input-contract.md`. Reject if malformed: no H1 title, no H2 tasks, duplicate H2 titles, or unmatched `Depends on:` references. Print the first error found to the user and ABORT.

2. For each H2 task in document order:

   ```bash
   BID=$(bd create "<H2 title>" -t task -p $PRIORITY --silent --actor "$COORDINATOR_NAME")
   bd update $BID --description "<body verbatim>" --actor "$COORDINATOR_NAME"
   # Link as child of epic (argument order: dependent first, target second — per OV3)
   bd dep add $BID $EPIC_ID -t parent-child --actor "$COORDINATOR_NAME"
   # For each "Depends on:" entry resolved to a previously-created BID:
   bd dep add $BID $DEP_BID -t blocks --actor "$COORDINATOR_NAME"
   ```

   Priority mapping:
   | Risk in plan | bd priority |
   |---|---|
   | HIGH | P1 |
   | MEDIUM | P2 |
   | LOW (default) | P3 |

   Sequential default: when `Depends on:` is absent, task N automatically depends on task N-1 in document order. Override with `Depends on: none` for parallel-ready.

3. HIGH-risk spike beads — **deferred to v2**. v1 behavior: log warning only and continue.

   ```bash
   >&2 echo "WARN: task <title> marked HIGH risk; spike bead deferred to v2 (see spec §15)."
   ```

4. Sync beads DB to JSONL:

   ```bash
   bd export -o .beads/issues.jsonl  # export DB → JSONL (git-tracked snapshot)
   ```

5. **Track planning** per `references/decomposition-rules.md`:

   ```bash
   bv --robot-plan 2>/dev/null > ".beads/orchestrator-runs/$EPIC_ID/exec-plan.json"
   ```

   **Filter tracks before dispatching**: `bv --robot-plan` includes epic/milestone beads as their own single-item tracks. Before any further processing, drop any track whose sole item has `type == "epic"` or `type == "milestone"` — these must NOT be dispatched to workers. Only task beads are dispatched. (Smoke test 2026-05-07: 2-task fixture produced 3 tracks; track-B was the epic itself.)

   For each `.plan.tracks[]` (after filtering), compute file-scope union across all member bead `file_scope` globs.

   Reconcile overlapping tracks: if two tracks have overlapping file-scope unions, the track with MORE beads absorbs the smaller (append smaller's `items[]` to larger; deduplicate combined glob set; remove absorbed track). If bead counts equal, absorb later track (higher index) into earlier.

   Enforce max-tracks: if track count > `--max-tracks`, merge the two smallest tracks (by bead count) into one, repeating until count ≤ max.

6. Assign agent names — random adjective+noun pairs per track: `BlueLake`, `RedFox`, `SilentMountain`, `GreenMist`, etc. One name per track.

   After naming, register each worker agent and capture its token:
   ```bash
   for each AGENT_NAME in track agent names:
     result = mcp__mcp-agent-mail__register_agent(
       project_key, name=$AGENT_NAME, program="claude-code",
       model=<model_id>, task_description="track of $EPIC_ID"
     )
     WORKER_TOKEN = result.registration_token
     mcp__mcp-agent-mail__set_contact_policy(
       project_key, agent_name=$AGENT_NAME, policy="open",
       registration_token=$WORKER_TOKEN
     )
     # Append to agent-tokens.json: { "$AGENT_NAME": "$WORKER_TOKEN" }
   ```

   Setting `policy="open"` waives the contact-approval handshake for the duration of the run, so coordinator and workers can mail each other freely without the `request_contact` / `respond_contact` round-trip. The user can revert to `contacts_only` after orchestration if desired.

7. Write enriched `exec-plan.json` to state dir:

   ```jsonc
   {
     "epic_id": "<bd-...>",
     "mode": "shared" | "worktree",
     "integration_branch": "<branch>",
     "coordinator_name": "<Conductor-...>",
     "tracks": [
       {
         "track_id": "<bv-track-id>",
         "agent_name": "<BlueLake>",
         "bead_ids": ["<bd-...>", ...],
         "file_scope": ["<glob>", ...],
         "file_scope_regex": "<combined regex>",
         ...
       }
     ]
   }
   ```

   `exec-plan.tracks` order is authoritative for Phase 6 merge (topologically sorted by `bv --robot-plan`).

---

## Phase 3 — Spawn

Iterate tracks **sequentially** (spawning is fast; parallelizing adds no benefit and makes state tracking harder):

1. If `mode=worktree`, create an isolated worktree per track:

   ```bash
   WT_PATH="/tmp/orchestrate/${EPIC_ID}-${AGENT_NAME}"
   # Flat sibling naming — avoids git ref hierarchy conflict where INTEGRATION_BRANCH is
   # already a leaf and git refuses to create a child ref under it.
   WT_BRANCH="orchestrate-wt/${EPIC_ID}-${AGENT_NAME}"
   git worktree add "$WT_PATH" -b "$WT_BRANCH" "$INTEGRATION_BRANCH"
   # The third argument bases the new branch off $INTEGRATION_BRANCH (created in Phase 1 step 5),
   # not wherever HEAD happens to be.
   ```

2. Build subagent prompt from `references/worker-prompt-template.md`. Inject all worker inputs:
   `epic_id`, `agent_name`, `coordinator_name`, `track_thread_id`, `bead_ids`, `bead_titles` (id→title map from `exec-plan.json`), `file_scope`, `file_scope_regex` (pre-computed from `exec-plan.tracks[].file_scope_regex`), `project_key`, `mode`, `integration_branch`, plus mode-specific extras (`worktree_path` + `worktree_branch` for worktree mode; `test_cmd_template` for shared mode).

   `track_thread_id` format: `track-<agent_name>-<epic_id>` (dashes — colons are rejected by the server; thread IDs must match `[A-Za-z0-9][A-Za-z0-9._-]{0,127}`).

3. Pick prompt path based on `dispatch_mode`:
   - `dispatch_mode="skill"` (Path A): prompt instructs `Skill(skill="bead-worker")`.
   - `dispatch_mode="inline"` (Path B): read `~/.claude/skills/bead-worker/SKILL.md`, strip YAML frontmatter (lines between first two `---` lines), paste verbatim body into the prompt block.

   Path B frontmatter strip (pseudocode):
   ```python
   raw = Path("~/.claude/skills/bead-worker/SKILL.md").read_text()
   body = re.sub(r'^---\n.*?\n---\n', '', raw, count=1, flags=re.DOTALL).strip()
   prompt = template_path_b.replace("{{BEAD_WORKER_SKILL_BODY}}", body)
   ```

4. Dispatch:

   ```
   task_id = Task(
     run_in_background=true,
     subagent_type="general-purpose",
     prompt=<rendered_prompt>
   )
   ```

   Save `task_id` keyed by `agent_name` to `.beads/orchestrator-runs/$EPIC_ID/task-ids.json`.

After all tracks spawned: do NOT poll Task status. The runtime delivers completion notifications automatically.

---

## Phase 4 — Live monitor

Until all tasks notified complete:

- **Mail forwarding** every ~60 s:

  ```
  inbox = mcp__mcp-agent-mail__fetch_inbox(
    project_key, agent_name=$COORDINATOR_NAME,
    registration_token=<load COORDINATOR_TOKEN from agent-tokens.json>,
    unread_only=true, include_bodies=true, limit=50
  )
  for msg in inbox:
    print to terminal
    mcp__mcp-agent-mail__mark_message_read(project_key, $COORDINATOR_NAME, msg.id)
    if msg.requires_action:
      mcp__mcp-agent-mail__acknowledge_message(project_key, $COORDINATOR_NAME, msg.id, ack_payload="<short reason>")
      ask user if human decision needed
  ```

- **bv alerts** every ~3 min:

  ```bash
  bv --robot-alerts 2>/dev/null \
    | jq '.alerts[] | select(.severity=="warning" or .severity=="critical")'
  ```

  Forward stale-claim, blocking-cascade, and priority warnings to terminal verbatim.

- **User passthrough**: if user types an instruction during the run, orchestrator forwards it as a high-priority mail to the target agent:

  ```
  mcp__mcp-agent-mail__send_message(
    sender_name=$HUMAN_NAME,
    sender_token=<load HUMAN_TOKEN from agent-tokens.json>,
    to=[$AGENT_NAME],
    thread_id=$EPIC_ID,
    importance="high",
    body_md=<user instruction>
  )
  ```

- **On Task completion notification**:

  1. Parse return JSON via `jq`.
  2. **Translate worker JSON to mail** (required when worker returned `mail_sent=false` or `mail_sent` field is absent — treat absence as false):

     ```python
     worker_token = load agent-tokens.json[$WORKER_NAME]

     # Per-bead messages
     for bead in worker_json["bead_outcomes"]:
       mcp__mcp-agent-mail__send_message(
         sender_name=$WORKER_NAME,
         sender_token=worker_token,
         to=[$COORDINATOR_NAME],
         thread_id=$EPIC_ID,
         subject="[" + bead["bead_id"] + "] " + bead["status"].upper(),
         body_md="commit: " + (bead["commit"] or "none") + "\nreason: " + bead["reason"],
         importance="normal"
       )

     # End-of-track message
     per_bead_table = "\n".join(
       f"| {b['bead_id']} | {b['status']} | {b['commit'] or 'none'} | {b['reason']} |"
       for b in worker_json["bead_outcomes"]
     )
     mcp__mcp-agent-mail__send_message(
       sender_name=$WORKER_NAME,
       sender_token=worker_token,
       to=[$COORDINATOR_NAME],
       thread_id=$EPIC_ID,
       subject="[Track " + $WORKER_NAME + "] " + worker_json["track_status"].upper(),
       body_md="| bead_id | status | commit | reason |\n|---|---|---|---|\n" + per_bead_table,
       importance="normal"
     )
     ```

     Workers that DO have MCP can send these themselves — orchestrator only translates for workers where `mail_sent` is false or absent.

  3. Append to `final-report.json`.

If a Task hits its default 30-min timeout without returning: mark track `track_status="failed"`, send urgent mail to `$HUMAN_NAME`, continue monitoring remaining tracks.

---

## Phase 5 — Recovery sweep

After all Tasks notified complete (or timed out):

1. **Release dangling file reservations** per agent:

   ```
   for agent_name in tracks:
     mcp__mcp-agent-mail__release_file_reservations(
       project_key, agent_name,
       registration_token=<load from agent-tokens.json[agent_name]>,
       paths=file_scope
     )
   ```

2. **Audit open/closed bead states**:

   ```bash
   # NOTE: bare `bd list --json` hides closed beads. Use --all to see all states.
   bd list --all --json 2>/dev/null | jq '.[] | {id, title, status}'
   ```

3. **Stale-claim sweep**:

   ```bash
   bv --robot-alerts 2>/dev/null \
     | jq -r '.alerts[] | select(.type=="stale_claim") | .issue_id'
   # For each stale issue:
   bd update $ISSUE_ID --status open --actor "$COORDINATOR_NAME"
   ```

4. **DB integrity check**:

   ```bash
   bd doctor --fix  # auto-fix detected inconsistencies (schema, dangling refs, blocked-cache)
   # Note: first run on a fresh workspace may self-heal stale blocked cache — this is benign.
   ```

5. **Aggregate outcomes** from `final-report.json`:

   ```
   complete_tracks = tracks where track_status == "complete"
   partial_tracks  = tracks where track_status == "partial"
   failed_tracks   = tracks where track_status == "failed"
   ```

---

## Phase 6 — Merge + close + handoff

Per `references/merge-strategy.md`:

1. **Merge** (`mode=worktree` only — skip entirely for `mode=shared`):

   Iterate `complete_tracks` in `exec-plan.tracks` order (already topologically sorted by `bv --robot-plan`).

   For each track:
   ```bash
   git merge "$WT_BRANCH" --no-ff -m "Merge track $AGENT_NAME ($BEAD_COUNT beads)"
   ```

   On conflict:
   ```bash
   git merge --abort
   ```
   Send ack-required high-importance mail to `$AGENT_NAME` and `$HUMAN_NAME`:
   ```
   mcp__mcp-agent-mail__send_message(
     sender_name=$COORDINATOR_NAME,
     sender_token=<load COORDINATOR_TOKEN from agent-tokens.json>,
     to=[$AGENT_NAME, $HUMAN_NAME],
     thread_id=$EPIC_ID,
     subject="[<agent_name>] Merge conflict",
     body_md="Conflicted files:\n<list>\n\nDiff summary:\n<excerpt>",
     importance="high",
     ack_required=true
   )
   ```
   Mark track `next_action="needs_human"`. KEEP worktree (do NOT remove — human needs it for resolution). Continue to next track.

   On success:
   ```bash
   git worktree remove "$WT_PATH"
   ```

2. **Close epic** (condition-dependent):

   If all tracks complete and no `needs_human`:
   ```bash
   bd close $EPIC_ID --reason "Orchestrate complete" --actor "$COORDINATOR_NAME"
   ```
   Summarize each track thread:
   ```
   for track in tracks:
     mcp__mcp-agent-mail__summarize_thread(project_key, thread_id=track.track_thread_id)
   ```

   If any partial / failed / needs_human tracks:
   ```bash
   bd update $EPIC_ID --status blocked \
     --description "Partial/failed tracks: <list>" \
     --actor "$COORDINATOR_NAME"
   ```

3. **Final summary mail** to all workers + `$HUMAN_NAME`:

   ```
   mcp__mcp-agent-mail__send_message(
     sender_name=$COORDINATOR_NAME,
     sender_token=<load COORDINATOR_TOKEN from agent-tokens.json>,
     to=[<all_agent_names>, $HUMAN_NAME],
     thread_id=$EPIC_ID,
     subject="Orchestrate complete — $EPIC_ID",
     body_md="## Track outcomes\n<per-track table>\n\n## Integration branch\n`$INTEGRATION_BRANCH`\n\nRun /ship when ready.",
     importance="normal"
   )
   ```

4. **Hand off** (do NOT auto-invoke `/ship`):

   Print to user:
   ```
   Integration branch: $INTEGRATION_BRANCH. Run /ship when ready.
   ```

5. **STATE.md (optional)**: if `.planning/STATE.md` exists, update `step: ship` and `last_updated: <now>`. If absent, no-op.

---

## Failure modes

| Phase | Symptom | Action |
|---|---|---|
| 1 | Tool/MCP missing | ABORT with install instructions. |
| 1 | Capability probe fails (no skill, no MCP) | Try inline+curl combination; ABORT only if neither path works. |
| 2 | Plan malformed / no H2 | ABORT, print first error, ask user to fix. |
| 2 | bv returns 0 tracks / dependency cycle | ABORT, ask user to replan. |
| 3 | Task() spawn fails | Retry once → ABORT that track only (continue others). |
| 4 | Subagent crash / no return within 30 min default timeout | Mark track failed; mail `$HUMAN_NAME`; continue. |
| 4 | User Ctrl-C during monitor | Save partial `final-report.json`; print "resumable from .beads/orchestrator-runs/<epic_id>/" hint. |
| 5 | bd doctor cannot fix | Log + continue (manual cleanup later). |
| 6 | Merge conflict | Abort that merge, mark needs_human, keep worktree, continue. |
| 6 | All workers failed | Skip merge phase, mark epic blocked, hand off as needs_human. |

---

## Output

**Terminal output during a run:**
- Phase headers as the orchestrator advances through each phase.
- Mail-forward lines printed verbatim from worker reports.
- bv alert lines printed when forwarded.
- Final summary table (per-track outcome) + integration branch + handoff message.

**Files on disk after completion:**

| File | Created in |
|---|---|
| `.beads/orchestrator-runs/$EPIC_ID/exec-plan.json` | Phase 2 |
| `.beads/orchestrator-runs/$EPIC_ID/task-ids.json` | Phase 3 |
| `.beads/orchestrator-runs/$EPIC_ID/final-report.json` | Phase 4–5 |

**Git state:**
- Integration branch with merged commits (`mode=worktree`) or accumulated commits (`mode=shared`).

**bd state:**
- Epic issue + all task issues created, claimed, closed/failed/skipped per outcome.

**mcp-agent-mail state:**
- One epic-level mail thread (`thread_id=$EPIC_ID`).
- Per-track threads (`track-<agent_name>-<epic_id>`) with full audit of bead progress.

---

## References

- `references/plan-input-contract.md` — required plan markdown shape (Phase 2 step 1).
- `references/decomposition-rules.md` — H2 → bd issue mapping, file-scope inference, track grouping (Phase 2).
- `references/merge-strategy.md` — Phase 6 merge order, conflict policy, after-merge actions.
- `references/return-schema.md` — worker return JSON contract (consumed Phase 4–5).
- `references/worker-prompt-template.md` — Path A / Path B prompt templates (Phase 3 step 2).
