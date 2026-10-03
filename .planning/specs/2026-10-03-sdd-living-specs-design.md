# SDD Living Specs (Sub-project F) — Design

Date: 2026-10-03
Status: awaiting user confirmation
Depends on:
- D (`.planning/specs/2026-10-01-best-practice-rules-design.md`, shipped as schema 2.5): project-over-plugin precedence pattern, installer copy of plugin data dirs, `setup doctor` suggestions.
Followed by: E (team mode) adds role-gated approval on top of the `spec_review: pr` flow defined here.

## Goal

A repository can keep its product requirements as a living, ID-addressable spec in git, change it through reviewable deltas, and trace every changed requirement to tests, while repositories that do not opt in keep today's behavior unchanged.

## Decisions

| Topic | Decision |
|---|---|
| Opt-in | `artifacts.layout: legacy \| sdd`, default `legacy`. Setup proposes `sdd` for greenfield; repos with `.planning/specs` or `.planning/plans` stay `legacy` until migrated. |
| Location | One `docs/` root: `docs/specs`, `docs/changes`, `docs/adr`, `docs/codebase`; every path configurable under `artifacts`. |
| Change folder | `docs/changes/<epic-id>-<slug>/`. `discuss` creates the epic bead right after the user confirms the design, so the folder name is final from the start. |
| Bead ↔ REQ | Bead ids keep the `bd` prefix and `<epic>.N` hierarchy. Track beads link requirements with `--spec-id <epic-id>-<slug>` (the change id, stable across archive; `bd list --spec <epic-id>` finds them) and one label `req:<REQ-ID>` per requirement. |
| Requirement format | `### REQ-<CAP>-<NNN>: <title>`, one SHALL/MUST statement, ≥1 `#### Scenario:` with GIVEN/WHEN/THEN bullets. EARS recommended in templates, not enforced. |
| ID allocation | Sequential per capability via `specs next-id`, scanning living specs and deltas in every local worktree and `refs/remotes`. `specs lint --against <base>` blocks duplicates; `specs renumber` repairs them. |
| Traceability | Automated tests carry the REQ-ID in the test name or a comment; manual/QE cases live in `tests.md`. Missing evidence warns under `easy`, blocks `verification-passed` under `standard`/`strict`. |
| Merge into living spec | `specs archive` runs at the start of `ship`, on the feature branch, before merge or PR. Deterministic and atomic; stops on base-hash conflict. |
| Spec approval | `artifacts.spec_review: chat \| pr`, default `chat`. `pr` pushes the change folder on `spec/<epic>-<slug>`, waits for the spec PR to merge, then records `requirement_confirmed`. Role checks belong to E. |
| Conventions | F ships templates (project override in `.agent-workflow/templates/`) and `specs lint`. Commit convention, commit-msg hook, PR template, and CODEOWNERS belong to E. |
| tech-doc | Kept. Under `sdd` it writes to `artifacts.codebase` using overridable templates; it also seeds living specs during migration. |
| Migration | Two phases: deterministic `specs migrate [--dry-run] [--force]`, then an optional AI-assisted, user-reviewed living-spec seeding in `/gin-workflow:migrate-specs`. |
| Schema | 2.6, with a defaults-only migration from 2.5. |

## Design

### 1. Configuration (schema 2.6)

New keys under `artifacts` (defaults shown):

```yaml
artifacts:
  layout: legacy            # legacy | sdd
  specs: docs/specs
  changes: docs/changes
  adr: docs/adr
  codebase: docs/codebase   # tech-doc output under sdd; legacy keeps .planning/codebase
  spec_review: chat         # chat | pr
  test_globs: ["**/test_*.py", "**/*_test.py", "**/*.test.*", "**/*.spec.*", "tests/**", "__tests__/**"]
  plans: .planning/plans    # existing; used by legacy only
```

