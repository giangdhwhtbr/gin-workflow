# Team workflow guide: monorepo modernization walkthrough, milestones instead of sprints, default price catalog

Workflow: team-workflow-guide
Status: confirmed by the user on 2026-11-01.

## Goal and scope

A team that inherits a legacy application can follow one guide from "we have the old code" to "milestone 1 shipped and reviewed", with the prompt to paste at each stage, what it returns, which gate applies, and the mistakes to avoid. The guide is the existing brownfield walkthrough, rewritten around a Java JSP modernization in a monorepo, with the stages it lacks today: repository strategy, the roadmap overview, milestone planning, and the milestone review with spill-over.

The guide can only teach one time-boxing concept, so the `sprint:<name>` label goes away and milestones take its place everywhere: the roadmap skill, `usage report`, and the `progress` and `report` skills. Two small gaps that the milestone flow exposes are closed in the same change: `milestone close` records a reason, and `milestone move` leaves a trace on the epic so a later analysis can count carry-overs.

A cost report that shows `-` for every model because nobody wrote `.agent-workflow/usage-prices.yaml` defeats the budget feature. The plugin ships a default price catalog for the Claude, OpenAI (Codex) and Gemini models that appear in logs, and the repository file only overrides it.

Out of scope: changes to the `gin-workflow milestone` schedule or JSON schema; a cross-repository dependency view (gin-console already has the Dependencies page and the milestone graph); milestone analytics in gin-console (tracked as `gin-console-unj`); migrating existing `sprint:` labels (none exist outside tests); the `getting-started.md` flow beyond a link to the walkthrough; long-context, batch, fast-mode or regional price tiers.

## Requirements

### Documentation

