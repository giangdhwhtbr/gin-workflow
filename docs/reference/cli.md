# CLI Reference

The plugin ships two command-line tools that skills call and that you can run yourself:

- `gin-workflow`: repository setup, lifecycle gates, rules, specs, team mode, and usage reports.
- `review-ledger.py`: the review ledger for one bead.

The local installer (`install.sh`, `install.ps1`) links `gin-workflow` into `~/.local/bin`. A marketplace install does not; see [Troubleshooting](troubleshooting.md#gin-workflow-is-not-on-path-after-a-marketplace-install).

`gin-workflow --version` prints the CLI version. An unknown or missing command prints the command list and exits 2.

Most commands accept `--repository PATH` (default: the current directory) and `--format text|json` (default `text`). JSON output is what skills parse.

## `gin-workflow setup`

```
gin-workflow setup <action> [options]
```

Configures a repository outside the lifecycle. The `setup` skill drives it one question at a time; see [Configuration](config.md).

| Action | What it does | Writes |
|---|---|---|
| `detect` | Detects project stage, shape, monorepo, stack, packages, verify commands, and code-index state | no |
| `preset` | Turns `--project-stage`, `--project-shape`, `--rigor`, `--task-tracking` (plus `--monorepo`, `--stack-intent`) into `--set` assignments | no |
| `models` | Lists models a provider CLI reports (`--provider claude\|codex\|antigravity\|opencode`) | no |
| `init` | First setup: validates and writes `.agent-workflow/config.yaml` and generated files; `--dry-run` previews; also writes the gin-workflow block in `AGENTS.md` and `@AGENTS.md` in `CLAUDE.md` (a symlinked `CLAUDE.md` is left alone), and adds a missing block on an initialized repository with `--approve` | yes |
| `configure` | Changes repository configuration (`--set key=value`) | yes |
| `refresh` | Regenerates `.agent-workflow/generated/` from the current configuration and re-renders an existing `AGENTS.md` block (never creates one) | yes |
| `update` | Proposes, then with `--approve` applies, a registered schema migration (`--to-version`) | yes |
| `doctor` | Checks configuration, main harness executable, verify commands, rule tool checks, the code index, and the `AGENTS.md` block (`ok`, `stale`, `absent`, `invalid`) | no |
| `status` | Shows whether the repository is initialized and the generated files exist | no |
| `diff` | Shows how generated configuration differs from what the current inputs would produce | no |
| `rollback` | Restores a validated backup (`--backup PATH`) | yes |
| `export-bundle` / `verify-bundle` | Writes (`--output`) or checks (`--bundle`) a portable configuration bundle | export only |
| `harness-override` | Sets (`--harness`), shows, or clears (`--clear`) a session override of the main harness | runtime only |

Other options: `--dry-run`, `--non-interactive`, `--approve`, `--reset`, `--probe`, `--harness`.

`doctor --probe` and `models` read provider health and model lists through the [orchestrator contract](orchestrator-contract.md).

Exit codes: 0 success; 2 setup, migration, bundle, or validation error; 3 a required dependency is missing (for example PyYAML).

## `gin-workflow state`

```
gin-workflow state [--workflow-id ID] [--scope-hash HASH] [--format text|json]
```

Prints the current lifecycle stage, the routing decision, the main harness, every gate (`satisfied`, `unmet`, or `waived(<reason>)`), evidence, and remedies. JSON adds the resolved `project` settings (including team mode) and the last five `recent_quick` runs.

`--workflow-id` defaults to `default-workflow`. Use one id per feature (for example the plan's slug) so gates from different features do not mix.

Exit codes: 0 when the decision is `route`; 1 when the workflow is held or blocked.

## `gin-workflow record`

```
gin-workflow record <gate> --evidence TEXT [--actor ID] [--workflow-id ID] [--epic BEAD] [--plan PATH] [--spec PATH]
```

Appends a gate event to `.agent-workflow/runtime/events.jsonl`. Gates:

| Gate | Records | Notes |
|---|---|---|
| `requirement-confirmed` | the user confirmed the design | evidence: spec path; team mode adds `--spec` |
| `plan-approved` | the user approved the plan | evidence: plan path; team mode adds `--plan` |
| `orchestration-ready` | beads, dependencies, and the worktree exist | `--epic <parent-bead>` is required to derive `implementation_complete` and `shipped` |
| `quick-completed` | a `/quick` change finished | evidence: files and verify results |
| `shipped` | a standalone bead (recorded as its own epic) was merged | an epic with children ships by closing the epic instead |

`--actor` is required unless team mode derives it from `git config user.email`. Recording the same gate with the same evidence twice reports `already_recorded`.

Exit codes: 0 recorded; 1 team mode rejected the evidence; 2 usage error (missing actor, `--epic` on another gate, `shipped` on an epic with children, or the removed `verification-passed` gate: quality checks run in the git hooks). `unblock --gate verification_passed` also exits 2.

## `gin-workflow unblock`

```
gin-workflow unblock --gate GATE --reason TEXT [--actor ID] [--follow-up BEAD]
gin-workflow unblock --clear-blocker --reason TEXT [--actor ID]
```

Waives a gate or clears a recorded blocker. A waiver is an auditable `gate.waived` event, scoped to the current source tree.

| Gate | Class | Waiver needs |
|---|---|---|
| `requirement_confirmed`, `plan_approved`, `orchestration_ready` | process | a reason |
| `review_approved` | safety | a reason and `--follow-up <bead>` |
| `implementation_complete`, `shipped` | not waivable | — |

Exit codes: 0 success; 1 invalid or non-waivable gate, or missing reason or follow-up; 2 missing actor or team-mode refusal.

## `gin-workflow quick-check`

```
gin-workflow quick-check --changed-files N [--modules M]
```

Decides whether a change may use the `/quick` path. `--modules` counts the source modules the change touches; a changed module's tests and docs count as that module, not as another one. It returns the rigor, the verify commands to run, and the review mode (`self_check` under `easy`, `independent` otherwise).

| Decision | Exit | When |
|---|---|---|
| `allowed` | 0 | within `quick.max_files` (default 5) and one module |
| `escalate` | 3 | more files or modules; use the full lifecycle |
| `refused` | 4 | `strict` rigor without a `requirement_confirmed` waiver |

## `gin-workflow rules`

```
gin-workflow rules --files PATH [PATH ...]
gin-workflow rules --list
```

`--files` prints the rule text for the given files: the `core` and `lean` packs, plus every enabled pack whose globs match, trimmed to the task budget (critical bullets are never trimmed). `--list` shows each pack with its source, tier, size, and impact counts. See [Configuration](config.md#rules).

Exit codes: 0 success; 2 invalid configuration or rule pack.

## `gin-workflow specs`

```
gin-workflow specs <command> [options]
```

Living specs for `artifacts.layout: sdd`. Every command except `template`, `reqs`, and `migrate` requires that layout.

| Command | Purpose |
|---|---|
| `new SLUG --epic BEAD [--title T]` | Create a change folder under `artifacts.changes` |
| `next-id CAP` | Next free requirement id for a capability |
| `lint [--change C] [--against REF]` | Lint the living specs, or one change's spec delta |
| `hash REQ-ID` | Print the base hash of a requirement (`<!-- base: ... -->`) |
| `template NAME` | Print a spec template |
| `renumber OLD NEW --change C [--against REF]` | Rename a requirement id in a change and its beads |
| `archive --change C` | Merge a change's spec delta into the living specs and archive the change |
| `trace --change C` | Show which tests and sources cover each requirement |
| `status --change C` | Show a change's review status, URL, and merge commit |
| `reqs [--change C]` | List requirements with section and hash |
| `migrate [--dry-run] [--force]` | Move `legacy` layout artifacts into the SDD layout |

Exit codes: 0 ok; 1 findings (lint errors, untraced requirements, archive conflicts, refused migration); 2 usage or configuration error.

## `gin-workflow team`

```
gin-workflow team <command> [options]
```

Opt-in team mode, active when the configuration has a `team:` section.

| Command | Purpose |
|---|---|
| `init [--ci] [--force]` | Write CODEOWNERS, the pull request template, and the commit-msg hook; `--ci` adds the CI workflow; `--force` overwrites files it did not generate |
| `codeowners [--check]` | Print CODEOWNERS, or check it is up to date |
| `hooks` | Install the commit-msg hook into git (exit 1 if another hook occupies it, 2 if the hook file is missing) |
| `whoami` | Show your member entry, roles, and areas (from `git config user.email`) |
| `check URL --gate GATE [--plan P] [--spec S]` | Check that a pull request of this repository changes the gate's artifact and satisfies its approvals; `--gate roadmap` checks the roadmap file without recording anything |
| `check-plan PLAN` | Check a plan's `Area:` and `Owner:` fields |
| `ready` | Ready beads in your areas |
| `claim BEAD` | Claim a bead as yourself |
| `reassign BEAD EMAIL` | Hand a track bead to another member. Allowed for the bead's current assignee or the lead of one of its areas; the new assignee must be allowed to own tracks in each area (`team.areas.<name>.roles`). Sets the assignee, appends a note, and pushes with shared Beads. A closed bead, a non-member, or a no-op is refused |
| `deps [--bead ID]` | Without `--bead`: close placeholders whose track PR merged, storing its merge commit. With `--bead`: exit 1 unless each external dependency's merge commit is in this workspace |
| `sync` | Sync Beads with `team.beads_sync.remote` |

Exit codes: 0 ok; 1 findings, rejection, or sync conflict; 2 usage, configuration, or host error.

## `gin-workflow hooks`

```
gin-workflow hooks install
gin-workflow hooks run pre-commit|pre-push
```

`install` writes marker-tagged `pre-commit` and `pre-push` shims into the active hooks directory (it honors `core.hooksPath`). It is idempotent, never overwrites a hook it did not write (`occupied`: add `exec gin-workflow hooks run <hook> "$@"` to your hook to chain it; a hook that already runs it is reported as `chained`), and does not create a missing hooks directory. It also sets a repo-local `core.sshCommand` of `ssh -o ServerAliveInterval=30` (`ssh_keepalive: set`) so the SSH connection git opens before `pre-push` survives a long test run; an existing `core.sshCommand`, `GIT_SSH` or `GIT_SSH_COMMAND` is left alone (`kept`); a write that fails is reported as `failed` and does not fail the install. `/setup` runs it once `verify.checks` is configured; `setup doctor` reports hooks that are missing or occupied.

`run` is what the shims call. `pre-commit` runs the `lint` and `typecheck` checks; `pre-push` runs `test`, plus `build` at `standard` rigor and `e2e` at `strict`, only when the pushed branch is the checked-out HEAD (tags and deletes are skipped). Package `verify.checks` run in the package directory. Commands stop at the first failure and print its output. Empty `verify.checks` exits 0 with a notice. Git's own `GIT_DIR`, `GIT_INDEX_FILE` and similar variables are removed before the commands run. `git commit/push --no-verify` is blocked by the safety hook.

Exit codes: install 0 installed or chained, 1 occupied, 2 hooks directory missing; run 0 pass, otherwise the failing command's exit code.

## `gin-workflow reviewer`

```
gin-workflow reviewer --base SHA --implementer PROVIDER [--tier low|medium|high] [--repository DIR] [--json]
```

Called by the `review` skill to pick the reviewer; you do not need to run it. Prints the review tier and the reviewer routes in order. `--tier` is the track's reasoning (default `medium`); a `low` track whose diff since `--base` changes anything but documentation (`*.md` or `docs/`, excluding `skills/`) is reviewed at `medium`. The reviewer runs on the main harness at the tier's default model: `actor_id` is `reviewer:<harness>`, or `reviewer:<harness>:session-<id>` (a fresh session) when the harness is also the implementer. `routing.review.independence: provider` adds a warning, because only gin-orchestrator can route the review to another harness. With `--json`, prints the route document `{"tier", "reason", "warnings", "routes": [{"provider", "model", "effort", "actor_id"}]}`.

Exit codes: 0 routes printed; 2 bad `--base`, an invalid config, or an unknown harness.

## `gin-workflow routes`

```
gin-workflow routes resolve --workflow-id ID --tracks FILE [--repository DIR] [--json]
```

Resolves execution routes for plan tracks: every track goes to the main harness at its tier's default model. Always prints JSON (`--json` is accepted and changes nothing): `{"workflow_id", "main_harness", "routes", "diagnostics", "warnings", "manifest"}`. On success, writes the assignment manifest to `.agent-workflow/runtime/assignments/<workflow-id>.yaml`. If any track has an unknown role, invalid reasoning, or a missing or duplicate `task_id`, or the workflow id is unsafe, writes nothing, lists every diagnostic, and exits 2.

Exit codes: 0 all routes resolved and manifest written; 2 unresolved tracks or invalid arguments.

## `gin-workflow paths`

```
gin-workflow paths [--json]
```

Prints the path of the directory holding `workflow_core` (`{"lib_dir": "..."}`) for external tools and extension launchers.

Exit codes: 0 ok.

## `gin-workflow task`

```
gin-workflow task <bd arguments>
```

The task-tracking entry point skills and agents use. With `providers.task_tracking: beads` it runs `bd` with the arguments unchanged, except that `ready` also leaves out a bead whose `external:<project>:<capability>` dependency is not shipped yet (no closed `provides:<capability>` bead in the database `external_projects.<project>` names); bd 1.0.5 reports such dependencies as resolved. `gin-workflow team ready` applies the same check. If bd cannot explain its ready list, `ready` exits 1 rather than list beads it could not check. Write `external_projects` paths as absolute paths or relative to the repo root; `~` is expanded. With `markdown` it serves the same subset in process from `.planning/tasks/` (git-ignored, local to this machine): `create`, `show`, `update`, `close`, `reopen`, `list`, `ready`, `blocked`, `dep add|remove|list`, `config get issue_prefix`, `remember`, `memories`, with `bd`-shaped `--json` output.

Exit codes: 0 ok; 1 invalid request or malformed task file (the message names the file); 127 `beads` is configured but `bd` is not installed.

## `gin-workflow usage`

```
gin-workflow usage collect --bead ID [--best-effort]
gin-workflow usage report [--bead ID | --epic ID | --sprint NAME | --since YYYY-MM-DD]
```

`collect` reads local Claude Code and Codex logs, attributes token usage to the bead and its lifecycle stages, adds quality signals, and stores the summary in the bead's `ai_usage` metadata. `report` reads those summaries back; with no scope it covers every closed bead and every bead that has a summary, and lists closed beads without one as `not collected`. `--sprint NAME` covers the epics labelled `sprint:NAME` and their tracks. Costs come from `.agent-workflow/usage-prices.yaml`; unpriced models show `-`.

Exit codes: 0 ok; 2 error. With `--best-effort`, `collect` turns any error into a `warning:` line and exits 0, so it never blocks closing a bead.

## `review-ledger.py`

```
python3 review-ledger.py <command> --bead-id BEAD [options]
```

Lives in the plugin's `scripts/` directory. Each bead's ledger is stored in `.planning/reviews/<bead-id>/` (`review.json` plus the rendered `review.md`); never edit those files by hand.

| Group | Commands |
|---|---|
| Lifecycle | `init`, `checkpoint`, `transition-requested`, `start-review`, `resync-lease`, `release-lease`, `change-scope`, `approve`, `reject`, `accept-as-is`, `record-human-decision` |
| Findings | `add-finding`, `fix-finding`, `dispute-finding`, `request-clarification`, `provide-clarification`, `propose-deferral`, `approve-deferral`, `verify-finding`, `reopen-finding`, `withdraw-finding`, `waive-finding` |
| Inspection | `status`, `validate` (`--in-history` for an earlier track on a shared branch), `render` (`--check` for drift) |
| Housekeeping | `cleanup` (`--bead-id` or `--all-closed`; also deletes the bead's `refs/gin/review/` refs) |

`change-scope` and `reject` invalidate an active approval. `approve` requires a clean worktree.

## `gin-qa`

The optional `gin-qa` plugin adds its own CLI with `gin-qa cases {plan,next-id,pin,check,export}` and `gin-qa e2e {init,plan,pin,run,check,export}`. Exit codes: 0 ok; 1 findings; 2 usage or environment error.
