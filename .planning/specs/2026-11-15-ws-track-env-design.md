# Track environment with read-only siblings and running services

Epic: gin-workflow-ws-track-env
Kind: capability
Status: draft for user review.

## Goal and scope

In a workspace, a plan track names the sibling repositories it reads and never edits. The plan gate checks the names, and orchestrate and execute check the clones and give the developer each sibling's path, branch, and commit. The workspace guide names one directory to open per kind of work and says how a team runs the services a track is tested against. gin-qa records the checked-out commit of each repository in its run record.

Problem (process review of 2026-11-07: BE-LEAD-26, FE-LEAD-10, QA-12):
- A track worktree holds one repository. A frontend track also needs the contract, a shared library, and the legacy pages; a backend track needs the legacy code and the other service. `team.Track` holds only `repo` (`workflow_core/team.py:220-226`), and the plan schema has only `Repo:` (`skills/plan/plan-schema.md:61`).
- The developer receives "track text, file scope, `gin rules` output, worktree path, validation commands, and `project.run_at`" (`skills/execute/SKILL.md:32`): no path outside the worktree. No command prints the absolute path of a sibling checkout. `gin workspace status --json` prints `path`, `present`, `branch`, `dirty`, and `frozen` (`workflow_core/workspace_cli.py:104-115`).
- `check_plan_repos` never checks a clone (`team.py:335-353`). The only clone check for a track is the orchestrate skill's sentence about `Repo:` (`skills/orchestrate/SKILL.md:24`).
- The workspace guide tells every engineer "Open the IDE on the child directory, never on the parent" (`docs/guides/workspace.md:63`) and tells backend and frontend engineers "Open: `<parent>/.planning/worktrees/<track-id>`" (`:104`).
- No page says how to run dependent services or a database, and no config key describes services or environments.
- gin-qa's run record holds no commit or branch: `{"started", "specs", "playwright_exit"}` for e2e (`gin_qa/e2e.py:387`) and `{"type", "started", "command", "cases", "exit"}` for typed runs (`gin_qa/tests.py:297-298`).

In scope:
- A `Reads:` line per plan track, parsed into `team.Track` and checked by `check_plan_repos`.
- `checkout` and `commit` in the rows of `gin workspace status --json`.
- The clone check and the developer's read-only context, in the orchestrate and worktrees skills and the developer agent.
- One rule for the directory to open, a section on running services and a database, and how QA gets a running combination, in the workspace guide and its Vietnamese twin.
- `checkouts` in gin-qa's `run.json`.

Out of scope:
- Any config key for services, environments, or a run command. gin starts nothing.
- A worktree of a sibling at a named ref. A sibling is read from its main checkout as it is.
- Enforcing read-only access. gin neither blocks writes to a sibling nor compares its state before and after a track.
- Repositories that are not `workspace.repos` entries.
- `checkouts` in the `gin-qa report` page, commits for manual runs (`/gin-qa:run`), and a flag that states the commits of a remote environment.
- The branch and pull request model (`gin-workflow-ws-branch-model`, shipped).

Confirmed decisions (user, 2026-11-15): a sibling is read from its main checkout as it is, and gin never switches or pulls it; an engineer opens the track worktree for a track; gin has no part in running services, the docs give conventions and the project's own tools run them; gin-qa records the checkout state of each cloned repository by itself, with no new flag; existing commands are extended and no command is added.

Assumptions:
- "Read-only" is an instruction to the developer, as the write boundary of `Files:` is today.
- A harness that limits reads to its working directory asks the person for access to a sibling path. The guide says so.

## Requirements

R1. Plan line. A track in a workspace may carry one `Reads:` line in its metadata, for example ``- **Reads**: `legacy/shop-portal`, `services/order-api` ``. Its value is a comma-separated list of `workspace.repos` paths; backticks are optional, as for `Repo:`. The line is optional and has no meaning outside a workspace. `skills/plan/plan-schema.md` defines it next to `Repo:`, and the plan skill names it in its workspace sentence.

R2. `team.Track` gains `reads: tuple[str, ...]`, empty by default, in the order written. `plan_tracks` fills it from the track's `Reads:` line.

R3. `check_plan_repos` reports, per track and per path of `Reads:`:
- `Track N: Reads: <repo> is not in workspace.repos`
- `Track N: Reads: <repo> is the beads repository`
- `Track N: Reads: <repo> is the track's own Repo:`

