# Changelog

This page lists what changed in each release of gin-workflow and its add-ons (gin-qa, gin-orchestrator, gin-ba), newest first. Releases before 3.1.0 are on the [GitHub releases page](https://github.com/giangdhwhtbr/gin-workflow/releases).

## [3.1.0] - 2026-11-15

gin, gin-qa, gin-orchestrator, and gin-ba now share one version. This release adds hosts for team mode (Gitea and AWS CodeCommit), a leaner lifecycle, milestone retros and closing, QA and BA work inside a workspace, and a version pin for projects.

### Upgrade notes

- Run `gin setup update --approve` once in each project. It migrates the configuration to schema 2.10, which drops the `notifications` key, and writes `.ginrc` with the installed version.
- `.ginrc` pins the lowest gin version a project needs, and gin 3.1.0 refuses to run in a project whose pin it does not meet. A gin older than 3.1.0 does not read the file, so update every machine. A new project gets it from `gin setup init`; run `gin version` to see the state.
- Update gin for every team member before the project uses a 3.1 team setting: `team.host: gitea` or `codecommit`, the approval policies `{all: [...], any: [...]}` and `host`, or a `requirement_confirmed` map per epic kind. Older versions reject those configurations.
- gin, gin-qa, gin-orchestrator, and gin-ba are all 3.1.0. `gin --version` prints `gin 3.1.0` instead of `gin 3.0`, and `gin-qa --version` prints `gin-qa 3.1.0` instead of `gin-qa 0.11`. Reinstall each add-on you use with `./install.sh --plugin <name>`; `gin setup doctor` reports one whose version differs from gin's.
- Reinstall with the installer to get a session-start check in the Claude Code hooks file. It tells the agent at the start of a session when gin is older than `.ginrc` needs.
- `verify.run_at` defaults to `push` under `easy` and `standard` rigor: a track runs only the tests of what it changed, and the full suite runs once before the push. Keep the old behavior with `gin setup configure --set verify.run_at=track --approve`.
- In team mode, `/quick` started on the base branch now pushes `quick/<slug>` and opens a pull request. It used to commit locally and stop.
- A milestone without a `lanes` value or an `AI capacity:` number now counts only the `team.members` who hold a building role as lanes, so forecasts can move. Set `gin milestone update ID --lanes N` to fix the number.

### Added

- `gin version` shows the installed gin, the pin in `.ginrc`, whether they are compatible, and the versions of gin-qa and gin-orchestrator when it finds them.
- `team.host` accepts `gitea`, through the `gt` CLI on a self-hosted instance, and `codecommit`, through the `aws` CLI; members on CodeCommit set `aws_identity`, the IAM user or `<role>/<session>` that gin matches against an approver.
- Approval policies accept `{all: [...], any: [...]}`: each `all` role and one `any` role must approve, and a role whose only holder is the author is skipped with a note.
- A gate policy can be `host`, which leaves approvals to the host's branch protection while gin keeps its repository, merge, and plan checks.
- `requirement_confirmed` takes a policy per epic kind (`capability`, `technical`, `parity`), and an epic's kind comes from its `kind:<kind>` label or the `Kind:` line of its spec.
- `gin specs template technical-design.md` prints the design of a technical epic, which needs no user stories, and a parity change names the confirmed legacy asset folders it matches with `Parity with:`.
- `gin record plan-approved` refuses while a technical question (`TQ-<n>`) in the design doc has no `Decision:` line.
- `gin team pending` lists the open pull requests of spec, plan, track, ship, and quick branches, and what each one still needs under its approval policy.
- `gin team complete EPIC` closes an epic once every track pull request and each `feat/<topic>` pull request has merged.
- `gin team claim` creates the track worktree on `feat/<topic>-t<N>` in the repository the track names, and `gin team takeover` and `gin team deps` work in a workspace child.
- `gin record shipped --evidence` can be repeated, one pull request per repository, for an epic that changes several repositories.
- `gin team ready --exclude-label LABEL` leaves out beads with a label, and the command lists a prep task that only its parent epic blocks.
- `/gin:allocate` proposes prep tasks (`capture`, `mockup`, `spike`, `question`, `other`) under roadmap epics before discuss, for one epic or a whole milestone.
- `/gin:retro` records one member's milestone retro as a `[gin retro]` comment on the milestone bead.
- `/gin:milestone-close` closes a milestone in one run: it summarizes delivered and open epics, moves the open ones to the next milestone, and compares team-level metrics with the previous close.
- `gin milestone update` takes `--away MEMBER:FROM[..TO]` for days off and `--integration YYYY-MM-DD` for an integration date, and `gin milestone show` marks `oversized` epics.
- `gin milestone show` warns `spec_due`, and `spec_not_ready` after the kick-off, for an epic whose spec is not confirmed within 5 working days of the milestone start.
- `gin usage report` marks a total that is incomplete with `partial` and lists the reasons in `partial_reasons`.
- `/gin:progress` shows the milestone, the pending approvals, the spec state, and the QA state, and keeps the tracks of one area (`--area`) or repository (`--repo`) when you ask.
- `/gin:roadmap` writes a manager view of the roadmap: a summary table, an outcome and a demo per milestone, and a legacy coverage table.
- `/gin:roadmap` plans capability epics with one track per repository, and an integration epic for each capability that a milestone lists under `Integrates:`.
- `/gin:tech-doc` also writes `12-DATABASE.md` for a datastore and `13-CAPABILITIES.md`, a capability catalog that `/gin:roadmap` reads.
- The rule packs `java`, `spring`, and `jvm-templates` cover Java 8, Spring, and JSP or Velocity templates, and they are detected from `pom.xml`, `build.gradle`, or `build.gradle.kts`.
- `workspace.repos.<path>.rules.packs` adds rule packs inside one repository, and `gin rules`, `gin setup doctor`, and `gin evidence run` use the entry's own packs and checks from a child.
- `gin workspace add PATH --url URL` records a repository in `workspace.repos`, `gin workspace clone` installs the verify hooks of a new clone, and `gin team init --all-repos` writes CODEOWNERS into each cloned child.
- A plan track can carry `Reads: <paths>`, the repositories it reads and never edits, and `gin workspace status --json` rows carry `checkout` and `commit`.
- `gin commit <path>... -m <message>` commits only the named paths, moves off `main` or `master` onto a new branch first, and never pushes.
- `gin specs assets list CAP` lists the dated asset folders of a capability, and `gin specs assets confirm` records `Confirmed by:` and, with `--agreed-with`, `Agreed with:`.
- Use cases are optional files under `<capability>/use-cases/` from `gin specs template use-case.md`; `gin specs lint` checks them and the SRS export prints them.
- `gin specs trace` scans the cloned children of a workspace and lists the ones it skipped.
- `gin specs lint` accepts `MODIFIED` and `REMOVED` on a requirement that another open change adds, and `gin specs archive` then asks you to archive the adding change first.
- `gin specs explain NAME --legacy APP` writes an explain page for the legacy code of a capability in a frozen workspace app, under the new `artifacts.explain` folder.
- gin-qa runs from the `shape: qa` workspace child, the QA home, and from its track worktrees; a single repository sets `qa.dir` instead.
- gin-qa cases take an optional `Legacy:` field that names, as relative paths, the legacy screens and recorded payloads a parity test checks.
- `gin-qa cases bug` files a bug for a case of any type, and it exits 2 and names the epics when a case belongs to several, so you pick one with `--discovered-from`.
- `run.json` of `gin-qa e2e run` and `gin-qa tests run` records `checkouts`, the branch and commit of each cloned workspace repository.
- The `qa` provider role and the `/gin:qa-track` skill route a QA track to the matching gin-qa skill, and `ship` and the reviewer read gin-qa coverage when gin-qa is installed.
- `/gin-ba:mockup` uses the cloned frontend child of a workspace as the existing UI, skips a one-to-one copy of a legacy screen, and records who agreed.
- Epics take `[gin question]` and `[gin answer]` comments between a worker and the people who own the spec, and the BA posts `[gin accept]` once the QA report is in.
- Every stage posts what it learned as a `[gin learn]` comment on the bead, and `ship` writes the knowledge records before it offers the options.
- The review ledger has `withdraw-deferral` for a proposed deferral and `require-human-decision`, which asks a human to decide an important deferral.
- The QA guide has ship checklists per kind of pull request and CI snippets that publish test evidence.

### Changed

- `verify.run_at` (`track`, `push`, or `host`) decides where the full suite runs, and under `host` the pre-push hook and `gin evidence run` run nothing because the host CI owns the tests.
- The review, ship, and worktree steps follow `project.review_ledger`, `project.review`, and `project.worktree`; with the ledger off, a reviewer reports a verdict and findings and no ledger is written.
- `ship` merges track branches into `feat/<topic>` outside team mode and workspaces, and under `run_at: push` it runs the full suite once on the feature branch before the merge.
- `gin milestone` places an unestimated open epic for the median estimate of its group instead of giving it no days.
- `/gin:quick` in team mode records a `[gin quick]` comment on an epic or the active milestone, and the pull request lists the QA cases that cover the change.
- `plan_approved: area_lead` accepts the lead of another area when the plan author is the only holder of an area's lead role.
- `gin setup doctor` checks a workspace child on its own, and from the parent it proposes the rule packs each entry could add.
- On Claude Code and Antigravity, tracks and reviews always run in native subagents, and an Antigravity subagent runs the model of the agy session.
- A track whose worker fails with `invalid_result_contract` but left new commits in the worktree is checked as if it were done.
- The brownfield starter shows a workspace of repositories with tracks per repository, a BA and a lead on `requirement_confirmed`, and the contract decided as technical questions in plan.

### Fixed

- `gin team check --gate ship` and `gin record shipped` no longer refuse every pull request of a workspace child: they match the pull request to its repository.
- `gin workspace clone` clones a remote that has no branches yet, and new `workspace.repos` paths are written inside the `.gitignore` block of the workspace.
- `gin setup refresh` adds a missing local-file entry to `.agent-workflow/.gitignore`.
- `gin task close` reads the review ledger of a workspace child track from the parent that holds its worktree.
- `gin task ready` holds a bead for an unshipped `external:` dependency only when the dependency type blocks (`blocks`, `conditional-blocks`, or `waits-for`).
- `gin goal` prints a condition that the Stop hook can check from Beads, the gates, and the ledgers, and it names the ledger clause only when the ledger is on.
- `gin-orchestrator dispatch` finds the repository that owns a track worktree, and it normalizes the status words and commit objects of a worker result before it checks the contract.
- Reinstalling gin refreshes an installed gin-ba add-on.

### Removed

- The event messages feature is removed, together with the command that sent them and the `notifications` configuration key; configuration schema 2.10 drops the key.
