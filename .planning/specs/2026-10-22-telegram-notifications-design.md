# Telegram notifications behind a config switch

Workflow: telegram-notifications
Status: draft for user review.

## Goal and scope

Telegram notifications exist today but almost never fire. The `telegram-notify`
skill and `scripts/telegram.sh` are opt-in through `TELEGRAM_BOT_TOKEN` and
`TELEGRAM_CHAT_ID` only, no lifecycle stage calls them, and the skill's `ask`
mode (approving a plan or a ship from Telegram) contradicts the stage contract
("Never: ... notification delivery" as evidence). gin-orchestrator's
`TelegramNotificationProvider` wraps the same script and nothing calls it.

The goal is one switch in the repository configuration and notifications for
exactly two situations: the agent needs the user's input, or a long unattended
run (or a worker on another harness) has finished.

In scope:

- `notifications.telegram` in `.agent-workflow/config.yaml`, default off.
- `workflow_core/notify.py` and `gin-workflow notify`: the single sender, Python
  stdlib only.
- The call sites: the shared stage contract (`needs_input`) and the `execute`
  skill (`run_finished`, `worker_finished`, `worker_failed`).
- gin-orchestrator sending through the same sender via `workflow_core.ext`.
- Removing `telegram.sh`, its install copies, and the `telegram-notify` skill.
- A `setup doctor` warning when the switch is on and credentials are missing.

Out of scope: two-way messages (replies, approvals over Telegram), other
channels (Slack, email), per-event toggles, and notifications for closing a
track or an epic, recording a gate, or shipping. Those happen with the user
present, so a message adds nothing.

## Requirements

1. **Switch.** `notifications: {telegram: <bool>}` is an optional key of the
   2.8 config schema; absent means off, so no migration is needed. It is set
   with `gin-workflow setup configure --set notifications.telegram=true
   --approve`. Credentials stay in `TELEGRAM_BOT_TOKEN` and `TELEGRAM_CHAT_ID`
   and are never written to the config.
2. **Sender.** `workflow_core.notify.notify(root, event, message) -> str | None`
   reads the effective config of `root`. Off: does nothing and returns `None`.
   On: posts `[<repository name>] <event>: <message>` to the Telegram Bot API
   `sendMessage` with `urllib.request`, timeout 10 seconds. It returns a warning
   string instead of raising on missing credentials, a network error, or a
   non-2xx reply. The token never appears in a warning or in output.
3. **Events.** `event` is one of `needs_input`, `run_finished`,
   `worker_finished`, `worker_failed`; anything else is a usage error.
4. **CLI.** `gin-workflow notify --event <event> [--repository <path>]
   "<message>"` calls `notify`, prints a returned warning to stderr, and exits
   0 except on a usage error (exit 2). A notification never fails the caller.
5. **needs_input.** `references/stage-contract.md` gains one rule for every
   stage: before stopping to wait for the user (a spec to confirm, a plan to
   approve, ship options, `human_decision_required`, a blocker or repeated
   failure in execute), run `gin-workflow notify --event needs_input "<what is
   needed>"`.
6. **run_finished.** The `execute` skill runs `gin-workflow notify --event
   run_finished "<epic>: all tracks closed"` when closing a track makes
   `implementation_complete` satisfied. "Long run" means this; elapsed time is
   not measured.
7. **worker events.** The `execute` skill runs `gin-workflow notify --event
   worker_finished|worker_failed "<track>: <provider>"` when a worker it
   dispatched to another provider's CLI returns.
8. **gin-orchestrator.** `TelegramNotificationProvider.notify` calls
   `workflow_core.ext.notify` instead of `telegram.sh`; its capabilities drop
   `notification.ask`, and the reply fields (`wait_for_reply`,
   `timeout_seconds`, `session_id` on the request, `reply` on the receipt)
   are removed. `worker_scheduler` sends `worker_finished` or `worker_failed`
   through the registry's notification provider after each dispatch it
   completes. `workflow_core.ext` exports `notify`.
9. **Removal.** Delete `plugins/gin-workflow/src/scripts/telegram.sh`, the
   `telegram.sh` entries in `install.sh` and `install.ps1`, and the
   `telegram-notify` skill. Docs (`docs/reference/config.md`, `cli.md`,
   `skills.md`, `troubleshooting.md`, `concepts/providers.md`, the
   gin-orchestrator README) describe the switch and the command instead.
10. **Doctor.** `gin-workflow setup doctor` reports a warning
    `telegram_credentials_missing` when the switch is on and either variable
    is unset; nothing when it is off.
11. **Versions.** gin-workflow 2.1.0 and gin-orchestrator 0.2.0, bumped once
    when every track is done.

## User Stories

### US-1: Know when the agent needs me
As a developer running a workflow, I want a Telegram message when the agent
stops to wait for me, so that I do not have to watch the terminal.

Acceptance criteria:
- With `notifications.telegram: true` and both variables set, `gin-workflow
  notify --event needs_input "plan ready"` delivers one message naming the
  repository and the event.
- The stage contract tells every stage to send `needs_input` before waiting
  for the user.

### US-2: Know when a long run is done
As a developer who started an unattended run (`/goal`, routed workers), I want
a message when it ends, so that I can come back to review or ship.

Acceptance criteria:
- `execute` sends `run_finished` when the last track of the epic closes.
- `execute` sends `worker_finished` or `worker_failed` when a worker on
  another provider returns; gin-orchestrator's scheduler sends the same events
  through `workflow_core.ext.notify`.

### US-3: Turn notifications on or off per repository
As a developer, I want one config key to enable or disable Telegram, so that
having the variables in my shell does not notify every repository.

Acceptance criteria:
- With the key absent or `false`, `gin-workflow notify` sends nothing and
  exits 0, even when both variables are set.
- `setup configure --set notifications.telegram=true --approve` turns it on.
- `setup doctor` warns `telegram_credentials_missing` when it is on and a
  variable is missing.

## Errors and compatibility

- Delivery failures never fail a command or a stage: `notify` returns a
  warning, the CLI exits 0, and gin-orchestrator's provider returns an
  `unavailable` result as it does today.
- Repositories that set only the environment variables stop receiving the
  (rare) messages until they turn the switch on. The 2.1 upgrade notes say so.
- Existing configs stay valid: the key is optional in schema 2.8.
- Removing `notification.ask` and the reply fields changes gin-orchestrator's
  internal provider contract, not the CLI contract (still 2).

## Testing

- `notify`: off (no request), on without credentials (warning), on with a fake
  HTTP opener (one request with the expected URL and text), a non-2xx reply and
  a network error (warnings without the token).
- CLI: unknown event exits 2; a delivery failure exits 0 with the warning on
  stderr.
- Schema: `notifications.telegram` accepted as a boolean, rejected otherwise.
- Doctor: warning only when on and a variable is missing.
- gin-orchestrator: the provider calls `workflow_core.ext.notify`; the
  scheduler sends one worker event per completed dispatch.
- Docs coverage: no page, skill or install script mentions `telegram.sh` or
  `telegram-notify`.
