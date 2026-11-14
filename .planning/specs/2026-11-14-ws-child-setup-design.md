# Workspace onboarding, frozen legacy access, and team init per child

Epic: gin-workflow-ws-child-setup
Kind: capability
Status: draft for user review.

## Goal and scope

Each role knows what to clone in a workspace, skills that read the frozen legacy say how to clone it when it is missing, setup collects the repository entries through a new `gin workspace add`, a clone installs its hooks, and `gin team init --all-repos` writes the team files into each workable child.

Problem (process review `.planning/reviews/2026-11-07-process-review/synthesis.md:69-79`): PM-1 and PM-2 (what a PM clones and where the PM works), BA-2 and BE-LEAD-12 (the frozen legacy is unreachable from a BA clone, and no skill says how to clone it), BE-LEAD-25 (setup leaves `workspace.repos` empty for hand editing), BE-LEAD-3 and FE-LEAD-2 (team files land in the parent only). Checked on master `b578d8f4`:
- `docs/guides/workspace.md:56-63`: every engineer clones the parent, runs `gin workspace clone <path>` for their repositories, and runs `gin hooks install` in each clone; "A PM or a BA clones the parent only". Nothing names the `.beads` entry (`shape: beads` holds the shared Beads database, `workspace.md:27`) or the frozen legacy for a BA. `workspace.md:67` says the PM works "from a parent session worktree", while `/gin:roadmap` creates its own `roadmap/<topic>` branch (`skills/roadmap/SKILL.md:28`).
- `skills/tech-doc/SKILL.md`, `skills/discuss/SKILL.md`, and `plugins/gin-ba/src/skills/capture/SKILL.md` have no workspace text. `skills/explain/SKILL.md:13` takes the frozen entries for `--legacy` and never checks whether they are cloned.
- `skills/setup/SKILL.md:21` writes an empty `workspace.repos` and leaves the entries to the lead; `gin workspace` has only `clone` and `status` (`workflow_core/workspace_cli.py:73-95`); `docs/starters/brownfield.md:80-117` has the lead edit the YAML by hand.
- `gin workspace clone` runs `git clone` and updates the parent `.gitignore` only (`workspace_cli.py:19-44`). `gin hooks install --all-repos` skips frozen, non-workable, and uncloned entries (`hooks.py:204-236`). `skills/ship/SKILL.md:16` runs `gin hooks status` for the parent only.
- `gin team init` writes CODEOWNERS (`/<glob> <lead>` for each `team.areas[*].paths` glob, then plan and spec folder lines), the pull request template, `.githooks/commit-msg`, and with `--ci` the CI workflow into the repository it runs in (`team_init.py:35-91`); `gin team hooks` points that repository's active hooks directory at `.githooks/commit-msg` (`team_init.py:125-137`); neither has a workspace option (`team_cli.py:17-25,78-95`). Area globs are relative to the parent (`team.py:81-82`).
- The CI template's "Specs and CODEOWNERS" step runs only when `.agent-workflow/config.yaml` exists (`templates/team/github-ci.yml`), so in a child only the commit message step runs.

In scope:
- `gin workspace add`.
- Hook installation by `gin workspace clone`.
- `--all-repos` for `gin team init` and `gin team hooks`.
- Frozen-legacy clone hints in the tech-doc, explain, discuss, and BA capture skills.
- The setup and ship skill changes.
- Docs per role.

Out of scope:
- Rule packs, checks, and shape per entry (`gin-workflow-ws-entry-rules`).
- Branch and pull request model for children (`gin-workflow-ws-branch-model`).
- Committing, pushing, or opening pull requests in children: the lead does that after `team init --all-repos`.
- A host per child.

Confirmed decisions (user, 2026-11-14): one epic with four tracks; CODEOWNERS globs are re-rooted into each child automatically; setup collects entries through a new `gin workspace add`; `gin workspace clone` installs both the verify hooks and, in team mode, the commit-msg hook.

Comments considered: 1, latest 2026-11-14T03:26:04Z
Confirmed summary (user, 2026-11-14): the goal and scope above; the `[gin note]` comment added two items, that `gin workspace clone <path>` installs the hooks of a new clone when its entry has `verify.checks`, and that in a workspace ship step 1 runs `gin hooks status --all-repos`; every process-review finding of the epic still holds on master; the epic has no dependency, and rule packs per entry stay in `gin-workflow-ws-entry-rules`.

## Requirements

