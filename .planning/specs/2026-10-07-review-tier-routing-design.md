# Review tier routing

Bead: `gin-workflow-hv9`. Status: draft for user review.

## Goal and scope

Size the reviewer to the change. Today the `review` skill names no reasoning tier, so every review runs on a high-tier model, and `independence: provider` applies to every review: a docs-only track is blocked when the only independent provider is out of quota (teamwork-hardening Track 4).

This change adds one read-only command that tells the reviewer dispatch which tier and which ordered reviewer routes to use. The command is agent-facing: the `review` skill calls it, and users keep invoking `/gin-workflow:review` as before. It does not dispatch reviewers, change implementer routing, or touch ledgers.

## Requirements

### 1. `gin-workflow reviewer`

```
gin-workflow reviewer --base SHA --implementer PROVIDER [--tier low|medium|high]
```

- **Inputs.** `--tier` is the reviewed track's `Reasoning:` from the approved plan (default `medium` for work without a plan). `--implementer` is the provider that actually implemented the work; the caller knows it, and the orchestration manifest only records the planned route.
- **Raise rule.** Changed files come from `git diff --name-only --no-renames <base>...HEAD` (since the merge base, so commits added to the base branch later are not counted; a rename lists both paths). When the base tier is `low` and any changed file is not documentation, the tier becomes `medium` with reason `low track changes non-docs files: <first few paths>`. A documentation file ends in `.md` or lies under `docs/`, unless a path segment is `skills` (skill files define workflow behavior). The tier is never lowered and no other rule raises it.
- **Routes.** `resolve_assignment` with role `review` and the resolved tier gives the ordered candidates (provider, model, effort) from `routing.roles.review` and `providers.local.yaml`.
- **Independence.** At tier `low` the implementer provider stays in the list (a fresh session with a different actor id is independent enough for a low-tier review). At `medium` and `high` the implementer provider is removed, as today. `routing.review.require_independent: false` keeps every candidate; `allow_self_review_fallback` keeps its meaning.
- **Output.** Text: a line `tier <tier>`, a `reason: ...` line when the tier was raised, then one route per line (`<provider> <model> [<effort>]`) in order. Nothing is written.

### 2. `review` skill

The dispatch step runs `gin-workflow reviewer --base <ledger base> --implementer <provider> --tier <track reasoning>` and dispatches the first available route with its model; on an infrastructure failure (quota, rate limit, timeout) it tries the next route. The actor id is `reviewer:<provider>`, or `reviewer:<provider>:session-<id>` when the provider equals the implementer's. When the list is empty or every route fails, return `human_decision_required` as today.

## Errors and compatibility

- Exit 0: routes printed. Exit 2: `git diff <base>...HEAD` failed (for example `--base` is not a commit), no candidate resolves for the tier (the `resolve_assignment` diagnostics), or an empty list after the independence filter.
- Existing ledgers, approvals, and in-progress reviews are unaffected; the command only informs the next dispatch.
- No new configuration keys.

## Testing

- Raise rule (pure function): `low` + only `.md`/`docs/` files → `low`; `low` + a `.py` file → `medium`; `low` + `plugins/x/skills/y/SKILL.md` → `medium`; `medium` and `high` are never changed; an empty diff keeps the base tier.
- Routing in a temporary git repository: models follow the tier; a commit added to the base branch after the track branched is not counted; at `low` the implementer provider is listed; at `medium` it is not; `require_independent: false` keeps it; an empty list after the filter is an error unless `allow_self_review_fallback`; a bad `--base` is an error. One CLI smoke test: text output and exit 2 on a bad `--base`.
- Docs: `docs/concepts/providers.md` (Independent review), `docs/reference/cli.md` (new `reviewer` command, marked as called by the `review` skill rather than run by hand); the `review` skill stays within its instruction budget and the packaging and docs checks pass.

## Out of scope

Raising the tier when a diff leaves the track's declared `Files:` (the reviewer's scope rule already flags it; revisit if a medium-tier review misses scope drift), diff-size heuristics, reading the tier or implementer from the orchestration manifest, JSON output, a configuration switch for low-tier independence, runtime events for routing decisions, and automatic reviewer dispatch.
