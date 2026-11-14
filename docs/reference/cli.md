# CLI reference

The plugin ships two command-line tools that skills call and that you can run yourself:

- `gin`: repository setup, lifecycle gates, rules, specs, team mode, and usage reports.
- `review-ledger.py`: the review ledger for one bead.

The local installer (`install.sh`, `install.ps1`) links `gin` into `~/.local/bin`. A marketplace install does not; see [Troubleshooting](troubleshooting.md#gin-command-not-found-after-a-marketplace-install).

`gin --version` prints the CLI version. An unknown or missing command prints the command list and exits 2.

Most commands accept `--repository PATH` (default: the current directory) and `--format text|json` (default `text`). JSON output is what skills parse.

## `gin setup`

```
gin setup <action> [options]
```

Configures a repository outside the lifecycle. The `setup` skill drives it one question at a time; see [Configuration](config.md). `gin setup --help` prints one line per action.

| Action | What it does | Writes |
|---|---|---|
| `detect` | Detects project stage, shape, monorepo, stack, packages, verify commands, and code-index state | no |
| `preset` | Turns `--project-stage`, `--project-shape`, `--rigor`, `--task-tracking` (plus `--monorepo`, `--workspace`, `--stack-intent`) into `--set` assignments | no |
| `models` | Lists models a provider CLI reports (`--provider claude\|codex\|antigravity\|opencode\|copilot`) | no |
| `init` | First setup: validates and writes `.agent-workflow/config.yaml` and generated files; `--dry-run` previews. It also writes `.agent-workflow/executables.local.yaml` and the `gin` block in `AGENTS.md` and `@AGENTS.md` in `CLAUDE.md` (a symlinked `CLAUDE.md` is left alone). On an initialized repository, `--approve` adds a missing block | yes |
| `configure` | Changes repository configuration (`--set key=value`) | yes |
| `refresh` | Regenerates `.agent-workflow/generated/` from the current configuration, rewrites `executables.local.yaml`, and re-renders an existing `AGENTS.md` block (never creates one) | yes |
| `update` | Proposes, then with `--approve` applies, a registered schema migration (`--to-version`) | yes |
| `doctor` | Checks configuration, main harness executable, verify commands, rule tool checks, external CLI paths, the code index, and the `AGENTS.md` block (`ok`, `stale`, `absent`, `invalid`) | no |
| `status` | Shows whether the repository is initialized and the generated files exist | no |
| `diff` | Shows how generated configuration differs from what the current inputs would produce | no |
| `rollback` | Restores a validated backup (`--backup PATH`) | yes |
| `export-bundle` / `verify-bundle` | Writes (`--output`) or checks (`--bundle`) a portable configuration bundle | export only |
| `harness-override` | Sets (`--harness`), shows, or clears (`--clear`) a session override of the main harness | runtime only |

`--workspace` (on `preset` and `init`) writes an empty `workspace.repos` list and, on `init`, the parent `.gitignore` entries.

Other options: `--dry-run`, `--non-interactive`, `--approve`, `--reset`, `--probe`, `--harness`.

`doctor --probe` and `models` read provider health and model lists through the [orchestrator contract](orchestrator-contract.md).

Exit codes: 0 success; 2 setup, migration, bundle, or validation error; 3 a required dependency is missing (for example PyYAML).

## `gin state`

```
gin state [--workflow-id ID] [--scope-hash HASH] [--format text|json]
```

Prints the current lifecycle stage, the routing decision, the main harness, every gate (`satisfied`, `unmet`, `waived(<reason>)`, or `unknown`), evidence, and remedies. Text format prints any active warnings (`Warning: ...`). JSON adds the main harness's [model catalog](config.md#models) as `catalog` (`null` while no harness is set), `extensions.orchestrator` (`available`, `version`, `contract`, `capabilities`, `reason`), `warnings`, the resolved `project` settings (including team mode), the last five `recent_quick` runs, `epic` (the epic recorded at `orchestration-ready` for the workflow id, or `null`), and `review_waivers` (`task_id`, `reason`, `actor`) for tracks closed with `task close --waive-review`.

A gate reads `unknown` when `state` cannot read the task tracker or the event log. The decision is then `hold`. `warnings` and `remedies` carry the cause: `tracker unavailable: <cause>` or `event log unreadable: <error>; waivers not applied`.

`--workflow-id` defaults to `default-workflow`. Use one id per feature (for example the spec's topic slug) so gates from different features do not mix.

Exit codes: 0 when the decision is `route`; 1 when the workflow is held or blocked.

## `gin record`

```
gin record <gate> --evidence TEXT [--actor ID] [--workflow-id ID] [--epic BEAD] [--plan PATH] [--spec PATH]
```

Appends a gate event to `.agent-workflow/runtime/events.jsonl`. Gates:

| Gate | Records | Notes |
|---|---|---|
| `requirement-confirmed` | the user confirmed the design | evidence: spec path; team mode adds `--spec`. With `artifacts.layout: legacy` and an existing `.md` evidence file, the spec is linted first (`specs lint --spec`); a failing spec exits 1 with the errors and records nothing. With `--workflow-id <epic>` it refuses a spec `Kind:` that differs from the epic's `kind:` label, and in team mode it uses the policy of that kind |
| `plan-approved` | the user approved the plan | evidence: plan path; team mode adds `--plan`. Refused (exit 1, nothing recorded) while the workflow's design doc has a `- TQ-<n>:` line under `## Open Technical Questions` without an indented `Decision:` line. The design doc is the legacy spec in `.planning/specs/` with `Epic: <id>` or `Workflow: <id>`, or the SDD change's `03-design.md`. Exit 2 when two legacy specs name the id, when the SDD change is ambiguous, or when the design doc cannot be read as UTF-8 |
| `orchestration-ready` | beads, dependencies, and the worktree exist | `--epic <parent-bead>` is required to derive `implementation_complete` and `shipped`, and the epic bead is set to `in_progress`, claimed as `task update --claim` would when it has no assignee (an existing assignee is kept); the markdown tasks backend leaves the epic unchanged; when `bd` fails the gate stays recorded with a `warning`; an epic that is a [prep task](../concepts/lifecycle.md#prep-tasks) is refused with `orchestration-ready refused: <id> is a prep task, not implementation work` |
| `quick-completed` | a `/quick` change finished | evidence: files and verify results |
| `shipped` | a standalone bead (recorded as its own epic) was merged | an epic with children ships by closing the epic instead. Team mode with a `ship` policy: evidence is the merged PR URL, approved on its head commit by a listed role other than the author; the local HEAD is not compared |

`--actor` is required unless team mode derives it from `git config user.email`. Recording the same gate with the same evidence twice reports `already_recorded`. Recording `shipped` for a workflow that already has a `shipped` event also reports `already_recorded`. The checks below and the write happen under one lock on the event store. In team mode with Beads, `record` also writes the gate's PR proof into the epic bead's `gates` metadata (see `docs/concepts/state-model.md`); when that write fails, the gate stays recorded, the command exits 0, and it prints `warning: ...` to stderr (`warning` in JSON).

Exit codes: 0 recorded; 1 team mode rejected the evidence, or the event could not be written; 2 usage error. Usage errors are a missing actor, `--epic` on another gate, a process gate on a workflow that already shipped, `shipped` on anything but a standalone bead, `shipped` while the task tracker cannot be read (the message names the cause), and, in team mode, `shipped` evidence that is not a PR URL, or a team configuration or host error. The removed `verification-passed` gate also exits 2, because quality checks run in the git hooks; so does `unblock --gate verification_passed`.

## `gin unblock`

```
gin unblock --gate GATE --reason TEXT [--actor ID] [--follow-up BEAD]
gin unblock --clear-blocker --reason TEXT [--actor ID]
```

Waives a gate or clears a recorded blocker. A waiver is an auditable `gate.waived` event, scoped to the current source tree.

| Gate | Class | Waiver needs |
|---|---|---|
| `requirement_confirmed`, `plan_approved`, `orchestration_ready` | process | a reason |
| `review_approved` | safety | a reason and `--follow-up <bead>` |
| `implementation_complete`, `shipped` | not waivable | cannot be waived |

Exit codes: 0 success; 1 invalid or non-waivable gate, or missing reason or follow-up; 2 missing actor or team-mode refusal.

## `gin quick-check`

```
gin quick-check --changed-files N [--modules M]
```

Decides whether a change may use the `/quick` path. `--modules` (default 1) counts the source modules the change touches; a changed module's tests and docs count as that module, not as another one. It returns the rigor, the verify commands to run, and the review mode (`self_check` under `easy`, `independent` otherwise).

| Decision | Exit | When |
|---|---|---|
| `allowed` | 0 | within `quick.max_files` (default 5) and one module |
| `escalate` | 3 | more files or modules; use the full lifecycle |
| `refused` | 4 | `strict` rigor without a `requirement_confirmed` waiver |

## `gin rules`

```
gin rules --files PATH [PATH ...]
gin rules --list
```

`--files` prints the rule text for the given files: the `core` and `lean` packs, `docs` when a Markdown file is given, plus every enabled pack whose globs match. The output is trimmed to the task budget; critical bullets are never trimmed. `--list` shows each pack with its source, tier, size, and impact counts. See [Configuration](config.md#rules).

Exit codes: 0 success; 2 invalid configuration or rule pack.

## `gin specs`

```
gin specs <command> [options]
```

Living specs for `artifacts.layout: sdd`. Every command except `template`, `migrate`, `reqs` without `--change`, and `lint --spec` requires that layout; `migrate` and `lint --spec` require the `legacy` layout.

| Command | Purpose |
|---|---|
| `new SLUG --epic BEAD [--title T]` | Create a change folder under `artifacts.changes` |
| `next-id CAP` | Next free requirement id for a capability |
| `lint [--change C] [--against REF] [--spec FILE]` | Lint the living specs, or one change: its spec delta, and each repository path its files cite in backticks that exists on disk but git neither tracks nor ignores, and each dated asset folder `<specs>/<cap>/assets/<YYYY-MM-DD>/` without a `description.md`, each `<specs>/<cap>/diagrams/*-activity.md` without a mermaid block starting with `flowchart` or `graph` and `*-state.md` without one starting with `stateDiagram`, each `<specs>/<cap>/use-cases/*.md` without a title, an `Actor:` line, a `Requirements:` line with a REQ-ID that is in a living spec or `ADDED` or `MODIFIED` in an open change (only `REMOVED` is reported), or a numbered `## Main flow`, and with `--change` each capability with an `ADDED` or `MODIFIED` block but no `*-activity.md`; `--spec` lints a legacy-layout design spec (every `### US-<n>:` story needs `Acceptance criteria:` with a bullet, no `{{`, `TBD`, or `TODO` outside code); per [epic kind](../concepts/lifecycle.md#epic-kinds), `Kind:` must be `capability`, `technical`, or `parity` (reported with file and line); `--spec` needs no user stories for `technical` and `parity`; a `parity` spec needs a `Parity with:` line that lists backticked asset folders (paths relative to the repository root), each existing, with `Kind: legacy` and a `Confirmed:` date; `--change` accepts a `technical` change with no `02-spec-delta.md` (see [SDD](../guides/sdd.md#epic-kinds)); `--spec` and `--change` also check `## Open Technical Questions` (`- TQ-<n>: <question>` lines, unique ids, at most one non-empty indented `Decision:` line right below each); an open question is not an error; it also reports a `Confirmed:` value that is neither `no` nor a date and any change to a dated asset folder confirmed on the base (`--against REF`, else the merge-base with `main` or `master`; without one it warns and skips that check), and `--against` works without `--change` for this check |
| `assets add CAP [FILES...] [--date D] [--legacy] [--new-capability]` | Copy files into the dated asset folder `<specs>/CAP/assets/D/` (default today), or its `legacy/` folder with `--legacy` (images only), and write `description.md` when missing; `--new-capability` allows a capability without a folder; exit 2 on refusal (a confirmed folder, an existing file, a non-image with `--legacy`) |
| `assets confirm CAP --date D [--agreed-with TEXT]` | Set `Confirmed:` to today in that folder's `description.md`, add `Confirmed by:` with the git `user.email`, and add `Agreed with: TEXT` when given; exit 2 when the file is missing, already confirmed, or git `user.email` is unset |
| `assets list CAP` | List the dated asset folders of CAP, oldest first: JSON rows `{"date", "kind", "confirmed", "path", "screens"}` (`confirmed` is the date or `null`; `screens` are the `### ` headings under `## As-is behaviour`); with the legacy layout it lists nothing; exit 2 for an unknown capability |
| `hash REQ-ID` | Print the base hash of a requirement (`<!-- base: ... -->`); a requirement another open change adds gets that block's hash, and the JSON `change` names that change |
| `template NAME` | Print a spec template (`technical-design.md` is the legacy-layout design of a technical epic: `Kind: technical`, `## Goal and scope`, `## Approach`, `## Risks and rollback`, `## Testing`, `## Open Technical Questions`) |
| `renumber OLD NEW --change C [--against REF]` | Rename a requirement id in a change and its beads |
| `archive --change C` | Merge a change's spec delta into the living specs and archive the change; a new capability's `spec.md` links each file in its `diagrams/` under `## Diagrams` and in its `use-cases/` under `## Use Cases` |
| `trace --change C` | Show which tests and sources cover each requirement; in a workspace it also scans every cloned child that is neither frozen nor the Beads repository, names each source by its workspace path, and lists children it could not scan under `skipped` |
| `status --change C` | Show a change's review status, URL, and merge commit |
| `reqs [--change C]` | List requirements with section, hash, and the epic of the change that holds them; the JSON also carries `root` (the project root) and `qa_root` (the `shape: qa` workspace child, or the worktree of it you run from; null without one) |
| `export (CAP \| --all) [--out FILE]` | Write the living specs of one capability, or of every capability, into one printable SRS HTML file with each chapter's purpose, use cases, diagrams, requirements, and assets (default `srs-CAP.html` or `srs.html` at the repository root, overwritten), from the templates `srs.html` and `srs-capability.html`; images are embedded, diagrams load Mermaid from jsDelivr; a local image not found, outside the repository, or not an image is listed and exits 1 |
| `explain NAME [--narrative FILE] [--out FILE] [--legacy APP]` | Write one interactive HTML page for a capability, or for an active change found as `--change` finds it (default `<artifacts.explain>/NAME/NAME.html`, overwritten; `artifacts.explain` defaults to `.agent-workflow/runtime/explain`), from the template `explain.html`: tabs for the overview (the `--narrative` Markdown file first), the requirements with a search box, the stories, the diagrams, and the dated asset folders with an image viewer and each `mockup/index.html` in a sandboxed frame; a requirement's `Source:` path under `assets/<date>/` opens that file on the page; `--legacy APP` names a frozen workspace entry by its last path component, takes a capability only, writes `<artifacts.explain>/legacy/APP/NAME/NAME.html`, and sets the kind line to `legacy capability (APP)`; a narrative, `--out`, or `artifacts.explain` outside the repository, `--legacy` with a change, without a workspace, or with an app that is not frozen exits 2; an image or a mockup not embedded is listed and exits 1 |
| `migrate [--dry-run] [--force]` | Move `legacy` layout artifacts into the SDD layout |

Exit codes: 0 ok; 1 findings (lint errors, untraced requirements, archive conflicts, refused migration, images an export could not find, images or mockups an explain page could not embed); 2 usage or configuration error.

## `gin docs`

```
gin docs check <file>... [--template NAME] [--repository PATH] [--format text|json]
```

Checks Markdown pages against the mechanical rules of the `docs` rule pack. Fenced code blocks and inline code are not checked. The command reads no workflow configuration.

| Rule | Reported when |
|---|---|
| `dash` | A line has an em or en dash |
| `bold-label item` | A list item opens with bold text |
| `emoji` | A line has an emoji |
| `numbered heading` | A heading starts with a digit |
| `placeholder` | A line has `{{...}}`, or `TBD` or `TODO` as a word |
| `dead link` | A relative link points to a file that does not exist |
| `missing section` | With `--template`, a `##` heading of the template without a placeholder is not in the page |

Each finding prints as `<file>:<line>: <rule>`, or `<file>: missing section: <heading>`. `--template` resolves like `specs template`, so a project override in `.agent-workflow/templates/` applies.

Exit codes: 0 no findings; 1 findings; 2 a file does not exist or is not UTF-8, or the template is unknown.

## `gin team`

```
gin team <command> [options]
```

Opt-in team mode, active when the configuration has a `team:` section.

| Command | Purpose |
|---|---|
| `init [--ci] [--force]` | Write CODEOWNERS, the pull request template, and the commit-msg hook; `--ci` adds the CI workflow; `--force` overwrites files it did not generate. On `codecommit` it writes only the commit-msg hook, and `--ci` exits 2 because CodeCommit has no CI workflow file |
| `codeowners [--check]` | Print CODEOWNERS, or check it is up to date. Exits 2 on `codecommit`, which has no CODEOWNERS file |
| `hooks` | Install the commit-msg hook into git (exit 1 if another hook occupies it, 2 if the hook file is missing) |
| `whoami` | Show your member entry, roles, areas, and whether you hold a technical role (an area `lead` or a role in an area's `roles`), from `git config user.email` |
| `check URL --gate GATE [--plan P] [--spec S] [--workflow-id EPIC]` | Check a pull request of this repository against the approval policy of `GATE` (`requirement_confirmed`, `plan_approved`, `ship`, or `roadmap`). With `--workflow-id`, `requirement_confirmed` applies the policy of the epic's kind and the JSON carries `kind` ([per-kind policies](../guides/team.md#policy-per-epic-kind)). Every gate but `ship` also needs the pull request merged and changing the gate's spec, plan, or roadmap file. Nothing is recorded |
| `check-plan PLAN` | Check a plan's `Area:` and `Owner:` fields, that the paths in each track's `Files` block stay inside its area, and that no path is listed by two tracks |
| `pending [--workflow-id EPIC \| --milestone ID]` | List the open pull requests of the remote `spec/*` and `plan/*` branches, of `feat/<topic>-t<N>` for each open track bead, and of `feat/<topic>` for each open or in-progress epic when `team.approvals.ship` has roles. `<topic>` is the name of the plan file on the `Plan:` line of a track bead, without its date. The ship branch counts closed track beads too. `spec/` is `requirement_confirmed`, `plan/` is `plan_approved`, `feat/<topic>` is `ship`, and a track pull request has no gate. The epic of a spec or plan row is the value of the `Epic:` or `Workflow:` line in its file, read from the branch; other rows take the track bead's parent. Each JSON row under `pending` carries `gate`, `branch`, `url`, `author`, `epic`, `approvals`, `missing`, and `notes`. `missing` holds the reasons `check` gives under the policy of the epic's kind, without the merge and local HEAD checks; a plan's areas are read from its branch. A track row lists its approvers only. It exits 2 when the host CLI is missing or fails before any lookup succeeds, when `git ls-remote` fails, or when Beads cannot be read. A later failed lookup gives only its row `error`. Text shows one line per pull request, gate rows first, then track rows. `--workflow-id` keeps the rows of one epic, `--milestone` those of its child epics |
| `ready [--exclude-label LABEL]` | Ready beads in your areas, and beads held by another member whose claim lease has expired (`expired_claim`). A bead labelled `released` is listed for every member (`released: true`). `--exclude-label` leaves out beads with the label; repeat it or separate labels with commas. A [prep task](../concepts/lifecycle.md#prep-tasks) that `bd` blocks only through its parent epic is listed too, so the BA sees prep work of epics that wait on other epics. Each group, ready first and then expired claims, is sorted by priority and then id; this order applies to every team project |
| `claim BEAD` | Claim a bead as yourself, or renew your claim. Refused when you hold no role allowed in one of its `area:` labels (unless the bead is labelled `released` by `handoff --release`), or another member's lease (`claim.expires_at`, `team.claim_ttl_hours` ahead) has not expired; an expired lease is taken over with a note. Without `team.beads_sync.remote` the claim is advisory: only this machine sees it |
| `reassign BEAD EMAIL` | Hand a track bead to another member. Allowed for the bead's current assignee or the lead of one of its areas; the new assignee must be allowed to own tracks in each area (`team.areas.<name>.roles`). Sets the assignee, appends a note, writes a fresh claim lease for the new assignee, and pushes with shared Beads. A closed bead, a non-member, or a no-op is refused |
| `handoff BEAD [EMAIL] [--release] [--worktree PATH]` | Hand a track over in one step. Give exactly one of `EMAIL` or `--release`. It refuses a track worktree (`.planning/worktrees/<bead>`, or `--worktree`) with uncommitted or untracked files, and lists them. It also refuses a `--worktree` that is not a Git worktree. These checks, and the authority and target checks, run before any push. It then pushes the track branch to `origin`. A broken `review.json` is refused after the branch push and before the review ref push, leaving the branch on `origin` and the bead unchanged. Otherwise it pushes the review ref when the ledger exists. It records `handoff` metadata (`branch`, `from`, `to`, `at`) only after the branch is on `origin`. With `EMAIL` it reassigns the bead as `reassign` does. With `--release` the bead loses its assignee and lease, returns to status `open`, and gets the label `released`. A rejected push is reported plainly |
| `takeover BEAD [--branch NAME]` | Take a handed-off track on your machine. Run it in the main checkout only. It fetches the branch recorded by `gin team handoff` (or `--branch`), checks it out at `.planning/worktrees/<bead>` (`gin worktree checkout`), fetches the review ref when present, then claims the bead. A branch name that starts with `-` or fails `git check-ref-format` is refused. Only a review ref under `refs/gin/review/` is fetched. If a step fails after the worktree exists, it reports `worktree left at <path>; remove it with gin worktree cleanup <bead>`. A bead labelled `released` can be claimed by any member, and the label is removed on claim |
| `deps [--bead ID]` | Without `--bead`: close placeholders whose track PR merged, storing its merge commit. With `--bead`: exit 1 unless each external dependency's merge commit is in this workspace |
| `sync` | Sync Beads with `team.beads_sync.remote` |

Exit codes: 0 ok; 1 findings, rejection, or sync conflict; 2 usage, configuration, or host error.

`gin setup doctor` checks the host CLI and its login for every host (`host_cli`, with the fix `gh auth login`, `glab auth login`, `gt auth login --host <instance URL>`, or `aws configure` or `aws sso login`). On `gitea` it also checks that `gt` is Gitea's CLI (`gitea_cli`), that it is logged in to the instance of `origin` (`host_login`), and that the instance runs Gitea 28 or later (`server_version`). On `codecommit` it adds a note that CodeCommit does not enforce code owners and an approval rule template is needed ([guide](../guides/team.md#aws-codecommit)).

## `gin milestone`

```
gin milestone list [--all] [--json]
gin milestone show ID [--start YYYY-MM-DD] [--json]
gin milestone create TITLE --start YYYY-MM-DD --end YYYY-MM-DD [--lanes N]
gin milestone update ID [--title TITLE] [--start YYYY-MM-DD] [--end YYYY-MM-DD] [--lanes N] [--away MEMBER:FROM[..TO]|MEMBER:none]... [--integration YYYY-MM-DD|none]
gin milestone kickstart ID [--date YYYY-MM-DD]
gin milestone move EPIC... --to ID|none
gin milestone estimate EPIC DAYS
gin milestone close ID --reason TEXT
```

Dated milestones over roadmap epics, stored in Beads; they need `providers.task_tracking: beads`. `list` reports each open milestone (every milestone with `--all`) with its status, period, epic progress, and warning count, plus the number of open `roadmap` epics without a parent. It ends with a forecast line when any `roadmap` epic is open: when every open epic finishes against the roadmap's `Deadline:`, with the spare or overflow working days, the default lanes, and the open and unestimated counts. Open milestones are scheduled one after another in `end` order, each on its own lanes, then every open roadmap epic outside an open milestone on the default lanes. `show` reports the schedule of one milestone: each epic's planned start and end in working days (Monday to Friday) from `--start`, else the kick-off date, else the start date, and its warnings (`overflow`, `late`, `unestimated`, `external_blocker`, `spec_not_ready`). Schedules are lane-bound: a lane runs one epic at a time, so with one lane estimated epics run in sequence and independent epics overlap only with two or more lanes. A milestone's lanes come from its `lanes` metadata, else the whole number that starts the `AI capacity:` line of the roadmap file, else the number of `team.members` holding a building role (`dev`, `be_*`, `fe_*`, `*_dev`, `*_lead`), else 1. When the lanes come from those members, lane n belongs to the n-th of them and the schedule skips their `away` days on that lane. Lanes from `--lanes` or `AI capacity:` ignore `away`. The `list` forecast applies `away` to a milestone the same way. `show` lists `away` and `integration`. `after_integration` marks an open epic planned to end after the milestone's integration date. `open_bugs` counts open bug beads discovered from the epic. `oversized` marks an open epic whose planned days exceed the milestone's working days, with the excess in `days`. Malformed `away` or `integration` metadata is ignored with a warning on stderr. A milestone planned before lanes existed now shows later dates and may gain `overflow` warnings at the default of 1 lane; set `--lanes` or the `AI capacity:` number to match the team. Each epic row of `show` carries `spec_confirmed`: whether a `requirement.confirmed` event for the epic exists in `.agent-workflow/runtime/events.jsonl` of the main checkout. An open epic without one in a `scheduled` or `active` milestone gets `spec_not_ready`. An unreadable event log prints `warning: event log unreadable: ...; spec readiness unknown` on stderr, sets `spec_confirmed` to null, and the command still exits 0. A `list` entry whose schedule cannot be computed (a dependency cycle or a malformed date) carries `error` and keeps the other entries; its status then falls back to `planned`. `--start` is a read-only preview. `--json` prints `schema: 1` with the additive keys `lanes` (per milestone and on `show`), `away` and `integration` (on `show`), `spec_confirmed` (per epic on `show`), and `forecast` (`deadline`, `lanes`, `start`, `finish`, `overflow_days`, `open_epics`, `unestimated`, `error`; null without an open roadmap epic); fields are defined in the gin-console contract (`gin-harness/docs/changes/gin-harness-6s4-milestones/design.md`) and only ever added to.

Each epic row of `show` carries `estimate_days`, `remaining_days`, and `assumed_days`. An in-progress epic is placed for its remaining days. With child tracks that is the estimate times the share of open tracks, rounded up. Without tracks it is the estimate minus the working days since the epic started. It is at least 1. An open epic without an estimate is placed for the median estimate of its group, rounded up, or 1 day, shown in `assumed_days` with the `unestimated` warning. The group is the estimated, not-closed epics of the milestone, or of the unassigned pool in the forecast. `remaining_days` equals the estimate for an open epic and is null when unestimated. A closed unestimated epic takes no days. `late` means an open epic of an active milestone whose planned end is before today. `spec_due` marks an open epic without a confirmed spec in a planned milestone that starts within 5 working days, today included; `spec_not_ready` replaces it once the milestone is kicked off. A spec counts as confirmed when the epic bead's `gates` metadata holds `requirement_confirmed` or the local event log has the event. `show` also reports `deadline` from the roadmap's `Deadline:` line, null without one.

The write commands:

| Command | Effect |
|---|---|
| `create` | New milestone with a start and end date; prints its id. `--start` after `--end` is refused; `--lanes N` stores the lane count |
| `update` | Change the title, either date, or the lanes of an open milestone; `--away` records a member's days off (repeatable), `MEMBER:none` removes them; `--integration` stores or clears the integration date |
| `kickstart` | Set the kick-off date (default today) that the schedule starts from |
| `move` | Put epics under a milestone, or take them out with `--to none`. Refuses a non-epic, a closed target, an epic in a closed milestone, and an epic whose parent is not a milestone. Appends `{from, to, at, actor}` to each epic's `milestone_moves` metadata (a failed append prints a warning and keeps the move) |
| `estimate` | Set an epic's estimate as a positive whole number of working days (480 minutes each) |
| `close` | Close a milestone with a reason (`bd close --reason`); refused while it has open epics; `--reason` missing is a usage error |

Each write command first checks the team role. With `team.permissions.milestone` set, the git user must hold one of its roles, otherwise the command names the roles and exits 2. With `team.beads_sync.remote`, it pulls first and stops with `pull failed, nothing written` (exit 1) when the pull fails or times out. After the write it pushes; a rejected or timed-out push prints `<change> written locally but not pushed` and exits 1. The local write stays and is never reset. In team mode, the member's email is recorded as the Beads actor. See [Team mode](../guides/team.md).

Exit codes: 0 ok, warnings included; 1 unknown id, a refused change, a `--lanes` that is not a positive whole number, dependency cycle, non-Beads tracking, a failed pull or push, or a `bd` error; 2 usage error or a role that may not write milestones.

A malformed `Deadline:` line or a dependency cycle among open epics is reported in `forecast.error`; `list` still exits 0.

## `gin hooks`

```
gin hooks install [--all-repos]
gin hooks status [--all-repos]
gin hooks run pre-commit|pre-push
```

`install` writes marker-tagged `pre-commit` and `pre-push` shims into the active hooks directory (it honors `core.hooksPath`, so a husky repository's hooks live in `.husky`). It is idempotent and does not create a missing hooks directory. It never overwrites a hook it did not write (`occupied`: add `exec gin hooks run <hook> "$@"` to your hook to chain it); a hook that already runs it is reported as `chained`. It also sets a repo-local `core.sshCommand` of `ssh -o ServerAliveInterval=30` (`ssh_keepalive: set`), so the SSH connection git opens before `pre-push` survives a long test run. An existing `core.sshCommand`, `GIT_SSH` or `GIT_SSH_COMMAND` is left alone (`kept`); a write that fails is reported as `failed` and does not fail the install. `/setup` runs it once `verify.checks` is configured; `setup doctor` reports hooks that are missing or occupied.

`status` prints `{"hooks": {...}, "verify_commands": [...], "ok": ...}`: each hook's state (`ok`, `missing`, `occupied`) and the configured check names, including `<package>:<name>` for packages. It exits 1 when a hook is not `ok` or no verify command is configured; `ship` warns on that and continues.

`--all-repos` runs `install` or `status` in every cloned repository of a [workspace](#gin-workspace), skipping `frozen` and `beads` entries and entries that are not cloned; it works from anywhere inside the workspace. `install --all-repos` prints `<path>: <hook>: <state>` per hook, keeps an occupied hook and names the file to chain `exec gin hooks run <hook> "$@"` into, and reports a repository whose hooks directory does not exist; its exit code is the worst single-repository result (2 when a hooks directory is missing, else 1 when any hook is occupied, else 0). `status --all-repos` prints `{"repos": {"<path>": <status report>, ...}, "ok": ...}` for the repositories that have `verify.checks` and exits 1 when any of them is not `ok`; a child without checks has nothing for the hooks to run and is left out. `setup doctor` lists the same missing, stale, or occupied hooks as `workspace:` actions for each cloned child that has `verify.checks`, and reports a child whose `.git` cannot be read.

`run` is what the shims call. `pre-commit` runs the `lint` and `typecheck` checks. `pre-push` runs `test` under `easy` rigor, `test` and `build` under `standard`, and `test`, `build`, and `e2e` under `strict`. It runs them only when the pushed branch is the checked-out HEAD (tags and deletes are skipped). Package `verify.checks` run in the package directory. Commands stop at the first failure and print its output. Empty `verify.checks` exits 0 with a notice. Git's own `GIT_DIR`, `GIT_INDEX_FILE` and similar variables are removed before the commands run. `git commit/push --no-verify` is blocked by the safety hook. A passing `pre-push` on a tree with no tracked changes is recorded for [`evidence check`](#gin-evidence). When such a record for the pushed tree already covers every command the hook would run, `pre-push` prints a notice naming the record time and exits 0 without running them again. A record file it cannot read is reported and the commands run.

Exit codes: install 0 installed or chained, 1 occupied, 2 hooks directory missing (with `--all-repos`, the worst repository); `--all-repos` 1 outside a workspace; run 0 pass, otherwise the failing command's exit code.

## `gin evidence`

```
gin evidence run [--repository DIR]
gin evidence check [--commit SHA] [--repository DIR] [--json]
```

When every `pre-push` verify command passes on a tree with no tracked changes, `hooks run pre-push` and `evidence run` append a `checks.passed` event (workflow id `checks`; payload `tree`, `hook`, `commands`) to `.agent-workflow/runtime/events.jsonl` in the main checkout. A record that cannot be written prints a warning and never changes the exit code. `pre-commit` records nothing, because it runs no `test`.

`run` runs the `pre-push` verify commands on the checked-out commit. The `review` skill runs it after `checkpoint`, because the branch is pushed only after review. It refuses with exit 2 when a tracked file differs from `HEAD`. Like the hook, it exits 0 without rerunning when a record for the same tree already covers the commands.

`check` finds the newest record for the tree of `--commit`, or of `HEAD` when no tracked file differs from it, whose commands include `test` or `<package>:test`. It prints the record, or why none matches; `--json` prints `{"record": {"tree", "hook", "commands", "recorded_at"} | null, "reason"}`. The reviewer reruns the tests only when it exits 1.

Exit codes: `run` 0 pass, 2 tracked changes, otherwise the failing command's exit code; `check` 0 a record matches, 1 none does.

## `gin reviewer`

```
gin reviewer --base SHA --implementer PROVIDER --model MODEL [--effort EFFORT] [--repository DIR] [--json]
```

Called by the `review` skill to pick the reviewer; you do not need to run it. `--model` and `--effort` are the implementer's final route, including any escalation, in the implementer's [catalog](config.md#models); a value outside that catalog exits 2. A diff since `--base` that changes anything but documentation (`*.md` or `docs/`, excluding `skills/`) raises the weakest model of a multi-model catalog to the next one. `reason` then reads `non-docs files changed`.

Without gin-orchestrator the reviewer runs on the main harness. It keeps the route when the main harness is the implementer; otherwise it gets the route mapped by rank from the implementer's catalog ([rank mapping](../orchestrator/routing.md#rank-mapping)). `actor_id` is `reviewer:<harness>`, or `reviewer:<harness>:session-<id>` (a fresh session) when the harness is also the implementer. `routing.review.independence: provider` adds a warning, because only gin-orchestrator can route the review to another harness. Always prints the route document `{"model", "effort", "reason", "warnings", "routes": [{"provider", "model", "effort", "actor_id"}]}`; `--json` changes nothing. `--tier` was removed in 2.9 and exits 2 as an unknown option.

Exit codes: 0 routes printed; 2 bad `--base`, an invalid config, an unknown harness, a model or effort outside the catalog, an unknown option, or an empty route list from gin-orchestrator.

## `gin routes`

```
gin routes resolve --workflow-id ID --tracks FILE [--repository DIR] [--json]
gin routes dispatch --workflow-id ID --task-id ID [--escalate REASON] [--repository DIR] [--json]
```

Both actions always print JSON; `--json` is accepted and changes nothing.

`resolve` resolves execution routes for plan tracks. `FILE` is a JSON list of tracks, each `{"task_id", "provider_role", "model", "effort"}`, where `model` and `effort` come from the main harness's [catalog](config.md#models) and `effort` is left out or `null` when the catalog lists no efforts. Without gin-orchestrator every track goes to the main harness at its model and effort. It prints `{"workflow_id", "main_harness", "routes", "diagnostics", "warnings", "manifest"}`. `warnings` names the strongest model when two or more tracks all route to the last model of a catalog with two or more models; the exit code does not change. On success, it writes the assignment manifest to `.agent-workflow/runtime/assignments/<workflow-id>.yaml`: per track, `requested` (role, model, effort), `resolved`, `fallback`, and `escalations`.

`resolve` writes nothing, lists every diagnostic, and exits 2 when the workflow id is unsafe or any track has one of these problems:

- an unknown role;
- a missing or duplicate `task_id`;
- a model or effort outside the catalog, or an effort for a catalog without efforts;
- a `reasoning` field and no `model`; `model` and `effort` replace `reasoning`.

`dispatch` prints the current route of one track from the manifest, `{"task_id", "provider", "model", "effort", "escalated"}`, and appends a `route.dispatched` event with that route to `.agent-workflow/runtime/events.jsonl` in the main checkout. `--escalate REASON` first moves the track one step up its provider's catalog: the next model at the same effort, or the next effort at the strongest model. It writes the new route and an `escalations` entry (`from`, `to`, `reason`) to the manifest. At the strongest model and highest effort it prints `{"status": "human_decision_required", ...}`, changes nothing, and exits 2. With `usage.budget_usd` set, it first reads the stored `ai_usage` of the epic (the one `orchestration-ready` recorded for the workflow, else the workflow id). At or above 120% of the budget it prints `{"status": "over_budget", "epic", "cost", "budget_usd"}`, changes nothing, and exits 3. When `bd` cannot be read it prints a warning and dispatches.

Exit codes: 0 all routes resolved and manifest written, or a route printed; 2 unresolved tracks, a missing or invalid manifest, a track missing from it or without a resolved route, an invalid configuration, an unknown provider, or a manifest route outside its provider's catalog on `--escalate`, nothing left to escalate to, or invalid arguments; 3 the epic is over budget (`dispatch`).

## `gin paths`

```
gin paths [--json]
```

Prints the path of the directory holding `workflow_core` (`{"lib_dir": "..."}`) for external tools and extension launchers. It always prints JSON; `--json` changes nothing.

Exit codes: 0 ok.

## `gin goal`

```
gin goal --workflow-id ID [--repository PATH]
```

Prints a Claude Code `/goal` for the epic recorded by `orchestration-ready`. The goal lists the open tracks in dependency order, leaving out every track labelled `human-gate` and every open track that depends on one. Its turn limit is 6 per track, at most 30. A track run on a fallback from its route counts as run on its routed provider. A standalone bead is its own single track. When no open track is left for the agent, it prints a `No goal:` line instead, which names the human-gate tracks when any wait.

Exit codes: 0 ok; 1 no epic recorded for the workflow, or the task backend is unavailable.

## `gin workspace`

```
gin workspace add PATH --url URL [--shape SHAPE] [--frozen] [--default-branch BRANCH] [--check NAME=COMMAND ...] [--repository DIR] [--json]
gin workspace clone [--repository DIR] [--json] [--all | PATH ...]
gin workspace status [--repository DIR] [--json]
```

A workspace is a parent repository whose `workspace.repos` lists child repositories ([configuration](config.md#workspace)). `add` records a repository entry in `workspace.repos` of the parent repository and writes it through setup configuration. `add` rewrites `.agent-workflow/config.yaml` without its comments. It validates the entry, refuses duplicate or nested paths, and prints the clone command to run next. `clone` clones the named entries, or every entry with `--all`, at their manifest paths from their `url` and `default_branch`. A `frozen` entry is cloned with `--depth 1`. An entry already present is reported as `present`. In a workable clone, `clone` installs the verify hooks when the entry has `verify.checks`. In team mode, it activates the commit-msg hook when the child has `.githooks/commit-msg`. Frozen and beads entries receive no hooks. An occupied hook reports its status and prints its chain command to stderr. Each path gets a `/<path>` line in the parent `.gitignore`. `status` prints one line per entry: path, `present` or `missing`, branch, `clean` or `dirty`, and `frozen`. `clone` and `status` run from anywhere inside the workspace, including a child repository.

Exit codes: 0 done; 1 outside a workspace (`clone`, `status`) or a workspace parent (`add`), an unknown path, a duplicate or invalid entry, or a git failure (message on stderr); 2 invalid arguments.

## `gin worktree`

```
gin worktree create [--repository DIR] TRACK_ID BRANCH [BASE_REF]
gin worktree cleanup [--repository DIR] TRACK_ID
gin worktree checkout [--repository DIR] TRACK_ID BRANCH
```

Creates or removes the git worktree for one track at `.planning/worktrees/<track-id>` in the repository's top level. `TRACK_ID` must match `[A-Za-z0-9._-]+` and resolve inside `.planning/worktrees`. `create` makes the new branch `BRANCH` from `BASE_REF` (default: the current branch, or `HEAD` when detached) and refuses an existing directory. `checkout` checks out an existing branch `BRANCH` at the same path; a branch that exists only on `origin` is created locally tracking it; it refuses an existing directory and an unknown branch. `cleanup` runs `git worktree remove` and succeeds without doing anything when the directory does not exist.

Exit codes: 0 created, removed, or nothing to remove; 1 invalid track id, existing directory, unknown or empty branch, or git failure (message on stderr); 2 invalid arguments.

## `gin task`

```
gin task <bd arguments>
```

The task-tracking entry point skills and agents use. With `providers.task_tracking: beads` it runs `bd` with the arguments unchanged, with one exception. `ready` also leaves out a bead of type `milestone` and a bead whose `external:<project>:<capability>` dependency is not shipped yet: no closed `provides:<capability>` bead exists in the database `external_projects.<project>` names. bd 1.0.5 reports such dependencies as resolved. `gin team ready` applies the same check. If bd cannot explain its ready list, `ready` exits 1 rather than list beads it could not check. Write `external_projects` paths as absolute paths or relative to the repo root, which is the main checkout when you run from a linked worktree; `~` is expanded. With `markdown` it serves the same subset in process from `.planning/tasks/` (git-ignored, local to this machine): `create`, `show`, `update` (`--claim` sets `in_progress` and the assignee from `BD_ACTOR`, else `git config user.email`), `close`, `reopen`, `list` (`--assignee` filters by assignee), `ready`, `blocked`, `dep add|remove|list`, `config get issue_prefix`, `remember`, `memories`, with `bd`-shaped `--json` output. `comments <id> --json` and `comment <id> "<text>"` reach `bd` with the Beads backend. They do not exist with `markdown`. `list` and `ready` take `--exclude-label <label>` on both backends; repeat it or separate labels with commas to leave out beads with any of them. The markdown `create` accepts `--no-inherit-labels` and ignores it, because it never copies labels from the parent. Epic comments are described in `docs/concepts/lifecycle.md`.

`close` has one guard of its own. With `project.review_ledger: true`, closing a bead that has a parent epic (a track) needs a review ledger with a live approval. Otherwise the command names the ledger state, closes nothing, and exits 2. `--waive-review <reason> --actor <id>` records a `review.waived` event and then closes. `ship` lists those tracks. A bead without a parent, or `review_ledger: false`, closes as before. Running `bd close` directly skips the guard.

Exit codes: 0 ok; 1 invalid configuration, invalid request, or malformed task file (the message names the file); 2 `close` refused by the review guard or given bad arguments; 127 `beads` is configured but `bd` is not installed. Other `bd` commands exit with `bd`'s own code.

## `gin usage`

```
gin usage collect --bead ID [--best-effort]
gin usage report [--bead ID | --epic ID | --milestone ID | --since YYYY-MM-DD]
```

`collect` reads local Claude Code and Codex logs, attributes token usage to the bead and its lifecycle stages, adds quality signals, and stores the summary in the bead's `ai_usage` metadata. `report` reads those summaries back; with no scope it covers every closed bead and every bead that has a summary, and lists closed beads without one as `not collected`. `--milestone ID` covers the epics under that milestone and their tracks; a non-milestone id exits 2. Costs come from `.agent-workflow/usage-prices.yaml`; unpriced models show `-`. With `usage.budget_usd` set, collecting an epic adds `budget: {budget_usd, cost, status}` to its summary and the status to the printed line. `report` prints totals per model, then per role and model (`role main <model>`, `role subagent <model>`). A Claude Code record whose log line has `"isSidechain": true` counts as `subagent`; every other record, including every Codex record, counts as `main`. When totals miss runs, JSON output adds `partial` and `partial_reasons`, and the text report prints `partial: <reasons>` after the total line.

Exit codes: 0 ok; 2 error. With `--best-effort`, `collect` turns any error into a `warning:` line and exits 0, so it never blocks closing a bead.

## `review-ledger.py`

```
python3 review-ledger.py <command> --bead-id BEAD [options]
```

Lives in the plugin's `scripts/` directory. Each bead's ledger is stored in `.planning/reviews/<bead-id>/` (`review.json` plus the rendered `review.md`); never edit those files by hand.

| Group | Commands |
|---|---|
| Lifecycle | `init`, `checkpoint`, `transition-requested`, `start-review`, `resync-lease`, `release-lease`, `change-scope`, `approve`, `reject`, `accept-as-is`, `record-human-decision` |
| Findings | `add-finding`, `fix-finding`, `dispute-finding`, `request-clarification`, `provide-clarification`, `propose-deferral`, `withdraw-deferral`, `approve-deferral`, `require-human-decision`, `verify-finding`, `reopen-finding`, `withdraw-finding`, `waive-finding` |
| Inspection | `status`, `validate` (`--in-history` for an earlier track on a shared branch or after a squash merge), `render` (`--check` for drift) |
| Housekeeping | `push-refs` (force-pushes each repository's review ref to `origin`), `cleanup` (`--bead-id` or `--all-closed`; also deletes the bead's `refs/gin/review/` refs, locally and on `origin`) |

`init --max-cycles N` caps `start-review` to N review cycles (a cycle is one `review-started` event) until `record-human-decision`. `record-human-decision` without `--finding-id` records a decision for the review and lets one more `start-review` run. At the limit, a review whose findings are all terminal may still start as a verification pass. The init actor is stored as `owner` and may not start a review. `status --format json` adds `owner`, `max_cycles`, `cycles`.

`change-scope` and `reject` invalidate an active approval. `approve` refuses when the working source tree differs from the reviewed checkpoint.

`validate --in-history` accepts an approved source found in a commit of HEAD's history. After a squash merge, the search starts where the histories diverged. An earlier track also passes when an approved track with a later review base started from its approved source and itself passes. A review base missing locally is fetched from the ledger's review ref on `origin`.

## Delegation to gin-orchestrator

When `provider_mode: multi` is set, `gin-orchestrator` is available on `PATH`, and the extension lists the required capability, `gin` delegates commands:

| `gin` command | Delegates to | Capability |
|---|---|---|
| `gin routes resolve` | `gin-orchestrator routes resolve` | `routes` |
| `gin reviewer` | `gin-orchestrator reviewer` | `reviewer` |
| `gin setup doctor --probe` | `gin-orchestrator doctor` | `doctor` |
| `gin setup models` | `gin-orchestrator models` | `models` |
| Worker execution (`execute`, `review`) | `gin-orchestrator dispatch` | `dispatch` |

In single-harness mode (`provider_mode: single`), `gin` resolves for the main harness without a warning. In `provider_mode: multi`, when `gin-orchestrator` is missing or mismatched, or when the orchestrator fails, it resolves for the main harness and emits a warning. Stage worker execution delegates cross-harness tasks to `gin-orchestrator dispatch` when available, falling back to native subagents on the main harness. `setup models` needs no `provider_mode: multi`: it lists models whenever an available orchestrator has the `models` capability, and an empty list otherwise.

## `gin-qa`

The optional `gin-qa` plugin adds its own CLI with `gin-qa cases {plan,next-id,pin,result,bug,to-manual,new,split,check,export}`, `gin-qa e2e {init,plan,pin,run,check,export}`, `gin-qa tests {plan,pin,check,run}`, and `gin-qa report [capability] [--out DIR] [--zip]`. Exit codes: 0 ok; 1 findings; 2 usage or environment error. `gin-qa e2e init [--base-url URL] [--install]` also writes `playwright.config.ts` when the Playwright folder has none. That folder is `e2e` in the [QA home](../guides/qa.md#the-qa-home), or the repository root for an existing root setup; an invalid URL exits 2 and writes nothing. It adds the evidence folder to `.gitignore`. On an existing `evidence.ts` without `ariaSnapshot`, it merges the step snapshots when the file matches the template, and otherwise prints a line to merge by hand and leaves the file.

`--install` first reads `package.json` in the Playwright folder; a missing or invalid file, or a `scripts` that is not an object, exits 2 before anything changes. It then runs the install commands for the package manager of the lockfile in the Playwright folder (`pnpm-lock.yaml`, `yarn.lock`, else `npm` and `npx`): add `@playwright/test`, unless it is already installed, and `playwright install chromium`. It adds `"e2e": "playwright test"` to `scripts` when missing. A manager not found or a failed command exits 2 and names the commands to run by hand. Without the flag, `init` only prints those steps. `gin-qa e2e plan` and `gin-qa tests plan` exit 2 when the capability is a TC-ID, and name its capability.

### `gin-qa cases check`

Reports problems in the case files: structure, IDs, the `REQ:` or `Source:` fields, case files that match `artifacts.test_globs`, and, in the SDD layout, missing, stale, and obsolete cases. When the guidelines file has a `## Types` section, it also reports each entry that is not `` - `<type>` `` optionally followed by `:` and a description, a section that lists no types, and each case whose type is not listed (`<file>:<line>: <TC-ID>: type '<type>' is not listed under '## Types' in <guidelines>`). Guidelines without the section accept any type. Exit 0 prints `ok`; exit 1 lists the findings.

### `gin-qa cases result`

`gin-qa cases result <TC-ID> <status> [--run REF] [--bug ID|none]` is the only command that writes the `Result`, `Run`, and `Bug` lines. `status` is `passed`, `failed`, `blocked`, or `not run`. `--run` sets the `Run` line; without it the line is removed. `--bug` sets the `Bug` line, `--bug none` removes it, and without it the line stays.

Exit 2, writing nothing, when the ID does not exist, the status is not one of the four, `--run` or `--bug` is empty or holds a non-printable character, or the case files have a finding that names the case.

Output: text `TC-AUTH-001 passed`; JSON `{"tc", "result", "run", "bug", "file"}`.

### `gin-qa cases bug`

`gin-qa cases bug <TC-ID> --actual TEXT [--evidence REF]... [--external-ref REF] [--discovered-from BEAD] [--run REF]` records `failed` on a case of any type and files a bug bead for it.

- When the case's `Bug:` is a bead that `gin task show` reports with a `status` other than `closed`, no bead is created, the case keeps that bug, and `epic` is `null`. No epic is needed.
- When the bug is open, the new actual result is added to its notes with `gin task update --append-notes`, as one line, `Re-run <date>; Run: <ref>; Actual: <text>; Evidence: <refs>`; the `Run` and `Evidence` parts are left out when empty, and double quotes become single quotes. A failed update exits 2 and leaves the case unchanged.
- A `Bug:` value that is not a bead, or that `task show` cannot read, counts as no open bug; the new bug names it as `Previous bug`.
- Otherwise the epic is found:
  - from the spec named in `Source:`, which must be inside the repository: its `Epic:` line, or the `epic` of `gin state --workflow-id <topic>` for its `Workflow: <topic>` line;
  - or, with REQs, the distinct `epic` values of the case's REQs in `gin specs reqs`, in REQ order; it needs exactly one.
- `--discovered-from` replaces the epic found. The epic must be a bead `gin task show` can read.
- It then runs `gin task create -t bug --title "<TC-ID>: <title>" --body-file - --deps discovered-from:<epic> -p <priority> [--external-ref REF] --json` in the repository, with the description on stdin. Then it writes `Result: failed`, the run (`--run`, else the case's current `Run`), and the new bug.

Exit 2, writing nothing, when:

- the ID does not exist;
- an option value is empty or not one printable line;
- no epic is found (`no epic for <TC-ID>; pass --discovered-from <bead>`), the REQs name several (`several epics for <TC-ID>: <epic>, <epic>; pass --discovered-from <bead>`), or the epic is not a bead (`<epic>: no such bead; pass --discovered-from <bead>`);
- the spec named in `Source:` is outside the repository or cannot be read;
- `task show` on the epic fails for another reason, or `task create` fails (their stderr is passed on).

When the bead is created but the result cannot be recorded, it exits 2 and names the bead and the `cases result` command to run.

Output: text `TC-AUTH-001 failed gw-12`; JSON `{"tc", "bug", "epic", "created", "appended", "file"}`. `appended` is true when the result went into the notes of an open bug.

### `gin-qa cases new`

`gin-qa cases new <capability> --type TYPE --title TITLE (--req REQ-ID... | --source PATH#HEADING)` writes `<TC-ID>-<slug>.<type>.md` under `cases/<capability>/` of the [QA home](../guides/qa.md#the-qa-home) (default `qa/cases/<capability>/`) with the next ID. The case holds the `REQ` field with the requirement's current `hash8` (SDD layout, `--req` repeated for several requirements, a repeated one pinned once) or the `Source` field (legacy layout, `--source`), `Priority: medium`, and the four sections empty. `gin-qa cases check` reports the case until its steps and expected results are written.

Exit 2, writing nothing, when `--req` is used with the legacy layout or `--source` with the SDD layout, a REQ-ID does not exist, the title or source is empty or not one line, the capability is not `[a-z][a-z0-9-]*`, the type is not listed under `## Types` in the guidelines, or `cases/<capability>.md` of the QA home is a flat file (run `cases split` first).

Output: text the file path; JSON `{"tc", "file"}`.

### `gin-qa cases to-manual`

`gin-qa cases to-manual <TC-ID> --reason TEXT` moves an e2e case to manual. Under the cases lock it writes `Moved from e2e: <UTC date>: <reason>` and `Result: not run`, removes the `Run` line, keeps `Bug:`, renames the file from `.e2e.md` to `.manual.md`, and deletes the spec last, so a failed delete leaves an orphan that `gin-qa e2e check` reports.

Exit 2, writing nothing, when the ID does not exist, the case is not `e2e`, the reason is empty or not one line, the case is in a flat cases file, it already has a `Moved from e2e:` line, `manual` is missing under `## Types` in the guidelines, or the `.manual.md` file exists.

Output: text the new file path, then the deleted spec path or `no spec`; JSON `{"tc", "file", "spec"}` (`spec` is `null` when there was none).

### `gin-qa cases split`

`gin-qa cases split <capability>` turns the flat `cases/<capability>.md` of the QA home into one file per case under `cases/<capability>/`, named `<TC-ID>-<slug>.<type>.md`, and removes the flat file. Each new file drops its `Type:` line and keeps the case's `hash8`, so e2e specs stay pinned.

Exit 1, writing nothing, when the flat file has findings, a case has no `Type:` line or an invalid type, the file holds text outside its title and case blocks, the file holds no test case, or a target file already exists. Exit 2 when the capability name is not `[a-z][a-z0-9-]*` or the flat file does not exist.

Output: text lists the files written; JSON `{"written": [...]}`.

### `gin-qa cases export` and `gin-qa e2e run`

Each case in `gin-qa cases export --format json` adds `result` (`not run` without a `Result:` line), `run` and `bug` (empty strings when absent), `moved_from_e2e` (`{"date", "reason"}`, or `null`), `test_data` (a list), and `legacy` (the references of the `Legacy:` line, a list).

`gin-qa e2e run` records each case's result in its case file, the worst over its Playwright projects: `failed`, then `blocked`, then `passed`. A case with no result folder, or an invalid `result.json`, is `blocked`. Its JSON output lists them under `recorded` as `[{"tc", "result"}]`. A recording error is listed under `findings` and does not stop the other cases.

### `gin-qa tests`

`gin-qa tests` plans, pins, checks, and runs the tests of the automated types declared under `## Automated types` in the guidelines file (`qa.guidelines`). One `### <type>` per type, with `- Tests:` (backticked globs, relative to the repository root, never absolute or containing `..`) and `- Run:` (one backticked command that holds `{junit}` and optionally `{files}` as a whole argument). `e2e` and `manual` cannot be declared. A declaration error is a finding of `check` and makes the other subcommands exit 2.

- `plan [capability] [--type T]`: `missing` (a case of the type with no `TC: <TC-ID>@<hash8>` line in the type's test files). The other rows are `stale` (a marker whose hash8 is not the case's), and `orphan` (a marker of a case that is gone or of another type). `--format json` adds `types` and `guidelines`.
- `pin <TC-ID>...`: rewrites the hash8 of every marker of each case; writes nothing when any ID fails.
- `check [--type T]`: the declaration errors when there are any; otherwise the `plan` rows, as findings.
- `run --type T [TC-ID|capability ...]`: runs the command from the repository root, without a shell, into `evidence/<UTC stamp>-<T>/` of the QA home (`run.json`, `junit.xml`), which it adds to `.gitignore`. `{junit}` becomes the JUnit file's path and `{files}` the test files of the selected cases. A JUnit test case whose name or classname holds the TC-ID (in any case, `_` read as `-`) belongs to that case. The case records `failed` (a failure or error), `blocked` (skipped), or `passed`, the worst over its tests, and `blocked` with a finding when none ran. When `junit.xml` is missing or unreadable, every selected case records `blocked` with one finding. `--format json` prints `{"run", "exit", "findings", "recorded"}`. Exit: the command's non-zero exit, else 1 on findings, else 0; a command not found exits 2.

### `gin-qa report`

`gin-qa report [capability] [--out DIR] [--zip] [--format text|json]` writes `index.html` and a copy of each screenshot it shows into a new folder, `evidence/report-<UTC stamp>/` of the QA home by default (`-2`, `-3`, ... when that folder exists). `--out DIR`, relative to the repository, must be missing or empty. `--zip` also writes `<folder>.zip` next to the folder. The command prints the path of `index.html`, then the zip path with `--zip`; `--format json` prints `{"report", "zip", "cases", "moved", "screenshots", "missing_evidence"}`, where `zip` is `null` without the flag and `moved` counts the cases with a `Moved from e2e:` line. A report under the evidence folder adds that folder to `.gitignore`. A run folder named by a case's `Run` line that cannot be read is listed under `missing_evidence` and on stderr, and the report is still written. No test cases in scope, an unknown capability, or a non-empty `--out` exit 2 and write nothing. A `Run` folder written by `gin-qa tests run` is shown as text, not read as e2e evidence.