R1. `gin workspace add <path> --url <url> [--shape <shape>] [--frozen] [--default-branch <branch>] [--check <name>=<command>]... [--repository <dir>] [--json]`:
- Builds one `workspace.repos` entry and validates it with the parser that `gin workspace` already uses for `workspace.repos` (path inside the workspace and not reserved, url required, shape in `frontend`, `backend`, `library`, `qa`, `beads` or empty only when frozen, `beads` only at `.beads`, check names in `lint`, `typecheck`, `test`, `build`, `e2e`).
- `--check` is repeatable; a value without `=`, an empty name, or an empty command is refused.
- Refuses a path already in `workspace.repos`.
- Appends the entry to `workspace.repos` in `.agent-workflow/config.yaml` through the existing setup configuration writer, so `gin workspace status` and `gin state` show it right away.
- Does not clone and does not touch `.gitignore`; it prints the next step `gin workspace clone <path>`.
- Errors print `error: <cause>` and exit 1, as the other `gin workspace` subcommands do; nothing is written on an error. Outside a workspace parent the cause says to run `/gin:setup` and answer `workspace`.

R2. `gin workspace clone` installs hooks in each repository it newly clones (not in one reported `present`):
- the verify hooks (`pre-commit`, `pre-push`) through the same install as `gin hooks install`, when the entry is workable and has `verify.checks`;
- in team mode, the commit-msg hook through the same install as `gin team hooks`, when the entry is workable and the clone has `.githooks/commit-msg`.
- Frozen and `beads` entries get no hooks.
- Each cloned row gains `hooks`: hook name to status (`installed`, `active`, `occupied`, `missing`). An `occupied` hook prints the line to chain it, as `gin hooks install --all-repos` does. A hook problem never changes the exit code, which still reflects only the clones.

R3. `gin team init --all-repos [--ci] [--force]`:
- Writes into the parent as `gin team init` does today, then into each workspace entry that is workable and cloned; frozen, `beads`, and uncloned entries are skipped with their reason, using the skip rules of `gin hooks install --all-repos`.
- Per child: CODEOWNERS with re-rooted area globs (R4) and no plan or spec folder lines, the pull request template, `.githooks/commit-msg`, and with `--ci` the CI workflow; file names come from `team.host`.
- A child that no area covers gets no CODEOWNERS file, and its row says so.
- A child file without the gin marker is skipped unless `--force`, as in the parent.
- Output: one row per repository (`path`, `written`, `unchanged`, `skipped`, and `reason` or `error`); the text form ends by telling the lead to commit and open a pull request in each child that has written files.
- Exit 0 when every repository was written, unchanged, or skipped; exit 1 when a write failed in a child, after the other repositories were processed; exit 2 outside a workspace or with team mode off.

R4. Re-rooting an area glob into the child at path `P` (segments compared one by one, `*` and `?` matched per segment):
- a glob whose leading segments match all segments of `P` keeps the rest: `services/order-api/src/**` and `services/*/src/**` become `/src/**` in `services/order-api`;
- a glob in which a `**` segment is reached while the segments so far match `P` covers the whole child: `services/**`, `services/order-api/**`, and `**` become `/**`;
- a glob that matches the child path exactly becomes `/**`;
- any other glob is dropped for that child.
The owners are the area's lead logins, as in the parent file.

R5. `gin team hooks --all-repos` installs the commit-msg hook in the parent and in each workable cloned child; a child without `.githooks/commit-msg` reports `missing` with `run gin team init --all-repos`. The exit code is the worst per-repository result of `gin team hooks` (`occupied` 1, `missing` 2).

R6. Ship. In a workspace, `skills/ship/SKILL.md` step 1 runs `gin hooks status --all-repos` instead of `gin hooks status`; the result still only warns and never stops ship.

R7. Setup. In `skills/setup/SKILL.md` step 6, after the user answers `workspace`, setup asks for each repository (path, url, shape, frozen, default branch, checks) and runs `gin workspace add` for each, then `gin workspace clone --all`; it no longer tells the lead to fill the entries by hand or to run `gin hooks install --all-repos`. In team mode it names `gin team init --all-repos` as the step after `/gin:team-setup`.

R8. Frozen legacy hints. In a workspace, these skills run `gin workspace status --json` and, for each entry with `frozen: true` and `present: false`, print `gin workspace clone <path>` and continue without that entry:
- `skills/tech-doc/SKILL.md`;
- `skills/explain/SKILL.md` for `--legacy`, which skips that app and names it with the command;
- `skills/discuss/SKILL.md` step 1, in one sentence (the discuss chain is 10,790 of 12,000 characters);
- `plugins/gin-ba/src/skills/capture/SKILL.md`.
When the command fails, the skill says the state of the frozen entries is unknown, gives the error, and continues.

