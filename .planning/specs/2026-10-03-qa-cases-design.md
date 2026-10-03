# QA Test Cases (Sub-project G1) — Design

Date: 2026-10-03
Status: awaiting user confirmation
Depends on:
- F (`.planning/specs/2026-10-03-sdd-living-specs-design.md`, schema 2.6): REQ-IDs, GIVEN/WHEN/THEN scenarios, `block_hash`, living specs and change deltas.
Followed by: G2 (Playwright evidence), G3 (agent-driven E2E runs). Both build on the test case format defined here.

## Goal

A QA engineer can generate, maintain, and check test cases (TCs) derived from the project's specs. TCs are plain markdown that people review in a PR and that the QA engineer's own skills can consume through a JSON export (for example to build a spreadsheet report). Every TC traces to the requirement it tests and is flagged when that requirement changes or disappears. A developer who installs only `gin-workflow` sees no difference.

## Decisions

| Topic | Decision |
|---|---|
| Packaging | A separate plugin `gin-qa` (`plugins/gin-qa/src/`) in the existing marketplace. Not installed by default: `install.sh --plugin gin-qa` (or `--plugin all`, or `/plugin install gin-qa@gin-workflow-marketplace`). It requires `gin-workflow`; core never refers to `gin-qa`. |
| Source | gin-workflow specs. SDD layout: REQ blocks of living specs and of change deltas. Legacy layout: spec files under `.planning/specs/`, referenced by heading. |
| Format | One markdown file per capability, one `### TC-<CAP>-NNN: <title>` block per TC, fixed fields plus free `Key: value` fields. |
| Lifetime | Living TCs per capability under `qa/cases/<capability>.md`, accumulating into the regression suite. |
| Lifecycle | Standalone. The QA engineer runs `/gin-qa:cases` when needed. No gate, stage skill, or `verify` change. A team that wants enforcement adds `gin-qa cases check` to `project.verify_commands` or CI. |
| AI / CLI split | The CLI does the deterministic work (what needs a TC, IDs, hash pins, checks, export). The skill writes TC content. |
| Customization | `qa/guidelines.md`, written by QA, read by the skill before writing; its rules override the skill's defaults. Free fields are kept and exported, never rejected. |
| Generic | No spreadsheet formats, no language- or domain-specific rules, no report format other than JSON. |

## Design

### 1. Core addition: `gin-workflow specs reqs`

A read-only command, useful on its own, that `gin-qa` calls through a subprocess (it never imports core code):

```
gin-workflow specs reqs [--change <epic>] [--format json]
```

- Without `--change`: every block of every living spec (`<specs>/<capability>/spec.md`), followed by the delta blocks (`ADDED`, `MODIFIED`, `REMOVED`) of every open change (every folder under `<changes>/` except `archive/`).
- With `--change`: only the blocks of that change's `spec-delta.md`, including `REMOVED` blocks.
- JSON: `{"requirements": [{"id", "title", "capability", "section", "change", "hash", "source", "scenarios": [{"title", "given": [], "when": [], "then": []}]}]}`. `section` is `LIVING`, `ADDED`, `MODIFIED`, or `REMOVED`; `change` is the change folder name, or `null` for a living block; `hash` is `block_hash` of the block (base lines ignored, so a delta block and the living block it becomes after `specs archive` have the same hash); `source` is `<repo-relative path>:<line>`.
- Exit 0; exit 2 on the legacy layout or an unknown change, like the other `specs` commands.

### 2. Configuration (schema 2.8)

```yaml
qa:
  cases: qa/cases            # default
  guidelines: qa/guidelines.md   # default
```

Core accepts and validates the `qa:` key (two optional non-empty strings, no other keys); only `gin-qa` reads it. The `2.7 → 2.8` migration only bumps the version. A repository without `qa:` uses the defaults. `cases` must not match any `artifacts.test_globs` pattern (TC files are designs, not executed tests, and must not count as coverage in `specs trace`); `gin-qa cases check` reports it if it does.

### 3. Test case format

`qa/cases/<capability>.md` (`<capability>` is the living spec folder name, the lower-case CAP of its REQ-IDs):

```markdown
# Test cases: auth

### TC-AUTH-001: Login with a valid password
REQ: REQ-AUTH-003@1a2b3c4d
Type: e2e
Priority: high
Owner: qa-team

Preconditions:
- user alice@example.com exists

Steps:
1. Open /login
2. Fill "Email" with alice@example.com
3. Click "Sign in"

Expected:
- The dashboard is shown
```

- `REQ:` one or more `REQ-<CAP>-NNN@<hash8>` separated by `, `; `hash8` is the first 8 hex characters of the REQ's `hash`. Legacy layout: `Source: <spec path>#<heading>` instead of `REQ:`.
- `Type:` free text, recommended `manual` or `e2e` (G2 runs `e2e`). `Priority:` free text.
- `Preconditions:` (optional), `Steps:` (numbered `1.`, `2.`, …), `Expected:` (bullets) are required sections, in that order.
- Any other `Key: value` line before `Preconditions:`/`Steps:` is a free field (here `Owner`).
- The TC ID's CAP is the file's capability; numbers are unique per capability and never reused.

### 4. CLI `gin-qa cases`

**Effective requirements.** `gin-qa` reads `specs reqs` (without `--change`) and resolves each REQ-ID to one effective block: an open change's `ADDED` or `MODIFIED` block wins over the living block; an open change's `REMOVED` block makes the REQ removed. So a TC written for an unarchived change is valid immediately and stays valid after `specs archive`. Two open changes with an `ADDED`/`MODIFIED` block for the same REQ-ID are reported by `check` as a conflict (exit 1). `--change <epic>` narrows the scope of `plan` and `check` to that change's REQs; resolution stays the same.