A frozen repository is accepted. Whether a repository is cloned is not checked here, because clones differ per machine. `gin team check-plan` and `gin record plan-approved` refuse the plan on these findings, as they do for `Repo:` findings today.

R4. `gin workspace status --json`: each row gains `checkout`, the absolute path of the repository's main checkout, and `commit`, the full sha of its HEAD. `commit` is `null` when the repository is not cloned or git cannot read HEAD. The text output does not change.

R5. Orchestrate. A track bead's description carries `Reads: <paths>` after `Repo: <path>`. Outside team mode, each `Reads:` repository must be `present` in `gin workspace status --json`; a missing one stops orchestrate with `gin workspace clone <path>`, as a missing `Repo:` clone does. In team mode orchestrate does not check it, because another machine runs the track.

R6. Execute. For a track with `Reads:`, the session that runs the track reads `gin workspace status --json` before it dispatches the developer. A repository that is not `present` stops the track with `gin workspace clone <path>`. The developer's context gains, per `Reads:` repository, its `checkout`, `branch`, and `commit`, marked read-only. gin never switches the branch of that checkout and never pulls it. The rule lives in the Workspace section of the `worktrees` skill, which execute follows in a workspace.

R7. Developer agent. `agents/developer.md` says that a `Reads:` repository is read-only: no edit, commit, branch switch, or pull there. A change the track needs there is escalated like any out-of-scope change.

R8. Budgets hold: stage chains at most 12,000 characters, shared skills 6,000, agents 4,000 (`tests/workflow_core/test_token_budget.py`). Today the execute chain is 11,977, the plan chain 11,770, the orchestrate chain 8,140, the `worktrees` skill 3,853, and `developer.md` 3,902. Text added where the limit is near comes with an equal cut of wording in the same file or chain. No rule is dropped to make room.

R9. gin-qa. When the QA home is a workspace child (the `qa_root` that `gin specs reqs` reports), `gin-qa e2e run` and `gin-qa tests run --type <T>` write `checkouts` into `run.json`. It holds one `{path, branch, commit, dirty}` object per cloned repository, taken from `gin workspace status --json`. It states what was checked out on the machine that ran the tests, not what an environment deployed. Outside a workspace `run.json` is unchanged. When the status command fails, the run continues, gin-qa prints one warning on stderr, and `run.json` has no `checkouts`.

R10. Workspace guide (`docs/guides/workspace.md` and `workspace.vi.md`):
- One rule for the directory to open. A track: its worktree `<parent>/.planning/worktrees/<track-id>`. Setup, roadmap, discuss, plan, orchestrate, and ship: the parent. A child's main checkout: `/gin:quick` in that child, the QA home for QA, and what other tracks read. Onboarding step 3 states this rule and no longer says "never on the parent"; the role sections keep their `Open:` lines.
- Read-only siblings. The engineers' section describes `Reads:`, what the developer receives, that the checkout is read as it is (pull it yourself for a newer state), and that a harness may ask for read access to the path.
- Running a track's dependencies, written as team conventions and not as gin behaviour. Each repository documents its own run command. The combination of services and a database runs with the team's own tool: a compose file in the parent, or the host's preview environment for a pull request. The plan track names the commands a track needs as validation commands. gin starts nothing and stores no configuration for it.
- QA. QA checks out the track branches under test in each child and starts the combination with the team's tool, or uses the preview environment. `run.json` records `checkouts`. By convention, a tester who tests a preview environment names each repository's pull request URL in the approval comment.

R11. Other pages match the code. `docs/reference/cli.md`: the two new fields of `gin workspace status`, the `Reads:` findings of `gin team check-plan` and `gin record plan-approved`, and `checkouts` in the run record of `gin-qa e2e run` and `gin-qa tests run`. `docs/starters/brownfield.md`: the plan prompt names `Reads:` for a track that reads the legacy. Vietnamese twins carry the same facts. The workspace knowledge record is updated at ship.

## User Stories

### US-1: A track names what it reads
As a tech lead, I want a plan track to name the repositories it reads, so that the plan says what each developer needs before work starts.

