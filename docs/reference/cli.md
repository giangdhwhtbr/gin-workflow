# CLI reference

The plugin ships two command-line tools that skills call and that you can run yourself:

- `gin`: repository setup, lifecycle gates, rules, specs, and team mode.
- `review-ledger.py`: the review ledger for one bead.

The local installer (`install.sh`, `install.ps1`) links `gin` into `~/.local/bin`. A marketplace install does not; see [Troubleshooting](troubleshooting.md#gin-command-not-found-after-a-marketplace-install).

`gin --version` prints the CLI version. An unknown or missing command prints the command list and exits 2.

`gin` refuses to run in a project whose [`.ginrc`](config.md#ginrc) it does not satisfy. Every command except `gin --version`, `gin paths`, and `gin version` checks the file first. It looks for `.ginrc` in the `--repository` directory when given, else the current directory, then in their parent directories, as [`.ginrc`](config.md#ginrc) describes. The refusal also stops `gin hooks run`, so the git hooks fail in that project until gin or the project is updated. A refusal prints one line on stderr and exits 2:

| Case | Message |
|---|---|
| Installed version older than the pin | `error: gin <installed> is older than this project needs (<pin>, <path>); update gin: <guide>` |
| Installed major version newer than the pin | `error: gin <installed> is a newer major version than this project uses (<pin>, <path>); upgrade the project with gin setup update --approve: <guide>` |
| `.ginrc` is not one version, is not UTF-8, or cannot be read | `error: <path> must hold one version X.Y.Z`, followed by the read error in parentheses when there is one |

`<guide>` is the [upgrade guide](https://giangdhwhtbr.github.io/gin-workflow/guides/upgrading/). With a newer major version, `gin setup` commands still run, so the project can be upgraded.

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
| `init` | First setup: validates and writes `.agent-workflow/config.yaml` and generated files; `--dry-run` previews. It also writes `.agent-workflow/executables.local.yaml` and the `gin` block in `AGENTS.md` and `@AGENTS.md` in `CLAUDE.md` (a symlinked `CLAUDE.md` is left alone). On an initialized repository, `--approve` adds a missing block. A first setup also writes `.ginrc` with the installed version, unless the file exists | yes |
| `configure` | Changes repository configuration (`--set key=value`) | yes |
| `refresh` | Regenerates `.agent-workflow/generated/` from the current configuration, rewrites `executables.local.yaml`, adds any missing local-file entry to `.agent-workflow/.gitignore`, and re-renders an existing `AGENTS.md` block (never creates one) | yes |
| `update` | Proposes, then with `--approve` applies, a registered schema migration (`--to-version`). When `.ginrc` is missing or lower than the installed version, it also proposes `write .ginrc <old or none> -> <installed>` and writes it with `--approve`, with or without a migration | yes |
| `doctor` | Checks configuration, main harness executable, verify commands, rule tool checks, external CLI paths, the code index, the `AGENTS.md` block (`ok`, `stale`, `absent`, `invalid`), and the [versions](#gin-version) | no |
| `status` | Shows whether the repository is initialized and the generated files exist | no |
| `diff` | Shows how generated configuration differs from what the current inputs would produce | no |
| `rollback` | Restores a validated backup (`--backup PATH`) | yes |
| `export-bundle` / `verify-bundle` | Writes (`--output`) or checks (`--bundle`) a portable configuration bundle | export only |
| `harness-override` | Sets (`--harness`), shows, or clears (`--clear`) a session override of the main harness | runtime only |

`--workspace` (on `preset` and `init`) writes an empty `workspace.repos` list and, on `init`, the parent `.gitignore` entries.

In a workspace child, or a worktree of one, `doctor` without `--repository` checks that entry: `checks_details.entry` (`path`, `shape`), `verify_commands.missing` against the entry's `verify.checks`, its hooks, and its rules with the entry's packs added. From the parent, `checks_details.workspace.repos.<path>.proposed_packs` lists the packs each entry could add, with an action `workspace: <path>: rules.packs could add <a>, <b>`. A child whose manifest cannot be read gets `workspace: <path>: cannot detect rule packs: <error>`.

Other options: `--dry-run`, `--non-interactive`, `--approve`, `--reset`, `--harness`.

`doctor` reports versions as findings, never as a failed check. `checks_details.version` holds `installed`, `required`, and `status`. An initialized project without `.ginrc` gets `version: no .ginrc; run gin setup update --approve`; a project without `.agent-workflow/config.yaml` does not. A pin of an older major version gets `version: .ginrc <pin> is an older major version; run gin setup update --approve`. A `gin-qa`, found as `gin version` finds it, whose version differs from gin's gets `version: <name> <version> differs from gin <installed>; run ./install.sh --plugin <name>`.

Exit codes: 0 success; 2 setup, migration, bundle, or validation error; 3 a required dependency is missing (for example PyYAML).

## `gin state`

```
gin state [--workflow-id ID] [--scope-hash HASH] [--format text|json]
```

Prints the current lifecycle stage, the routing decision, the main harness, every gate (`satisfied`, `unmet`, `waived(<reason>)`, or `unknown`), evidence, and remedies. Text format prints any active warnings (`Warning: ...`). JSON adds the main harness's [model catalog](config.md#models) as `catalog` (`null` while no harness is set), `warnings`, the resolved `project` settings (including team mode), the last five `recent_quick` runs, `epic` (the epic recorded at `orchestration-ready` for the workflow id, or `null`), and `review_waivers` (`task_id`, `reason`, `actor`) for tracks closed with `task close --waive-review`. The `workspace` key is `null` outside a workspace; inside one, `workspace.current` is the entry the command runs in (`path`, `shape`, `checks`), and `null` in the parent.

A gate reads `unknown` when `state` cannot read the task tracker or the event log. The decision is then `hold`. `warnings` and `remedies` carry the cause: `tracker unavailable: <cause>` or `event log unreadable: <error>; waivers not applied`.

`--workflow-id` defaults to `default-workflow`. Use one id per feature (for example the spec's topic slug) so gates from different features do not mix.

Exit codes: 0 when the decision is `route`; 1 when the workflow is held or blocked.

## `gin record`

```
gin record <gate> --evidence TEXT [--evidence TEXT]... [--actor ID] [--workflow-id ID] [--epic BEAD] [--plan PATH] [--spec PATH]
```

Appends a gate event to `.agent-workflow/runtime/events.jsonl`. Gates:

| Gate | Records | Notes |
|---|---|---|
| `requirement-confirmed` | the user confirmed the design | evidence: spec path; team mode adds `--spec`. With `artifacts.layout: legacy` and an existing `.md` evidence file, the spec is linted first (`specs lint --spec`); a failing spec exits 1 with the errors and records nothing. With `--workflow-id <epic>` it refuses a spec `Kind:` that differs from the epic's `kind:` label, and in team mode it uses the policy of that kind. With `artifacts.layout: sdd`, the event lists each requirement of the epic's open change as `requirements: [{id, hash8, op}]`, and team mode copies the list into the epic bead's `gates` |
| `plan-approved` | the user approved the plan | evidence: plan path; team mode adds `--plan`. Refused (exit 1, nothing recorded) while the workflow's design doc has a `- TQ-<n>:` line under `## Open Technical Questions` without an indented `Decision:` line. An open question marked `- TQ-<n> (lane <name>):` does not refuse it when the plan declares that lane under `## Lanes`. The plan is read from `--plan`, else from `--evidence` when that is a file. Without one it is refused with `questions marked for a lane need the plan file as --plan or --evidence`, and a lane the plan does not declare with `questions marked for a lane the plan does not declare`. The design doc is the legacy spec in `.planning/specs/` with `Epic: <id>` or `Workflow: <id>`, or the SDD change's `03-design.md`. Exit 2 when two legacy specs name the id, when the SDD change is ambiguous, or when the design doc cannot be read as UTF-8. In a workspace it is also refused, with the same findings as `gin team check-plan`, when a track's `Repo:` or `Reads:` is not workable |
| `orchestration-ready` | beads, dependencies, and the worktree exist | `--epic <parent-bead>` is required to derive `implementation_complete` and `shipped`, and the epic bead is set to `in_progress`, claimed as `task update --claim` would when it has no assignee (an existing assignee is kept); in team mode it is not assigned to anyone, because its tracks carry the claims; the markdown tasks backend leaves the epic unchanged; when `bd` fails the gate stays recorded with a `warning`; an epic that is a [prep task](../concepts/lifecycle.md#prep-tasks) is refused with `orchestration-ready refused: <id> is a prep task, not implementation work` |
| `quick-completed` | a `/quick` change finished | evidence: files and verify results |
| `shipped` | a standalone bead (recorded as its own epic) was merged | an epic with children ships by closing the epic instead. Team mode with a `ship` policy: evidence is the merged PR URL, approved on its head commit by a listed role other than the author (no approval under `host`); the local HEAD is not compared. Repeat `--evidence` for one PR per repository: each is checked, and two PRs of one repository or one failing PR record nothing, with each reason prefixed by its URL. The proof keeps `pr_url` and `merge_commit` of the first PR and adds `pull_requests` (`pr_url`, `merge_commit`, `repository` per PR) |

`--actor` is required unless team mode derives it from `git config user.email`. Only `shipped` takes several `--evidence` values; the event's `evidence` joins them with `, `. Recording the same gate with the same evidence twice reports `already_recorded`. Recording `shipped` for a workflow that already has a `shipped` event also reports `already_recorded`. The checks below and the write happen under one lock on the event store. In team mode with Beads, `record` also writes the gate's PR proof into the epic bead's `gates` metadata (see `docs/concepts/state-model.md`); when that write fails, the gate stays recorded, the command exits 0, and it prints `warning: ...` to stderr (`warning` in JSON).

Exit codes: 0 recorded; 1 team mode rejected the evidence, or the event could not be written; 2 usage error. Usage errors are a missing actor, several `--evidence` values on another gate, `--epic` on another gate, a process gate on a workflow that already shipped, `shipped` on anything but a standalone bead, `shipped` while the task tracker cannot be read (the message names the cause), and, in team mode, `shipped` evidence that is not a PR URL, or a team configuration or host error. The removed `verification-passed` gate also exits 2, because quality checks run in the git hooks; so does `unblock --gate verification_passed`.

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

Decides whether a change may use the `/quick` path. `--modules` (default 1) counts the source modules the change touches; a changed module's tests and docs count as that module, not as another one. It returns the rigor, the verify commands to run, `run_at`, and the review mode from `project.review` (`self_check` under `easy`, `independent` otherwise). With `verify.run_at: host`, the verify commands are only `lint` and `typecheck`. Outside a workspace child, each package's checks from `project.packages` appear too, named `<package>:<name>`; run them in the package directory.

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

In a workspace child, or a worktree of one, without `--repository`, the entry's `rules.packs` are added to the parent's, the child's `.agent-workflow/rules` project rules load, and an absolute `--files` path inside the child is taken relative to it. `--list` uses the same merged packs.

Exit codes: 0 success; 2 invalid configuration or rule pack.

## `gin specs`

```
gin specs <command> [options]
```

Living specs for `artifacts.layout: sdd`. Every command except `template`, `migrate`, `reqs` without `--change`, `trace --all`, and `lint --spec` requires that layout; `migrate` and `lint --spec` require the `legacy` layout.

| Command | Purpose |
|---|---|
| `new SLUG --epic BEAD [--title T] [--kind capability\|technical\|parity]` | Create a change folder under `artifacts.changes`; `--kind` writes the `Kind:` line of `01-proposal.md` (default: the epic's `kind:` label, else `capability`) |
| `next-id CAP` | Next free requirement id for a capability |
| `lint [--change C] [--against REF] [--spec FILE]` | Lint the living specs, or one change: its spec delta, and each repository path its files cite in backticks that exists on disk but git neither tracks nor ignores, and each dated asset folder `<specs>/<cap>/assets/<YYYY-MM-DD>/` without a `description.md`, each `<specs>/<cap>/diagrams/*-activity.md` without a mermaid block starting with `flowchart` or `graph` and `*-state.md` without one starting with `stateDiagram`, each `<specs>/<cap>/use-cases/*.md` without a title, an `Actor:` line, a `Requirements:` line with a REQ-ID that is in a living spec or `ADDED` or `MODIFIED` in an open change (only `REMOVED` is reported), or a numbered `## Main flow` (an included use case may omit `Actor:`), each `Includes:`, `Extends:`, or `Specializes:` reference (a slug, or `<capability>/<slug>`) that names the file itself (`<key> names the use case itself`) or no use case (`<key> names unknown use case '<reference>'`), a loop of `Specializes:` (`use case generalization cycle: <capability>/<slug>, ...`), and each `Use case:` slug of an activity diagram that names no use case of the capability, an `<specs>/actors.md` without a table that has `Actor` and `Description` columns (`needs a table with Actor and Description columns`) or with a row whose actor is in no use case (`actor '<name>' is in no use case`), with an `Is a` value that is no actor (`actor '<name>' is a '<parent>', which is no actor`), or with actors that are each other's ancestors (`actor generalization cycle: <actor>, ...`), each requirement block whose `Type:` is not `functional`, `non-functional`, or `business-rule`, whose non-functional `Category:` is unknown, that has `Category:` or `Measure:` without `Type: non-functional`, or a non-functional one with neither a scenario nor a `Measure:` line (see [requirement types](../guides/sdd.md#requirement-types)), and with `--change` each capability with an `ADDED` or `MODIFIED` block but no `*-activity.md` (a non-functional block does not count); with `--change --against REF` instead each capability with an `ADDED` block and no activity diagram added or changed since REF (`no activity diagram added or changed in ... since REF`), each use case changed since REF with an alternative or exception flow that no activity diagram names on `Use case:` (`no activity diagram with 'Use case: <slug>'`), and each edge leaving a decision of an activity diagram changed since REF without a label (`edge from decision '<node>' has no label`); `--change` reads the kind from the epic's `kind:` label, else `Kind:` of `01-proposal.md`, and reports a mismatch (without Beads, `Kind:` decides); a `technical` change skips the activity diagram rules (per capability, per changed use case, decision labels) but its use case files are still checked, and `--against` with a ref that cannot be resolved exits 2 for any other change; `--spec` lints a legacy-layout design spec (every `### US-<n>:` story needs `Acceptance criteria:` with a bullet, no `{{`, `TBD`, or `TODO` outside code); per [epic kind](../concepts/lifecycle.md#epic-kinds), `Kind:` must be `capability`, `technical`, or `parity` (reported with file and line); `--spec` needs no user stories for `technical` and `parity`; a `parity` spec needs a `Parity with:` line that lists backticked asset folders (paths relative to the repository root), each existing, with `Kind: legacy` and a `Confirmed:` date; `--change` accepts a `technical` change with no `02-spec-delta.md` (see [SDD](../guides/sdd.md#epic-kinds)); `--spec` and `--change` also check `## Open Technical Questions` (`- TQ-<n>: <question>` or `- TQ-<n> (lane <name>): <question>` lines, unique ids, at most one non-empty indented `Decision:` line right below each); an open question is not an error; it also reports a `Confirmed:` value that is neither `no` nor a date and any change to a dated asset folder confirmed on the base (`--against REF`, else the merge-base with `main` or `master`; without one it warns and skips that check), and `--against` works without `--change` for this check; without `--change` it also warns on stderr, exit code unchanged, about each `<specs>/<cap>/diagrams/*-activity.md` added with an archived technical change: the commit that added it also touched that change folder, the change cites it in backticks, no non-technical change cites it, and its `Use case:` names no use case of the capability; such a diagram was written before 3.1.2 required none and can be deleted with its `## Diagrams` link (a change's kind comes from its epic's `kind:` label, else its `Kind:` line); a shallow clone gives no such warning, because it cannot show who added a diagram |
| `assets add CAP [FILES...] [--date D] [--legacy] [--new-capability]` | Copy files into the dated asset folder `<specs>/CAP/assets/D/` (default today), or its `legacy/` folder with `--legacy` (images only), and write `description.md` when missing; `--new-capability` allows a capability without a folder; exit 2 on refusal (a confirmed folder, an existing file, a non-image with `--legacy`) |
| `assets confirm CAP --date D [--agreed-with TEXT]` | Set `Confirmed:` to today in that folder's `description.md`, add `Confirmed by:` with the git `user.email`, and add `Agreed with: TEXT` when given; exit 2 when the file is missing, already confirmed, or git `user.email` is unset |
| `assets list CAP` | List the dated asset folders of CAP, oldest first: JSON rows `{"date", "kind", "confirmed", "path", "screens"}` (`confirmed` is the date or `null`; `screens` are the `### ` headings under `## As-is behaviour`); with the legacy layout it lists nothing; exit 2 for an unknown capability |
| `hash REQ-ID` | Print the base hash of a requirement (`<!-- base: ... -->`); a requirement another open change adds gets that block's hash, and the JSON `change` names that change |
| `template NAME` | Print a spec template (`technical-design.md` is the legacy-layout design of a technical epic: `Kind: technical`, `## Goal and scope`, `## Approach`, `## Risks and rollback`, `## Testing`, `## Open Technical Questions`) |
| `renumber OLD NEW --change C [--against REF]` | Rename a requirement id in a change and its beads |
| `archive --change C` | Merge a change's spec delta into the living specs and archive the change; a new capability's `spec.md` links each file in its `diagrams/` under `## Diagrams` and in its `use-cases/` under `## Use Cases`. It then writes `06-signoff.md` into the archived folder from the sign-off of the change's epic (its bead's `gates`, else its newest local `requirement.confirmed` event, else a waiver) and stages it. Without a sign-off, or for a requirement changed after sign-off, it prints a warning on stderr |
| `trace --change C` | Show which tests and sources cover each requirement; in a workspace it also scans every cloned child that is neither frozen nor the Beads repository, names each source by its workspace path, and lists children it could not scan under `skipped` |
| `trace --all` | List every requirement with its changes, sign-off, beads, gin-qa cases, and tests ([Requirement trace](#requirement-trace)) |
| `status --change C` | Show a change's review status, URL, and merge commit |
| `reqs [--change C]` | List requirements with section, `type`, `category`, hash, and the epic of the change that holds them; the JSON also carries `root` (the project root) and `qa_root` (the `shape: qa` workspace child, or the worktree of it you run from; null without one) |
| `export (CAP \| --all) [--out FILE]` | Write the living specs of one capability, or of every capability, into one printable SRS HTML file with each chapter's purpose, use cases (opening with a generated use case diagram), diagrams, requirements, and assets, framed by Revision history, Sign-off, Glossary, Actors (a context diagram, then a table with an `Is a` column), Non-functional requirements, and Business rules before them and a Traceability matrix (with a Type column) after them, requirements grouped under type headings when a capability has a non-functional one or a business rule, and a use case ID `<CAP>/<slug>` under each use case heading, followed by its `Actor`, `Secondary actors`, `Trigger`, `Requirements`, `Includes`, `Extends`, and `Specializes` lines as a two-column table (default `srs-CAP.html` or `srs.html` at the repository root, overwritten), from the templates `srs.html` and `srs-capability.html`; images are embedded, and a page that holds a diagram embeds the vendored Mermaid 11.4.1 library, so diagrams draw offline; a local image not found, outside the repository, or not an image is listed and exits 1 |
| `explain NAME [--narrative FILE] [--out FILE] [--legacy APP]` | Write one interactive HTML page for a capability, or for an active change found as `--change` finds it (default `<artifacts.explain>/NAME/NAME.html`, overwritten; `artifacts.explain` defaults to `.agent-workflow/runtime/explain`), from the template `explain.html`: tabs for the overview (the `--narrative` Markdown file first), the requirements with a search box, the stories, the diagrams, and the dated asset folders with an image viewer and each `mockup/index.html` in a sandboxed frame; a requirement's `Source:` path under `assets/<date>/` opens that file on the page; `--legacy APP` names a frozen workspace entry by its last path component, takes a capability only, writes `<artifacts.explain>/legacy/APP/NAME/NAME.html`, and sets the kind line to `legacy capability (APP)`; with `--legacy`, NAME is a change only when it is the whole name of a change folder, and any other name is a capability; a capability that has no living spec yet is accepted when `--narrative` is given, and the page then holds the narrative and any diagrams and dated asset folders; a narrative, `--out`, or `artifacts.explain` outside the repository, `--legacy` with a change folder name, without a workspace, or with an app that is not frozen exits 2; the page embeds the vendored Mermaid library when it holds a diagram, and a missing vendored file exits 2 naming its path; an image or a mockup not embedded is listed and exits 1 |
| `migrate [--dry-run] [--force]` | Move `legacy` layout artifacts into the SDD layout |

Exit codes: 0 ok; 1 findings (lint errors, untraced requirements of `trace --change`, archive conflicts, refused migration, images an export could not find, images or mockups an explain page could not embed); 2 usage or configuration error.

### Requirement trace { #requirement-trace }

`gin specs trace --all [--format text|json]` lists every requirement of the SDD layout with its changes, sign-off, beads, gin-qa cases, and tests. It is the contract the gin-console requirements view reads. It exits 0 whatever the coverage, and 2 on a usage or configuration error. With the `legacy` layout it prints an empty `requirements` list. A source that cannot be read adds a line to `warnings` and leaves its field null.

| Field | Meaning |
|---|---|
| `schema` | `1`; fields are only ever added |
| `layout` | `artifacts.layout` |
| `requirements[].id`, `title`, `capability` | The requirement id, its heading title, and its capability |
| `requirements[].state` | `living` in a living spec; `proposed` when only an open change adds it; `removed` when an archived change removed it |
| `requirements[].hash8` | The first 8 hex characters of the block hash; null for a removed requirement |
| `requirements[].source` | `<file>:<line>` of the block; null for a removed requirement |
| `requirements[].changes[]` | Each archived change, oldest first, then each open change whose spec delta names the requirement: `change`, `epic`, `op` (`added`, `modified`, or `removed`), `archived` (the archive date, null when open), and `signoff` |
| `requirements[].changes[].signoff` | `at`, `actor`, `evidence`, `hash8` (the hash at sign-off, null when unknown), `source`, and `waived`; null without a sign-off |
| `requirements[].signoff` | The last change sign-off, plus `change` and `current`: true when its `hash8` equals the requirement's, false when it differs, null when either is null. For a living requirement whose last signed change is still open, `current` compares the signed pending text with the living text, so it stays false until archive. |
| `requirements[].beads` | `{id, title, status}` of each bead labelled `req:<id>`; null with the markdown task backend or when `bd` fails |
| `requirements[].cases` | `{id, effective_result}` of each gin-qa case that pins the requirement, from `gin-qa cases export`; null without gin-qa or when it fails |
| `requirements[].tests` | Test files that name the id, and the `05-tests.md#<case>` rows of open and archived changes whose evidence cell is filled (not empty or `-`) |
| `warnings`, `skipped` | Sources that could not be read; workspace children that could not be listed |

A change's sign-off comes from its `06-signoff.md` (`source: git`), else its epic bead's `gates` (`beads`), else the newest local `requirement.confirmed` event of the epic (`events`). A `requirement_confirmed` waiver comes last, with `waived: true` and the reason in `evidence`. The text output prints one line per requirement: `<id> <state> signoff:<yes|stale|waived|no> beads:<n|-> cases:<n|-> tests:<n>`.

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
| `init [--ci] [--force] [--all-repos]` | Write CODEOWNERS, the pull request template, and the commit-msg hook; `--ci` adds the CI workflow; `--force` overwrites files it did not generate. With `--all-repos`, write into each workable cloned child in the workspace with re-rooted CODEOWNERS globs. On `codecommit` it writes only the commit-msg hook, and `--ci` exits 2 because CodeCommit has no CI workflow file |
| `codeowners [--check]` | Print CODEOWNERS, or check it is up to date. Exits 2 on `codecommit`, which has no CODEOWNERS file |
| `hooks [--all-repos]` | Install the commit-msg hook into git (exit 1 if another hook occupies it, 2 if the hook file is missing). With `--all-repos`, install into each workable cloned child in the workspace; a failed repository is reported as `error` (exit 1) and continues |
| `whoami` | Show your member entry, roles, areas, and whether you hold a technical role (an area `lead` or a role in an area's `roles`), from `git config user.email` |
| `check URL --gate GATE [--plan P] [--spec S] [--workflow-id EPIC]` | Check a pull request of this repository against the approval policy of `GATE` (`requirement_confirmed`, `plan_approved`, `ship`, or `roadmap`). With `--workflow-id`, `requirement_confirmed` applies the policy of the epic's kind and the JSON carries `kind` ([per-kind policies](../guides/team.md#policy-per-epic-kind)). Every gate but `ship` also needs the pull request merged and changing the gate's spec, plan, or roadmap file. Under a `host` policy it checks no approver and no local HEAD, and a pass prints `ok (approvals are enforced by the host)`. Nothing is recorded |
| `check-plan PLAN` | Check a plan's `Area:` and `Owner:` fields, that the paths in each track's `Files` block stay inside its area, and that no path is listed by two tracks. In team mode it also checks lanes and reports `Track <N>: missing Lane:`, `Track <N>: invalid lane <name>`, `lane <name>: tracks <A> and <B> have different owners`, and `lane <name>: tracks <A> and <B> are in different repositories`. A plan with `## Lanes` needs no track. Each `### Lane <name>` declaration is checked (`lane <name>: missing Owner:`, `invalid lane name`, `declared twice`, `owner <email> is not in team.members`, `Depends on lanes: <other> is not a declared lane`). With `team.areas` configured it also reports `missing Area:`, `unknown area <area>`, and `owner <email> holds no role allowed in area <area>`. Each track is checked against the lane its `Lane:` names (`Track <N>: lane <lane> is not declared in ## Lanes`, `Owner: <email> is not the owner of lane <lane> (<owner>)`, `Repo: <path> is not the repository of lane <lane> (<repo>)`, `area <area> is not an area of lane <lane>`). A lane plan `<plan stem>.lane-<lane>.md` is checked against its lane's declaration in the plan beside it: `<path>: lead plan <lead> not found`, `<path>: lane <lane> is not declared in <lead>`, `<path>: lane <lane> has tracks in <lead>; the lead plans it there`, `Track <N>: lane <other> is not lane <lane>`, the track findings above, `<path>: missing Spec: <design doc path> line`, `<path>: Spec: <spec> is not a file`, and `<path>: Spec: <spec> is outside the repository`. For each open question of the design doc that its `Spec:` line names (relative to the top of its git repository) and that is marked for the lane, it reports `<spec>:<line>: TQ-<n> (lane <lane>) has no Decision:`. A malformed question line of that design doc is reported too. In a workspace it also checks each track's `Repo:` and its `Reads:` paths: a `Reads:` path must be in `workspace.repos`, not the beads repository, and not the track's own `Repo:`; a frozen repository is allowed |
| `pending [--workflow-id EPIC \| --milestone ID]` | List the open pull requests of the remote `spec/*` and `plan/*` branches, of `feat/<topic>-<lane>` for each lane with an open track bead, and of `feat/<topic>` for each open or in-progress epic when `team.approvals.ship` has roles or is `host`. `<topic>` is the name of the plan file on the `Plan:` line of a track bead, without its date and without `.lane-<lane>`. The ship branch counts closed track beads too. `spec/` is `requirement_confirmed`, `plan/` is `plan_approved`, `feat/<topic>` is `ship`, and a lane row has `gate` null, because `pending` checks no gate for it before the merge; `gin team check --gate ship` still applies `team.approvals.ship` to a lane pull request. The epic of a spec or plan row is the value of the `Epic:` or `Workflow:` line in its file, read from the branch; other rows take the track bead's parent. Each JSON row under `pending` carries `gate`, `branch`, `url`, `author`, `epic`, `approvals`, `missing`, and `notes`. `missing` holds the reasons `check` gives under the policy of the epic's kind, without the merge and local HEAD checks; a plan's areas are read from its branch. A row whose gate policy is `host` gets the note `approvals: host`. A track row lists its approvers only. It also lists the open pull requests of remote `quick/*` branches as `ship` rows with `epic` null, with no gate when `team.approvals.ship` has no policy; `--workflow-id` and `--milestone` leave them out. It exits 2 when the host CLI is missing or fails before any lookup succeeds, when `git ls-remote` fails, or when Beads cannot be read. A later failed lookup gives only its row `error`. Text shows one line per pull request, gate rows first, then track rows. `--workflow-id` keeps the rows of one epic, `--milestone` those of its child epics |
| `ready [--exclude-label LABEL]` | Ready beads in your areas, and beads held by another member whose claim lease has expired (`expired_claim`). A bead labelled `released` is listed for every member (`released: true`). `--exclude-label` leaves out beads with the label; repeat it or separate labels with commas. A [prep task](../concepts/lifecycle.md#prep-tasks) that `bd` blocks only through its parent epic is listed too, so the BA sees prep work of epics that wait on other epics. Each group, ready first and then expired claims, is sorted by priority and then id; this order applies to every team project. An open track whose lease has expired is listed as an expired claim. A row for a track bead carries `lane` and `branch` (`feat/<topic>-<lane>`); `lane` is `t<N>` for a bead without a `Lane:` line. A lane bead (`Plan: <plan>, Lane <name>`) is listed with its lane and branch. Text lists rows without a branch first, then one header `<branch> (<holder or unclaimed>)` per branch with that branch's rows indented |
| `claim BEAD` | Claim a bead as yourself, or renew your claim. A track bead claims its whole lane (the open tracks of one plan that share a `Lane:` line): the lease covers every open track of the lane, and the named bead becomes `in_progress`. It is refused when another member holds an unexpired lease on any of them (`lane <name> is claimed by <holder> until <time> (<bead>)`). Refused when you hold no role allowed in one of its `area:` labels (unless the bead is labelled `released` by `handoff --release`), or another member's lease (`claim.expires_at`, `team.claim_ttl_hours` ahead) has not expired; an expired lease is taken over with a note. Without `team.beads_sync.remote` the claim is advisory: only this machine sees it. When the bead has a `Plan: <path>, Track <N>` line, the claim also creates the lane worktree `.planning/worktrees/<epic>-<lane>` on `feat/<topic>-<lane>`. A bead without a `Lane:` line is its own lane `t<N>`, with worktree `.planning/worktrees/<bead>` on `feat/<topic>-t<N>`. A lane bead (`Plan: <plan>, Lane <name>`, made by orchestrate for a lane the plan declares without tracks) claims its lane in the same way. The beads of a lane are the epic's children whose plan is the plan or one of its lane plans `<plan stem>.lane-<lane>.md`, with the same lane. The track's repository is the workspace child its `Repo:` line names, else this repository. An existing worktree of that repository is kept; another directory at that path is refused. Otherwise the claim checks out `feat/<topic>-<lane>` when the repository or its `origin` has it. Without that branch it runs `git fetch origin <default_branch>` and branches from `origin/<default_branch>`. `<default_branch>` is the child's `workspace.repos` entry, else the branch `origin/HEAD` names, else `main`. These are refused before the lease: a `Repo:` outside `workspace.repos`, a frozen or `shape: beads` entry, a child that is not cloned (`gin workspace clone <path>`), and a branch name `git check-ref-format` rejects. A failed fetch or worktree keeps the lease and exits 1; run the claim again. The result carries `lane` and `beads` (the claimed tracks), and gains `worktree`, `branch`, and `created`; the text adds `at <worktree> on <branch>`. When the lane has a closed track and its newest pull request has merged, a claim whose worktree sits on that pull request's head restarts the branch from `origin/<default_branch>`, unless the merged commit is already in the branch. The result then has a `note` (printed as `note: ...`) that says so, or that the branch has commits made after the merged pull request and needs `origin/<default_branch>` merged in |
| `reassign BEAD EMAIL` | Hand a track bead to another member. Allowed for the bead's current assignee or the lead of one of its areas; the new assignee must be allowed to own tracks in each area (`team.areas.<name>.roles`). Sets the assignee, appends a note, writes a fresh claim lease for the new assignee, and pushes with shared Beads. It moves every open track of the bead's lane, and the new assignee must be allowed in the areas of all of them; the text appends ` (lane <name>: <beads>)` when the lane has more than one bead. A closed bead, a non-member, or a no-op is refused |
| `handoff BEAD [EMAIL] [--release] [--worktree PATH]` | Hand a track over in one step. Give exactly one of `EMAIL` or `--release`. It refuses a lane worktree (`.planning/worktrees/<epic>-<lane>`, `.planning/worktrees/<bead>` for a bead without a `Lane:` line, or `--worktree`) with uncommitted or untracked files, and lists them. It also refuses a `--worktree` that is not a Git worktree. These checks, and the authority and target checks, run before any push. It then pushes the track branch to `origin`. A broken `review.json` is refused after the branch push and before the review ref push, leaving the branch on `origin` and the bead unchanged. Otherwise it pushes the review ref when the ledger exists. It records `handoff` metadata (`branch`, `from`, `to`, `at`) only after the branch is on `origin`. With `EMAIL` it reassigns the bead as `reassign` does. It acts on every open track of the lane, records `handoff` on each, and the text appends ` (lane <name>: <beads>)` when the lane has more than one bead. With `--release` the bead loses its assignee and lease, returns to status `open`, and gets the label `released`. A rejected push is reported plainly |
| `takeover BEAD [--branch NAME]` | Take a handed-off track on your machine. Run it in the main checkout only, unless the bead's `Repo:` line names a workspace child. It fetches the branch recorded by `gin team handoff` (or `--branch`) from `origin` of the track's repository: that child, else this repository. It checks the branch out at the lane worktree (`.planning/worktrees/<epic>-<lane>`, or `.planning/worktrees/<bead>` for a bead without a `Lane:` line; `gin worktree checkout`), fetches the review ref of each open track of the lane when present, then claims the bead, and with it the lane. A child that is not cloned is refused with `gin workspace clone <path>`. A branch name that starts with `-` or fails `git check-ref-format` is refused. Only a review ref under `refs/gin/review/` is fetched. If a step fails after the worktree exists, it reports `worktree left at <path>; remove it with gin worktree cleanup <bead>`. A bead labelled `released` can be claimed by any member, and the label is removed on claim |
| `deps [--bead ID]` | Without `--bead`: close placeholders whose track is listed on the `Tracks:` line of a merged PR that names the plan on its `Plan:` line, storing its merge commit; in a workspace it searches the child named by the track's `Repo:` and records it as `repo` (`.` for the parent), and a placeholder it cannot resolve (child not cloned, frozen, or not in `workspace.repos`; plan not pulled; track not in the plan) stays waiting with a reason. Outside a workspace the plan is not read. With `--bead`: exit 1 unless each external dependency's merge commit is in the current repository's `HEAD`, or, from another repository, on `origin/<default branch>` of the repository it names; a placeholder with no recorded `repo` is checked against `HEAD` of the current repository. A placeholder `external: <plan>#lane-<name>` closes when every bead of lane `<name>` of that plan, its lane bead included, is closed and merged PRs list every track of the lane, whichever lane plan names it. It waits with a reason while the lane has no bead, an open bead, or no track bead. It records the merge commit of each of those PRs, separated by spaces, and `--bead` requires each one |
| `complete EPIC` | Close an epic bead once every track bead is closed and every pull request has merged. Allowed only for a member holding an area lead role (`team.areas.<name>.lead`). Checks that every child bead not labelled `prep` is closed, and that a merged pull request in each track's repository lists the track: its `Plan:` line names the track's plan and its `Tracks:` line holds the track number. A track of a lane plan is listed by a PR whose `Plan:` line names the lane plan. A track no merged pull request lists is reported as `<bead> (<plan>#<N>): no merged pull request lists it`. In a workspace, when `feat/<topic>` exists on `origin` of the parent repository, its pull request must be `merged` too. When every check passes, it closes the epic with a reason listing the merged pull request URLs, after closing each open `prep` child with the reason `not needed: <epic> shipped` (printed as `closed prep <id>`). An epic or `prep` child that another member holds is first assigned to the lead, with a note, because bd refuses to close it otherwise. It prints `next: gin team sync` when `team.beads_sync.remote` is configured. If any check fails, it lists the missing items, closes nothing, and exits 1. Refused with exit 2 when team mode is off, the member leads no area, the bead is not an epic, or the host CLI fails |
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
gin milestone points EPIC N --reason TEXT [--stage roadmap|discuss|close]   # alias of gin points
gin milestone close ID --reason TEXT
```

Dated milestones over roadmap epics, stored in Beads; they need `providers.task_tracking: beads`. `list` reports each open milestone (every milestone with `--all`) with its status, period, epic progress, and warning count, plus the number of open `roadmap` epics without a parent. It ends with a forecast line when any `roadmap` epic is open: when every open epic finishes against the roadmap's `Deadline:`, with the spare or overflow working days, the default lanes, and the open and unestimated counts. Open milestones are scheduled one after another in `end` order, each on its own lanes, then every open roadmap epic outside an open milestone on the default lanes. `show` reports the schedule of one milestone: each epic's planned start and end in working days (Monday to Friday) from `--start`, else the kick-off date, else the start date, and its warnings (`overflow`, `late`, `unestimated`, `external_blocker`, `spec_not_ready`). Schedules are lane-bound: a lane runs one epic at a time, so with one lane estimated epics run in sequence and independent epics overlap only with two or more lanes. A milestone's lanes come from its `lanes` metadata, else the whole number that starts the `AI capacity:` line of the roadmap file, else the number of `team.members` holding a building role (`dev`, `be_*`, `fe_*`, `*_dev`, `*_lead`), else 1. When the lanes come from those members, lane n belongs to the n-th of them and the schedule skips their `away` days on that lane. Lanes from `--lanes` or `AI capacity:` ignore `away`. The `list` forecast applies `away` to a milestone the same way. `show` lists `away` and `integration`. `after_integration` marks an open epic planned to end after the milestone's integration date. `open_bugs` counts open bug beads discovered from the epic. `oversized` marks an open epic whose planned days exceed the milestone's working days, with the excess in `days`. Malformed `away` or `integration` metadata is ignored with a warning on stderr. A milestone planned before lanes existed now shows later dates and may gain `overflow` warnings at the default of 1 lane; set `--lanes` or the `AI capacity:` number to match the team. Each epic row of `show` carries `spec_confirmed`: whether a `requirement.confirmed` event for the epic exists in `.agent-workflow/runtime/events.jsonl` of the main checkout. An open epic without one in a `scheduled` or `active` milestone gets `spec_not_ready`. An unreadable event log prints `warning: event log unreadable: ...; spec readiness unknown` on stderr, sets `spec_confirmed` to null, and the command still exits 0. A `list` entry whose schedule cannot be computed (a dependency cycle or a malformed date) carries `error` and keeps the other entries; its status then falls back to `planned`. `--start` is a read-only preview. `--json` prints `schema: 1` with the additive keys `lanes` (per milestone and on `show`), `away` and `integration` (on `show`), `spec_confirmed` (per epic on `show`), and `forecast` (`deadline`, `lanes`, `start`, `finish`, `overflow_days`, `open_epics`, `unestimated`, `error`; null without an open roadmap epic); fields are defined in the gin-console contract (`gin-harness/docs/changes/gin-harness-6s4-milestones/design.md`) and only ever added to. `list` and `show` add `days_per_point` with `value`, `measured_epics`, and `assumed`. Each milestone adds `velocity` with `committed_points`, `completed_points`, `added_points`, `say_do`, `days_per_point`, `planned_days_per_point`, and `accuracy`. Each epic row of `show` adds `points`, `points_reason`, `estimate_source` (`points`, `days`, or `assumed`), `actual_days`, and `actual_days_per_point`. `forecast` also carries `milestones` and `epics`. `milestones` lists each open milestone in chain order with `id`, `start`, `finish`, and `overflow_days`. `start` is the working day the milestone's epics are placed from. `start` and `finish` are null when the milestone has no open roadmap epic, or when `error` stopped the chain at or before it. `epics` has one row per placed open roadmap epic, ordered by `planned_start` and then `id`. Each row has `id`, `title`, `status`, `milestone`, `lane`, `planned_start`, `planned_end`, `remaining_days`, `estimate_source`, and `warnings`. `milestone` is null for an epic outside an open milestone, and `lane` counts from 1. `warnings` use the `show` rules on these chained dates. Outside a milestone only `unestimated`, `external_blocker`, and `open_bugs` apply.

An epic with story points is planned for `ceil(points * days_per_point)` working days, at least 1, recomputed on every run. `days_per_point` is the actual working days over the points of the 10 most recently closed epics with points, counted from `started_at` to `closed_at`, both included. Without such epics it is the number on the roadmap's `- Days per point:` line, else 1, and `assumed` is true. `list` prints it on a `days per point:` line; `show` prints `<points>pt/<days>d` for such an epic. `list` and `show` ignore a malformed `points` value on an open epic and warn on stderr.

`velocity` compares the kick-start snapshot with the milestone's closed epics that have points. `say_do` is completed over committed points, and null before kick-start or with 0 committed. `added_points` counts epics moved in after the kickoff date, read from `milestone_moves`. `days_per_point` is measured over the milestone's closed epics with points. `accuracy` is `planned_days_per_point` over it: 1.00 is on plan, below 1 is slower. `list --all` returns it for closed milestones too.

Each epic row of `show` carries `estimate_days`, `remaining_days`, and `assumed_days`. An in-progress epic is placed for its remaining days. With child tracks that is the estimate times the share of open tracks, rounded up. Without tracks it is the estimate minus the working days since the epic started. It is at least 1. An open epic without an estimate is placed for the median estimate of its group, rounded up, or 1 day, shown in `assumed_days` with the `unestimated` warning. The group is the estimated, not-closed epics of the milestone, or of the unassigned pool in the forecast. `remaining_days` equals the estimate for an open epic and is null when unestimated. A closed unestimated epic takes no days. `late` means an open epic of an active milestone whose planned end is before today. `spec_due` marks an open epic without a confirmed spec in a planned milestone that starts within 5 working days, today included; `spec_not_ready` replaces it once the milestone is kicked off. A spec counts as confirmed when the epic bead's `gates` metadata holds `requirement_confirmed` or the local event log has the event. `show` also reports `deadline` from the roadmap's `Deadline:` line, null without one.

The write commands:

| Command | Effect |
|---|---|
| `create` | New milestone with a start and end date; prints its id. `--start` after `--end` is refused; `--lanes N` stores the lane count |
| `update` | Change the title, either date, or the lanes of an open milestone; `--away` records a member's days off (repeatable), `MEMBER:none` removes them; `--integration` stores or clears the integration date |
| `kickstart` | Set the kick-off date (default today) that the schedule starts from; also stores `committed_points` (the points of its open epics) and `planned_days_per_point`, and warns when a second kick-start changes the commitment |
| `move` | Put epics under a milestone, or take them out with `--to none`. Refuses a non-epic, a closed target, an epic in a closed milestone, and an epic whose parent is not a milestone. Appends `{from, to, at, actor}` to each epic's `milestone_moves` metadata (a failed append prints a warning and keeps the move) |
| `estimate` | Set an epic's estimate as a positive whole number of working days (480 minutes each); refused for an epic with story points, which `gin points` changes |
| `points` | Alias of [`gin points`](#gin-points), with the same arguments, output, and exit codes |
| `close` | Close a milestone with a reason (`bd close --reason`); refused while it has open epics; `--reason` missing is a usage error |

Each write command first checks the team role. With `team.permissions.milestone` set, the git user must hold one of its roles, otherwise the command names the roles and exits 2. With `team.beads_sync.remote`, it pulls first and stops with `pull failed, nothing written` (exit 1) when the pull fails or times out. After the write it pushes; a rejected or timed-out push prints `<change> written locally but not pushed` and exits 1. The local write stays and is never reset. In team mode, the member's email is recorded as the Beads actor. See [Team mode](../guides/team.md).

Exit codes: 0 ok, warnings included; 1 unknown id, a refused change, a `--lanes` that is not a positive whole number, dependency cycle, non-Beads tracking, a failed pull or push, or a `bd` error; 2 usage error or a role that may not write milestones.

A malformed `Deadline:` line or a dependency cycle among open epics is reported in `forecast.error`; `list` still exits 0.

## `gin points`

```
gin points EPIC N --reason TEXT [--stage roadmap|discuss|close]
```

Set the story points of an open epic on the scale 1, 2, 3, 5, 8, 13, 21 with a one-line reason. Any epic is accepted, with or without the `roadmap` label. The command writes `points` and `points_reason`, appends `{from, to, at, actor, stage}` to `points_history`, and prints `points of <epic> set to <n>`. A failed append prints a warning and keeps the points. `--stage` names the step that set them: `roadmap` (default), `discuss`, or `close`. It needs `providers.task_tracking: beads`.

It refuses, writing nothing, an off-scale value, an empty `--reason`, an unknown id, a bead that is not an epic, a closed epic, and an epic of a kicked-off milestone unless `--stage close`; that message names `/milestone-close`. `gin milestone points` is an alias. In team mode it follows the role, pull, and push rules of the [milestone writes](#gin-milestone). Errors start with `points error:`.

Exit codes: 0 ok; 1 a refused value, non-Beads tracking, a failed pull or push, or a `bd` error; 2 usage error or a role that may not write.

## `gin attach`

```text
gin attach add <bead> <file>... [--caption TEXT] [--case ID] [--step N] [--format text|json] [--repository PATH]
gin attach list <bead> [--format text|json] [--repository PATH]
gin attach fetch [--bead ID --out DIR] [--repository PATH]
gin attach push [--repository PATH]
gin attach prune [--apply] [--format text|json] [--repository PATH]
```

Attaches PNG, JPEG, WebP, or GIF images to a bead and keeps them in the store set by `attachments.store`, `git-ref` by default. It needs `providers.task_tracking: beads`.

Any bead can carry attachments. The [`attachments`](config.md#attachments) config section sets the store, the size limit, and the retention.

- `add` stores each file and lists it in the bead's `metadata.attachments`. It prints one `![caption](attachment:<sha256>)` line per file, and the caption defaults to the file name. `--case` and `--step` record the QA case and step the image belongs to. A file already attached to the bead is not added twice.
- `add` accepts PNG, JPEG, WebP, and GIF by their first bytes, not by the file name. It removes EXIF and XMP metadata before hashing, and leaves GIF unchanged. A file that is not an image, is malformed, or is larger than `max_bytes` is refused with a line on stderr; the other files are still added. `--format json` prints `{"bead", "entries", "refused", "warning"}`; `warning` is the push problem as a string, or null, and also goes to stderr as `warning: <text>`. Each `refused` item is `{"name", "reason"}` and goes to stderr as `refused <name>: <reason>`.
- `list` prints `<sha256>  <mime>  <bytes>  <name>` per entry, with `(pruned)` after an entry whose blob was pruned. `--format json` prints `{"bead", "entries"}`.
- `fetch` brings the store up to date. With `--bead ID --out DIR` it also writes the bead's images to `DIR` as `<sha256>.<ext>` and prints each path; the two options go together. A blob whose bytes do not match its `sha256` stops the command.
- `push` sends the `git-ref` store to `origin`. It exits 2 when there is no `origin` or the push fails. It prints nothing on success, and does nothing for the `local` and `s3` stores, which have nothing to push. `add` pushes on its own; when that fails (including no `origin` remote) it keeps the entry, warns on stderr, and still exits 0, and `gin attach push` retries.
- `prune` lists the blobs to delete and changes nothing without `--apply`. A blob is a candidate when no bead entry references it (`orphan`), or, with `retention_days` set, when every bead that references it closed more than that many days ago (`closed <date>`). `--apply` deletes the blobs and sets `pruned_at` on the entries. Text output prints `<path> <reason>` per candidate, and a reminder to run `bd dolt pull` first when an orphan is listed without `--apply`. `--format json` prints `{"candidates": [{"path", "sha256", "reason", "beads"}], "applied"}`.

Run `bd dolt pull` before `gin attach prune --apply`. A blob whose entry has not reached this machine counts as an orphan, so the machine that added an entry must have run `bd dolt push` first. Prune stops, and deletes nothing, when a bead's `metadata.attachments` cannot be read.

An entry in `metadata.attachments` has the fields `sha256`, `name`, `mime`, `bytes`, `caption`, `case`, `step`, `added_by`, `added_at`, `store`, and `path`, plus `pruned_at` once the blob is pruned. A Markdown description or note points at an image with `![caption](attachment:<sha256>)`.

The stores:

- `git-ref` (default) keeps blobs in one commit history on `refs/gin/attachments`, at `<aa>/<sha256>` where `<aa>` is the first two hex digits. It needs git 2.29 or later. Its pushes run the repository's pre-push hooks, because gin passes no `--no-verify`.
- `local` keeps blobs under `.agent-workflow/attachments/`; see [`attachments`](config.md#attachments).
- `s3` keeps private objects at `<prefix>/<aa>/<sha256>` in a bucket, and needs `boto3`.

To read images, a read-only clone that never runs `gin attach add` fetches the ref with `git fetch origin +refs/gin/attachments:refs/gin/attachments`. It then reads a blob with `git cat-file blob refs/gin/attachments:<aa>/<sha256>`. Any clone that writes attachments runs `gin attach fetch` instead, because the forced fetch drops blobs that are not pushed yet.

Exit codes: 0 ok; 1 at least one file refused; 2 usage, a missing bead or tracker, a configuration error, or a store that cannot be reached.

## `gin hooks`

```
gin hooks install [--all-repos]
gin hooks status [--all-repos]
gin hooks run pre-commit|pre-push
```

`install` writes marker-tagged `pre-commit` and `pre-push` shims into the active hooks directory (it honors `core.hooksPath`, so a husky repository's hooks live in `.husky`). It is idempotent and does not create a missing hooks directory. It never overwrites a hook it did not write (`occupied`: add `exec gin hooks run <hook> "$@"` to your hook to chain it); a hook that already runs it is reported as `chained`. It also sets a repo-local `core.sshCommand` of `ssh -o ServerAliveInterval=30` (`ssh_keepalive: set`), so the SSH connection git opens before `pre-push` survives a long test run. An existing `core.sshCommand`, `GIT_SSH` or `GIT_SSH_COMMAND` is left alone (`kept`); a write that fails is reported as `failed` and does not fail the install. `/setup` runs it once `verify.checks` is configured; `setup doctor` reports hooks that are missing or occupied.

`status` prints `{"hooks": {...}, "verify_commands": [...], "run_at": ..., "ok": ...}`: each hook's state (`ok`, `missing`, `occupied`), the configured check names, including `<package>:<name>` for packages, and `verify.run_at`. Under `host` only the `pre-commit` checks are listed, and an empty list is still `ok`. It exits 1 when a hook is not `ok`, or when no verify command is configured and `run_at` is not `host`; `ship` warns on that and continues.

`--all-repos` runs `install` or `status` in every cloned repository of a [workspace](#gin-workspace), skipping `frozen` and `beads` entries and entries that are not cloned; it works from anywhere inside the workspace. `install --all-repos` prints `<path>: <hook>: <state>` per hook, keeps an occupied hook and names the file to chain `exec gin hooks run <hook> "$@"` into, and reports a repository whose hooks directory does not exist; its exit code is the worst single-repository result (2 when a hooks directory is missing, else 1 when any hook is occupied, else 0). `status --all-repos` prints `{"repos": {"<path>": <status report>, ...}, "ok": ...}` for the repositories that have `verify.checks` and exits 1 when any of them is not `ok`; a child without checks has nothing for the hooks to run and is left out. `setup doctor` lists the same missing, stale, or occupied hooks as `workspace:` actions for each cloned child that has `verify.checks`, and reports a child whose `.git` cannot be read.

`run` is what the shims call. `pre-commit` runs the `lint` and `typecheck` checks. `pre-push` runs `test` under `easy` rigor, `test` and `build` under `standard`, and `test`, `build`, and `e2e` under `strict`. It runs them only when the pushed branch is the checked-out HEAD (tags and deletes are skipped). Root `verify.checks` run for any change that [`verify.no_test_paths`](config.md#verifyno_test_paths) does not cover. Package `verify.checks` run in the package directory, and only for the packages a change touches: the staged files for `pre-commit`, the files between the remote and local commit of each pushed branch for `pre-push`. A changed file outside every package path (a lockfile, root configuration, docs) runs every package. So does a change set git cannot name: a new branch, a remote commit missing locally, or `gin evidence run`. A known but empty change set runs no package checks. The hook prints one `gin <hook>: skipped <path>, ... (no changed files)` line naming the packages it leaves out. Commands stop at the first failure and print its output. Empty `verify.checks` exits 0 with a notice. Git's own `GIT_DIR`, `GIT_INDEX_FILE` and similar variables are removed before the commands run. `git commit/push --no-verify` is blocked by the safety hook. A passing `pre-push` on a tree with no tracked changes is recorded for [`evidence check`](#gin-evidence). When such a record for the pushed tree already covers every command the hook would run, `pre-push` prints a notice naming the record time and exits 0 without running them again. A record file it cannot read is reported and the commands run. With `verify.run_at: host`, `pre-push` prints a notice that the host CI runs the tests, runs nothing, records nothing, and exits 0. When every file between the remote and local commit of the pushed branches lies under `verify.no_test_paths`, `pre-push` prints a notice naming those paths, runs nothing, records nothing, and exits 0.

Exit codes: install 0 installed or chained, 1 occupied, 2 hooks directory missing (with `--all-repos`, the worst repository); `--all-repos` 1 outside a workspace; run 0 pass, otherwise the failing command's exit code.

## `gin evidence`

```
gin evidence run [--repository DIR]
gin evidence check [--commit SHA] [--repository DIR] [--json]
```

When every verify command it ran passes on a tree with no tracked changes, `hooks run pre-push` or `evidence run` appends a `checks.passed` event (workflow id `checks`; payload `tree`, `hook`, `commands`) to `.agent-workflow/runtime/events.jsonl` in the main checkout. `commands` lists exactly the commands that ran. `evidence run` runs the checks of every package, but the hook runs only those of the packages the push touches ([rule](#gin-hooks)), so a hook record may cover only those packages. A record that cannot be written prints a warning and never changes the exit code. `pre-commit` records nothing, because it runs no `test`.

In a workspace child, or a worktree of one, `run` and `check` without `--repository` act on that checkout and its entry's `verify.checks`. `check` reads the record from the parent's event log, where the child's `pre-push` hook writes it. An explicit `--repository` keeps its meaning.

`run` runs the `pre-push` verify commands on the checked-out commit; with `verify.run_at: host` it runs nothing and exits 0. With `verify.run_at: track`, the `review` skill runs it before each review request (with the ledger, after `checkpoint`). It refuses with exit 2 when a tracked file differs from `HEAD`. Like the hook, it exits 0 without rerunning when a record for the same tree already covers the commands.

`check` finds the newest record for the tree of `--commit`, or of `HEAD` when no tracked file differs from it, whose commands include `test` or `<package>:test`. It prints the record, or why none matches; `--json` prints `{"record": {"tree", "hook", "commands", "recorded_at"} | null, "reason"}`. The reviewer reruns the tests only when it exits 1.

Exit codes: `run` 0 pass, 2 tracked changes, otherwise the failing command's exit code; `check` 0 a record matches, 1 none does.

## `gin reviewer`

```
gin reviewer --base SHA --implementer PROVIDER --model MODEL [--effort EFFORT] [--repository DIR] [--json]
```

Called by the `review` skill to pick the reviewer; you do not need to run it. `--model` and `--effort` are the implementer's final route, including any escalation, in the implementer's [catalog](config.md#models); a value outside that catalog exits 2. A diff since `--base` that changes anything but documentation (`*.md` or `docs/`, excluding `skills/`) raises the weakest model of a multi-model catalog to the next one. `reason` then reads `non-docs files changed`.

The reviewer runs on the main harness. It keeps the route when the main harness is the implementer; otherwise it gets the route mapped from the implementer's catalog: the model at the same relative position in the main harness's catalog, and the same effort when that catalog lists it, otherwise the effort at the same relative position. `actor_id` is `reviewer:<harness>`, or `reviewer:<harness>:session-<id>` (a fresh session) when the harness is also the implementer. Always prints the route document `{"model", "effort", "reason", "warnings", "routes": [{"provider", "model", "effort", "actor_id"}]}`; `--json` changes nothing. `--tier` was removed in 2.9 and exits 2 as an unknown option.

Exit codes: 0 routes printed; 2 bad `--base`, an invalid config, an unknown harness, a model or effort outside the catalog, or an unknown option.

## `gin routes`

```
gin routes resolve --workflow-id ID --tracks FILE [--repository DIR] [--json]
gin routes dispatch --workflow-id ID --task-id ID [--escalate REASON] [--repository DIR] [--json]
```

Both actions always print JSON; `--json` is accepted and changes nothing.

`resolve` resolves execution routes for plan tracks. `FILE` is a JSON list of tracks, each `{"task_id", "provider_role", "model", "effort"}`, where `model` and `effort` come from the main harness's [catalog](config.md#models) and `effort` is left out or `null` when the catalog lists no efforts. Every track goes to the main harness at its model and effort. It prints `{"workflow_id", "main_harness", "routes", "diagnostics", "warnings", "manifest"}`. `warnings` names the strongest model when two or more tracks all route to the last model of a catalog with two or more models; the exit code does not change. On success, it writes the assignment manifest to `.agent-workflow/runtime/assignments/<workflow-id>.yaml`: per track, `requested` (role, model, effort), `resolved`, `fallback`, and `escalations`.

`resolve` writes nothing, lists every diagnostic, and exits 2 when the workflow id is unsafe or any track has one of these problems:

- an unknown role;
- a missing or duplicate `task_id`;
- a model or effort outside the catalog, or an effort for a catalog without efforts;
- a `reasoning` field and no `model`; `model` and `effort` replace `reasoning`.

`dispatch` prints the current route of one track from the manifest, `{"task_id", "provider", "model", "effort", "escalated"}`, and appends a `route.dispatched` event with that route to `.agent-workflow/runtime/events.jsonl` in the main checkout. `--escalate REASON` first moves the track one step up its provider's catalog: the next model at the same effort, or the next effort at the strongest model. It writes the new route and an `escalations` entry (`from`, `to`, `reason`) to the manifest. At the strongest model and highest effort it prints `{"status": "human_decision_required", ...}`, changes nothing, and exits 2.

Exit codes: 0 all routes resolved and manifest written, or a route printed; 2 unresolved tracks, a missing or invalid manifest, a track missing from it or without a resolved route, an invalid configuration, an unknown provider, or a manifest route outside its provider's catalog on `--escalate`, nothing left to escalate to, or invalid arguments.

## `gin paths`

```
gin paths [--json]
```

Prints the path of the directory holding `workflow_core` (`{"lib_dir": "..."}`) for external tools and extension launchers. It always prints JSON; `--json` changes nothing.

Exit codes: 0 ok.

## `gin version`

```
gin version [--repository PATH] [--format text|json] [--hook]
```

Compares the installed `gin` with the project's [`.ginrc`](config.md#ginrc), found as the refusal finds it. Text output prints `gin <installed>`. When there is a `.ginrc`, it adds `project: <pin> (<path>)` and `compatible: yes` or `no`. An invalid `.ginrc` shows `project: invalid (<path>)` and `compatible: no`. Then it prints `gin-qa <version>` when it finds the companion CLI on `PATH`. A companion that is missing or fails is left out.

`--format json` prints `{"installed", "required", "path", "status", "compatible", "companions"}`. `status` is `none` (no `.ginrc`), `compatible`, `older`, `newer_major`, or `invalid`. `compatible` is `true` for `none` and `compatible`, so it is `true` without a `.ginrc`. `companions` maps each CLI found to its version.

`--hook` is for session-start hooks. It prints nothing when the versions are compatible or there is no `.ginrc`. Otherwise it prints the refusal message without `error: `, followed by ` Tell the user before any other work.`, on one line. It runs no other program, loads no configuration, and prints nothing when `.ginrc` cannot be read.

Exit codes: 0 compatible or no `.ginrc`; 1 otherwise. `--hook` always exits 0.

## `gin goal`

```
gin goal --workflow-id ID [--repository PATH] [--lane NAME]
```

Prints a Claude Code `/goal` for the epic recorded by `orchestration-ready`. The goal lists the open tracks in dependency order, leaving out every track labelled `human-gate` and every open track that depends on one. The condition is checkable from durable state the agent shows with commands: those tracks are closed in Beads (`gin task show`), `gin state --workflow-id ID --format json` shows `implementation_complete` satisfied. With the review ledger on (`project.review_ledger`, default only in the `strict` preset), the condition adds that each track's `python3 review-ledger.py status --bead-id <id>` shows an approved state (`review-approved` or later) or the track is listed in `review_waivers`; with it off, that clause is left out, because no ledger or waiver exists to show. It has no turn limit. A standalone bead is its own single track. When no open track is left for the agent, it prints a `No goal:` line instead, which names the human-gate tracks when any wait.

In team mode the goal covers only the tracks assigned to you. `--lane NAME` picks one lane and also covers its unassigned tracks; outside team mode it exits 1 with `--lane needs team mode`. The condition then drops the `implementation_complete` clause and requires that `git status -sb` in each lane's worktree shows the branch is not ahead of `origin`. A track that depends on an open `external:` placeholder is left out, and the goal says `Do not start <beads>: they wait for another lane to merge.` Next to the sentence `Do not start <beads>: they need a human.`, two more `No goal:` lines exist: `No goal: <member> has no open track in epic <epic>.` (or `in lane <name> of epic <epic>`), and `No goal: every open track of epic <epic> assigned to <member> waits on a human or on another lane to merge: <beads>.` A lane bead is no track: when you have a lane bead to plan and no open track, it prints `No goal: lane <name> has no tracks yet; run /plan for it.` for each such lane.

Exit codes: 0 ok; 1 no epic recorded for the workflow, or the task backend is unavailable.

## `gin commit`

```
gin commit <path>... -m <message> [--branch <name>] [--format text|json]
```

`gin commit` commits only the named files and directories without pushing.

Before any change, the command checks every input.
The message must be non-empty after trimming whitespace.
Each path must exist on disk or be tracked in the git index.
All paths must resolve inside one git repository.
A detached `HEAD` or invalid branch name exits 2 without modifying repository state.

When there are no changes under the paths, the command creates no branch and prints that there is nothing to commit.
When the current branch is `main`, `master`, or the workspace entry `default_branch`, it creates a new branch before committing.
The new branch name uses `--branch` when specified, or `gin/<slug>-<YYYY-MM-DD>` with an incrementing numeric suffix if the branch exists.
Other staged or unstaged changes outside the named paths remain in the working tree.
The command stages and commits only the named paths and never calls `git push`.

Exit codes: 0 on success or when there is nothing to commit; 2 on usage errors or failed checks. A failing git hook makes `git commit` fail. `gin commit` exits with git's exit code, not the hook's own status.

Output: text prints committed file count, branch, commit SHA, committed paths, and `Not pushed.`. JSON output returns `{"repository", "branch", "created_branch", "commit", "files", "pushed"}` or `{"repository", "branch", "created_branch", "nothing_to_commit", "files", "pushed"}`.

## `gin workspace`

```
gin workspace add PATH --url URL [--shape SHAPE] [--frozen] [--default-branch BRANCH] [--check NAME=COMMAND ...] [--repository DIR] [--json]
gin workspace clone [--repository DIR] [--json] [--all | PATH ...]
gin workspace status [--repository DIR] [--json]
```

A workspace is a parent repository whose `workspace.repos` lists child repositories ([configuration](config.md#workspace)). `add` records a repository entry in `workspace.repos` of the parent repository and writes it through setup configuration. `add` rewrites `.agent-workflow/config.yaml` without its comments. It validates the entry, refuses duplicate or nested paths, and prints the clone command to run next.

`clone` clones the named entries, or every entry with `--all`, at their manifest paths from their `url` and `default_branch`. A `frozen` entry is cloned with `--depth 1`. An entry already present is reported as `present`. When `--branch` fails because the remote has no branches yet, it clones without it, points `HEAD` at `default_branch`, and reports the row with `"empty": true` and a note that the first commit creates the branch. Each newly cloned path gets a `/<path>` line in the parent `.gitignore`.

`clone` installs the verify hooks when an entry has `verify.checks`. In team mode, it installs the commit-msg hook when the clone has `.githooks/commit-msg`. Like `gin hooks install`, it sets the local `core.sshCommand` keepalive in a clone with verify hooks. Each newly cloned row gets `hooks` with each hook's status (`installed`, `unchanged`, `chained`, `active`, `occupied`, `missing`, or `error`). Text mode prints `<path>: <hook>: <state>`. Problems are printed on stderr and never change the exit code. No `hooks` key is included for `present`, frozen, or `beads` rows or when nothing was installed.

`status` prints one line per entry: path, `present` or `missing`, branch, `clean` or `dirty`, and `frozen`. With `--json` each row has `path`, `present`, `branch`, `dirty`, `frozen`, `checkout` (the absolute checkout path, also when missing), and `commit` (the `HEAD` sha, `null` when missing or unreadable). `clone` and `status` run from anywhere inside the workspace, including a child repository.

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

## `gin-qa`

The optional `gin-qa` plugin adds its own CLI with `gin-qa cases {plan,next-id,pin,result,bug,to-manual,new,split,renumber,check,export,due}`, `gin-qa e2e {init,plan,pin,run,check,export}`, `gin-qa tests {plan,pin,check,run}`, `gin-qa runs export [--capability CAP] [--case TC-ID] [--since YYYY-MM-DD]`, and `gin-qa report [capability] [--out DIR] [--zip]`. Exit codes: 0 ok; 1 findings; 2 usage or environment error. `gin-qa e2e init [--base-url URL] [--install]` also writes `playwright.config.ts` when the Playwright folder has none. That folder is `e2e` in the [QA home](../guides/qa.md#the-qa-home), or the repository root for an existing root setup; an invalid URL exits 2 and writes nothing. It adds the evidence folder to `.gitignore`. On an existing `evidence.ts` without `ariaSnapshot`, it merges the step snapshots when the file matches the template, and otherwise prints a line to merge by hand and leaves the file. `gin-qa cases next-id CAP` prints the lowest number free in the capability (a number an e2e spec or a test marker still names stays taken); `gin-qa cases renumber CAP [--dry-run]` closes the gaps to 001..N and rewrites the case files, e2e specs, test markers, and the e2e evidence of the renamed cases, or exits 1 and writes nothing on a flat file, a duplicate, an orphan spec or marker, an uncommitted file, or an existing target.

`--install` first reads `package.json` in the Playwright folder; a missing or invalid file, or a `scripts` that is not an object, exits 2 before anything changes. It then runs the install commands for the package manager picked by the nearest lockfile (`pnpm-lock.yaml`, `yarn.lock`, `package-lock.json`; npm when none), looked up from the Playwright folder up to the repository root and never above it. The commands run in the Playwright folder: they add `@playwright/test`, unless it is already installed, and run `playwright install chromium`. It adds `"e2e": "playwright test"` to `scripts` when missing. A manager not found or a failed command exits 2 and names the commands to run by hand. Without the flag, `init` only prints those steps. `gin-qa e2e plan` and `gin-qa tests plan` exit 2 when the capability is a TC-ID, and name its capability.

### `gin-qa cases check`

Reports problems in the case files: structure, IDs, the `REQ:` or `Source:` fields, case files that match `artifacts.test_globs`, and, in the SDD layout, missing, stale, and obsolete cases. A `Checked:` line that is not 8 hex characters, or has no `Result:` line, is a finding (`Checked must be 8 hex characters`, `Checked: needs a Result: line`). A `- Regression:` line under `## Manual runs` of the guidelines with a value other than `none`, `high`, or `high+medium` is a finding (`<guidelines>:<line>: Regression must be none, high, or high+medium`). When the guidelines file has a `## Types` section, it also reports each entry that is not `` - `<type>` `` optionally followed by `:` and a description, a section that lists no types, and each case whose type is not listed (`<file>:<line>: <TC-ID>: type '<type>' is not listed under '## Types' in <guidelines>`). Guidelines without the section accept any type. Exit 0 prints `ok`; exit 1 lists the findings.

### `gin-qa cases result`

`gin-qa cases result <TC-ID> <status> [--run REF] [--bug ID|none] [--actor ID] [--evidence REF]...` is the only command that writes the `Result`, `Run`, `Bug`, and `Checked` lines. `Checked` is a stamp of the case as recorded: its content and its pinned requirements (or its `Source`). Each call rewrites it. `status` is `passed`, `failed`, `blocked`, or `not run`. `--run` sets the `Run` line; without it the line is removed. `--bug` sets the `Bug` line, `--bug none` removes it, and without it the line stays.

Each call first appends a run record to the [run history](#gin-qa-runs-export), then writes the case file. `--actor` names who recorded the result (default `git config user.email`, else `unknown`); the repeatable `--evidence` lists its evidence. Both go into the run record only. A run record that cannot be written exits 2 and leaves the case file unchanged.

Exit 2, writing nothing, when the ID does not exist, the status is not one of the four, `--run`, `--bug`, `--actor`, or `--evidence` is empty or holds a non-printable character, or the case files have a finding that names the case.

Output: text `TC-AUTH-001 passed`; JSON `{"tc", "result", "run", "bug", "file"}`.

### `gin-qa cases bug`

`gin-qa cases bug <TC-ID> --actual TEXT [--evidence REF]... [--external-ref REF] [--discovered-from BEAD] [--run REF] [--actor ID]` records `failed` on a case of any type and files a bug bead for it.

- The `failed` result appends a run record whose `evidence` holds the `--evidence` values; `--actor` works as in `gin-qa cases result`.
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

Images are attached to the bug with [`gin attach add`](#gin-attach), in the bug that is created or the open bug that is kept:

- Each `--evidence` file that exists inside the repository and has an image suffix is attached.
- When `--run` names an e2e run folder, the screenshot of each failed step of the case's results there is attached, with the case and step recorded.
- The bug's Evidence section lists each attached image as `![label](attachment:<sha256>)` followed by a `local: <path>` line. A kept bug gets `attachment:<sha256>` values in its `Re-run` line.
- A problem with an image prints `warning: ...` on stderr and never stops the bug; the local path stays in the Evidence section.
- The JSON result gains `attachments` (the `sha256` values) and `warnings`.

Output: text `TC-AUTH-001 failed gw-12`; JSON `{"tc", "bug", "epic", "created", "appended", "file"}`. `appended` is true when the result went into the notes of an open bug.

### `gin-qa cases new`

`gin-qa cases new <capability> --type TYPE --title TITLE (--req REQ-ID... | --source PATH#HEADING)` writes `<TC-ID>-<slug>.<type>.md` under `cases/<capability>/` of the [QA home](../guides/qa.md#the-qa-home) (default `qa/cases/<capability>/`) with the lowest free ID. The case holds the `REQ` field with the requirement's current `hash8` (SDD layout, `--req` repeated for several requirements, a repeated one pinned once) or the `Source` field (legacy layout, `--source`), `Priority: medium`, and the four sections empty. `gin-qa cases check` reports the case until its steps and expected results are written.

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

Each case in `gin-qa cases export --format json` adds `result` (`not run` without a `Result:` line), `run` and `bug` (empty strings when absent), `moved_from_e2e` (`{"date", "reason"}`, or `null`), `test_data` (a list), `legacy` (the references of the `Legacy:` line, a list), `checked` (the `Checked:` stamp, an empty string when absent), and `effective_result`. `effective_result` equals `result` unless a recorded `passed`, `failed`, or `blocked` is `outdated`: the stamp no longer matches the case, or, in the SDD layout, a pinned requirement changed or no longer exists. A result without a stamp is outdated only by the requirement check; the legacy layout skips that check. `gin-qa report` shows `effective_result`, and `Last recorded` (`result`) when they differ.

### `gin-qa runs export`

`gin-qa runs export [--capability CAP] [--case TC-ID] [--since YYYY-MM-DD] [--format text|json]` lists the run history: one record per result that `cases result`, `cases bug`, `e2e run`, and `tests run` recorded. It exits 0 whatever it finds, and 2 on a usage error such as a `--since` that is not a date.

Each result is appended as one JSON line to `runs/<yyyy-mm>/<actor>.jsonl` next to the cases folder (`qa/runs` by default). The actor is lowercased and each run of other characters than `a-z`, `0-9`, `.`, `_`, `-` becomes `-`. One file per tester and month means two testers never write the same file. The first record adds `/<runs folder>/** merge=union` to `.gitattributes`, so one tester's appends on two branches merge in a local `git merge`. A hosted merge button may not apply that driver. `gin-qa cases renumber` leaves the records unchanged, so a record keeps the case ID it ran under.

JSON output is `{"runs": [...], "problems": [...]}`. `runs` is sorted by `at`, then file, then line; the filters combine, and `--since` keeps records on or after that UTC date. A line that is not a record adds `<file>:<line>: <reason>` to `problems` and is skipped. Text output prints one line per record, `<at> <case> <result> <actor> <run>`, then the problems, or `no runs`. Keys are added in later versions, never renamed or removed.

| Key | Meaning |
|---|---|
| `actor` | `--actor`, else `git config user.email`, else `unknown` |
| `at` | UTC time of the record, `YYYY-MM-DDTHH:MM:SSZ` |
| `bug` | the case's `Bug:` after the result, `""` when none |
| `capability` | the case's capability, as in `gin-qa cases export` |
| `case` | the TC-ID |
| `evidence` | `--evidence` values of `cases result` and `cases bug`; `<run folder>/<tc-id>` for `e2e run`, with the TC-ID in lowercase; the run folder for `tests run`; `[]` when none |
| `hash8` | the case's `hash8` when the result was recorded, as in `gin-qa cases export` |
| `result` | `passed`, `failed`, `blocked`, or `not run` |
| `run` | the case's `Run:` after the result, `""` when none |

### `gin-qa cases due`

`gin-qa cases due <capability> [--change CHANGE] [--all] [--format text|json]` lists the manual cases of the capability to run, in ID order, each with a reason:

- `todo`: the effective result is `not run`, `outdated`, `failed`, or `blocked`. With `--change`, only for cases that pin a requirement the change added or modified (removed ones do not count).
- `regression`: not `todo`, and the case's `Priority:` is in the level of the `- Regression:` line under `## Manual runs` of the guidelines: `none` (default, also when the line or file is missing) lists nothing, `high` lists `high`, `high+medium` lists both. The comparison ignores case and surrounding spaces.
- `all`: with `--all`, every manual case, whatever its result.

Text output prints one `<TC-ID> <reason> <effective result> <title>` line per case, or `nothing due`. JSON output is `{"capability", "change", "cases"}`, where `change` is `null` without the flag and each case is `{"id", "title", "reason", "effective_result", "priority"}`. Exit 0, also when nothing is due or the capability has no manual cases; exit 2 for a usage or environment error, such as an unknown `--change`. See [manual runs](../guides/qa.md#manual-runs-gin-qarun).

`gin-qa e2e run` records each case's result in its case file, the worst over its Playwright projects: `failed`, then `blocked`, then `passed`. `--actor ID` works as in `gin-qa cases result`; each recorded case appends a run record whose `evidence` is `<run folder>/<tc-id>`. A case with no result folder, or an invalid `result.json`, is `blocked`. Its JSON output lists them under `recorded` as `[{"tc", "result"}]`. A recording error is listed under `findings` and does not stop the other cases.

In a workspace, `run.json` of `gin-qa e2e run` and of `gin-qa tests run` also has `checkouts`: one `{"path", "branch", "commit", "dirty"}` row per cloned repository, read from `gin workspace status`. It states the checkout state of the machine that ran the tests, not what an environment deployed. When that command fails, gin-qa prints `gin-qa: checkouts not recorded: <reason>` on stderr, leaves the key out, and the run goes on. Outside a workspace the key is absent.

### `gin-qa tests`

`gin-qa tests` plans, pins, checks, and runs the tests of the automated types declared under `## Automated types` in the guidelines file (`qa.guidelines`). One `### <type>` per type, with `- Tests:` (backticked globs, relative to the repository root, never absolute or containing `..`) and `- Run:` (one backticked command that holds `{junit}` and optionally `{files}` as a whole argument). `e2e` and `manual` cannot be declared. A declaration error is a finding of `check` and makes the other subcommands exit 2.

- `plan [capability] [--type T]`: `missing` (a case of the type with no `TC: <TC-ID>@<hash8>` line in the type's test files). The other rows are `stale` (a marker whose hash8 is not the case's), and `orphan` (a marker of a case that is gone or of another type). `--format json` adds `types` and `guidelines`.
- `pin <TC-ID>...`: rewrites the hash8 of every marker of each case; writes nothing when any ID fails.
- `check [--type T]`: the declaration errors when there are any; otherwise the `plan` rows, as findings.
- `run --type T [TC-ID|capability ...]`: runs the command from the repository root, without a shell, into `evidence/<UTC stamp>-<T>/` of the QA home (`run.json`, `junit.xml`), which it adds to `.gitignore`. `{junit}` becomes the JUnit file's path and `{files}` the test files of the selected cases. A JUnit test case whose name or classname holds the TC-ID (in any case, `_` read as `-`) belongs to that case. The case records `failed` (a failure or error), `blocked` (skipped), or `passed`, the worst over its tests, and `blocked` with a finding when none ran. When `junit.xml` is missing or unreadable, every selected case records `blocked` with one finding. `--actor ID` works as in `gin-qa cases result`; each recorded case appends a run record whose `evidence` is the run folder. `--format json` prints `{"run", "exit", "findings", "recorded"}`. Exit: the command's non-zero exit, else 1 on findings, else 0; a command not found exits 2.

### `gin-qa report`

`gin-qa report [capability] [--out DIR] [--zip] [--format text|json]` writes `index.html` and a copy of each screenshot it shows into a new folder, `evidence/report-<UTC stamp>/` of the QA home by default (`-2`, `-3`, ... when that folder exists). `--out DIR`, relative to the repository, must be missing or empty. `--zip` also writes `<folder>.zip` next to the folder. The command prints the path of `index.html`, then the zip path with `--zip`; `--format json` prints `{"report", "zip", "cases", "moved", "screenshots", "missing_evidence"}`, where `zip` is `null` without the flag and `moved` counts the cases with a `Moved from e2e:` line. A report under the evidence folder adds that folder to `.gitignore`. A run folder named by a case's `Run` line that cannot be read is listed under `missing_evidence` and on stderr, and the report is still written. No test cases in scope, an unknown capability, or a non-empty `--out` exit 2 and write nothing. A `Run` folder written by `gin-qa tests run` is shown as text, not read as e2e evidence.