Python stdlib only; installed as a launcher on `PATH` the same way as `gin-workflow`. Every command takes `--repository` (default cwd) and `--format text|json`. Exit 0 = clean, 1 = findings, 2 = usage or environment error (missing `gin-workflow`, a `gin-workflow` without `specs reqs`, no `/setup`, `specs reqs` failure — its stderr is passed through).

| Command | Behavior |
|---|---|
| `plan <capability> \| --change <epic>` | JSON work list: `missing` (REQ with no TC, with its scenarios), `stale` (TC whose pinned `hash8` differs from the REQ's, with the current REQ text), `obsolete` (TC pointing at a REQ that does not exist or is removed). Exit 0 even when the list is non-empty. |
| `next-id <capability>` | Prints the next unused `TC-<CAP>-NNN` (one past the highest ever used in the file). |
| `pin <TC-ID>...` | Rewrites each TC's `REQ:` hashes to the current `hash8` of its REQs. Touches nothing else. Exit 1 if a TC or REQ does not exist. |
| `check [--change <epic>]` | Findings, each with `file:line`: malformed block (missing `Steps:` or `Expected:`, unnumbered step, sections out of order), duplicate ID, ID whose CAP differs from the file, `REQ:` without `@hash8`, unknown REQ, stale, obsolete, uncovered REQ (every effective REQ, or only the change's `ADDED`/`MODIFIED` with `--change`), conflicting open changes, `cases` path matching `test_globs`. Free fields never produce findings. Legacy layout: structure and IDs only. |
| `export` | `{"cases": [{"id", "title", "capability", "file", "line", "reqs": [{"id", "hash8"}], "source", "type", "priority", "fields": {...}, "preconditions": [], "steps": [], "expected": []}]}` for every TC, free fields included. |

### 5. Skill `/gin-qa:cases <capability | --change <epic>>`

1. Preconditions: `gin-workflow` on `PATH` and recent enough to provide `specs reqs`, and the repository set up (`.agent-workflow/generated/effective-config.yaml`). Otherwise stop and name the command to run.
2. Read `qa/guidelines.md`; if missing, create it from the template and tell the QA engineer to edit it. Its rules override the skill's defaults.
3. `gin-qa cases plan …`.
4. `missing`: `next-id` per TC, at least one TC per scenario, boundary and error cases where the REQ implies them, then `pin`. `stale`: re-read the REQ, update the TC, then `pin` (never type a hash by hand). `obsolete`: list them and ask whether to delete or keep; never delete on its own.
5. Loop on `gin-qa cases check` until exit 0, then report which TCs were added, changed, or removed.
6. Never commit; the QA engineer reviews and commits (through a PR in team mode, like any file).

### 6. Packaging and install

- `plugins/gin-qa/src/` with `.claude-plugin/plugin.json`, `.codex-plugin/plugin.json`, `skills/cases/SKILL.md`, `scripts/` (CLI), `templates/{cases.md, guidelines.md}`; added to `.claude-plugin/marketplace.json`.
- `install.sh` and `install.ps1`: `--plugin gin-workflow|gin-qa|all`, default `gin-workflow` (unchanged). Installing `gin-qa` installs its launcher; if `gin-workflow` is not installed it warns and continues. `--dry-run` and `--uninstall` cover `gin-qa`.
- Core skills, agents, and references contain no mention of `gin-qa`.

## Testing

- Core `specs reqs`: living plus open-change JSON, `--change` JSON, archived changes excluded; multi-scenario REQs; a delta block's hash equals the living block's hash after `specs archive`; `REMOVED` blocks listed; legacy layout and unknown change exit 2.
- Schema 2.8: `qa:` accepted with defaults, unknown sub-keys rejected, `2.7 → 2.8` migration.
- `gin-qa cases`: effective-requirement resolution (open `MODIFIED` wins, open `REMOVED` removes, two open changes on one REQ conflict); a TC for an unarchived change passes `check` before and after `specs archive`; `plan` finds `missing`, `stale`, `obsolete`; `next-id` never reuses a number; every `check` finding type with `file:line`; free fields give exit 0; `pin` changes only the named TC; `export` keeps free fields; legacy `Source:` checks; missing or too-old `gin-workflow` exits 2.
- Packaging: `install.sh --plugin gin-qa`, `--plugin all`, `--dry-run`; the default install does not install `gin-qa`; no core skill or agent mentions `gin-qa`; token budget for the `cases` skill and its description.
- Smoke: an SDD sample repository → write TCs → `check` exit 0 → edit a REQ → `check` reports stale → `pin` → `check` exit 0.

## Success criteria

1. On an SDD repository with REQs and scenarios, `/gin-qa:cases <cap>` produces TCs for which `gin-qa cases check` exits 0.
2. Editing a REQ makes `check` report exactly the TCs that test it as stale.
3. `gin-qa cases export` gives JSON that a QA engineer's own skill can turn into a report.
4. A user who installs only `gin-workflow` sees no change.

## Non-goals

- Running TCs or collecting evidence (G2).
- Agents exploring the application (G3).
- Spreadsheet or any report format other than JSON export.
- Language- or domain-specific writing rules (QA puts them in `qa/guidelines.md`).
- A gate or `verify` rule requiring TC coverage.
- A QA role in team mode.
