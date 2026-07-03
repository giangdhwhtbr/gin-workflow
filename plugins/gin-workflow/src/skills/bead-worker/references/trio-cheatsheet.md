# Trio Cheatsheet — bd / bv / agent-mail CLI & MCP Signatures

Quick reference for the bead-worker. Read on demand — not memorized.

---

## bd

Beads CLI (`bd` v1.0.3+, Homebrew Go build). Backed by Dolt — `bd init` creates `.beads/beads.db` (or Dolt-equivalent files) inside the repo.

### Core commands

```bash
# Create
bd create "<title>" -t task|epic|bug|feature -p <priority> --silent
#   --silent          outputs only the ID (preferred for shell capture)
#   --json            outputs full JSON
#   -d / --description (alias --body)
#   --actor <name>    audit-trail field. Orchestrator: $COORDINATOR_NAME; workers: $AGENT_NAME.
#                     All bd commands accept this as a global flag.

# Show
bd show <id>  |  bd show <id> --json

# Update
bd update <id> --status <S>     # -s / --status (open|in_progress|closed|failed|blocked)
bd update <id> --claim          # atomic: assignee=actor + status=in_progress (idempotent)
bd update <id> --description "<body>"
bd update <id> -p <priority>  |  bd update <id> --actor <name>

# Close
bd close <id> --reason "<reason>"            # -r / --reason
bd close <id> --reason "<r>" --suggest-next  # returns newly-unblocked IDs
bd close <id> --actor <name>                 # audit-trail
bd close <id1> <id2> ...                     # batch close

# List
bd list -s open|in_progress|closed|failed|blocked
bd list -t task|epic -p P1 --json
bd list --all                                # include closed (default hides them)

# Ready (truly claimable — blocker-aware, not just status=open)
bd ready  |  bd ready --json

# Dependencies  (dependent first, target second — easy to invert!)
bd dep add <issue_id> <depends_on_id> -t blocks|parent-child|related

# Export / Import (no `bd sync` — bd uses explicit export/import instead)
bd export -o .beads/issues.jsonl    # export DB → JSONL (git-tracked snapshot)
bd import .beads/issues.jsonl       # import JSONL → DB (upsert semantics)

# Doctor
bd doctor  |  bd doctor --fix
```

### Enums

**Status** (verified `bd 1.0.3`): `open` | `in_progress` | `closed` | `failed` | `skipped` | `blocked`
- Workers use `failed` (test fail × 3) or `skipped` (file-reservation conflict). Spec §5 step 3 references `bd update --status failed` for fail-path.

**Priority**: `0`/`P0` (critical) → `1`/`P1` → `2`/`P2` → `3`/`P3` (default) → `4`/`P4` (low)

### Key patterns

```bash
bid=$(bd create "Do X" -t task -p P2 --silent)
bd update "$bid" --claim --actor "$AGENT_NAME"
bd close "$bid" --reason "Implemented and tested" --actor "$AGENT_NAME"
bd dep add "$bid" "$epic_id" -t parent-child
bd dep add "$bid" "$dep_bid" -t blocks
```

---

## bv (beads_viewer)

Workers do not run `bv`. See `bead-orchestrator/references/decomposition-rules.md` for orchestrator-side bv usage (`--robot-plan`, `--robot-alerts`, `--robot-next`).

---

## agent-mail (MCP)

> **Per OV2 (spec §17), workers cannot call `mcp__mcp-agent-mail__*` directly —
> orchestrator owns these calls. Worker fallback: curl shell-out (see below).**

> **CRITICAL — OV2 deviation:** MCP tools are NOT propagated into Task() subagent
> contexts. Workers must NOT assume they are callable. Worker fallback for mid-task
> mail:
>
> ```bash
> curl -s -X POST http://127.0.0.1:8765/api/ \
>   -H "Authorization: Bearer $MCP_AGENT_MAIL_TOKEN" \
>   -H "Content-Type: application/json" \
>   -d '{"jsonrpc":"2.0","method":"tools/call","params":{"name":"send_message","arguments":{...}},"id":1}'
> ```
>
> Otherwise workers report status via the return JSON (§8) — orchestrator translates to mail.

