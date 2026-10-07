# Review tier routing

Bead: `gin-workflow-hv9`. Status: draft for user review.

## Goal and scope

Size the reviewer to the change. Today the `review` skill names no reasoning tier, so every review runs on a high-tier model, and `independence: provider` applies to every review: a docs-only track is blocked when the only independent provider is out of quota (teamwork-hardening Track 4).

This change adds one read-only command that tells the reviewer dispatch which tier and which ordered reviewer routes to use. The command is agent-facing: the `review` skill calls it, and users keep invoking `/gin-workflow:review` as before. It does not dispatch reviewers, change implementer routing, or touch ledgers.

## Requirements

### 1. `gin-workflow reviewer`

```
gin-workflow reviewer --bead ID --base SHA [--workflow-id ID] [--format text|json]
```

- **Base tier.** The `requested.reasoning` of the bead's entry in `.agent-workflow/runtime/assignments/<workflow-id>.yaml` (main checkout), and the implementer provider from its `resolved.provider`. Without a manifest or entry, the base tier is `medium`, the implementer provider is the main harness, and the reasons include `no assignment manifest`.
- **Raise rule.** Changed files come from `git diff --name-only <base>..HEAD`. When the base tier is `low` and any changed file is not documentation, the tier becomes `medium` with reason `low track changes non-docs files: <first few paths>`. A documentation file ends in `.md` or lies under `docs/`, unless a path segment is `skills` (skill files define workflow behavior). The tier is never lowered and no other rule raises it.
- **Routes.** `resolve_assignment` with role `review` and the resolved tier gives the ordered candidates (provider, model, effort) from `routing.roles.review` and `providers.local.yaml`.
- **Independence.** At tier `low` the implementer provider stays in the list (a fresh session with a different actor id is independent enough for a low-tier review). At `medium` and `high` the implementer provider is removed, as today. `routing.review.require_independent: false` keeps every candidate; `allow_self_review_fallback` keeps its meaning.
- **Output.** `tier`, `base_tier`, `reasons`, `implementer`, `independence` (`session` or `provider`), and `routes` in order. Text format prints one route per line. Nothing is written.

### 2. `review` skill

The dispatch step runs `gin-workflow reviewer --bead <id> --base <ledger base>` and dispatches the first available route with its model; on an infrastructure failure (quota, rate limit, timeout) it tries the next route. The actor id is `reviewer:<provider>`, or `reviewer:<provider>:session-<id>` when the provider equals the implementer's. When the list is empty or every route fails, return `human_decision_required` as today.

## Errors and compatibility

- Exit 0: routes printed. Exit 2: bead not found, `--base` not a commit, `git diff` failed, no candidate resolves for the tier (the `resolve_assignment` diagnostics), or an empty list after the independence filter.
- Existing ledgers, approvals, and in-progress reviews are unaffected; the command only informs the next dispatch.
- No new configuration keys.

## Testing

- Raise rule (pure function): `low` + only `.md`/`docs/` files → `low`; `low` + a `.py` file → `medium`; `low` + `plugins/x/skills/y/SKILL.md` → `medium`; `medium` and `high` are never changed; an empty diff keeps the base tier.
- CLI in a temporary git repository with a manifest and a `providers.local.yaml`: tier and models follow the manifest tier; at `low` the implementer provider is listed; at `medium` it is not; without a manifest the tier is `medium` with reason `no assignment manifest`; a bad `--base` exits 2; `require_independent: false` keeps the implementer at `medium`.
- Docs: `docs/concepts/providers.md` (Independent review), `docs/reference/cli.md` (new `reviewer` command, marked as called by the `review` skill rather than run by hand); the `review` skill stays within its instruction budget and the packaging and docs checks pass.

## Out of scope

Raising the tier when a diff leaves the track's declared `Files:` (the reviewer's scope rule already flags it; revisit if a medium-tier review misses scope drift), diff-size heuristics, a configuration switch for low-tier independence, runtime events for routing decisions, and automatic reviewer dispatch.
