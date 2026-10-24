# Upgrading to gin-workflow 2.1 and gin-orchestrator 0.2

gin-workflow 2.1 and gin-orchestrator 0.2 change how Telegram notifications and `/goal` work. The configuration schema stays at 2.8, so `gin-workflow setup update` has nothing to migrate.

## Telegram is off by default

Telegram notifications are now off unless you turn them on:

```bash
gin-workflow setup configure --set notifications.telegram=true --approve
```

Set `TELEGRAM_BOT_TOKEN` and `TELEGRAM_CHAT_ID` in the environment. `gin-workflow setup doctor` warns when the flag is on and either credential is missing.

The old Telegram skill and its helper script are gone. Agents send messages with `gin-workflow notify --event <event> "<message>"` (see [CLI](cli.md#gin-workflow-notify)). Messages are one-way: a notification is never an approval, so the agent still waits for the user's reply.

## Print a goal for an epic

`gin-workflow goal --workflow-id <id>` prints the `/goal` that `/orchestrate` suggests. It covers only the tracks the agent can finish unattended:

- A plan track with a `Human gate:` line is labelled `human-gate`. That track and every track that depends on it are left out.
- Each track gets 6 turns, up to 30 turns in total.

If no track is left for the agent, the command prints a `No goal:` line naming the human-gate tracks. See [CLI](cli.md#gin-workflow-goal).

## 2.1.1

The printed goal now says a track run on a fallback from its route counts as run on its routed provider. Before, the goal named only the routed provider, so a track that ran on a fallback from its route could be judged as not meeting it. Nothing to migrate.