- Schema: `layout` and `spec_review` are enums; path keys are non-empty strings; `test_globs` is an array of non-empty unique strings.
- Supported versions become `("2.3", "2.4", "2.5", "2.6")`; `_migrate_2_5_to_2_6` only bumps versions (defaults come from `BUILT_IN_DEFAULTS`). Launcher, CLI, registry, installers, smoke tests, and `examples/config.full.yaml` move to 2.6.
- A config without `layout` behaves exactly as today. Every existing test passes unmodified.

### 2. Setup and doctor

- `setup preset` on a `greenfield` project proposes `artifacts.layout: sdd` in the dry-run assignments, the same way D proposes `rule_packs`. The user accepts or edits before anything is written.
- Path conflict: under `sdd`, if `artifacts.specs` exists and contains no `spec.md` with a `### REQ-` heading, preset and doctor report `checks_details.sdd.conflict` with the path and suggest another `artifacts.specs` value.
- `setup doctor` on a `legacy` repo that has `.planning/specs` or `.planning/plans` adds a suggestion to run `/gin-workflow:migrate-specs`. Health is not affected.

### 3. Templates

- Plugin templates in `plugins/gin-workflow/src/templates/`: `proposal.md`, `spec.md`, `spec-delta.md`, `design.md`, `plan.md`, `tests.md`, `adr.md`, and `codebase/{OVERVIEW,STACK,INTEGRATIONS,ARCHITECTURE,STRUCTURE,CONVENTIONS,TESTING,CONCERNS}.md`.
- Project override: `.agent-workflow/templates/<same relative path>` wins over the plugin file.
- Placeholders: `{{epic}}`, `{{slug}}`, `{{date}}`, `{{title}}`, `{{capability}}`.
- Installers copy `templates/` into each platform dist and the launcher, like `rules/`. Lookup order matches `plugin_rules_dir()`: `here.parent/templates`, then `here.parent.parent/templates`.

### 4. File formats

Change folder `docs/changes/<epic-id>-<slug>/`:

| File | Sections | Owner (team) |
|---|---|---|
| `proposal.md` | Why, What Changes, Capabilities Affected, Non-goals, Success Criteria | BA |
| `spec-delta.md` | `## ADDED`, `## MODIFIED`, `## REMOVED`, each holding requirement blocks | BA |
| `design.md` | Architecture, Data Flow, Error Handling, Testing | Lead |
| `plan.md` | `plan-schema.md` format; each track adds `Requirements: REQ-…` in Metadata | Lead |
| `tests.md` | table `\| TC \| REQ \| type \| evidence \|` | QE |

Living spec `docs/specs/<cap>/spec.md`: `# <Capability>`, `## Purpose`, `## Requirements`, then requirement blocks. `docs/specs/README.md` lists capabilities.

Requirement block:

```markdown
### REQ-AUTH-003: Lock account after failed logins
The system SHALL lock an account for 15 minutes after 5 failed logins.

#### Scenario: fifth failure locks
- GIVEN a user with 4 failed logins
- WHEN the next login fails
- THEN the account is locked and the user sees "Account locked"
```

- ID regex `^REQ-([A-Z][A-Z0-9-]*)-(\d{3,})$`; `<CAP>` is the capability folder name (`[a-z][a-z0-9-]*`) upper-cased. The trailing `-NNN` is the number; everything between `REQ-` and it is the capability.
- A block runs from its `### REQ-` heading to the next `###` or `##` heading or end of file.
- Block hash: sha256 of the block text with trailing whitespace stripped per line and leading/trailing blank lines removed.
- In `spec-delta.md`, every `MODIFIED` and `REMOVED` block carries `<!-- base: <hash> -->` on the line after its heading, the hash of the living block it replaces. `REMOVED` blocks also carry a `Reason:` line. One delta may touch several capabilities.

### 5. CLI: `gin-workflow specs`

Module `workflow_core/specs.py` (parse, lint, ids, archive, migrate) plus `workflow_core/specs_trace.py` (trace, status). All subcommands take `--format text|json`. Exit 0 success, 1 content findings (`path:line: message` list), 2 usage error, missing config, or wrong layout. Every subcommand except `migrate` requires `layout: sdd`; `migrate` requires `layout: legacy`.

