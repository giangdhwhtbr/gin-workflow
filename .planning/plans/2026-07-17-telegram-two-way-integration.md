# Plan: Telegram Two-Way Communication Integration

## Objective
Agents running gin-workflow can send notifications to a private Telegram bot and receive replies (approve/reject/input) within a 10-minute polling window. If the user doesn't reply in time, the message includes the session ID so the user can resume later via `codex|agy|claude resume {conversationId}`.

## Model Guidance
- `default_model_class`: `standard_impl`
- `phase_guidance`:
  - `brainstorm`: `high_reasoning`
  - `design`: `high_reasoning`
  - `plan`: `standard_impl`
  - `implement`: `standard_impl`
  - `verify`: `standard_impl`
  - `review`: `high_reasoning`
  - `docs`: `cheap_simple`
- `override_rule`: Use `high_reasoning` for planning only when execution boundaries, dependency sequencing, or major tradeoffs are still unresolved.

## Requirement Analysis
- Problem statement: gin-workflow agents currently have no way to notify the user when they complete a task, need approval, or encounter a blocker. The user must actively watch the terminal. This is especially painful during autonomous `/goal` runs or long-running background tasks.
- Success criteria:
  - A `telegram.sh` script exists that can send messages and poll for replies via Telegram Bot API.
  - A `telegram-notify` skill defines when and how agents should use the script.
  - The six lifecycle skills (`plan`, `bead-worker`, `bead-orchestrator`, `verify`, `ship`, `execute`) reference the notification skill at the correct trigger points.
  - Messages include conversation/session ID for resume.
  - Polling times out after 10 minutes and the agent parks gracefully.
  - Configuration is via environment variables (`TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`).
  - Notification is opt-in: if env vars are unset, skills behave exactly as before.
- Constraints:
  - No external daemon or long-running service — everything runs within the agent's session.
  - Uses only `curl` and standard shell tools (no Python/Node dependencies).
  - Must work across all three host platforms (Claude Code, Antigravity, Codex).
  - Telegram Bot API only (no Telegram client libraries).
  - Does not change the core lifecycle or Beads ownership model.
- Non-goals:
  - Multi-user/team channel support.
  - Rich interactive UI (inline keyboards, etc.) — plain text replies only.
  - Persistent bot service or webhook server.
  - Modifying the `bd` CLI itself.

## Approach Options
### Option 1: Shell script with send/ask modes (Selected)
- Summary: A single `telegram.sh` script with two modes: `send` (fire-and-forget notification) and `ask` (send message + poll `getUpdates` for a reply with 10-minute timeout). A companion `telegram-notify` skill defines the trigger points and message templates. Existing skills get a single-line addition referencing the notification skill.
- Pros: No new dependencies. Self-contained. Works within agent session. Easy to test. Opt-in via env vars.
- Cons: Blocking poll during `ask` mode ties up the agent session (but this mirrors current terminal-wait behavior).

