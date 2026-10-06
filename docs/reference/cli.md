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
| `preset` | Turns `--project-stage`, `--project-shape`, `--rigor`, `--provider-mode` (plus `--monorepo`, `--stack-intent`) into `--set` assignments | no |
| `models` | Lists models a provider CLI reports (`--provider claude\|codex\|antigravity`) | no |
| `init` | First setup: validates and writes `.agent-workflow/config.yaml`, `providers.local.yaml`, and generated files; `--dry-run` previews | yes |
| `configure` | Changes portable (`--set key=value`) or local (`--provider-set key=value`) settings | yes |
| `refresh` | Regenerates `.agent-workflow/generated/` from the current configuration | yes |
| `update` | Proposes, then with `--approve` applies, a registered schema migration (`--to-version`) | yes |
| `doctor` | Checks configuration, providers, verify commands, rule tool checks, and the code index; `--probe` also probes model health | no |
| `status` | Shows whether the repository is initialized and the generated files exist | no |
| `diff` | Shows how generated configuration differs from what the current inputs would produce | no |
| `rollback` | Restores a validated backup (`--backup PATH`) | yes |
| `export-bundle` / `verify-bundle` | Writes (`--output`) or checks (`--bundle`) a portable configuration bundle | export only |
| `harness-override` | Sets (`--harness`), shows, or clears (`--clear`) a session override of the main harness | runtime only |

Other options: `--dry-run`, `--non-interactive`, `--approve`, `--reset`, `--probe`, `--harness`.

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
gin-workflow record <gate> --evidence TEXT [--actor ID] [--workflow-id ID] [--epic BEAD] [--plan PATH]
```

Appends a gate event to `.agent-workflow/runtime/events.jsonl`. Gates:

| Gate | Records | Notes |
|---|---|---|
| `requirement-confirmed` | the user confirmed the design | evidence: spec path |
| `plan-approved` | the user approved the plan | evidence: plan path; team mode adds `--plan` |
| `orchestration-ready` | beads, dependencies, and the worktree exist | `--epic <parent-bead>` is required to derive `implementation_complete` and `shipped` |
| `verification-passed` | every verification check has evidence | evidence: commands and results |
| `quick-completed` | a `/quick` change finished | evidence: files and verify results |
| `shipped` | a standalone bead (recorded as its own epic) was merged | an epic with children ships by closing the epic instead |

`--actor` is required unless team mode derives it from `git config user.email`. Recording the same gate with the same evidence twice reports `already_recorded`.

Exit codes: 0 recorded; 1 team mode rejected the evidence; 2 usage error (missing actor, `--epic` on another gate, `shipped` on an epic with children).

## `gin-workflow unblock`

```
gin-workflow unblock --gate GATE --reason TEXT [--actor ID] [--follow-up BEAD]
gin-workflow unblock --clear-blocker --reason TEXT [--actor ID]
```

Waives a gate or clears a recorded blocker. A waiver is an auditable `gate.waived` event, scoped to the current source tree.

| Gate | Class | Waiver needs |
|---|---|---|
| `requirement_confirmed`, `plan_approved`, `orchestration_ready` | process | a reason |
| `verification_passed`, `review_approved` | safety | a reason and `--follow-up <bead>` |
| `implementation_complete`, `shipped` | not waivable | — |

Exit codes: 0 success; 1 invalid or non-waivable gate, or missing reason or follow-up; 2 missing actor or team-mode refusal.

## `gin-workflow quick-check`

```
gin-workflow quick-check --changed-files N [--modules M]
```

Decides whether a change may use the `/quick` path. It returns the rigor, the verify commands to run, and the review mode (`self_check` under `easy`, `independent` otherwise).

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
| `check URL --gate GATE [--plan P]` | Check that a pull request satisfies a gate's approvals |
| `check-plan PLAN` | Check a plan's `Area:` and `Owner:` fields |
| `ready` | Ready beads in your areas |
| `claim BEAD` | Claim a bead as yourself |
| `deps` | Resolve cross-team placeholder dependencies |
| `sync` | Sync Beads with `team.beads_sync.remote` |

Exit codes: 0 ok; 1 findings, rejection, or sync conflict; 2 usage, configuration, or host error.

## `gin-workflow usage`

```
gin-workflow usage collect --bead ID [--best-effort]
gin-workflow usage report [--bead ID | --epic ID | --since YYYY-MM-DD]
```

`collect` reads local Claude Code and Codex logs, attributes token usage to the bead and its lifecycle stages, adds quality signals, and stores the summary in the bead's `ai_usage` metadata. `report` reads those summaries back; with no scope it covers every closed bead and every bead that has a summary, and lists closed beads without one as `not collected`. Costs come from `.agent-workflow/usage-prices.yaml`; unpriced models show `-`.

Exit codes: 0 ok; 2 error. With `--best-effort`, `collect` turns any error into a `warning:` line and exits 0, so it never blocks closing a bead.

## `gin-workflow describe`

```
gin-workflow describe ID [--out PATH] [--format text|json]
```

Writes a self-contained HTML file presenting an interactive visualization of the bead or epic. The page contains a fixed two-column template: an SVG graph on the left and full Beads details, metadata, and comments on the right.

- **Graph scope**: The root bead, its ancestor parent chain up to the top, all descendant children down the parent-child hierarchy, and any bugs discovered from them (`discovered-from`, one hop). `blocks` dependencies between nodes in the graph are drawn as arrows; blockers outside the graph are listed in the bead's detail pane under `Blocked By`.
- **Default output path**: `.agent-workflow/runtime/describe/<ID>.html`.
- **Limits**: Maximum 300 nodes. If a graph exceeds 300 nodes, `describe` halts with exit code 3.

Exit codes: 0 ok; 2 error (unknown bead or `bd` failure); 3 graph too large.

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
| Housekeeping | `cleanup` (`--bead-id` or `--all-closed`) |

`change-scope` and `reject` invalidate an active approval. `approve` requires a clean worktree.

## `gin-qa`

The optional `gin-qa` plugin adds its own CLI with `gin-qa cases {plan,next-id,pin,check,export}` and `gin-qa e2e {init,plan,pin,run,check,export}`. Exit codes: 0 ok; 1 findings; 2 usage or environment error.
