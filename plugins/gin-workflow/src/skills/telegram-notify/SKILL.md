---
name: telegram-notify
description: Defines when and how agents send Telegram notifications during gin-workflow lifecycle events. Opt-in via TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID environment variables.
---

# Telegram Notify Skill

This skill defines the notification contract for gin-workflow lifecycle events.
Agents reference this skill to know **when** to notify, **what** to say, and **how** to handle replies.

## Opt-In Behavior

Telegram notifications are enabled only when both environment variables are set:

- `TELEGRAM_BOT_TOKEN` — Bot API token from @BotFather
- `TELEGRAM_CHAT_ID` — Numeric chat ID for the private conversation

If either is unset, the `telegram.sh` script exits silently (code 0). Skills should invoke the script unconditionally — the script handles the opt-in guard internally.

## Script Location

The notification script is at `${PLUGIN_ROOT}/scripts/telegram.sh`.

## Notification Events

### 1. Plan Ready for Approval (two-way)

**Trigger:** After the `plan` skill writes the implementation plan, before asking for user approval in the terminal.

**Mode:** `ask` — send message and wait for reply.

**Template:**
```
📋 Plan ready for approval

{plan title}
Tracks: {N tracks}
Files: {N files changed}

Reply "approve" to proceed, or "reject: <reason>" to revise.
```

**Agent behavior:**
- Run: `telegram.sh ask "{message}" --timeout 600 --session-id {SESSION_ID}`
- If reply is `approve` (case-insensitive): continue to orchestrate.
- If reply starts with `reject`: treat the remainder as feedback and revise the plan.
- If exit code 124 (timeout): save state and exit gracefully. The Telegram message persists with the session ID for later resume.

---

### 2. Task Completed (one-way)

**Trigger:** After a `bead-worker` finishes execution and passes its verification step (step 4 in bead-worker skill).

**Mode:** `send` — fire-and-forget.

**Template:**
```
✅ Task completed

{bead title}
Track: {track id}
Status: Verified and ready for integration

Session: {SESSION_ID}
```

**Agent behavior:**
- Run: `telegram.sh send "{message}"`
- Continue with normal close-out workflow.

---

### 3. Work Blocked (one-way)

**Trigger:** When a `bead-worker` encounters out-of-scope changes, or when `execute` returns to `discuss` due to ambiguity or missing requirements.

**Mode:** `send` — fire-and-forget.

**Template:**
```
🚫 Work blocked

{bead title or task context}
Reason: {blocker description}
Action needed: {what the user should do}

Session: {SESSION_ID}
```

**Agent behavior:**
- Run: `telegram.sh send "{message}"`
- Record the blocker in Beads as normal.
- Save state and exit gracefully if the blocker requires user input.

---

### 4. Verification Result (one-way)

**Trigger:** After the `verify` skill finishes running quality gates.

**Mode:** `send` — fire-and-forget.

**Template (pass):**
```
✅ Verification passed

{plan or task title}
Tests: {N passed}
Checks: {summary of what was run}

Ready to ship. Session: {SESSION_ID}
```

**Template (fail):**
```
❌ Verification failed

{plan or task title}
Failures: {summary of what failed}
Action needed: Review failures and decide next steps.

Session: {SESSION_ID}
```

**Agent behavior:**
- Run: `telegram.sh send "{message}"`
- Continue with normal verify workflow (transition to ship on pass, or fix on fail).

---

### 5. Ship Ready (two-way)

**Trigger:** After the `ship` skill completes verification-and-handoff checks, before final delivery.

**Mode:** `ask` — send message and wait for reply.

**Template:**
```
🚀 Ready to ship

{plan title}
Changed files: {N files}
Validation: {summary}

Reply "ship" to deliver, or "hold: <reason>" to pause.
```

**Agent behavior:**
- Run: `telegram.sh ask "{message}" --timeout 600 --session-id {SESSION_ID}`
- If reply is `ship` (case-insensitive): proceed with delivery.
- If reply starts with `hold`: pause and record the reason.
- If exit code 124 (timeout): save state and exit. User resumes later.

---

### 6. All Work Complete (one-way)

**Trigger:** After the `bead-orchestrator` confirms all beads are closed.

**Mode:** `send` — fire-and-forget.

**Template:**
```
🎉 All work complete

{plan title}
Tracks completed: {N}/{N}
Duration: {elapsed time if available}

Session: {SESSION_ID}
```

**Agent behavior:**
- Run: `telegram.sh send "{message}"`
- Continue with normal close-out.

## Session ID Retrieval

The session/conversation ID is platform-specific. Agents should obtain it as follows:

| Platform | How to obtain |
|---|---|
| **Antigravity CLI** | Available in the system metadata as `Conversation ID`. Use the value directly. |
| **Claude Code** | Use the current session ID visible via `claude --resume`. |
| **Codex CLI** | Use the session identifier from the active Codex session context. |

If the session ID cannot be determined, omit the `--session-id` flag. The notification still works — the user just won't have the resume shortcut.

## Timeout and Resume Flow

When `ask` mode times out (exit code 124):

1. The agent should **not** treat this as an error.
2. The agent should save any in-progress state to Beads (notes, current status).
3. The agent should exit gracefully.
4. The Telegram message remains in the user's chat with the session ID.
5. The user can later resume using their platform's resume mechanism:
   - `agy resume {session-id}`
   - `claude --resume {session-id}`
   - `codex resume {session-id}`

## Implementation Notes

- All notifications are best-effort. A network failure sending a Telegram message should not block or fail the workflow.
- Wrap `telegram.sh` calls in a subshell or use `|| true` to prevent notification failures from aborting the agent's work.
- The script path is relative to the plugin root: `${PLUGIN_ROOT}/scripts/telegram.sh`.
