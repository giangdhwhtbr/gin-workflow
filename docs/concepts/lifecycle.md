# Lifecycle

Every change moves through the same stages, each closed by a gate. The agent runs the stages; you confirm the design, approve the plan, and choose how to ship. Skills hold the actionable rules (`plugins/gin-workflow/src/skills/<stage>/SKILL.md`); this page explains the model they share. The [architecture diagram](architecture.md#lifecycle) shows it at a glance.

Before the first stage, a repository needs `/setup` once ([Configuration](../reference/config.md)). Stages read `.agent-workflow/generated/effective-config.yaml` and stop with setup guidance when it is missing; they never run setup themselves.

## Stages and gates

| Stage | Does | Closes with | Gate recorded by |
|---|---|---|---|
| `discuss` | Clarifies the requirement one question at a time, proposes approaches, writes the design spec to `.planning/specs/`, and waits for your confirmation | `requirement_confirmed` | `gin-workflow record requirement-confirmed --evidence <spec> --actor <id>` |
| `plan` | Writes `.planning/plans/<date>-<feature>.md`: tracks with files, interfaces, test-first steps, a provider role, and a model and effort from the model catalog each; waits for your approval | `plan_approved` | `record plan-approved --evidence <plan> --actor <id>` |
| `orchestrate` | Creates the epic and one track bead per plan track, mirrors dependencies, resolves provider routes, creates the worktree | `orchestration_ready` | `record orchestration-ready --epic <epic> --evidence <ids; worktree; branch> --actor <id>` |
| `execute` | Implements one ready track test-first, gets it reviewed, collects usage, closes it; repeat per track | `implementation_complete` | derived: every child of the epic is closed |
| `ship` | Offers merge, pull request, keep, or discard; runs the one you choose; cleans up; closes the epic | `shipped` | derived: the epic is closed |

Every `record` needs `--actor <id>`; in team mode the actor comes from `git config user.email`. One stage invocation does one stage and stops; it never starts the next one. `workflow` reads the state and runs the stage that comes next. Each feature uses its own `--workflow-id` (for example the spec's topic slug) so gates from different features do not mix; without one, `default-workflow` is used.

`gin-workflow state` evaluates the gates and routes to exactly one stage, or holds at `progress` with evidence and remedies when the work is blocked, a capability is disabled, or an approval is missing.

`/roadmap` runs before the stages and records no gate; its epics enter `/discuss <epic-id>`. With `/roadmap --milestone <id>` it plans a dated milestone: it proposes an estimate in working days for each epic and adopts open `roadmap` epics that have no parent. It sets membership and estimates only through `gin-workflow milestone move` and `gin-workflow milestone estimate`. On a re-run Beads wins, and the skill reports where the roadmap file differs. Commands and flags are in the [milestone reference](../reference/cli.md#gin-workflow-milestone).

### Standalone beads

A pre-existing bead can skip discuss and plan: record it as its own epic with `record orchestration-ready --workflow-id <bead> --epic <bead> --evidence <bead> --actor <id>`, and pass `--workflow-id <bead>` to every later call. The bead's description and acceptance criteria stand in for the spec and plan, so `requirement_confirmed` and `plan_approved` count as satisfied while the bead has no children; no waiver is needed. `implementation_complete` is then the bead itself closed, and after the merge `record shipped --workflow-id <bead> --evidence <merge commit> --actor <id>` marks it shipped.

## Execute and review

- The main session picks a ready task (`gin-workflow task ready`), claims it, and runs `gin-workflow rules --files <scope>`. It implements no track itself: it spawns `gin-workflow:developer` at the model and effort that `gin-workflow routes dispatch` returns. The developer gets a bounded context: track text, file scope, rules output, worktree path, and validation commands.
- The developer follows the rules output, reads the shape appendix for `project.shape`, writes the failing test first, implements, and keeps the command output as evidence. It reports `done`, `needs_clarification`, `failed`, or `blocked`.
- `failed` escalates one step with `gin-workflow routes dispatch --escalate`: the next model at the same effort, or the next effort at the strongest model. `needs_clarification` is answered from the spec or plan at the same route. At the top of both lists, on `blocked`, or on a question the spec and plan do not answer, the bead stays in progress with a note and you decide.
- A track routed to another harness runs there through [gin-orchestrator](../orchestrator/README.md).
- Review runs inside `execute`, per track; it is not a router lifecycle stage, and `gin-workflow state` has no review gate. `ship` checks the approvals instead.
- Review is independent of the implementer's session; [Providers](providers.md#independent-review) defines session and provider independence. Findings and approvals are recorded in the review ledger for at most `routing.review.max_cycles` cycles. Findings are answered one by one with the `gin-review-response` skill; there is no silent dismissal.
- When tests pass and review approves, the agent runs `gin-workflow usage collect --bead <id> --best-effort` and closes the track bead. Closing a track needs no merge; it unblocks the dependent tracks.
- The feature branch is committed and pushed. The agent never reports "waiting for PR merge" without a real pull request link; it offers to request a pull request or to continue with the next track.

## Quality gates and handoff

Quality checks are mechanical, so there is no separate verification step: git hooks run them without spending agent tokens (`gin-workflow hooks install`; `/setup` runs it):

1. `pre-commit` runs `lint` and `typecheck` from `verify.checks`.
2. `pre-push` runs `test`, plus `build` at `standard` rigor and `e2e` at `strict`, when the pushed branch is the checked-out HEAD. It stops at the first failure.
3. CI is the backstop for large projects: nothing in `ship` proves a hook ran.
4. `ship` runs a few plain steps instead of re-running the suite. With the review ledger on, every closed track validates (`--in-history`), `render --check` shows no drift, and nothing but spec and review artifacts changed after the newest approval. With SDD, it runs `specs lint` and `specs trace`. A failure stops `ship` and reports; it does not retry. Failures go to `gin-debugging`.

The agent still checks, per track during review, that each spec and plan requirement the track delivers is met in the code, not just the diff.

| Claim | Requires | Not enough |
|---|---|---|
| Tests pass | test output with 0 failures | an earlier run |
| Bug fixed | the original symptom's test passes, red then green | code changed |
| Agent completed | the diff checked | the agent says so |
| Requirements met | the checklist checked | tests passing |
| Waiting for PR merge | a pushed branch and a real PR link | uncommitted code |

At handoff the agent reports what changed, what was validated and what was not, waived gates with reasons and follow-up beads, the bead status, remaining risks, and the next commands.

## Ship

`ship` requires `implementation_complete` and a terminal review state, and runs the plain steps above. It then offers four options for a named branch: merge locally, push and open a pull request, keep the branch, or discard (typed confirmation). Merging, opening a pull request, and force-pushing each need your explicit approval. For a merge, it first runs `usage collect` for the epic and deletes the closed tracks' review ledgers in a commit on the feature branch. It then merges, removes the worktree, deletes the branch, and closes the epic, which marks `shipped`.

## The quick path

`/quick` is for a small, low-risk change: no spec, plan, beads, or gates. `gin-workflow quick-check --changed-files N --modules M` decides:

- `allowed`: within `quick.max_files` (default 5) and one module. The agent implements, runs the verify commands for the rigor, and reviews (self check under `easy`, independent otherwise), then records `quick-completed`.
- `escalate`: too large; use the full lifecycle.
- `refused`: `strict` rigor without a `requirement_confirmed` waiver.

`/quick` never commits; you do. See [Use cases](../guides/use-cases.md#small-change).

## Waivers

A gate is never removed: it is satisfied, or waived on the record with `gin-workflow unblock`. A waiver is a `gate.waived` event bound to the current scope hash.

| Class | Gates | Waiver |
|---|---|---|
| Process | `requirement_confirmed`, `plan_approved`, `orchestration_ready` | the agent may waive with a stated reason |
| Safety | `review_approved` | needs a follow-up bead (`--follow-up`); asking a person first is a convention the CLI does not check. In [team mode](../guides/team.md) the CLI requires a team member who holds the gate's approval role when `team.approvals` sets one |
| Not waivable | `implementation_complete`, `shipped` | facts, not formalities |

`review_approved` is not a routing gate; it is classified so that skipping independent review is recorded like any other waiver. `unblock --clear-blocker` clears a recorded blocker.

## Approvals

You approve the design (confirmation), the plan, production-impacting parallel work, disabling worktree isolation or running on the current branch, data moves, changes to scope or execution strategy, and every merge, pull request, or force-push. An approval is recorded before the action and stays valid while the approved scope is unchanged, within `policy.approval.ttl_seconds` (default 24 hours).

## Variations

- With the SDD layout (`artifacts.layout: sdd`), `discuss` writes a change folder with REQ-IDs instead of a dated spec, tests carry the REQ-IDs, and `ship` archives the change into the living specs. See [SDD](../guides/sdd.md).
- In team mode (`team:` configured), gates are proven by approved pull requests from the right roles, tracks carry `Area:` and `Owner:`, and beads are claimed per member. See [Team mode](../guides/team.md).
- `easy` rigor skips worktrees and uses a self check; `strict` rigor always isolates and requires a review ledger.