### Option 2: Beads hook-based notifications
- Summary: Use Beads' hook system to fire Telegram notifications on status transitions (e.g., `bd close` triggers a post-hook).
- Pros: Automatic, no skill modifications needed.
- Cons: Beads hooks are git-lifecycle hooks, not status-transition hooks. Would require `bd` CLI changes (out of scope). Can't do two-way communication through hooks. Doesn't cover all trigger events (plan approval isn't a Beads event).

### Recommended Approach
- Selected option: Option 1 — Shell script with send/ask modes
- Reasoning: It requires no changes to `bd` or Beads internals, works across all platforms, is fully opt-in, and handles both one-way notifications and two-way approval flows within the agent's existing session model.

## Scope
- In scope:
  - New script: `plugins/gin-workflow/src/scripts/telegram.sh`
  - New skill: `plugins/gin-workflow/src/skills/telegram-notify/SKILL.md`
  - Modifications to 6 existing skills to add notification trigger references
  - Documentation updates to `README.md`
- Out of scope:
  - Changes to `bd` CLI or Beads internals
  - Changes to `install.sh` build pipeline (script is just a shell file, no compilation needed)
  - Superpowers base skills
  - Inline keyboards or rich Telegram formatting
  - Webhook/server-based bot architecture

## Tasks

### Track 1: Create telegram.sh script
- **Dependencies**: none
- **Files**:
  - [NEW] `plugins/gin-workflow/src/scripts/telegram.sh`
- **Model class**: `standard_impl`
- **Acceptance criteria**:
  - Script supports two subcommands: `send` and `ask`
  - `send` posts a message via `POST /sendMessage` and exits
  - `ask` posts a message, then polls `GET /getUpdates` every 5 seconds for up to 600 seconds (10 min)
  - `ask` uses `update_id` offset to only capture replies after the question was sent
  - `ask` exits with the reply text on stdout, or exits with code 124 (timeout convention) if no reply
  - Both modes read `TELEGRAM_BOT_TOKEN` and `TELEGRAM_CHAT_ID` from environment
  - If either env var is unset, the script exits silently with code 0 (opt-in behavior)
  - Script is POSIX-compatible and uses only `curl`, `jq` (or grep/sed fallback), and standard shell
  - Messages support multi-line content and emoji
- **Estimated complexity**: medium

### Track 2: Create telegram-notify skill
- **Dependencies**: Track 1
- **Files**:
  - [NEW] `plugins/gin-workflow/src/skills/telegram-notify/SKILL.md`
- **Model class**: `standard_impl`
- **Acceptance criteria**:
  - Defines the six notification trigger events with message templates:
    1. `plan_ready` — two-way (ask for approval)
    2. `task_completed` — one-way (inform)
    3. `work_blocked` — one-way (inform with details)
    4. `verification_result` — one-way (pass/fail with summary)
    5. `ship_ready` — two-way (ask for final approval)
    6. `all_work_complete` — one-way (inform)
  - Each template includes: event emoji, event title, context summary, conversation/session ID, and reply instructions (for two-way events)
  - Documents opt-in behavior: if `TELEGRAM_BOT_TOKEN` or `TELEGRAM_CHAT_ID` are unset, skip notification silently
  - Documents timeout behavior: on timeout (exit 124), agent should save state and exit gracefully, leaving the Telegram message as a persistent notification with the session ID
  - Documents how to obtain conversation/session ID across platforms
- **Estimated complexity**: medium

### Track 3: Integrate notifications into lifecycle skills
- **Dependencies**: Track 2
- **Files**:
  - [MODIFY] `plugins/gin-workflow/src/skills/plan/SKILL.md`
  - [MODIFY] `plugins/gin-workflow/src/skills/bead-worker/SKILL.md`
  - [MODIFY] `plugins/gin-workflow/src/skills/bead-orchestrator/SKILL.md`
  - [MODIFY] `plugins/gin-workflow/src/skills/verify/SKILL.md`
  - [MODIFY] `plugins/gin-workflow/src/skills/ship/SKILL.md`
  - [MODIFY] `plugins/gin-workflow/src/skills/execute/SKILL.md`
- **Model class**: `standard_impl`
- **Acceptance criteria**:
  - `plan` skill: after writing the plan and before asking for user approval, send `plan_ready` notification via telegram-notify. If Telegram reply is "approve", continue. If "reject: reason", incorporate feedback.
  - `bead-worker` skill: after completion (step 4), send `task_completed` notification.
  - `bead-worker` skill: when stopping due to out-of-scope changes needed, send `work_blocked` notification.
  - `bead-orchestrator` skill: after all beads are closed, send `all_work_complete` notification.
  - `verify` skill: after running quality gates, send `verification_result` notification with pass/fail summary.
  - `ship` skill: before final delivery, send `ship_ready` notification (two-way, ask for go/no-go).
  - `execute` skill: when returning to `discuss` due to ambiguity, send `work_blocked` notification.
  - Each integration is a small addition (1-3 lines of instruction), not a rewrite of the skill.
  - All notifications are conditional on telegram-notify opt-in check.
- **Estimated complexity**: low

### Track 4: Update documentation
- **Dependencies**: Track 1, Track 2, Track 3
- **Files**:
  - [MODIFY] `README.md`
- **Model class**: `cheap_simple`
- **Acceptance criteria**:
  - README documents the Telegram integration feature
  - README includes setup instructions (BotFather, env vars)
  - README documents the six trigger events
  - README documents the timeout/resume flow
- **Estimated complexity**: low

## Integration
- **Branch**: master
- **Merge strategy**: sequential

## Validation
- [ ] `telegram.sh send` successfully delivers a test message to the configured bot
- [ ] `telegram.sh ask` successfully polls and captures a reply
- [ ] `telegram.sh ask` correctly times out after the configured duration and exits 124
- [ ] Both commands exit silently when env vars are unset
- [ ] All modified skill files parse correctly (no broken markdown)
- [ ] `install.sh --platform antigravity` runs successfully with the new files
- [ ] Manual end-to-end test: run a workflow, receive Telegram notification, reply, agent continues

## Notes
- `jq` is strongly preferred for JSON parsing but the script should degrade gracefully if unavailable (grep/sed fallback).
- The conversation/session ID is platform-specific: Antigravity uses `Conversation ID` from metadata, Claude Code uses `--resume` session IDs, Codex has its own session model. The skill should document how to obtain it on each platform but the script itself just takes a string parameter.
- Model guidance is planning metadata, not Beads state.
- If omitted, agents should assume `standard_impl`.
- Use provider-neutral model classes only; do not name vendor-specific models in the plan schema.
