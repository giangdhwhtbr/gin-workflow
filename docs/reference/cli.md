# CLI reference

The plugin ships two command-line tools that skills call and that you can run yourself:

- `gin-workflow`: repository setup, lifecycle gates, rules, specs, team mode, and usage reports.
- `review-ledger.py`: the review ledger for one bead.

The local installer (`install.sh`, `install.ps1`) links `gin-workflow` into `~/.local/bin`. A marketplace install does not; see [Troubleshooting](troubleshooting.md#gin-workflow-command-not-found-after-a-marketplace-install).

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
| `init` | First setup: validates and writes `.agent-workflow/config.yaml` and generated files; `--dry-run` previews. It also writes the gin-workflow block in `AGENTS.md` and `@AGENTS.md` in `CLAUDE.md` (a symlinked `CLAUDE.md` is left alone). On an initialized repository, `--approve` adds a missing block | yes |
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

Prints the current lifecycle stage, the routing decision, the main harness, every gate (`satisfied`, `unmet`, or `waived(<reason>)`), evidence, and remedies. Text format prints any active warnings (`Warning: ...`). JSON adds the main harness's [model catalog](config.md#models) as `catalog` (`null` while no harness is set), `extensions.orchestrator` (`available`, `version`, `contract`, `capabilities`, `reason`), `warnings`, the resolved `project` settings (including team mode), and the last five `recent_quick` runs.

`--workflow-id` defaults to `default-workflow`. Use one id per feature (for example the spec's topic slug) so gates from different features do not mix.

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

Exit codes: 0 recorded; 1 team mode rejected the evidence, or the event could not be written; 2 usage error. Usage errors are a missing actor, `--epic` on another gate, a process gate on a workflow that already shipped, `shipped` on anything but a standalone bead, and, in team mode, a team configuration or host error. The removed `verification-passed` gate also exits 2, because quality checks run in the git hooks; so does `unblock --gate verification_passed`.

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
| `implementation_complete`, `shipped` | not waivable | cannot be waived |

Exit codes: 0 success; 1 invalid or non-waivable gate, or missing reason or follow-up; 2 missing actor or team-mode refusal.

## `gin-workflow quick-check`

```
gin-workflow quick-check --changed-files N [--modules M]
```

Decides whether a change may use the `/quick` path. `--modules` (default 1) counts the source modules the change touches; a changed module's tests and docs count as that module, not as another one. It returns the rigor, the verify commands to run, and the review mode (`self_check` under `easy`, `independent` otherwise).

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

`--files` prints the rule text for the given files: the `core` and `lean` packs, `docs` when a Markdown file is given, plus every enabled pack whose globs match. The output is trimmed to the task budget; critical bullets are never trimmed. `--list` shows each pack with its source, tier, size, and impact counts. See [Configuration](config.md#rules).

Exit codes: 0 success; 2 invalid configuration or rule pack.

## `gin-workflow specs`

```
gin-workflow specs <command> [options]
```

Living specs for `artifacts.layout: sdd`. Every command except `template`, `migrate`, and `reqs` without `--change` requires that layout; `migrate` requires the `legacy` layout.

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
| `check URL --gate GATE [--plan P] [--spec S]` | Check a pull request of this repository against the approval policy of `GATE` (`requirement_confirmed`, `plan_approved`, `ship`, or `roadmap`). Every gate but `ship` also needs the pull request merged and changing the gate's spec, plan, or roadmap file. Nothing is recorded |
| `check-plan PLAN` | Check a plan's `Area:` and `Owner:` fields, and that the paths in each track's `Files` block stay inside its area |
| `ready` | Ready beads in your areas |
| `claim BEAD` | Claim a bead as yourself |
| `reassign BEAD EMAIL` | Hand a track bead to another member. Allowed for the bead's current assignee or the lead of one of its areas; the new assignee must be allowed to own tracks in each area (`team.areas.<name>.roles`). Sets the assignee, appends a note, and pushes with shared Beads. A closed bead, a non-member, or a no-op is refused |
| `deps [--bead ID]` | Without `--bead`: close placeholders whose track PR merged, storing its merge commit. With `--bead`: exit 1 unless each external dependency's merge commit is in this workspace |
| `sync` | Sync Beads with `team.beads_sync.remote` |

Exit codes: 0 ok; 1 findings, rejection, or sync conflict; 2 usage, configuration, or host error.

## `gin-workflow milestone`

```
gin-workflow milestone list [--all] [--json]
gin-workflow milestone show ID [--start YYYY-MM-DD] [--json]
gin-workflow milestone create TITLE --start YYYY-MM-DD --end YYYY-MM-DD
gin-workflow milestone update ID [--title TITLE] [--start YYYY-MM-DD] [--end YYYY-MM-DD]
gin-workflow milestone kickstart ID [--date YYYY-MM-DD]
gin-workflow milestone move EPIC... --to ID|none
gin-workflow milestone estimate EPIC DAYS
gin-workflow milestone close ID
```

Dated milestones over roadmap epics, stored in Beads; they need `providers.task_tracking: beads`. `list` reports each open milestone (every milestone with `--all`) with its status, period, epic progress, and warning count, plus the number of open `roadmap` epics without a parent. `show` reports the schedule of one milestone: each epic's planned start and end in working days (Monday to Friday) from `--start`, else the kick-off date, else the start date, and its warnings (`overflow`, `late`, `unestimated`, `external_blocker`). A `list` entry whose schedule cannot be computed (a dependency cycle or a malformed date) carries `error` and keeps the other entries; its status then falls back to `planned`. `--start` is a read-only preview. `--json` prints `schema: 1`; fields are defined in the gin-console contract (`gin-harness/docs/changes/gin-harness-6s4-milestones/design.md`) and only ever added to.

The write commands:

| Command | Effect |
|---|---|
| `create` | New milestone with a start and end date; prints its id. `--start` after `--end` is refused |
| `update` | Change the title or either date of an open milestone |
| `kickstart` | Set the kick-off date (default today) that the schedule starts from |
| `move` | Put epics under a milestone, or take them out with `--to none`. Refuses a non-epic, a closed target, an epic in a closed milestone, and an epic whose parent is not a milestone |
| `estimate` | Set an epic's estimate as a positive whole number of working days (480 minutes each) |
| `close` | Close a milestone; refused while it has open epics |

Each write command first checks the team role. With `team.permissions.milestone` set, the git user must hold one of its roles, otherwise the command names the roles and exits 2. With `team.beads_sync.remote`, it pulls first and stops with `pull failed, nothing written` (exit 1) when the pull fails or times out. After the write it pushes; a rejected or timed-out push prints `<change> written locally but not pushed` and exits 1. The local write stays and is never reset. In team mode, the member's email is recorded as the Beads actor. See [Team mode](../guides/team.md).

Exit codes: 0 ok, warnings included; 1 unknown id, a refused change, dependency cycle, non-Beads tracking, a failed pull or push, or a `bd` error; 2 usage error or a role that may not write milestones.

## `gin-workflow hooks`

```
gin-workflow hooks install
gin-workflow hooks run pre-commit|pre-push
```

`install` writes marker-tagged `pre-commit` and `pre-push` shims into the active hooks directory (it honors `core.hooksPath`). It is idempotent and does not create a missing hooks directory. It never overwrites a hook it did not write (`occupied`: add `exec gin-workflow hooks run <hook> "$@"` to your hook to chain it); a hook that already runs it is reported as `chained`. It also sets a repo-local `core.sshCommand` of `ssh -o ServerAliveInterval=30` (`ssh_keepalive: set`), so the SSH connection git opens before `pre-push` survives a long test run. An existing `core.sshCommand`, `GIT_SSH` or `GIT_SSH_COMMAND` is left alone (`kept`); a write that fails is reported as `failed` and does not fail the install. `/setup` runs it once `verify.checks` is configured; `setup doctor` reports hooks that are missing or occupied.

`run` is what the shims call. `pre-commit` runs the `lint` and `typecheck` checks. `pre-push` runs `test` under `easy` rigor, `test` and `build` under `standard`, and `test`, `build`, and `e2e` under `strict`. It runs them only when the pushed branch is the checked-out HEAD (tags and deletes are skipped). Package `verify.checks` run in the package directory. Commands stop at the first failure and print its output. Empty `verify.checks` exits 0 with a notice. Git's own `GIT_DIR`, `GIT_INDEX_FILE` and similar variables are removed before the commands run. `git commit/push --no-verify` is blocked by the safety hook.

Exit codes: install 0 installed or chained, 1 occupied, 2 hooks directory missing; run 0 pass, otherwise the failing command's exit code.

## `gin-workflow reviewer`

```
gin-workflow reviewer --base SHA --implementer PROVIDER --model MODEL [--effort EFFORT] [--repository DIR] [--json]
```

Called by the `review` skill to pick the reviewer; you do not need to run it. `--model` and `--effort` are the implementer's final route, including any escalation, in the implementer's [catalog](config.md#models); a value outside that catalog exits 2. A diff since `--base` that changes anything but documentation (`*.md` or `docs/`, excluding `skills/`) raises the weakest model of a multi-model catalog to the next one. `reason` then reads `non-docs files changed`.

Without gin-orchestrator the reviewer runs on the main harness. It keeps the route when the main harness is the implementer; otherwise it gets the route mapped by rank from the implementer's catalog ([rank mapping](../orchestrator/routing.md#rank-mapping)). `actor_id` is `reviewer:<harness>`, or `reviewer:<harness>:session-<id>` (a fresh session) when the harness is also the implementer. `routing.review.independence: provider` adds a warning, because only gin-orchestrator can route the review to another harness. Always prints the route document `{"model", "effort", "reason", "warnings", "routes": [{"provider", "model", "effort", "actor_id"}]}`; `--json` changes nothing. `--tier` was removed in 2.9 and exits 2 as an unknown option.

Exit codes: 0 routes printed; 2 bad `--base`, an invalid config, an unknown harness, a model or effort outside the catalog, an unknown option, or an empty route list from gin-orchestrator.

## `gin-workflow routes`

```
gin-workflow routes resolve --workflow-id ID --tracks FILE [--repository DIR] [--json]
gin-workflow routes dispatch --workflow-id ID --task-id ID [--escalate REASON] [--repository DIR] [--json]
```

Both actions always print JSON; `--json` is accepted and changes nothing.

`resolve` resolves execution routes for plan tracks. `FILE` is a JSON list of tracks, each `{"task_id", "provider_role", "model", "effort"}`, where `model` and `effort` come from the main harness's [catalog](config.md#models) and `effort` is left out or `null` when the catalog lists no efforts. Without gin-orchestrator every track goes to the main harness at its model and effort. It prints `{"workflow_id", "main_harness", "routes", "diagnostics", "warnings", "manifest"}`. On success, it writes the assignment manifest to `.agent-workflow/runtime/assignments/<workflow-id>.yaml`: per track, `requested` (role, model, effort), `resolved`, `fallback`, and `escalations`.

`resolve` writes nothing, lists every diagnostic, and exits 2 when the workflow id is unsafe or any track has one of these problems:

- an unknown role;
- a missing or duplicate `task_id`;
- a model or effort outside the catalog, or an effort for a catalog without efforts;
- a `reasoning` field and no `model`; `model` and `effort` replace `reasoning`.

`dispatch` prints the current route of one track from the manifest, `{"task_id", "provider", "model", "effort", "escalated"}`, and appends a `route.dispatched` event with that route to `.agent-workflow/runtime/events.jsonl` in the main checkout. `--escalate REASON` first moves the track one step up its provider's catalog: the next model at the same effort, or the next effort at the strongest model. It writes the new route and an `escalations` entry (`from`, `to`, `reason`) to the manifest. At the strongest model and highest effort it prints `{"status": "human_decision_required", ...}`, changes nothing, and exits 2.

Exit codes: 0 all routes resolved and manifest written, or a route printed; 2 unresolved tracks, a missing or invalid manifest, a track missing from it or without a resolved route, an invalid configuration, an unknown provider, or a manifest route outside its provider's catalog on `--escalate`, nothing left to escalate to, or invalid arguments.

## `gin-workflow notify`

```
gin-workflow notify --event EVENT [--repository DIR] MESSAGE
```

Sends a one-way notification message to Telegram. It is a no-op unless `notifications.telegram` is true. The four supported events are `needs_input`, `run_finished`, `worker_finished`, and `worker_failed`. Credentials are read from the `TELEGRAM_BOT_TOKEN` and `TELEGRAM_CHAT_ID` environment variables. If delivery fails or credentials are missing, a warning is printed to stderr and the command exits 0.

Exit codes: 0 message sent, disabled, or delivery warning; 2 invalid arguments or unknown event.

## `gin-workflow paths`

```
gin-workflow paths [--json]
```

Prints the path of the directory holding `workflow_core` (`{"lib_dir": "..."}`) for external tools and extension launchers. It always prints JSON; `--json` changes nothing.

Exit codes: 0 ok.

## `gin-workflow goal`

```
gin-workflow goal --workflow-id ID [--repository PATH]
```

Prints a Claude Code `/goal` for the epic recorded by `orchestration-ready`. The goal lists the open tracks in dependency order, leaving out every track labelled `human-gate` and every open track that depends on one. Its turn limit is 6 per track, at most 30. A track run on a fallback from its route counts as run on its routed provider. A standalone bead is its own single track. When no open track is left for the agent, it prints a `No goal:` line instead, which names the human-gate tracks when any wait.

Exit codes: 0 ok; 1 no epic recorded for the workflow, or the task backend is unavailable.

## `gin-workflow worktree`

```
gin-workflow worktree create [--repository DIR] TRACK_ID BRANCH [BASE_REF]
gin-workflow worktree cleanup [--repository DIR] TRACK_ID
```

Creates or removes the git worktree for one track at `.planning/worktrees/<track-id>` in the repository's top level. `TRACK_ID` must match `[A-Za-z0-9._-]+` and resolve inside `.planning/worktrees`. `create` makes the new branch `BRANCH` from `BASE_REF` (default: the current branch, or `HEAD` when detached) and refuses an existing directory. `cleanup` runs `git worktree remove` and succeeds without doing anything when the directory does not exist.

Exit codes: 0 created, removed, or nothing to remove; 1 invalid track id, existing directory, or git failure (message on stderr); 2 invalid arguments.

## `gin-workflow task`

```
gin-workflow task <bd arguments>
```

The task-tracking entry point skills and agents use. With `providers.task_tracking: beads` it runs `bd` with the arguments unchanged, with one exception. `ready` also leaves out a bead of type `milestone` and a bead whose `external:<project>:<capability>` dependency is not shipped yet: no closed `provides:<capability>` bead exists in the database `external_projects.<project>` names. bd 1.0.5 reports such dependencies as resolved. `gin-workflow team ready` applies the same check. If bd cannot explain its ready list, `ready` exits 1 rather than list beads it could not check. Write `external_projects` paths as absolute paths or relative to the repo root, which is the main checkout when you run from a linked worktree; `~` is expanded. With `markdown` it serves the same subset in process from `.planning/tasks/` (git-ignored, local to this machine): `create`, `show`, `update`, `close`, `reopen`, `list`, `ready`, `blocked`, `dep add|remove|list`, `config get issue_prefix`, `remember`, `memories`, with `bd`-shaped `--json` output.

Exit codes: 0 ok; 1 invalid configuration, invalid request, or malformed task file (the message names the file); 127 `beads` is configured but `bd` is not installed. Other `bd` commands exit with `bd`'s own code.

## `gin-workflow usage`

```
gin-workflow usage collect --bead ID [--best-effort]
gin-workflow usage report [--bead ID | --epic ID | --sprint NAME | --since YYYY-MM-DD]
```

`collect` reads local Claude Code and Codex logs, attributes token usage to the bead and its lifecycle stages, adds quality signals, and stores the summary in the bead's `ai_usage` metadata. `report` reads those summaries back; with no scope it covers every closed bead and every bead that has a summary, and lists closed beads without one as `not collected`. `--sprint NAME` covers the epics labelled `sprint:NAME` and their tracks. Costs come from `.agent-workflow/usage-prices.yaml`; unpriced models show `-`. `report` prints totals per model, then per role and model (`role main <model>`, `role subagent <model>`). A Claude Code record whose log line has `"isSidechain": true` counts as `subagent`; every other record, including every Codex record, counts as `main`.

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
| Inspection | `status`, `validate` (`--in-history` for an earlier track on a shared branch, or after a squash merge, where an earlier track also passes when an approved track with a later review base started from its approved source and itself passes `--in-history`), `render` (`--check` for drift) |
| Housekeeping | `cleanup` (`--bead-id` or `--all-closed`; also deletes the bead's `refs/gin/review/` refs) |

`change-scope` and `reject` invalidate an active approval. `approve` refuses when the working source tree differs from the reviewed checkpoint.

## Delegation to gin-orchestrator

When `provider_mode: multi` is set, `gin-orchestrator` is available on `PATH`, and the extension lists the required capability, `gin-workflow` delegates commands:

| `gin-workflow` command | Delegates to | Capability |
|---|---|---|
| `gin-workflow routes resolve` | `gin-orchestrator routes resolve` | `routes` |
| `gin-workflow reviewer` | `gin-orchestrator reviewer` | `reviewer` |
| `gin-workflow setup doctor --probe` | `gin-orchestrator doctor` | `doctor` |
| `gin-workflow setup models` | `gin-orchestrator models` | `models` |

In single-harness mode (`provider_mode: single`), `gin-workflow` resolves for the main harness without a warning. In `provider_mode: multi`, when `gin-orchestrator` is missing or mismatched, or when the orchestrator fails, it resolves for the main harness and emits a warning. `setup models` needs no `provider_mode: multi`: it lists models whenever an available orchestrator has the `models` capability, and an empty list otherwise.

## `gin-qa`

The optional `gin-qa` plugin adds its own CLI with `gin-qa cases {plan,next-id,pin,check,export}` and `gin-qa e2e {init,plan,pin,run,check,export}`. Exit codes: 0 ok; 1 findings; 2 usage or environment error.