| Command | Behavior |
|---|---|
| `specs new <slug> --epic <id> [--title T]` | Create `<changes>/<epic>-<slug>/` from templates. Refuse if it exists. |
| `specs next-id <cap>` | Print the next free `REQ-<CAP>-NNN` (3-digit zero padded, max+1). Scans `<specs>` and `<changes>/*/spec-delta.md` in the current tree, every `git worktree list` path, and `git grep` over `refs/remotes/*` after `git fetch --quiet`. Fetch failure or no remote prints a warning to stderr and continues. |
| `specs lint [--change ID] [--against BASE]` | Without `--change`: all living specs. With it: that change folder. Checks: block structure, SHALL/MUST present, ≥1 scenario with GIVEN/WHEN/THEN, `<CAP>` matches an existing capability folder or a capability the delta adds, unique IDs, `MODIFIED`/`REMOVED` target exists with a `base:` hash, `REMOVED` has `Reason:`, `ADDED` IDs unused in living specs. `--against BASE` also checks `ADDED` IDs against living specs and open deltas at `BASE`. |
| `specs trace --change ID` | For every `ADDED`/`MODIFIED` REQ: evidence = files matched by `test_globs` (from `git ls-files`) containing the ID as a word, plus `tests.md` rows with that REQ and non-empty evidence. Output per REQ: `covered` with sources, or `missing`. Exit 1 when any REQ is missing. |
| `specs archive --change ID` | Validate everything first: lint passes, every `MODIFIED`/`REMOVED` base hash equals the current living block hash. Then apply `ADDED` (append; create `spec.md` from template for a new capability and add it to README), `MODIFIED` (replace block), `REMOVED` (delete block), and `git mv` the folder to `<changes>/archive/<YYYY-MM-DD>-<epic>-<slug>/`. Any failure before writing leaves the tree untouched. |
| `specs renumber OLD NEW --change ID [--against BASE]` | Replace the ID in the change folder, in test files changed on the branch (`git diff --name-only BASE...HEAD` filtered by `test_globs`), and swap `req:OLD` for `req:NEW` on child beads of the epic via `bd`. Refuse if `NEW` is taken. `BASE` defaults to the merge-base with `main` or `master`. |
| `specs status --change ID` | With `spec_review: pr`: find the PR for head `spec/<epic>-<slug>` with `gh pr list --state all --json url,state,mergeCommit`; report `none`, `open`, `merged <url> <sha>`, or `closed`. `gh` missing reports `gh unavailable` with the manual `record` command. |
| `specs migrate [--dry-run] [--force]` | See §8. |

### 6. Stage integration

Each stage `SKILL.md` gains at most two lines of the form "With `artifacts.layout: sdd`: …"; the detailed procedure lives in `references/sdd-layout.md`, referenced conditionally so it is not counted in the stage chain (same pattern as `gin-debugging`). Under `legacy` nothing changes.

- **discuss**: after the design is confirmed: `bd create --type epic` → `specs new <slug> --epic <id>` → write `proposal.md`, `spec-delta.md` (IDs from `next-id`), `design.md` → `specs lint --change <id>`. Then:
  - `spec_review: chat`: user confirms → `record requirement-confirmed --workflow-id <epic> --evidence <change folder>`.
  - `spec_review: pr`: commit only the change folder on `spec/<epic>-<slug>`, push, ask approval to create the PR, create it, return `awaiting_spec_review` without recording. A later `/gin-workflow:discuss <epic>` or `/gin-workflow:workflow` runs `specs status`; on `merged` it records `requirement_confirmed` with the PR URL and merge commit as evidence. Implementation then branches from the updated base.