**project_key invariant:** every call MUST pass `project_key = absolute path of original repo root`.
Obtain once via `git rev-parse --show-toplevel` (from OUTSIDE any worktree). Never recompute from `pwd`.

### Signatures (orchestrator-side)

> **Token note (D5):** `register_agent` returns a `registration_token` per agent. The orchestrator
> MUST persist tokens to `.beads/orchestrator-runs/<epic_id>/agent-tokens.json` and supply
> `sender_token`, `registration_token` (for `fetch_inbox` / `set_contact_policy`), etc. in every
> subsequent call that sends or reads on behalf of a named agent.

> **$HUMAN_NAME (D3):** The user is registered at orchestration start via `register_agent(program="human", model="human")` with NO `name` argument — server auto-generates an adjective+noun identity (e.g. "BrightCat"). The orchestrator prints it and stores it as `$HUMAN_NAME`. All conflict/failure mails go to `$HUMAN_NAME`. Do not hardcode a descriptive role name — the server will reject it.

```python
mcp__mcp-agent-mail__macro_start_session(name="Conductor-<epic_suffix>")
# epic_suffix = ${EPIC_ID##*-}  (suffix after last '-', not first 8 chars)

mcp__mcp-agent-mail__register_agent(
    project_key="<root>", name="<agent_name>", program="claude-code",
    model="<model_id>", task_description="track of <epic_id>")
# Returns: { name, registration_token, ... }
# Capture registration_token for later send_message / fetch_inbox / set_contact_policy calls.

# Set contact policy to 'open' after each register_agent so agents can mail freely
# without the request_contact / respond_contact round-trip.
mcp__mcp-agent-mail__set_contact_policy(
    project_key="<root>", agent_name="<name>", policy="open",
    registration_token="<that agent's registration_token>")

mcp__mcp-agent-mail__summarize_thread(project_key="<root>",
    thread_id="track-<AgentName>-<epic_id>")
# IMPORTANT: thread IDs use dashes, NOT colons. Format: track-<AgentName>-<epic_id>

# File reservations (orchestrator or worker-via-curl)
mcp__mcp-agent-mail__file_reservation_paths(
    project_key="<root>", agent_name="<name>",
    registration_token="<that agent's token>",
    paths=["<glob>"], ttl_seconds=1800, exclusive=True, reason="<bead_id>")
mcp__mcp-agent-mail__release_file_reservations(
    project_key="<root>", agent_name="<name>",
    registration_token="<that agent's token>",
    paths=["<glob>"])

# sender_token is required to send as a named agent when the MCP session is
# authenticated as a different agent (e.g. coordinator sending as a worker).
mcp__mcp-agent-mail__send_message(
    sender_name="<sender>",
    sender_token="<sender's registration_token>",
    to=["<name>"], thread_id="<epic_id>", subject="[<bead_id>] COMPLETE",
    body_md="commit: <sha>\nsummary: ...", ack_required=False, importance="normal")

mcp__mcp-agent-mail__fetch_inbox(
    agent_name="<coordinator>",
    registration_token="<coordinator's token>",
    unread_only=True, urgent_only=False, include_bodies=True, limit=50)

# Server liveness probe — use at orchestrator pre-flight
mcp__mcp-agent-mail__health_check(project_key=None)
# Returns {ok: bool, ...}

# Register/upsert a project entry — call once per epic from orchestrator
mcp__mcp-agent-mail__ensure_project(project_key, name=None)

# Mark a message as acknowledged when sender set ack_required=true
mcp__mcp-agent-mail__acknowledge_message(project_key, agent_name, message_id, ack_payload=None)

# Mark inbox item as read after forwarding/processing
mcp__mcp-agent-mail__mark_message_read(project_key, agent_name, message_id)
```
