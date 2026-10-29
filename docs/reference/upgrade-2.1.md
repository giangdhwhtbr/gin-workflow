# Upgrading to gin-workflow 2.1 and gin-orchestrator 0.2

gin-workflow 2.1 and gin-orchestrator 0.2 change how Telegram notifications and `/goal` work. The configuration schema stays at 2.8, so `gin-workflow setup update` has nothing to migrate.

## What changed

| Before (2.0) | After (2.1) |
|---|---|
| Telegram notifications on whenever `TELEGRAM_BOT_TOKEN` and `TELEGRAM_CHAT_ID` are set | On only with `notifications.telegram: true` and both variables set |
| The Telegram skill and its helper script send a message, or ask and wait for a reply | `gin-workflow notify --event <event> "<message>"` sends a one-way message |
| gin-orchestrator 0.1 notifies through that helper script | gin-orchestrator 0.2 sends `worker_finished` and `worker_failed` through `gin-workflow notify`'s sender |
| No `gin-workflow goal` | `gin-workflow goal --workflow-id <id>` prints the `/goal` that `/orchestrate` suggests |

## Telegram is off by default

Telegram notifications are now off unless you turn them on:

```bash
gin-workflow setup configure --set notifications.telegram=true --approve
```

Set `TELEGRAM_BOT_TOKEN` and `TELEGRAM_CHAT_ID` in the environment. `gin-workflow setup doctor` warns when the flag is on and either credential is missing ([`notifications`](config.md#notifications)).

The old Telegram skill and its helper script are gone. Agents send messages with `gin-workflow notify` ([CLI](cli.md#gin-workflow-notify)). Messages are one-way: a notification is never an approval, so the agent still waits for the user's reply.

## Print a goal for an epic

`gin-workflow goal --workflow-id <id>` prints the `/goal` that `/orchestrate` suggests, over only the tracks the agent can finish unattended. `/orchestrate` labels a track `human-gate` when its plan entry has a `Human gate:` line; the goal leaves out that track and every track that depends on it. The turn limit and the `No goal:` output are in the [CLI reference](cli.md#gin-workflow-goal).

## Rollback

The schema stays at 2.8, so going back to 2.0 needs no configuration change: reinstall the earlier release from your gin-workflow checkout.

1. Check out the release tag:

   ```bash
   git checkout v2.0.0
   ```

2. Reinstall it on every platform; add `--plugin all` to reinstall gin-orchestrator 0.1 and gin-qa as well:

   ```bash
   ./install.sh --platform all
   ```

## Changes in 2.1.1

The printed goal now says a track run on a fallback from its route counts as run on its routed provider. Before, the goal named only the routed provider, so a track that ran on a fallback from its route could be judged as not meeting it. Nothing to migrate.