Acceptance criteria:
- A plan whose track has ``- **Reads**: `legacy/shop-portal`, `services/order-api` `` with both paths in `workspace.repos` passes `gin team check-plan` and `gin record plan-approved`.
- A frozen repository in `Reads:` is accepted.
- A path that is not in `workspace.repos`, the beads repository, or the track's own `Repo:` is refused with the message of R3 that names the track and the path.
- A plan without any `Reads:` line gives the same result as today.

### US-2: Orchestrate finds a missing clone
As a tech lead outside team mode, I want orchestrate to stop when a repository a track reads is not cloned, so that no track starts without what it needs.

Acceptance criteria:
- With a `Reads:` repository that is not cloned, orchestrate stops and prints `gin workspace clone <path>`.
- Each track bead's description shows `Reads: <paths>` after `Repo: <path>`.
- In team mode orchestrate finishes without that check.

### US-3: The developer gets the sibling paths
As an engineer who runs a track, I want the developer agent to receive the path, branch, and commit of each repository the track reads, so that it reads the right code without searching for it.

Acceptance criteria:
- `gin workspace status --json` shows `checkout` (an absolute path) and `commit` (a full sha) for a cloned repository, and `commit: null` for a missing one.
- With a `Reads:` repository that is not cloned on this machine, execute stops before the developer starts and prints `gin workspace clone <path>`.
- The developer's context names each `Reads:` repository with its `checkout`, `branch`, and `commit` as read-only.
- The developer agent's instructions say that a `Reads:` repository is read-only.

### US-4: One directory to open
As an engineer new to the workspace, I want one rule for which directory to open, so that the IDE and the session start in the right place.

Acceptance criteria:
- The onboarding steps and the role sections of the workspace guide give the same directory for the same kind of work.
- The guide no longer contains "never on the parent".

### US-5: Running what a track depends on
As a backend engineer, I want the guide to say how a team runs dependent services and a database, so that I can test a track against them.

Acceptance criteria:
- The workspace guide has a section on running a track's dependencies that names the conventions of R10.
- The section says that gin starts nothing and has no configuration for it.

### US-6: QA records what was tested
As a QA engineer, I want each automated run to record the commit of every repository on my machine, so that a result can be traced to the code it ran against.

Acceptance criteria:
- In a workspace, `run.json` of `gin-qa e2e run` and of `gin-qa tests run --type <T>` has `checkouts` with `path`, `branch`, `commit`, and `dirty` for each cloned repository.
- Outside a workspace, `run.json` has no `checkouts`.
- When `gin workspace status` fails, the tests still run, one warning is printed, and `run.json` has no `checkouts`.
- The workspace guide says how QA gets a running combination and what `checkouts` means.

## Errors and compatibility

- A plan without `Reads:` parses and checks as today. `Track.reads` is the last field and has a default, so existing callers keep working.
- A `Reads:` value that names no known path (`none`, a typo) is refused at plan approval and never ignored.
- A `Reads:` repository that is not cloned passes plan approval. Orchestrate (outside team mode) and execute stop with the clone command.
- `gin workspace status --json` adds keys only. gin-console reads `gin state` and `bd`, not this command.
- gin-qa copies the keys a row has; a key an older gin does not print is `null`. A failed status command never fails a test run.
- gin never writes to a sibling checkout: no branch switch, pull, hook, or worktree because of `Reads:`.

## Testing

- `tests/workflow_core/test_team_gates.py`: `plan_tracks` reads `Reads:` with and without backticks; each finding of R3; a frozen repository accepted; a plan without the line unchanged; `gin team check-plan` and `gin record plan-approved` refuse a bad `Reads:`.
- `tests/workflow_core/test_workspace_cli.py`: `checkout` and `commit` for a cloned child and `commit: null` for a missing one.
- `tests/workflow_core/test_skill_routing.py` and `test_token_budget.py`: orchestrate names the `Reads:` check and the bead line; the Workspace section of the `worktrees` skill names `gin workspace status --json`, `gin workspace clone`, and the read-only context; the developer agent has the rule of R7; every budget of R8 holds.
- `tests/gin_qa/test_e2e_cli.py` and `test_tests_cli.py`, with a fake `gin`: `checkouts` in a workspace, none outside one, and a warning with no `checkouts` when the status command fails.
- Docs: `gin docs check` on every changed page, and `tests/workflow_core/test_docs_coverage.py` and `test_walkthrough_docs.py` stay green.
- The full suite runs once, at ship (`project.run_at: push`).

## Open Technical Questions
