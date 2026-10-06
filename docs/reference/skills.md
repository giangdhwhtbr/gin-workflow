# Skills Reference

Every skill is also a slash command: `/gin-workflow:<name>` (Claude Code) or the harness equivalent, and `/gin-qa:<name>` for the QA add-on.

## gin-workflow: lifecycle stages

Run these in order for a feature. `workflow` picks the next one for you.

| Skill | Purpose | Ends with |
|---|---|---|
| `discuss` | Clarify a requirement into a confirmed design spec before any planning, tasks, or code | `requirement_confirmed` |
| `plan` | Turn the confirmed spec into an implementation plan with routed tracks | `plan_approved` |
| `orchestrate` | Mirror the plan into Beads tracks, resolve provider routes, create the worktree | `orchestration_ready` |
| `execute` | Implement and validate one ready track, directly or through a routed worker | track closed |
| `review` | Request or perform an independent review recorded in the review ledger | approved ledger |
| `verify` | Check finished work against spec, plan, and review with fresh command output | `verification_passed` |
| `ship` | Offer merge, PR, keep, or discard; run the chosen one; close beads and ledgers | `shipped` |

## gin-workflow: entry points and status

| Skill | Purpose |
|---|---|
| `workflow` | Route the current state to exactly one lifecycle stage, or diagnose a held workflow |
| `quick` | Small, low-risk change without plan or beads: confirm, implement, verify per rigor, report |
| `progress` | Report task status, blockers, open waivers, and next ready work without changing anything |
| `report` | Report AI usage per bead or epic (tokens, cost, quality signals) without changing anything |
| `describe` | Write a self-contained HTML page for a bead or epic: graph of children, blockers, and bugs beside its full details, without changing anything |
| `setup` | First-time repository configuration and requested setup maintenance |

## gin-workflow: supporting skills

Stages load these when needed; you can also invoke them directly.

| Skill | Purpose |
|---|---|
| `gin-debugging` | Find the root cause of a bug, test failure, or build failure before fixing it |
| `gin-review-response` | Handle review findings: verify each, then fix, dispute, defer, or clarify in the ledger |
| `gin-worktrees` | Detect or create an isolated git worktree and check a clean test baseline |
| `gin-parallel-agents` | Work several independent tasks concurrently, one bounded agent per domain |
| `gin-knowledge` | Capture durable decisions and lessons, and reconcile project knowledge at ship |
| `gin-sdd` | Stage rules for `artifacts.layout: sdd`: change folders, REQ-IDs, trace, spec review, archive ([guide](../guides/sdd.md)) |
| `gin-team` | Stage rules for team mode: identity, PR-proven gates, areas and owners, claims, Beads sync ([guide](../guides/team.md)) |

## gin-workflow: setup and maintenance

| Skill | Purpose |
|---|---|
| `team-setup` | Set up or join team mode: members, roles, areas, approvals, conventions, hooks, shared Beads |
| `migrate-specs` | Move a legacy `.planning` specs and plans layout into the SDD `docs/` layout |
| `beads-migration` | Move a repository's local `.beads` directory to the central vault and link it back |
| `tech-doc` | Write technical documentation (features, API, stack, architecture, conventions, testing) from repository evidence, on request only |
| `telegram-notify` | Send Telegram notifications on lifecycle events; opt-in via `TELEGRAM_BOT_TOKEN` and `TELEGRAM_CHAT_ID` |

## gin-qa (optional add-on)

See [QA](../guides/qa.md).

| Skill | Purpose |
|---|---|
| `cases` | Write or update test cases from specs, one block per case in `qa/cases/<capability>.md`, traced to REQ-IDs |
| `e2e` | Write, run, and check Playwright specs for `Type: e2e` cases by exploring the running application |
