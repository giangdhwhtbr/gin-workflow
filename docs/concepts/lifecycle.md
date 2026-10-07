# Lifecycle

Every change moves through the same stages, each closed by a gate. The agent runs the stages; you confirm the design, approve the plan, and choose how to ship. Skills hold the actionable rules (`plugins/gin-workflow/src/skills/<stage>/SKILL.md`); this page explains the model they share. The [architecture diagram](architecture.md#lifecycle) shows it at a glance.

Before the first stage, a repository needs `/setup` once ([Configuration](../reference/config.md)). Stages read `.agent-workflow/generated/effective-config.yaml` and stop with setup guidance when it is missing; they never run setup themselves.

## Stages and gates

| Stage | Does | Closes with | Gate recorded by |
|---|---|---|---|
| `discuss` | Clarifies the requirement one question at a time, proposes approaches, writes the design spec to `.planning/specs/`, and waits for your confirmation | `requirement_confirmed` | `gin-workflow record requirement-confirmed --evidence <spec> --actor <id>` |
| `plan` | Writes `.planning/plans/<date>-<feature>.md`: tracks with files, interfaces, test-first steps, a provider role and reasoning tier each; waits for your approval | `plan_approved` | `record plan-approved --evidence <plan> --actor <id>` |
| `orchestrate` | Creates the epic and one track bead per plan track, mirrors dependencies, resolves provider routes, creates the worktree | `orchestration_ready` | `record orchestration-ready --epic <epic> --evidence <ids; worktree; branch> --actor <id>` |
| `execute` | Implements one ready track test-first, gets it reviewed, collects usage, closes it; repeat per track | `implementation_complete` | derived: every child of the epic is closed |
| `verify` | Re-runs the quality gates, validates every review ledger, and checks the spec and plan line by line against the code. The recorded event names the verified branch and commit; a later commit that changes more than spec artifacts returns the gate to unmet | `verification_passed` | `record verification-passed --evidence <commands and results> --actor <id>` |
| `ship` | Offers merge, pull request, keep, or discard; runs the one you choose; cleans up; closes the epic | `shipped` | derived: the epic is closed |

Every `record` needs `--actor <id>` (in team mode it comes from your git email). One stage invocation does one stage and stops; it never starts the next one. `workflow` reads the state and runs the stage that comes next. Each feature uses its own `--workflow-id` (for example the plan's slug) so gates from different features do not mix; without one, `default-workflow` is used.

`gin-workflow state` evaluates the gates and routes to exactly one stage, or holds at `progress` with evidence and remedies when the work is blocked, a capability is disabled, or an approval is missing.

### Standalone beads

A pre-existing bead can skip discuss and plan: record it as its own epic with `record orchestration-ready --workflow-id <bead> --epic <bead> --evidence <bead> --actor <id>`, and pass `--workflow-id <bead>` to every later call. The bead's description and acceptance criteria stand in for the spec and plan, so `requirement_confirmed` and `plan_approved` count as satisfied while the bead has no children; no waiver is needed. `implementation_complete` is then the bead itself closed, and after the merge `record shipped --workflow-id <bead> --evidence <merge commit> --actor <id>` marks it shipped.

## Execute and review

- The agent picks a ready bead (`bd ready`), claims it, and works in the track's worktree. It runs `gin-workflow rules --files <scope>` and follows the output, and reads the shape appendix for `project.shape`.
- It writes the failing test first, implements, and keeps the command output as evidence. A blocker, a plan gap, or repeated failures stop the work: the bead stays in progress with a note.
- Work runs directly in the session for sequential plans and three or fewer tasks; routed workers are for more than three parallel tasks, long-running or specialized work, or independent review ([Providers](providers.md)).
- Review runs inside `execute`, per track; it is not a router lifecycle stage, and `gin-workflow state` has no review gate. `verify` checks the approvals instead.
- Review is independent: a different provider (or session, in single-provider mode) reviews the bounded diff and records findings and approval in the review ledger, for at most `routing.review.max_cycles` cycles. Findings are answered one by one with the `gin-review-response` skill; there is no silent dismissal.
- When tests pass and review approves, the agent runs `gin-workflow usage collect --bead <id> --best-effort` and closes the track bead. Closing a track needs no merge; it unblocks the dependent tracks.
- The feature branch is committed and pushed. The agent never reports "waiting for PR merge" without a real pull request link; it offers to request a pull request or to continue with the next track.

## Verification and handoff

`verify` claims nothing without fresh evidence from this run:

1. Every track's ledger validates (`review-ledger.py validate`, `--in-history` for earlier tracks on a shared branch) and `render --check` shows no drift.
2. The verify commands for the rigor pass (easy: lint, typecheck, test; standard: + build; strict: + e2e), plus any manual checks in the plan.
3. A checklist of every spec and plan requirement is checked against the code, not just the diff.
4. Every run, failure, skipped check, risk, and unavailable provider is recorded. Failures go to `gin-debugging`.

| Claim | Requires | Not enough |
|---|---|---|
| Tests pass | test output with 0 failures | an earlier run |
| Bug fixed | the original symptom's test passes, red then green | code changed |
| Agent completed | the diff checked | the agent says so |
| Requirements met | the checklist checked | tests passing |
| Waiting for PR merge | a pushed branch and a real PR link | uncommitted code |

At handoff the agent reports what changed, what was validated and what was not, waived gates with reasons and follow-up beads, the bead status, remaining risks, and the next commands.

## Ship

`ship` requires `verification_passed`, re-runs the tests, and offers exactly four options for a named branch: merge locally, push and open a pull request, keep the branch, or discard (typed confirmation). Merging, opening a pull request, and force-pushing each need your explicit approval. After a merge it re-runs the tests on the merged result, removes the worktree, deletes the branch, runs `usage collect` for the epic, closes the epic (which marks `shipped`), and cleans up the closed beads' review ledgers.

## The quick path

`/quick` is for a small, low-risk change: no spec, plan, beads, or gates. `gin-workflow quick-check --changed-files N --modules M` decides:

- `allowed`: within `quick.max_files` (default 5) and one module. The agent implements, runs the verify commands for the rigor, and reviews (self check under `easy`, independent otherwise), then records `quick-completed`.
- `escalate`: too large; use the full lifecycle.
- `refused`: `strict` rigor without a `requirement_confirmed` waiver.

`/quick` never commits; you do. See [Use cases](../guides/use-cases.md#small-change).

## Waivers

A gate is never removed: it is satisfied, or waived on the record with `gin-workflow unblock`. A waiver is a `gate.waived` event bound to the current source tree.

| Class | Gates | Waiver |
|---|---|---|
| Process | `requirement_confirmed`, `plan_approved`, `orchestration_ready` | the agent may waive with a stated reason |
| Safety | `verification_passed`, `review_approved` | needs human approval and a follow-up bead |
| Not waivable | `implementation_complete`, `shipped` | facts, not formalities |

`review_approved` is not a routing gate; it is classified so that skipping independent review is recorded like any other waiver. `unblock --clear-blocker` clears a recorded blocker.

## Approvals

You approve the design (confirmation), the plan, production-impacting parallel work, disabling worktree isolation, changes to scope or execution strategy, and every merge, pull request, or force-push. An approval is recorded before the action and stays valid while the approved scope is unchanged, within `policy.approval.ttl_seconds` (default 24 hours).

## Variations

- **SDD layout** (`artifacts.layout: sdd`): `discuss` writes a change folder with REQ-IDs instead of a dated spec, tests carry the REQ-IDs, and `ship` archives the change into the living specs. See [SDD](../guides/sdd.md).
- **Team mode** (`team:` configured): gates are proven by approved pull requests from the right roles, tracks carry `Area:` and `Owner:`, and beads are claimed per member. See [Team mode](../guides/team.md).
- **Rigor**: `easy` skips worktrees and uses a self check; `strict` always isolates and requires a review ledger.
