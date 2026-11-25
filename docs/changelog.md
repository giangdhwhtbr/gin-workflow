# Changelog

This page lists what changed in each release of gin-workflow and its add-ons (gin-qa, gin-ba), newest first. Releases before 3.1.0 are on the [GitHub releases page](https://github.com/giangdhwhtbr/gin-workflow/releases).

## [3.5.3] - 2026-11-25

### Upgrade notes

- Update gin on each machine. No project step is needed, and `.ginrc` stays as it is.
- gin needs bd 1.3.4 or later. Update bd on each machine that uses the Beads backend.
- In team mode, an epic that `gin record orchestration-ready --epic` claimed before 3.5.3 stays assigned. `gin team complete` takes it over. To close it with `gin task close` instead, remove its assignee once: `bd update <epic> --assignee "" --force`.

### Changed

- gin no longer supports bd before 1.3.4. `gin team claim`, `reassign`, and `handoff --release` always pass `--force` when they take a bead from another member.
- In team mode, `gin record orchestration-ready --epic` sets the epic `in_progress` without assigning it to anyone. Its tracks carry the claims.

### Fixed

- `gin team complete` closes an epic or open `prep` child that another member holds. It assigns the bead to the lead with a note, then closes it. bd 1.3.4 refused the close, so the command exited 2.

## [3.5.2] - 2026-11-25

### Upgrade notes

- Update gin on each machine. No project step is needed, and `.ginrc` stays as it is.
- In team mode, a member who runs bd 1.3.4 needs gin 3.5.2 to take over a claim, reassign, or release a bead that another member holds.

### Fixed

- `gin team claim` on an expired claim, `gin team reassign`, and `gin team handoff --release` work with bd 1.3.4. That bd refuses to change the assignee of a bead another member holds without `--force`. gin passes `--force` after its own checks, and only to a bd that has the flag (1.3 and later).

## [3.5.1] - 2026-11-25

### Upgrade notes

- Update gin on each machine. No project step is needed, and `.ginrc` stays as it is.
- A project whose `qa.e2e` points outside the QA home now gets its e2e and tests runs in `evidence/` of the QA home (`qa/evidence` by default). Run folders written before stay where they are: `gin-qa report` shows their results without steps, and `gin-qa e2e check --run` refuses them. Run the cases again to get evidence in the new folder.

### Fixed

- gin-qa keeps the evidence folder in the QA home when `qa.e2e` points elsewhere. `qa.e2e: newapp/e2e` wrote runs to `newapp/evidence` instead of `qa/evidence`. When `newapp` is a repository of its own, the `.gitignore` entry that gin-qa added did not cover them.

## [3.5.0] - 2026-11-22

Beads can carry images: `gin attach` stores screenshots outside the tracker, and `gin-qa cases bug` attaches the evidence of a failed case. gin-qa keeps every recorded result in a run history that merges without conflicts. With the SDD layout, each requirement records who signed it off, and `gin specs trace --all` joins it to its beads, cases, and tests. Any epic takes story points, and the milestone forecast gives every roadmap epic chained dates.

### Upgrade notes

- Update gin on each machine. No project step is needed, and `.ginrc` stays as it is: raise it only when a project needs gin 3.5.0.
- The first gin-qa result recorded with 3.5.0 creates `runs/` next to the cases folder (`qa/runs` by default) and adds a `merge=union` line to `.gitattributes`. Commit both with the case files; `/gin-qa:run`, `/gin-qa:e2e`, and `/gin-qa:tests` do so when they save the work.
- `gin attach` uses the `git-ref` store unless [`attachments`](reference/config.md#attachments) says otherwise. The `s3` store needs `python3 -m pip install boto3`. An older gin ignores the `attachments` section.
- Track beads that orchestrate created before 3.5.0 may still hold the epic's `export:` label, so `bd ship <capability>` refuses. Remove the label from those tracks with `gin task update <track> --remove-label export:<capability>`.

### Added

- `gin attach {add,list,fetch,push,prune}` stores images for a bead in a `git-ref`, `local`, or `s3` store, strips EXIF and XMP, and lists them in the bead's `metadata.attachments`. `prune` keeps every image an open bead references. See [`gin attach`](reference/cli.md#gin-attach).
- `gin-qa cases bug` attaches the image `--evidence` files inside the repository and the failed-step screenshots of the case's e2e run, and shows them in the bug description. An attach problem is a warning.
- gin-qa appends one JSON line per recorded result to `runs/<yyyy-mm>/<actor>.jsonl`, from `cases result`, `cases bug`, `e2e run`, and `tests run`. The case file keeps the latest result as before.
- `gin-qa runs export [--capability CAP] [--case TC-ID] [--since YYYY-MM-DD]` lists that history. See [`gin-qa runs export`](reference/cli.md#gin-qa-runs-export).
- `--actor` on `gin-qa cases result`, `cases bug`, `e2e run`, and `tests run`, and a repeatable `--evidence` on `cases result`, fill the run record. The actor defaults to `git config user.email`.
- With the SDD layout, `gin record requirement-confirmed` stores each requirement of the change with its hash, and `gin specs archive` writes `06-signoff.md` into the archived change folder.
- `gin specs trace --all` lists every requirement with its changes, sign-off, beads, gin-qa cases, and tests. See [Requirement trace](reference/cli.md#requirement-trace).
- `gin points EPIC N --reason TEXT [--stage roadmap|discuss|close]` sets the story points of any open epic, with or without the `roadmap` label. `gin milestone points` is an alias.
- `/discuss` scores every workflow into a `Points:` line of the spec, and writes it to the epic once the spec is confirmed. `/orchestrate` copies the line to an epic it creates.
- `gin milestone list --json` adds `forecast.milestones` and `forecast.epics`: each open milestone and each open roadmap epic with its chained dates, lane, and warnings.

### Changed

- `days_per_point` is measured over the 10 most recently closed epics with points, whatever their labels.

### Fixed

- Orchestrate creates track and lane beads with `--no-inherit-labels`, so a track no longer copies the epic's `export:` label and `bd ship` works.
- A schema 2.11 configuration that holds a retired key in any layer is refused with a message that names the file to edit. The 2.11 update also backs up and removes a leftover `providers.local.yaml`.
- `gin setup doctor` names a working remedy for tier models left in `orchestrator.local.yaml` and reports any other leftover `orchestrator.local.yaml` as unused.

## [3.4.0] - 2026-11-21

gin no longer tracks AI usage. Collecting it took about a minute per epic at every track and at ship, and the figures missed most of the work, so the `gin usage` command, the price catalog, the per-epic budget, and the `report` skill are removed.

### Upgrade notes

- `gin usage collect` and `gin usage report` are gone; `execute`, `ship`, and `milestone-close` no longer run them. `ai_usage` already stored on beads stays, and nothing writes it any more.
- `usage.budget_usd` is ignored, and `gin routes dispatch` no longer exits 3. `gin state` and `gin setup doctor` say so until you delete `usage:` from `.agent-workflow/config.yaml`; no `gin setup update` is needed.
- `.agent-workflow/usage-prices.yaml` is no longer read; delete it.
- The `report` skill (`/gin:report`, OpenCode `gin-report`) is removed; a project install removes gin's copy and keeps gin-qa's `report` skill.
- `milestone-close` no longer computes `cost_per_epic` and `rework`.

## [3.3.0] - 2026-11-21

gin now runs every stage in the harness you opened. The gin-orchestrator extension, which started worker processes on other harness CLIs, is removed, and so are the config keys that only it read. Review is always a fresh session or subagent of the same harness.

### Upgrade notes

- The extension is removed from the repository, and every `./install.sh` run removes the launcher it installed and the plugin folders of the selected harnesses. A launcher it did not install is kept with a warning, and a dry run removes nothing. `--plugin gin-orchestrator` now fails with `gin-orchestrator was removed in gin 3.3.0`.
- Run `gin setup update --to-version 2.11 --approve` once per project. Until then a project keeps working, `gin state` warns once, and `gin setup doctor` lists one action.
- The update removes `orchestrator`, `provider_mode`, and `routing.review.independence`. It moves role names found only under `orchestrator.roles` into `routing.roles`, and it backs up and deletes `.agent-workflow/orchestrator.local.yaml`. `gin setup rollback --backup <dir>` restores it.
- Review is a fresh session of the same harness. A project that reviewed with `independence: provider` no longer gets a review on another harness.
- On Codex, OpenCode, and Copilot, `execute` implements the track in the session and notes `in_session` on the bead, and `review` stops for you to open a fresh session. Claude Code and Antigravity keep native subagents.
- `gin setup models`, `gin setup doctor --probe`, and the `--provider` option are gone.
- The documentation pages under `/orchestrator/` and `/reference/orchestrator-contract/` are gone, so a link to them returns 404.

### Changed

- The configuration schema is 2.11.
- `gin state --format json` has no `extensions` key, no `project.provider_mode`, and no `project.independence`.
- `gin routes resolve` routes every track to the main harness, and `gin reviewer` returns one route, a fresh session of the main harness.
- `gin version` and `gin setup doctor` list gin-qa as the only companion CLI.

## [3.2.0] - 2026-11-20

In team mode a member now works a lane, the tracks of one plan that share a `Lane:` line, on one branch and in one pull request, instead of a pull request per track. A team plan may also declare lanes and leave each lane's tracks to its owner, who writes them in a lane plan. The SRS export gains the document matter a customer expects, requirement types, and diagrams that draw offline. gin-qa re-runs only the manual cases that are due. Roadmap epics are sized in story points.

### Upgrade notes

- A track bead without a `Lane:` line keeps its own branch `feat/<topic>-t<N>` and its worktree `.planning/worktrees/<bead>`, so open work needs no step.
- Add `- **Lane**: <name>` to every track of a team plan. `gin team check-plan` fails a track without it.
- Update gin on each machine. No other project step is needed, and `.ginrc` stays as it is: raise it only when a project needs gin 3.2.0.
- A recorded gin-qa result now carries a `Checked:` stamp. A `passed`, `failed`, or `blocked` result that has none reads `outdated` only when a pinned requirement changed or was removed. Run the case again to record a stamp.
- `gin milestone estimate` refuses an epic that has story points. Use `gin milestone points EPIC N --reason TEXT` for it.
- On Windows, rerun `install.ps1` without `-NoModifyPath` if `gin` still runs `Get-ComputerInfo` in PowerShell. See [Troubleshooting](reference/troubleshooting.md).

### Added

- `gin team check-plan` reports a missing or invalid lane, and a lane whose tracks have different owners or repositories.
- `gin goal --lane NAME` covers one lane, including its unassigned tracks. In team mode the goal covers your tracks, leaves out tracks that wait for another lane to merge, and requires the lane's branch to be pushed.
- `gin team ready` rows carry `lane` and `branch`, and the text groups rows under their branch.
- A team plan may declare lanes under `## Lanes` and leave each lane's tracks to its owner, who writes them in a lane plan `<plan stem>.lane-<lane>.md` with no approval gate. `gin team check-plan` checks the declarations and the lane plan.
- A technical question for one lane is written `- TQ-<n> (lane <name>): <question>`. `gin record plan-approved` accepts it open when the plan declares the lane, and `gin team check-plan <lane plan>` fails until the lane plan answers it.
- `gin team deps` closes `external: <plan>#lane-<name>` placeholders once the lane's beads, its lane bead included, are closed and every track of that lane has merged.
- `gin goal` prints `No goal: lane <name> has no tracks yet; run /plan for it.` when you have a lane bead to plan and no open track.
- `gin specs export` adds a revision history, a sign-off table, a glossary, an Actors section, and a traceability matrix. Revisions come from the archived changes, the glossary from the confirmed rows of `11-GLOSSARY.md`, and the matrix lists use cases, test files, and QA cases per requirement.
- A use case is cited as `<capability>/<slug>` in the SRS. The optional `<specs>/actors.md` table describes actors, and `gin specs lint` checks it.
- A requirement block takes an optional `Type:` of `functional`, `non-functional`, or `business-rule`, a `Category:` for a non-functional one, and a `Measure:`. The SRS adds a Non-functional requirements and a Business rules section and a Type column in the matrix.
- `gin specs reqs` rows carry `type` and `category`.
- A use case may reference another capability as `<capability>/<slug>` in `Includes:` and `Extends:`, and a `Specializes:` line names a use case it is a special case of. The use case diagram draws them.
- An `Is a` column in `actors.md` names the parent of an actor. The SRS opens the Actors section with a context diagram of the capabilities and their actors.
- `gin specs lint` warns about an activity diagram that an archived technical change added and no feature change cites, so a project can delete the diagrams that earlier versions asked for.
- `gin milestone points EPIC N --reason TEXT [--stage roadmap|discuss|close]` sets the story points of a roadmap epic on the scale 1, 2, 3, 5, 8, 13, 21. `/roadmap` scores each epic, `/discuss` re-scores it, and `/milestone-close` corrects it.
- `gin milestone list` and `show` report `days_per_point`, and each milestone reports `velocity` with `committed_points`, `completed_points`, `added_points`, `say_do`, and `accuracy`. `gin milestone kickstart` stores the committed points.
- `gin-qa cases due <capability> [--change CHANGE] [--all]` lists the manual cases to run, each with the reason `todo`, `regression`, or `all`. `/gin-qa:run` walks that list.
- The `## Manual runs` section of the gin-qa guidelines takes a `- Regression: none | high | high+medium` line that picks the cases re-run whatever changed.
- `gin-qa cases renumber CAP [--dry-run]` closes the gaps in the TC-IDs of a capability and rewrites the case files, e2e specs, test markers, and e2e evidence. `gin-qa cases next-id CAP` prints the lowest free number.
- `install.ps1` removes PowerShell's `gin` alias in the user profiles, so `gin` reaches `gin.cmd`. `-NoModifyPath` leaves the profiles unchanged.

### Changed

- `gin-qa cases export` adds `checked` and `effective_result` to each case, and `gin-qa report` shows the effective result and the last recorded one when they differ.
- With a story-pointed epic, the schedule plans `ceil(points * days_per_point)` working days. `days_per_point` is measured over the 10 latest closed roadmap epics with points, else read from the roadmap's `- Days per point:` line, else 1.
- The SRS chapter groups its requirements under type headings when the capability has a non-functional requirement or a business rule. A non-functional requirement asks for no activity diagram.
- `gin specs explain` and `gin specs export` embed the vendored Mermaid library only when a file holds a diagram, so the pages draw their diagrams offline. A missing vendored file stops the export with an error that names its path.
- The SRS shows each header field of a use case on its own row.
- `gin team` calls to `bd dolt pull` and `bd dolt push` wait up to 1000 seconds and print a `bd dolt <step> (up to 1000s)...` line on stderr first. A `bd` call that times out is a clear error.
- `gin team claim`, `reassign`, `handoff`, and `takeover` act on every open track of the lane. A claim restarts the lane branch from the default branch after its pull request merged, also when the lane is checked out again after its worktree was removed or in another clone.
- `gin team pending` lists one branch per lane with an open track. `gin team deps` and `gin team complete` read the `Tracks:` line of merged pull requests.
- `gin team claim`, `ready`, `pending`, and `complete` treat a lane bead and the tracks of a lane plan as part of the lane of their lead plan; `<topic>` leaves out `.lane-<lane>`.
- With `plan_approved: area_lead`, the lead of each declared lane's area approves the plan.

### Fixed

- On Windows the knowledge reminders of `gin` name `.planning/knowledge` with forward slashes.
- On Windows the PowerShell hook and warning call `gin.cmd`, since `gin` is the alias of `Get-ComputerInfo` there.
- A timed-out `bd dolt push` in team mode keeps the local write and reports `run gin team sync`.

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