R9. Docs.
- `docs/guides/workspace.md` and `.vi.md`:
  - onboarding per role: a developer clones the children they work on; QA clones the `qa` entry; a PM clones the parent and, when there is a `shape: beads` entry, `.beads`; a BA clones what the PM clones plus the frozen legacy entries, which tech-doc, capture, and explain read;
  - hooks come with the clone (no separate `gin hooks install` step);
  - the PM and BA section names the parent checkout as the working directory and says that `/gin:roadmap` creates its `roadmap/<topic>` branch;
  - "Setup once" uses `gin workspace add` and, in team mode, `gin team init --all-repos`, then a commit and pull request in each child.
- `docs/starters/brownfield.md`: the workspace entries through setup or `gin workspace add`, and team init for the children.
- `docs/reference/cli.md`: `gin workspace add`, the hooks of `gin workspace clone`, and `--all-repos` for `gin team init` and `gin team hooks`.

## User Stories

### US-1: The lead registers the repositories without editing YAML
As a tech lead, I want setup to ask for each repository and record it, so that the workspace manifest is valid from the start.

Acceptance criteria:
- `gin workspace add services/order-api --url <url> --shape backend --check test="mvn -q test"` adds the entry, and `gin workspace status` lists `services/order-api` as missing.
- Adding the same path again exits 1 and leaves `.agent-workflow/config.yaml` unchanged.
- An unknown shape or a `--check` without `=` exits 1 and leaves the config unchanged.

### US-2: A new member's clone has its hooks
As a developer joining the team, I want `gin workspace clone <path>` to install the hooks, so that my first commit already runs the checks and the commit message rule.

Acceptance criteria:
- Cloning an entry with `verify.checks` installs `pre-commit` and `pre-push`; cloning an entry without checks installs neither.
- In team mode, cloning a child that has `.githooks/commit-msg` activates the commit-msg hook.
- Cloning a frozen entry installs no hook.
- An occupied hook is reported with the chain line, and the command still exits 0.

### US-3: Team files in every child
As a tech lead, I want `gin team init --all-repos` to write CODEOWNERS, the pull request template, the commit-msg hook, and the CI job into each child, so that code-owner review protects every repository.

Acceptance criteria:
- In `services/order-api`, an area with paths `services/order-api/**` and lead `be_lead` gives the CODEOWNERS line `/** @<be_lead login>`.
- A frozen entry, the `.beads` entry, and an uncloned entry are listed as skipped with their reason.
- A child that no area covers gets no CODEOWNERS file and is named.
- A child CODEOWNERS without the gin marker is kept unless `--force`.

### US-4: The BA reaches the frozen legacy
As a BA, I want tech-doc, capture, and explain to tell me how to clone a frozen legacy entry I do not have, so that I can document the current system.

Acceptance criteria:
- The workspace guide tells a BA to clone the frozen legacy entries and the `.beads` entry.
- With a frozen entry not cloned, the tech-doc, explain `--legacy`, discuss, and capture skills print `gin workspace clone <path>` and continue.

### US-5: Ship reports the hooks of every child
As a lead, I want ship to warn when a child's hook is missing, stale, or occupied, so that I know which checks did not run before integration.

Acceptance criteria:
- In a workspace, ship step 1 runs `gin hooks status --all-repos` and warns on exit 1 without stopping.

## Errors and compatibility

- Single-repository projects: nothing changes; `--all-repos` outside a workspace exits 2 (`team init`, `team hooks`), and `gin workspace add` exits 1 with a hint.
- Every child uses `team.host`; a child on another host gets the file names of `team.host` (a known limit).
- In a child, the CI job checks commit messages only; its CODEOWNERS and specs step needs `.agent-workflow/config.yaml`, which children do not have.
- `gin workspace clone --json` rows gain `hooks`; existing keys are unchanged.
- `gin team init` and `gin team hooks` without `--all-repos` behave as before.

## Testing

- `tests/workflow_core/test_workspace_cli.py` and `test_hooks.py`: `workspace add` (valid entry, duplicate path, unknown shape, malformed `--check`, outside a workspace, config unchanged on error); `workspace clone` hooks (with checks, without checks, frozen, team commit-msg, occupied hook with exit 0), with local bare repositories as urls.
- `tests/workflow_core/test_team_init.py`: `team init --all-repos` per child, skipped entries, a child without an area, a non-gin file kept, the re-rooting cases of R4; `team hooks --all-repos`.
- `tests/workflow_core/test_skill_routing.py`: ship has `gin hooks status --all-repos`; setup has `gin workspace add`; tech-doc, explain, discuss, and capture have `gin workspace clone <path>`; `tests/workflow_core/test_token_budget.py` holds.
- `gin docs check` on changed pages; `tests/workflow_core/test_walkthrough_docs.py` (every cited `gin` command is in `cli.md`); full suite `python3 -m pytest -n auto`.

## Open Technical Questions