- R1 `docs/starters/brownfield-modernize.md` gains a section "Repository strategy" that recommends one monorepo for the modernization, shows how to bring a legacy repository in with `git subtree add --prefix=<dir> <url> <ref>` and refresh it with `git subtree pull`, states why git submodules are not used (every checkout inside a submodule dirties the parent), names when a legacy repository stays separate (another owner's deploy pipeline, compliance, or size), and points to `monorepo`/`packages` with per-package `verify.checks` and `team.areas` by path. The section is the only home of this guidance; the walkthrough links to it.
- R2 `docs/starters/brownfield-walkthrough.md` is rewritten around one scenario: `shop-portal`, a Java 8 JSP and Struts monolith on Oracle, modernized behind a facade into a Spring Boot REST API and a React SPA, in one monorepo with `legacy/` (subtree), `services/api/`, `apps/web/` and `qa/`. The team keeps the five roles of today's walkthrough (`pm`, `ba`, `be_lead`, `be_dev`, `qe`) plus a `fe_dev`; areas are `legacy`, `api` and `web`. The `team:` block shown in the file validates against the schema (`gin-workflow setup configure` accepts it).
- R3 The walkthrough has these stages, in order, each with the headings Who, Prompt, You get, Gate or approval, Common mistakes, and a line "Put in the prompt:" naming the inputs that make the skill return a good result (goal, constraints, non-goals, capacity, dates): Repository and workspace setup; Setup and team setup; Survey the legacy system (`/tech-doc`); Roadmap overview (`/roadmap`, reading `gin-workflow task graph --all` or the gin-console Dependencies page, choosing what goes first); Milestone planning (`gin-workflow milestone create`, `/roadmap --milestone <id>`); Discuss an epic; Plan and orchestrate; Test cases; Execute (`team ready`, `team claim` and its lease, `team reassign` when a member is away); E2E; Ship (the gate proof written to the epic bead); Milestone review and spill-over; Solo variant. Every command and flag in the file exists in `docs/reference/cli.md`.
- R4 The "Milestone review and spill-over" stage shows, on the milestone's end date: `gin-workflow milestone show <id>` to list open epics and warnings, `milestone create` for the next milestone, `milestone move <open epics>... --to <next>`, `milestone close <id> --reason "<text>"`, `/gin-workflow:report --milestone <id>`, and `milestone kickstart <next>`. Its common mistakes include closing an unfinished epic so the milestone can close, and moving epics without a reason on the close.
- R5 `docs/roles.md`, `docs/guides/team.md`, `docs/reference/cli.md`, `docs/reference/skills.md` and `docs/guides/usage-report.md` say "milestone" where they say "sprint" today, and `docs/getting-started.md` links the walkthrough from its "Starters and guides" list. Each fact keeps one home.

### Roadmap skill

- R6 Step 7 of `plugins/gin-workflow/src/skills/roadmap/SKILL.md` (the `sprint:<name>` label) is removed.
- R7 In the `--milestone` section, estimating without a measured pace is defined: when `gin-workflow task list --label roadmap --type epic --status closed --json` returns no epic, the skill asks the PM for a day value per size (small, medium, large), applies one size per epic, and writes `Estimate:` lines marked as assumptions in the roadmap file.
- R8 The Adoption step proposes epics by dependency layer: epics with no open blocker first; an epic with an open blocker only when the blocker is also proposed; and the sum of proposed estimates stays within the milestone's working days (from `milestone show <id> --json`). The skill names the epics it left out and why.

### Usage report and progress by milestone

- R9 `gin-workflow usage report --milestone ID` replaces `--sprint NAME`. It selects the epics whose `parent` is `ID` and the rows whose `parent` is one of those epics. `--milestone` with a non-milestone id exits 2 with a message naming the id. `--sprint` is removed, not aliased.
- R10 The `progress` and `report` skills take `--milestone <id>`: `progress` lists the milestone's epics with `gin-workflow task list --parent <id> --all --json` and each epic's tracks; `report` passes `--milestone` through.

### Milestone close reason and move trace

- R11 `gin-workflow milestone close ID --reason TEXT` requires `--reason` (exit 2 without it) and passes it to `bd close --reason`. The open-epic refusal is unchanged.
- R12 `gin-workflow milestone move` appends `{"from": <previous parent or null>, "to": <target or null>, "at": <UTC timestamp>, "actor": <git user.email or "unknown">}` to the `milestone_moves` list in each moved epic's metadata (`bd update --set-metadata milestone_moves=<json>`), after the parent update succeeds. A metadata write failure is reported as a warning naming the epic; the move stands and the exit code is 0.

### Default price catalog

- R13 The plugin ships `plugins/gin-workflow/src/scripts/workflow_core/usage_prices_default.yaml` with the rows below (USD per million tokens, standard tier, Anthropic 5-minute cache writes, OpenAI cache writes at the 1.25x input rule its model pages state, Google cache writes 0 because Google bills cache storage per hour). Each row carries a comment with its source URL and the date 2026-11-01. The user's `.agent-workflow/usage-prices.yaml` overrides a default row by model id and adds any other model.

| Model id | input | output | cache_read | cache_write | Source |
|---|---|---|---|---|---|
| claude-fable-5-1 | 10 | 50 | 0.25 | 12.5 | platform.claude.com/docs/en/about-claude/pricing |
| claude-opus-5-5 | 4 | 20 | 0.20 | 5 | same |
| claude-opus-5 | 5 | 25 | 0.50 | 6.25 | same |
| claude-opus-4-8, claude-opus-4-7, claude-opus-4-6, claude-opus-4-5 | 5 | 25 | 0.50 | 6.25 | same |
| claude-sonnet-5-5 | 2 | 10 | 0.10 | 2.5 | same |
| claude-sonnet-5 | 2 | 10 | 0.20 | 2.5 | same |
| claude-sonnet-4-6, claude-sonnet-4-5 | 3 | 15 | 0.30 | 3.75 | same |
| claude-haiku-5-5 | 0.10 | 0.50 | 0.01 | 0.125 | same; prompts up to 100k tokens, the over-100k tier is 5x |
| claude-haiku-4-5 | 1 | 5 | 0.10 | 1.25 | same |
| gpt-6-astra | 10 | 50 | 1.0 | 12.5 | developers.openai.com/api/docs/models/gpt-6-astra |
| gpt-5.6-sol | 4 | 20 | 0.40 | 5 | developers.openai.com/api/docs/models/gpt-5.6-sol; promotional price through at least 2026-11-21 |
| gpt-5.6-terra | 2 | 12 | 0.20 | 2.5 | developers.openai.com/api/docs/models/gpt-5.6-terra |
| gpt-5.6-luna | 0.20 | 1.2 | 0.02 | 0.25 | developers.openai.com/api/docs/models/gpt-5.6-luna |
| gpt-5.4-mini | 0.75 | 4.5 | 0.075 | 0 | developers.openai.com/api/docs/pricing (no write price listed) |
| gpt-5.4-nano | 0.20 | 1.25 | 0.02 | 0 | same |
| gpt-5.3-codex | 1.75 | 14 | 0.175 | 0 | same |
| gpt-5.2 | 1.75 | 14 | 0.175 | 0 | same |
| gpt-5.1, gpt-5 | 1.25 | 10 | 0.125 | 0 | same |
| gpt-5-mini | 0.25 | 2 | 0.025 | 0 | same |
| gpt-5-nano | 0.05 | 0.40 | 0.005 | 0 | same |
| gemini-4-argon | 2 | 10 | 0.10 | 0 | ai.google.dev/gemini-api/docs/pricing; doubles from 2026-12-01 |
| gemini-3.1-pro-preview | 2 | 12 | 0.20 | 0 | same; prompts up to 200k tokens |
| gemini-3.8-flash, gemini-3.6-flash | 0.75 | 3.75 | 0.075 | 0 | same; doubles from 2027-01-01 |
| gemini-3.5-flash-lite | 0.30 | 2.5 | 0.03 | 0 | same |
| gemini-3.1-flash-lite | 0.25 | 1.5 | 0.025 | 0 | same |
| gemini-3-flash-preview | 0.50 | 3 | 0.05 | 0 | same |
| gemini-2.5-pro | 1.25 | 10 | 0.125 | 0 | same; prompts up to 200k tokens |
| gemini-2.5-flash | 0.30 | 2.5 | 0.03 | 0 | same |
| gemini-2.5-flash-lite | 0.10 | 0.40 | 0.01 | 0 | same |

`codex-auto-review` has no public price and stays unpriced.

- R14 `load_prices` returns the defaults overlaid by the repository file. A model id with no exact row matches the longest catalog key that is a prefix of the id followed by `-` or the end of the id (so `claude-sonnet-4-5-20250929` prices as `claude-sonnet-4-5`); no other fuzzy matching.
- R15 `usage report` and the summary document give each model a `price_source` of `default`, `repo` or `none`. `unpriced` and `unenforceable` keep their meaning for models with `none`.
- R16 `docs/guides/usage-report.md` describes the default catalog, its date, the override and the prefix rule, and says that prices change: the catalog is a convenience, not a billing source.

## User Stories

### US-1: Follow one guide from legacy code to the first milestone
As a tech lead starting a modernization, I want one walkthrough with the prompt for each stage, so that the team runs the same flow without reading every skill.

Acceptance criteria:
- The walkthrough contains the stages of R3 in that order, each with every heading of R3.
- The scenario, repository layout and `team:` block are those of R2, and the `team:` block passes `gin-workflow setup configure`.
- Every `gin-workflow` command in the file appears in `docs/reference/cli.md` with the flags used.
- `docs/getting-started.md` links the walkthrough.

### US-2: Plan a three-week milestone from the roadmap
As a PM, I want the agent to propose which roadmap epics fit milestone 1, so that I plan from dependencies and capacity instead of guesswork.

Acceptance criteria:
- With no closed roadmap epic, `/roadmap --milestone <id>` asks for day values per size and marks the resulting `Estimate:` lines as assumptions (R7).
- The proposal lists unblocked epics first, includes a blocked epic only with its blocker, keeps the total within the milestone's working days, and names the epics left out (R8).
- The `sprint:` label is no longer written by the roadmap skill (R6).

### US-3: Close a milestone with spill-over
As a PM at the end of milestone 1, I want to carry unfinished epics to milestone 2 and close milestone 1 with a reason, so that the carry-over is visible later.

Acceptance criteria:
- `gin-workflow milestone close <id>` without `--reason` exits 2; with `--reason` the milestone bead's close reason is the given text (R11).
- After `gin-workflow milestone move <epic> --to <m2>`, the epic's metadata `milestone_moves` has one more entry with `from`, `to`, `at` and `actor` (R12).
- The walkthrough's spill-over stage runs these commands in the order of R4.

### US-4: Report cost and progress per milestone
As a PM, I want `report` and `progress` by milestone, so that one concept covers planning and review.

Acceptance criteria:
- `gin-workflow usage report --milestone <id>` covers the milestone's epics and their tracks; `--sprint` is rejected as an unknown argument (R9).
- `/gin-workflow:progress --milestone <id>` and `/gin-workflow:report --milestone <id>` are documented in their skills and in `docs/reference/skills.md` (R10, R5).

### US-5: See costs without writing a price file
As a developer running `gin-workflow usage collect` for the first time, I want the common models priced by default, so that the report shows cost and the budget is enforceable.

Acceptance criteria:
- With no `.agent-workflow/usage-prices.yaml`, a summary for `claude-opus-5-5` tokens has a cost and `price_source: default` (R13, R15).
- A repository file row for `claude-opus-5-5` replaces the default and shows `price_source: repo`; a model in neither shows `price_source: none` and is listed under `unpriced` (R14, R15).
- `claude-sonnet-4-5-20250929` prices as `claude-sonnet-4-5` (R14).
- The catalog file's rows match the table in R13.

## Errors and compatibility

- `usage report --sprint` is removed. `argparse` rejects it; the message names `--milestone`. Existing `sprint:` labels on beads are left as they are and ignored.
- `milestone close` without `--reason` is a usage error (exit 2) like other usage errors of the command; an open-epic refusal stays exit 1.
- A failed `milestone_moves` metadata write never undoes a move: the move is the durable state, the trace is best effort, and the warning names the epic so the PM can add the note by hand.
- `load_prices` keeps raising `UsageError` for an invalid repository file; a malformed default catalog is a packaging bug and raises the same error naming the default file.
- The default catalog adds no dependency: it is read with the same YAML loader as the repository file.
- `gin-console` reads `milestone show --json`, whose schema does not change; `price_source` is a new key in the usage summary, which the console does not read.
- Installed snapshots pick up the new catalog and skills only after `install.sh` runs again.

## Testing

- `tests/workflow_core/test_usage.py`: `test_load_prices` covers defaults only, repository override, prefix match, and the invalid-file error; the sprint report test becomes a milestone report test (epic under a milestone bead, tracks under the epic, an unrelated epic excluded); the document shape test asserts `price_source`.
- `tests/workflow_core/test_usage_cli.py`: `usage report --milestone <id>` through the CLI; `--sprint` exits 2; `--milestone <non-milestone>` exits 2 with the id in the message.
- `tests/workflow_core/test_milestone_cli.py`: `close` without `--reason` exits 2; `close --reason` passes the reason to `bd close`; `move` appends to `milestone_moves` with `from`, `to`, `at`, `actor`; a failing metadata write keeps exit 0 and prints the warning.
- `tests/install_smoke_test.sh:181`: the built `progress` skill contains `--milestone` and no `sprint:`.
- Docs: a new `tests/workflow_core/test_walkthrough_docs.py` reads `brownfield-walkthrough.md` and asserts every `gin-workflow <command> <subcommand>` token it contains appears in `docs/reference/cli.md`; the catalog file is loaded by `load_prices` in a test to prove it parses and contains the ids of R13.
- Manual check after install: `gin-workflow usage report --since 2026-10-01` on this repository prices `claude-opus-5-5`, `claude-fable-5-1`, `claude-haiku-5-5` and the Codex `gpt-5.6-*` rows, and lists `codex-auto-review` under `unpriced`.
