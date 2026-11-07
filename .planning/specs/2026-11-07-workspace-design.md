# Multi-repo workspace: parent holds docs, specs, config and beads; child repos cloned from a manifest; tracks worktree one child repo

Epic: gin-workflow-workspace
Workflow: workspace
Status: draft for user review.

## Goal and scope

A brownfield modernization is rarely one repository. The legacy JSP application is one or more frozen repositories, the replacement is several Spring Boot services and several React apps that deploy independently, and the automation tests are a repository of their own. Today gin-workflow drives exactly one git repository: the project root is the current directory or `--repository`, config and specs live under it, every track worktree is a worktree of that whole repository, and hooks are installed into it (`workflow_core/cli.py:29`, `configuration.py:393`, `worktrees.py:22-41`, `hooks.py:43-59`). Run from a parent repository, a backend track gets a worktree of the parent and every other repository with it; run from a child repository, gin finds no config, no specs and no beads.

This epic makes a small parent repository the **workspace**: it holds `docs/`, `.planning/`, `.agent-workflow/config.yaml`, `.beads`, and a manifest of child repositories. Child repositories are ordinary git repositories cloned at their manifest path under the parent and gitignored there. Every `gin` command run inside a child resolves the workspace, plan tracks name the repository they change, orchestrate creates the worktree of that one child repository, hooks and checks run per child, and ship merges per repository. Engineers open only the repository or track worktree they work on; PMs and BAs open only the parent.

The shipped brownfield starter recommends `git subtree` into one monorepo (`docs/starters/brownfield.md:77-108`). That advice stays correct for a team that wants one repository; this epic adds the multi-repo layout next to it and makes it the starter's default scenario, because independent deploys per service were the requirement that decided it.

In scope: configuration and schema, workspace root resolution, `gin workspace clone|status`, hooks and `/quick` per child repository, `Repo:` on plan tracks with lint, orchestrate and execute and ship per child repository, `gin state` output, the docs set, tests, and one validation on qwikfone driven by a bead in the qwikfone Beads database.

qwikfone is the validation case: `~/qwikfone` is a parent repository with seven submodules (`backend`, `frontend`, `qwikfone-metabase`, `QFO-AT`, `QFO_Document`, `qfo-vision`, and `.beads` pointing at the `qfo-bd` repository), one directly tracked service (`postgres-mcp`), root compose files, and a parent CI job that only checks submodule pointers. The last track of this epic writes a bead in qwikfone's own Beads database that tells a Claude session in `~/qwikfone` how to turn the parent into a workspace step by step with plain git and the commands above; running that bead is how the implementation is validated. No new command and no documentation page exist for the migration.

Out of scope:
- Git submodules or subtrees as the mechanism; the manifest replaces both. Version pinning across repositories (a lock file) is not built.
- `project.packages` inside a child repository (a child that is itself a JavaScript workspace).
- Changes to gin-qa or gin-ba skills, and to gin-console beyond reading one new, additive JSON key.
- Cross-repository atomic commits: a track changes one repository.

## Requirements

### Configuration

R1. `.agent-workflow/config.yaml` accepts a `workspace.repos` list. Each entry has `path` (relative to the workspace root, required), `url` (git clone URL, required), `shape` (`frontend`, `backend`, `library`, `qa`, `beads`; required unless `frozen`), `frozen` (boolean, default `false`), `default_branch` (default `main`), and `verify.checks` with the same keys as the root `verify.checks` (`lint`, `typecheck`, `test`, `build`, `e2e`). A `beads` entry is the shared Beads repository cloned at `.beads`: `gin workspace clone` clones it, `bd` uses it, and it never gets hooks, tracks, or worktrees; at most one entry has this shape. The schema in `schemas.py` rejects unknown keys, duplicate paths, and a path that nests inside another entry's path. `project.monorepo` and `project.packages` keep their meaning for a single repository and are ignored for a workspace entry. A config without `workspace` behaves exactly as today.

R2. `/gin:setup` asks "Is this a workspace of several repositories?" when the current repository has no `workspace` key; on yes it writes an empty `workspace.repos` list, adds `.beads` and a `# workspace repos` block to `.gitignore`, and tells the lead to fill the entries by hand (no auto-detection). `gin setup doctor` reports entries whose path is missing on disk, entries with no checks, and repo paths missing from `.gitignore`.