- **plan**: writes `<change>/plan.md`; each track lists `Requirements:`; self-review fails if an `ADDED`/`MODIFIED` REQ maps to no track.
- **orchestrate**: reuses the existing epic as parent; track beads get `--spec-id <epic>-<slug>` and `--labels req:<id>,…` from their `Requirements:`.
- **execute / developer agent**: new or changed tests carry the REQ-ID in the test name or a comment.
- **review**: checks that each scenario of the track's REQs has a test.
- **verify**: adds `specs lint --change <id> --against <base>` and `specs trace --change <id>`; a missing REQ warns under `easy` and blocks under `standard`/`strict`.
- **ship**: first step `specs archive --change <id>` on the feature branch, commit, then the existing options. A base-hash conflict stops ship and asks the user.
- **quick**: never creates a change folder; when the change alters behavior described by a living-spec REQ, stop and recommend the full lifecycle.
- **tech-doc**: under `sdd` writes to `artifacts.codebase` using the `codebase/` templates (project override allowed).
- **Workflow id**: under `sdd`, every `state`/`record` call for a change uses `--workflow-id <epic>`.

### 7. Error handling

- Wrong layout, unknown change id, or missing config: exit 2 with one sentence naming the fix.
- `archive` and `migrate` are all-or-nothing: they plan every write first and write only when every check passes.
- `next-id` never fails because of network; it warns and uses what it could scan.
- `renumber` refuses when `NEW` exists anywhere `next-id` scans.
- `status` never records a gate itself; the stage skill records with the reported evidence.

### 8. Migration

`gin-workflow specs migrate [--dry-run] [--force]` (requires `layout: legacy`):

- Pairing: design `YYYY-MM-DD-<slug>-design.md` and plan `YYYY-MM-DD-<slug>.md` pair on equal `<slug>`. A pair moves to `<changes>/archive/<design date>-<slug>/{design,plan}.md`; an unpaired file moves alone to `<changes>/archive/<its date>-<slug>/`. Files not matching the date pattern are listed as `skipped`.
- `.planning/codebase/` moves to `artifacts.codebase`. `.planning/reviews`, `.planning/worktrees`, `.planning/knowledge` stay.
- Creates `<specs>/README.md` from the template and sets `artifacts.layout: sdd` in `.agent-workflow/config.yaml`.
- Moves use `git mv`. `--dry-run` prints the full plan (moves, skipped, refusals) and changes nothing.
- Refusals: uncommitted changes (never overridable); a workflow with `plan_approved` satisfied and `shipped` unmet, or an open worktree under `artifacts.worktrees` (both overridable with `--force`).
- Historical gate evidence keeps its old path strings; they are not rewritten.

Skill `/gin-workflow:migrate-specs`:
1. Run `specs migrate --dry-run`; show the plan.
2. On approval, run it on branch `chore/migrate-specs` and commit.
3. Optional seeding: propose capabilities from `docs/codebase` (run `tech-doc` first if empty) and the archived designs; for each capability draft `spec.md` with REQ-IDs and scenarios, run `specs lint`, wait for user approval, commit. Stopping midway keeps the committed capabilities.

## Testing

- All existing tests pass unmodified; new tests assert a config without `layout` and with `layout: legacy` behave as before (stage skills, state, setup).
- Unit tests: block parser and hash, every lint rule, `next-id` across worktrees and a fake remote, `renumber` (files, refusal, bead label calls via a fake `bd`), `trace` (code tag, `tests.md`, missing), `archive` (each delta kind, new capability, base-hash conflict leaves tree untouched), `migrate` (dry-run, pairing, unpaired, skipped, each refusal, `--force`), `status` (fake `gh`: none/open/merged/closed/unavailable).
- End-to-end on a temporary git repo: `new` → delta → `lint` → `trace` → `archive`.
- Schema 2.6 tests and migration from 2.5.
- Token budget: stage chains stay within current limits; `references/sdd-layout.md` is not counted in any stage chain; each stage skill mentions `sdd` in at most two lines.
- Installer smoke: `templates/` present in dists and launcher; `gin-workflow specs --help` exits 0.

## Non-goals

- Role-gated approvals, identity, commit-msg hook, PR template, CODEOWNERS (E).
- Generating test cases or Playwright evidence (G).
- Rewriting historical gate evidence paths.
- Enforcing EARS sentence patterns.
- Migrating this repository; it may run `/gin-workflow:migrate-specs` after F ships.
