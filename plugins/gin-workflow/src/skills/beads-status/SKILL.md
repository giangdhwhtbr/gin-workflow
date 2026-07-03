---
name: beads-status
description: |
  Read-only snapshot of the beads backlog (ready, blocked, alerts) plus
  the HumanOverseer inbox. Run any time during or after orchestration
  to check progress without mutating state.
argument-hint: "[--tui]"
---

# Beads Status (read-only)

Snapshot of beads backlog and HumanOverseer mail. No mutations.

## Steps

1. **Export beads to JSONL**:
   ```bash
   bd export -o .beads/issues.jsonl
   ```
   (Required before bv reads — exports DB → JSONL.)

2. **Backlog summary**:
   ```bash
   bv --robot-triage 2>/dev/null
   ```
   Pretty-print key sections from the resulting JSON: `quick_ref`, `recommendations`, top-priority items.

3. **Alerts**:
   ```bash
   bv --robot-alerts 2>/dev/null
   ```
   Forward critical/warning entries from `.alerts[]` to the user.

4. **HumanOverseer inbox**:
   ```
   mcp__mcp-agent-mail__fetch_inbox(
     project_key,
     agent_name="HumanOverseer",
     unread_only=true,
     include_bodies=true,
     limit=20
   )
   ```
   Print recent messages. `project_key = git rev-parse --show-toplevel` from current repo root.

5. **Optional TUI**: if user passed `--tui` in `$ARGUMENTS`, run `exec bv` (foreground TUI). Otherwise return.

## Output format

Concatenate the four JSON sections under headers:

- `## Backlog`
- `## Alerts`
- `## Inbox`
- `## TUI` (only if `--tui` was passed)

Mark stale items in red if terminal supports color (`tput setaf 1`).

## Notes

- This skill is read-only; never calls `bd update`, `bd close`, or `send_message`.
- If `mcp__mcp-agent-mail__*` tools are not available in this session, skip step 4 with a one-line warning ("MCP unavailable; skipping inbox").