### Resolution

R3. A new `workspace.resolve(start)` in `workflow_core` returns `(workspace_root, current_repo_entry | None)`. From `start` it takes the main checkout of the enclosing git repository (`checkout.main_checkout()`, so a linked worktree placed anywhere resolves to its repository's checkout), then walks up from that checkout's parent directory looking for a `.agent-workflow/config.yaml` whose `workspace.repos` has an entry whose resolved path equals that checkout. Found: the workspace root is the project root and the entry is the current repository. Not found: the project root is the enclosing repository as today and `current_repo_entry` is `None`. Every CLI entry point that defaults `--repository` to the current directory uses this resolution; an explicit `--repository` is taken as given.

R4. `gin state --format json` adds a top-level `workspace` object: `{"root": <path>, "current_repo": <path or null>, "repos": [{"path", "shape", "frozen", "present": <bool>, "branch": <str or null>}]}`; it is `null` when no workspace is configured. Every other key keeps its shape, so gin-console keeps parsing. `gin state` run from the parent, from a child checkout, or from a child's track worktree prints the same gates, epic and decision.

R5. `bd` is always run with the workspace root as its working directory (`tasks.py`, `team_beads.py`, and the interactive passthrough), so one Beads database serves every repository. `.beads` lives in the parent and may be a symlink as the `beads-migration` skill makes it.

### Workspace commands

R6. `gin workspace clone [PATH ...] | --all [--json]` clones each named entry (or all) at its path from its `url`, with `--depth 1` for a frozen entry, skipping entries already present, and ensures each path has a line in the parent `.gitignore`. `gin workspace status [--json]` prints one line per entry: path, present or missing, current branch, dirty or clean, frozen. Both refuse to run outside a workspace with a message naming the current directory.

### Hooks, checks and quick changes

R7. `gin hooks install` run inside a child repository installs the hooks into that child's git hooks directory (as today for any repository). `gin hooks run <hook>` fired inside a child resolves the workspace, takes the checks from that child's `workspace.repos` entry, runs them with the child checkout as working directory, and records the passing pre-push run against the child's clean tree. `gin hooks install` run in the parent installs the parent's hooks only; `gin hooks install --all-repos` run in the parent installs into every present, non-frozen child. A frozen entry never gets hooks.

R8. `/quick` and `gin quick-check` run inside a child use that child's checks and commit on the child's current feature branch or a new `quick/<slug>`, as the quick skill does today for one repository. `/quick` run in the parent applies to the parent (docs and planning files).

### Plan, orchestrate, execute, ship

R9. In a workspace, every plan track carries a `Repo: <path>` meta line after the track heading, next to `Area:` and `Owner:` in team mode. `gin record plan-approved` (and `gin team check-plan` in team mode) refuses a plan in a workspace when a track has no `Repo:`, names a path that is not an entry, names a frozen entry, or lists a `Files:` path outside its repository. `Files:` paths are workspace-relative (`services/order-api/src/...`). A change that spans two repositories is two tracks; the plan may state that the API track blocks the app track.

R10. Orchestrate, for each repository named by the plan: stops with the message `gin workspace clone <path>` when the clone is missing; creates `feat/<topic>` in the child from its `default_branch` when it does not exist; and creates each track's worktree as a worktree **of that child repository** at `<workspace>/.planning/worktrees/<track-id>` on branch `feat/<topic>-t<N>` branched from the child's `feat/<topic>`. The route manifest and the track bead record the repo path. The parent keeps its own `feat/<topic>` for the spec and plan, created at discuss as today.

R11. Execute runs inside the track worktree. The developer agent receives the track's `Files:` with the repo prefix removed and the repo's shape appendix when one exists (`references/shape-backend.md`, `shape-frontend.md`; `library` and `qa` have none). Commits and pushes go to the child repository. The review ledger and `gin review` work on the child worktree. The bead's handoff names the worktree path so a human opens exactly that directory.

R12. Ship presents one integration item per child repository that has tracks (merge the track branches into the child's `feat/<topic>`, then `feat/<topic>` into `default_branch`, locally or by PR per the existing approvals) and one for the parent (spec, plan and docs). `record shipped` takes the list of merge commits, one per repository, as evidence. Beads close as today. The `git.push` cadence applies per repository.

### Validation on qwikfone

R15. The last track of the epic creates one bead in the qwikfone Beads database (`bd -C ~/qwikfone create`, type task, title "Set up the gin workspace: submodules to workspace.repos") whose description is the step-by-step instruction for a Claude session run in `~/qwikfone`. The description holds: the precondition check (every submodule committed and pushed, active parent worktrees finished or removed, `gin --help` lists `workspace`); the manifest to write, one `workspace.repos` entry per submodule from `.gitmodules` (`backend` backend, `frontend` frontend, `qfo-vision` and `qwikfone-metabase` backend, `QFO-AT` qa, `QFO_Document` library, `.beads` beads, `default_branch` from each `branch` line, the checks from each repository's test scripts); the git steps per submodule (`git submodule deinit -f <path>`, `git rm -f <path>`, `rm -rf .git/modules/<name>`), deleting `.gitmodules`, adding the paths to `.gitignore`; `gin workspace clone --all`, `gin hooks install --all-repos`, `gin setup doctor`; what stays tracked in the parent (`postgres-mcp`, `scripts/`, the compose and nginx files, `docs/`, `.planning/`); what to retire in the same change (`.github/workflows/submodule-pointers.yml`, `scripts/check-submodule-pointers.sh`, `docs/submodule-pointers.md`); the teammate steps to put in the parent's `Readme.md` (`git pull`, `git submodule deinit --all -f`, `rm -rf .git/modules`, `gin workspace clone --all`, `gin hooks install` in their repositories); and the checks whose output the session attaches to the bead: `gin workspace status`, `gin state --format json` from the parent and from inside `backend` (same gates), `gin hooks run pre-commit` inside `backend` (that entry's checks only), and an orchestrate dry run of a two-track plan (`Repo: backend`, `Repo: frontend`) showing one worktree per child repository under `.planning/worktrees/`. The commit of the qwikfone parent and any push follow the approvals of that session.

R16. The epic is validated by running that bead in a qwikfone session with gin-workflow installed from this epic's branch. Every gap the run finds is fixed in this epic before ship, or filed as a gin-workflow bead with the reason; the qwikfone bead's attached outputs are the evidence linked from this epic's ship handoff.

### Documentation

R13. `docs/starters/brownfield.md` rewrites "Repository and workspace setup" for the workspace layout (parent, manifest, `gin workspace clone`, hooks per child) and keeps the one-repository subtree variant as a short alternative with the reasons to choose it. The scenario table gains the repositories: `legacy/shop-portal` (frozen), `services/order-api`, `services/catalog-api`, `apps/web-shop`, `apps/web-admin`, `qa` (the automation repository, so gin-qa keeps writing `qa/cases/`, `qa/e2e/` and `qa/evidence/` into it). Later sections name which directory each role runs each stage from.

R14. A new guide `docs/guides/workspace.md` describes the workflow by role (the "Workflow by role" section below is its outline). `docs/reference/config.md` documents `workspace.repos`; `docs/reference/cli.md` documents `gin workspace` and the `--all-repos` flag; `docs/concepts/state-model.md` states that the workspace root owns config, specs, plans, runtime and beads while each child owns its hooks, branches and worktrees; `docs/concepts/lifecycle.md` adds the per-repository orchestrate and ship rules; `docs/guides/claude-workflow.md` notes that a discuss or plan session worktree is a worktree of the parent. Vietnamese twins follow the repository's existing convention for the pages that have one.

## Workflow by role

Setup, once, by the tech lead: create the parent repository with `docs/` and `.planning/`; run `/gin:setup` and answer workspace; fill `workspace.repos`; run `gin workspace clone --all`; run `gin hooks install --all-repos`; in team mode, define one area per repository (`services/order-api/**` with lead `be_lead`, and so on) with `/gin:team-setup`.

Onboarding, every engineer: clone the parent; run `gin workspace clone` for the repositories they work on (a backend engineer clones one or two services, the frozen legacy only when they need to read it); run `gin hooks install` inside each; open the IDE on the child directory, never on the parent. A PM or BA clones the parent only.

PM and BA: everything happens in the parent. `/gin:roadmap`, `/gin:discuss`, `/gin:tech-doc` (reading `legacy/shop-portal` when present) and the spec review run from a parent session worktree; specs and plans are committed to the parent.

Tech lead: `/gin:plan` in the parent writes tracks with `Repo:`; `/gin:orchestrate` creates one worktree per track inside the named child; `/gin:ship` from the parent merges per repository.

Backend and frontend engineers: `gin task` or `/gin:progress` from anywhere in the workspace shows ready tracks with their worktree path; the engineer opens `<parent>/.planning/worktrees/<track-id>` in the IDE (one service or one app, nothing else), runs `/gin:execute` there, commits and pushes to that repository, requests `/gin:review` there. The spec and plan are read from the parent path the bead links; nothing in the parent is edited by a track.

QA: the `qa` entry is the automation repository; `/gin-qa:cases`, `/gin-qa:e2e` and `/gin-qa:run` write into it as they write into `qa/` today, and the tester opens that repository.

## User Stories

### US-1: Workspace setup
As the tech lead, I want to describe my repositories once in the parent config and clone them with one command, so that every teammate gets the same layout without submodule steps.

Acceptance criteria:
- A `workspace.repos` manifest with five entries validates; a duplicate or nested path is rejected with the offending path named.
- `gin workspace clone --all` on a fresh parent clone produces every entry at its path, the frozen one shallow, and each path gitignored; a second run clones nothing.
- `gin workspace status` shows present, branch and dirty state per entry.

### US-2: Work inside one repository
As a backend engineer, I want to open only my service and still see the project's gates, beads and checks, so that my IDE indexes one repository and my hooks run my service's tests only.

Acceptance criteria:
- `gin state` inside `services/order-api` and inside the parent print the same gates and epic.
- A pre-push hook fired in `services/order-api` runs that entry's `test` command in that directory and nothing from the parent or other repositories.
- `/quick` inside the child commits on a branch of the child only.

### US-3: Tracks per repository
As the tech lead, I want each track to name its repository and get a worktree of that repository only, so that a backend track never checks out the frontend.

Acceptance criteria:
- A plan with a track lacking `Repo:`, naming a frozen entry, or listing a file outside its repository is refused by `gin record plan-approved` with the track number and the reason.
- After orchestrate, `.planning/worktrees/<track-id>` is a worktree whose `git rev-parse --git-common-dir` is the child's `.git`, on `feat/<topic>-t<N>` branched from the child's `feat/<topic>`.
- Orchestrate with a missing clone stops with the exact `gin workspace clone <path>` command.

### US-4: Ship per repository
As the tech lead, I want ship to merge each touched repository separately and the parent last, so that one service can deploy without waiting for the other.

Acceptance criteria:
- Ship lists one item per repository with tracks plus the parent, each with the approval the existing rules require.
- `record shipped` accepts one merge commit per repository and marks the epic shipped only when every listed repository is merged.

### US-5: Guided workflow
As a new team member, I want one page that says which directory I open and which command I run at each stage for my role, so that I do not run `/gin:setup` in a child or plan from inside a service.

Acceptance criteria:
- `docs/guides/workspace.md` has one section per role (tech lead, PM, BA, backend engineer, frontend engineer, QA) with directory and commands per stage.
- The brownfield starter's stage sections each state the directory the stage runs from.

### US-6: Set up the qwikfone workspace from a bead
As the qwikfone tech lead, I want a bead in qwikfone that tells Claude step by step how to turn my submodules into manifest entries and plain clones with git and the workspace commands, so that the team stops bumping pointers, each engineer keeps working in the same directories, and the run proves the implementation on a real repository.

Acceptance criteria:
- The bead exists in the qwikfone Beads database with the preconditions, the manifest, the git steps, what stays, what to retire, the teammate steps, and the checks to attach, as R15 lists them.
- Running it ends with no `.gitmodules`, every former submodule path gitignored and present as a standalone clone (`git rev-parse --git-dir` inside it is its own `.git`), and `gin setup doctor` reporting no workspace finding.
- `gin state` from the parent and from inside `backend` print the same gates and epic, and `gin hooks run pre-commit` inside `backend` runs that entry's checks only.
- The orchestrate dry run creates a worktree of `backend` and one of `frontend` under the parent's `.planning/worktrees/`, each with its own `.git` common dir, and the outputs are attached to the qwikfone bead.

## Errors and compatibility

- A parent that still has a `.gitmodules` entry for a path also listed in `workspace.repos` is reported by `gin setup doctor` as "still a submodule" with the guide's step to run.
- No `workspace` key: every command behaves as today; the `workspace` key in state JSON is `null`. Existing single-repository projects need no migration.
- A child cloned outside its manifest path, or a repository not in the manifest, is not in the workspace: `gin` treats it as a standalone repository and `gin workspace status` shows the entry as missing.
- A frozen entry: no hooks, no tracks, no worktrees; `gin workspace clone` is the only command that touches it.
- Two entries resolving to the same path, or an entry path equal to `.planning`, `.agent-workflow` or `.beads`, fail validation.
- `gin hooks run` inside a child whose entry has no checks skips with the same message as an empty root check today.
- A plan that lists the same repository in two tracks is valid; the two worktrees are two worktrees of that child, which git allows on different branches.
- gin-console reads the parent as one project; the new `workspace` key is additive and may be ignored.
- gin-qa paths are unchanged because the automation repository is mounted at `qa`.

## Testing

- Unit: `workspace.resolve` from the parent, from a child checkout, from a child's linked worktree under `.planning/worktrees/`, from a repository outside the manifest, and with no `workspace` key.
- Unit: schema validation for duplicate, nested, reserved and unknown keys; `gin setup doctor` findings for missing clones and checks.
- CLI, with a temporary workspace and two local bare repositories as fixtures (one frozen): `gin workspace clone` (all, by path, shallow, idempotent, `.gitignore` lines) and `gin workspace status` text and JSON.
- CLI: `gin worktree create --repository <child>` places the worktree under the workspace `.planning/worktrees/` and branches from the child's `feat/<topic>`.
- CLI: `gin hooks run pre-push` inside a child runs the entry's commands in the child directory; `--all-repos` installs into present non-frozen children only.
- Plan parsing and lint: `Repo:` present, missing, frozen, unknown, mixed `Files:`.
- `gin setup doctor`: a path listed both in `.gitmodules` and in `workspace.repos` is reported.
- Validation (R15, R16): the qwikfone bead run in a qwikfone session, with its attached outputs as evidence; it is not an automated test of this repository.
- State: identical gate output from parent, child and track worktree; `workspace` key shape; `null` without a workspace.
- Docs: the existing documentation tests (page job, links) cover the new and rewritten pages; the brownfield starter commands are checked against the CLI help in the same way the current starter is.

## Open Technical Questions

## Assumptions

- The epic belongs to milestone `gin-workflow-96sx`, estimated at four days; `gin-workflow-process-review` depends on it and its brief uses this layout.
- The qwikfone bead changes the real `~/qwikfone` working copy; its parent commit, the pointer-CI removal and any push follow that session's approvals. Renaming `QFO-AT` to `qa` or extracting `postgres-mcp` are not in the bead.
- The bead is created by this epic's last track with `bd -C ~/qwikfone`; it is run only after `./install.sh` from this epic's branch, and it checks `gin --help` for `workspace` before starting.
- The run needs read access to the seven Qwikfoneoffice repositories from this machine; the SSH keys used by `~/qwikfone` are assumed to work.
- `QFO_Document` is a docs-only repository and gets `shape: library` with no checks; it is not frozen because it still changes.
- The automation tests are the `qa` entry so that gin-qa needs no change; a team that keeps tests elsewhere adds a `qa`-shaped entry and accepts that gin-qa writes under the parent.
- `default_branch` defaults to `main`; a child on `master` sets it in its entry.
- Workspace resolution requires the child to sit at its manifest path; a child cloned elsewhere is a standalone repository on purpose.
- Track worktrees stay under the parent's `.planning/worktrees/` (already gitignored) rather than inside each child, so one directory lists every active track and the child checkout stays clean.
- The developer and reviewer agents receive repo-relative file paths; the plan keeps workspace-relative paths so team areas and `Files:` validation keep working on one convention.
