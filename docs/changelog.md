# Changelog

This page lists what changed in each release of gin-workflow and its add-ons (gin-qa, gin-orchestrator, gin-ba), newest first. Releases before 3.1.0 are on the [GitHub releases page](https://github.com/giangdhwhtbr/gin-workflow/releases).

## Unreleased

In team mode a member now works a lane, the tracks of one plan that share a `Lane:` line, on one branch and in one pull request, instead of a pull request per track.

### Upgrade notes

- A track bead without a `Lane:` line keeps its own branch `feat/<topic>-t<N>` and its worktree `.planning/worktrees/<bead>`, so open work needs no step.
- Add `- **Lane**: <name>` to every track of a team plan. `gin team check-plan` fails a track without it.

### Added

- `gin team check-plan` reports a missing or invalid lane, and a lane whose tracks have different owners or repositories.
- `gin goal --lane NAME` covers one lane, including its unassigned tracks. In team mode the goal covers your tracks, leaves out tracks that wait for another lane to merge, and requires the lane's branch to be pushed.
- `gin team ready` rows carry `lane` and `branch`, and the text groups rows under their branch.

### Changed

- `gin team claim`, `reassign`, `handoff`, and `takeover` act on every open track of the lane. A claim restarts the lane branch from the default branch after its pull request merged.
- `gin team pending` lists one branch per lane with an open track. `gin team deps` and `gin team complete` read the `Tracks:` line of merged pull requests.

## [3.1.2] - 2026-11-15

Use cases and activity diagrams in the SDD layout now follow the SRS a business analyst writes, and technical epics are no longer asked for diagrams.

### Upgrade notes

- Update gin on each machine. No project step is needed, and `.ginrc` stays as it is.
- An open SDD change that adds requirements fails `gin specs lint --change <epic> --against <base>` until it adds or changes an activity diagram of that capability. A change that only modifies requirements no longer needs one.

### Added

- The use case template has optional `Secondary actors:`, `Trigger:`, `Includes:`, and `Extends:` lines and `## Exception flows` and `## Business rules` sections. Its comment gives the writing rules a BA expects.
- `gin specs export` opens each chapter's use cases with a generated use case diagram: actors outside the capability box, an actor edge only where a use case has `Actor:`, and `«include»` and `«extend»` edges.
- The activity template draws lanes as subgraphs, start and end nodes, labelled decision branches, and a `Use case:` line naming the use case it draws.
- `gin specs new` takes `--kind capability|technical|parity`. Without it, the kind comes from the epic's `kind:` label, else `capability`.

### Changed

- `gin specs lint` reports an `Includes:`, `Extends:`, or `Use case:` line that names a use case missing from the capability. A use case that another use case includes may omit `Actor:`.
- With `--change --against <base>`, lint asks for an activity diagram per feature instead of per capability. Each capability with added requirements needs an activity diagram added or changed since the base. Each changed use case with an alternative or exception flow needs a diagram naming it. Each edge leaving a decision in a changed diagram needs a label. An unknown base ref exits 2.
- `/gin:discuss` settles the kind of every epic, not only a roadmap epic, and SDD discuss labels the epic it creates with `kind:<kind>`.

### Fixed

- A technical change is no longer asked for activity diagrams, even when its spec delta holds requirements. Lint reads the kind from the epic's `kind:` label first, reports a label that disagrees with `Kind:` in `01-proposal.md`, and falls back to that line when Beads cannot answer.

## [3.1.1] - 2026-11-15

### Upgrade notes

- Update gin on each machine. No project step is needed, and `.ginrc` stays as it is.

### Fixed

- `gin specs explain NAME --legacy APP` accepts a capability that has no living spec yet when `--narrative` is given. The page holds the narrative and any diagrams and dated asset folders.
- With `--legacy`, `gin specs explain` takes a name as a change only when it is the whole name of a change folder. A capability whose name starts like an open change is no longer refused.
- `gin setup doctor` and `gin setup preset` no longer report the `assets`, `diagrams`, and `use-cases` folders of a capability as non-SDD files. Hidden files such as `.DS_Store` are ignored too.

## [3.1.0] - 2026-11-15

gin, gin-qa, gin-orchestrator, and gin-ba now share one version. This release adds hosts for team mode (Gitea and AWS CodeCommit) and milestone retros and closing. It runs the full suite once before the push, makes the review ledger optional, and adds QA and BA work inside a workspace and a version pin for projects.

### Upgrade notes

- Update gin on every machine before anyone runs `gin setup update --approve` in a project. Version 3.0 rejects a configuration at schema 2.10, so a member still on it could not work in the project. [The upgrade guide](https://giangdhwhtbr.github.io/gin-workflow/guides/upgrading/) gives the order step by step.
- Then run `gin setup update --approve` once in each project. It migrates the configuration to schema 2.10, which drops the `notifications` key, and writes `.ginrc` with the installed version.
- `.ginrc` pins the lowest gin version a project needs, and gin 3.1.0 refuses to run in a project whose pin it does not meet. A new project gets it from `gin setup init`; run `gin version` to see the state.
- Do not use a 3.1 team setting until every member has updated gin: `team.host: gitea` or `codecommit`, the approval policies `{all: [...], any: [...]}` and `host`, or a `requirement_confirmed` map per epic kind. Older versions reject those configurations.
- gin, gin-qa, gin-orchestrator, and gin-ba are all 3.1.0. `gin --version` prints `gin 3.1.0` instead of `gin 3.0`, and `gin-qa --version` prints `gin-qa 3.1.0` instead of `gin-qa 0.11`.
- The default `./install.sh` run refreshes the add-ons already installed. `./install.sh --plugin <name>` alone installs only that add-on and does not update gin, so run it after the default run. `gin version` lists the gin-qa and gin-orchestrator versions it finds, and `gin setup doctor` reports one whose version differs from gin's.
- Reinstall with the installer to get a session-start check in the Claude Code hooks file. It tells the agent at the start of a session when gin is older than `.ginrc` needs.
- `verify.run_at` defaults to `push` under `easy` and `standard` rigor: a track runs only the tests of what it changed, and the full suite runs once before the push. Keep the old behavior with `gin setup configure --set verify.run_at=track --approve`.
- In team mode, `/quick` started on the base branch now pushes `quick/<slug>` and opens a pull request. It used to commit locally and stop.
- A milestone without a `lanes` value or an `AI capacity:` number now counts only the `team.members` who hold a building role as lanes, so forecasts can move. Set `gin milestone update ID --lanes N` to fix the number.
- Forecast dates can also move because an in-progress epic is placed for its remaining days and an open epic without an estimate takes the median estimate of its group.

### Added

- `gin version` shows the installed gin, the pin in `.ginrc`, and whether they are compatible. It also lists the versions of gin-qa and gin-orchestrator when it finds them.
- `team.host` accepts `gitea`, for gitea.com and self-hosted instances through the `gt` CLI, and `codecommit`, through the `aws` CLI.
- Members on CodeCommit set `aws_identity`, the IAM user or `<role>/<session>` that gin matches against an approver.
- Approval policies accept `{all: [...], any: [...]}`: each `all` role and one `any` role must approve. When the policy has an `any` role, an `all` role whose only holder is the author is skipped with a note.
- A gate policy can be `host`, which leaves approvals to the host's branch protection while gin keeps its repository, merge, and plan checks.
- `requirement_confirmed` takes a policy per epic kind (`capability`, `technical`, `parity`). An epic's kind comes from its `kind:<kind>` label or the `Kind:` line of its spec.
- `gin specs template technical-design.md` prints the design of a technical epic, which needs no user stories.
- A parity change names the confirmed legacy asset folders it matches with `Parity with:`, and `gin specs lint` checks them.
- `gin record plan-approved` refuses while a technical question (`TQ-<n>`) in the design doc has no `Decision:` line.
- `gin team pending` lists the open pull requests of spec, plan, track, ship, and quick branches, and what each one still needs under its approval policy.
- `gin team complete EPIC` closes an epic when every child bead that is not a prep task is closed and the newest pull request of each track has merged. In a workspace, when `feat/<topic>` exists on `origin` of the parent repository, its pull request must have merged too. Only an area lead can run it.
- `gin team claim` creates the track worktree on `feat/<topic>-t<N>` in the repository the track names.
- `gin team takeover` and `gin team deps` work in a workspace child.
- `gin record shipped --evidence` can be repeated, one pull request per repository, for an epic that changes several repositories.
- `gin team ready --exclude-label LABEL` leaves out beads with a label, and the command lists a prep task that only its parent epic blocks.
- `/gin:allocate` proposes prep tasks (`capture`, `mockup`, `spike`, `question`, `other`) under roadmap epics before discuss, for one epic or a whole milestone.
- `/gin:retro` records one member's milestone retro as a `[gin retro]` comment on the milestone bead.
- `/gin:milestone-close` closes a milestone in one run: it summarizes delivered and open epics, moves the open ones to the next milestone, and compares team-level metrics with the previous close.
- `gin milestone update` takes `--away MEMBER:FROM[..TO]` for days off and `--integration YYYY-MM-DD` for an integration date.
- `gin milestone show` marks `oversized` epics, and it warns `spec_due` for an open epic whose spec is not confirmed when its planned milestone starts within 5 working days.
- `gin usage report` marks a total that is incomplete with `partial` and lists the reasons in `partial_reasons`.
- `/gin:tech-doc` also writes `12-DATABASE.md` for a datastore and `13-CAPABILITIES.md`, a capability catalog that `/gin:roadmap` reads.
- The rule packs `java`, `spring`, and `jvm-templates` cover Java 8, Spring, and JSP or Velocity templates. They are detected from `pom.xml`, `build.gradle`, or `build.gradle.kts`.
- `rules.packs` in a `workspace.repos` entry adds rule packs inside that repository.
- From a workspace child, `gin rules`, `gin setup doctor`, and `gin evidence run` use the entry's own packs and checks.
- `gin workspace add PATH --url URL` records a repository in `workspace.repos`.
- `gin workspace clone` installs the verify hooks of a new clone.
- `gin team init --all-repos` writes the team files, and `gin team hooks --all-repos` installs the commit-msg hook, in each cloned workspace child.
- A plan track can carry `Reads: <paths>`, the repositories it reads and never edits.
- `gin team check-plan` and `gin record plan-approved` report a `Reads:` path that is not in `workspace.repos`, is the beads repository, or is the track's own `Repo:`.
- `gin workspace status --json` rows carry `checkout` and `commit`.
- `gin commit <path>... -m <message>` commits only the named paths and never pushes. On `main`, `master`, or the `default_branch` of its `workspace.repos` entry, it first moves to a new branch.
- The gin-qa and gin-ba skills offer `gin commit` after you review what they wrote.
- `gin specs assets list CAP` lists the dated asset folders of a capability.
- `gin specs assets confirm` records `Confirmed by:` and, with `--agreed-with`, `Agreed with:`.
- Use cases are optional files under `<capability>/use-cases/`, written from `gin specs template use-case.md`. `gin specs lint` checks them, and the SRS export prints them.
- `gin specs trace` scans the cloned children of a workspace and lists the ones it skipped.
- `gin specs lint` accepts `MODIFIED` and `REMOVED` on a requirement that another open change adds. `gin specs archive` then asks you to archive the adding change first.
- `gin specs explain NAME --legacy APP` writes an explain page for the legacy code of a capability in a frozen workspace app, under the new `artifacts.explain` folder.
- gin-qa runs from the `shape: qa` workspace child, the QA home, and from its track worktrees. A single repository sets `qa.dir` instead.
- gin-qa cases take an optional `Legacy:` field that names, as relative paths, the legacy screens and recorded payloads a parity test checks.
- `/gin-qa:setup` warns when `project.layout` is not `sdd`, because `gin-qa cases plan` then has no work list.
- `run.json` of `gin-qa e2e run` and `gin-qa tests run` records `checkouts`: the path, branch, commit, and dirty state of each cloned workspace repository.
- The `qa` provider role and the `/gin:qa-track` skill route a QA track to the matching gin-qa skill.
- `ship` and the reviewer read gin-qa coverage when gin-qa is installed.
- `/gin-ba:mockup` uses the cloned frontend child of a workspace as the existing UI and skips a one-to-one copy of a legacy screen. It also records who agreed.
- Epics take `[gin question]` and `[gin answer]` comments between a worker and the people who own the spec. The BA posts `[gin accept]` once the QA report is in.
- Every stage posts what it learned as a `[gin learn]` comment on the bead, and `ship` writes the knowledge records before it offers the options.
- The review ledger has `withdraw-deferral` for a proposed deferral and `require-human-decision`, which asks a human to decide an important deferral.
- The QA guide has ship checklists per kind of pull request and CI snippets that publish test evidence.

### Changed

- `verify.run_at` (`track`, `push`, or `host`) decides where the full suite runs. Under `host`, the pre-push hook and `gin evidence run` run nothing, because the host CI owns the tests.
- The review, ship, and worktree steps follow `project.review_ledger`, `project.review`, and `project.worktree`. With the ledger off, a reviewer reports a verdict and findings and no ledger is written.
- `ship` merges track branches into `feat/<topic>` outside team mode and workspaces. Under `run_at: push`, it runs the full suite once on the feature branch before the merge.
- `gin milestone` reads spec readiness from the `gates` metadata of the epic bead as well as from the local event log.
- In team mode, `gin record orchestration-ready` writes `gates.orchestration_ready` to the epic bead, so `gin state` shows it on every machine.
- `gin milestone` places an in-progress epic for its remaining days, and the epic rows of `gin milestone show` carry `remaining_days` and `assumed_days`.
- `gin milestone show` prints `deadline` from the `Deadline:` line of the roadmap file.
- `gin milestone` places an unestimated open epic for the median estimate of its group instead of giving it no days.
- `gin-qa cases bug` now files a bug for a case of any type, not only manual cases. It exits 2 and names the epics when a case belongs to several; `--discovered-from` picks one.
- `/gin:quick` in team mode records a `[gin quick]` comment on an epic or the active milestone. The pull request lists the QA cases that cover the change.
- `plan_approved: area_lead` accepts the lead of another area when the plan author is the only holder of an area's lead role.
- `gin setup doctor` checks a workspace child on its own. From the parent, it proposes the rule packs each entry could add.
- `/gin:progress` now shows the milestone, the pending approvals, the spec state, and the QA state. `--area` or `--repo` keeps the tracks of one area or repository.
- `/gin:roadmap` now writes a manager view of the roadmap: a summary table, an outcome and a demo per milestone, and a legacy coverage table.
- `/gin:roadmap` now plans capability epics with one track per repository, and an integration epic for each capability that a milestone lists under `Integrates:`.
- On Claude Code and Antigravity, tracks and reviews always run in native subagents. An Antigravity subagent runs the model of the agy session.
- A track whose worker fails with `invalid_result_contract` but left new commits in the worktree is checked as if it were done.
- The brownfield starter shows a workspace of repositories with tracks per repository, a BA and a lead on `requirement_confirmed`, and the contract decided as technical questions in plan.

### Fixed

- `gin team check --gate ship` and `gin record shipped` no longer refuse every pull request of a workspace child. They match the pull request to its repository.
- `gin workspace clone` clones a remote that has no branches yet.
- New `workspace.repos` paths are written inside the `.gitignore` block of the workspace.
- `gin setup refresh` adds a missing local-file entry to `.agent-workflow/.gitignore`.
- `gin task close` reads the review ledger of a workspace child track from the parent that holds its worktree.
- `gin goal` prints a condition that can be checked from Beads, the gates, and the ledgers. It names the ledger clause only when the ledger is on.
- `gin-orchestrator dispatch` finds the repository that owns a track worktree.
- `gin-orchestrator dispatch` normalizes the status words and commit objects of a worker result before it checks the contract.
- Reinstalling gin refreshes an installed gin-ba add-on.

### Removed

- Outbound notifications are removed: the `notify` command and the `notifications` configuration key. `gin setup update --approve` deletes the key; until then, `gin setup doctor` reports that `notifications` is ignored.
