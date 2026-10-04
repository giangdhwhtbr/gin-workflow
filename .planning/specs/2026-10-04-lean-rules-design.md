# Lean Rule Pack — Design

Date: 2026-10-04
Status: draft
Credit: ideas from ponytail (https://github.com/dietrichgebert/ponytail, MIT, commit `c982cd4`); wording is our own.

## Goal

Agents write less code for the same result and reviewers catch over-engineering: reuse what exists, prefer the standard library, the platform, and installed dependencies, add nothing speculative, and never cut validation, error handling, security, accessibility, or required tests. Delivered through the existing rule-pack mechanism, so it reaches the `developer` agent, `/quick`, and the reviewer, and nothing else.

## Decisions

| Topic | Decision |
|---|---|
| Purpose | Both writing (execute, quick) and review. |
| Integration | A new rule pack `lean` in the existing `gin-workflow rules` mechanism. No ponytail plugin, hooks, Node, modes, or vendored skills. |
| Enablement | On by default next to `core`; `rules.disabled: [lean]` turns it off. |
| Review severity | A violated `high` `lean` bullet is `IMPORTANT` (blocks approval); any other `lean` bullet is `MINOR`. |
| Shortcut marker | A rule only: a deliberate simplification with a known ceiling carries a `simplified:` comment. No collection tool. |

## Global Constraints

- `discuss` and `plan` behavior is unchanged: they never receive the `lean` pack, and the design gate and test-first plan steps stay as they are.
- `lean` never overrides `core`, project rules, the plan, or tests the plan requires.
- No new runtime dependency.
- The pack's wording is written for gin-workflow, not copied from ponytail; the README credits ponytail.

## Design

### 1. Pack `plugins/gin-workflow/src/rules/lean.md`

Frontmatter `id: lean`, `tier: core`, `applies_to: ["**/*"]`. Body (before `## Why`) at most 1,000 characters, the `core`-tier limit:

```markdown
- [high] `reuse-existing`: Reuse an existing helper, type, or pattern from the repository before writing a new one.
- [high] `no-new-dependency`: Add no dependency for what the standard library, the platform, an installed dependency, or a few lines already do.
- `ladder`: Prefer, in order: not building it, existing code, the standard library, a platform feature, an installed dependency, one line, then minimal new code.
- `no-speculative`: Add no abstraction, option, or extension point without a second real use; no scaffolding for later.
- `delete-first`: Prefer deleting or shrinking code to adding it; shortest correct diff.
- `root-cause`: Fix a bug once in the shared code every caller goes through, not in each caller.
- `simplified-marker`: Mark a deliberate simplification with a `simplified:` comment naming its limit and upgrade path.
- `never-cut`: Never trim validation at trust boundaries, error handling, security, accessibility, tests the plan requires, or anything requested.

## Why
- `reuse-existing`: A second copy of existing logic drifts from the first and doubles every fix.
- `no-new-dependency`: Each dependency adds supply-chain, upgrade, and licence cost for the life of the project.
```

`core#reuse-first` stays, so reuse is still covered when `lean` is disabled.

### 2. Default enablement (`workflow_core/rules.py`)

`select_packs` enables `core`, `lean`, and the packs in `rules.packs`, minus `rules.disabled`. A plugin tree without `lean.md` (an older launcher) behaves as today. `rules.packs: [lean]` stays valid and adds nothing new.

### 3. Review (`skills/review/SKILL.md`)

One sentence in Reviewing step 3: a violated `high` `lean` bullet is recorded at `IMPORTANT`, any other `lean` bullet at `MINOR`; the finding names what to cut and what replaces it; code marked `simplified:` is not flagged for that simplification.

### 4. README

The rules section names the `lean` pack, how to disable it, and credits ponytail with a link.

## Testing

- Selection: `lean` is selected with the default config, with `rules.packs: [python]`, and with `rules.packs: [lean]` (once); not selected with `rules.disabled: [lean]`.
- Pack validity: the existing pack tests accept `lean.md` (frontmatter, body ≤ 1,000 chars, every `critical` anchor has a `## Why` line).
- Budget: `gin-workflow rules --files` output with `core`, `lean`, and framework packs stays within the 4,000-char budget; trimming order is unchanged (`critical` never trimmed).
- Packaging: the installed plugin ships `rules/lean.md`, and the review skill contains the `lean` severity sentence.

## Success criteria

- `gin-workflow rules --files <any file>` in a repository with default config prints the `lean` bullets after `core`.
- `rules.disabled: [lean]` removes them.
- The review skill tells the reviewer how to grade `lean` findings.

## Non-goals

- Always-on hooks, intensity levels (lite/full/ultra), or any per-turn injection.
- A debt-collection command, repository-wide audit, or benchmarks.
- Changes to `discuss`, `plan`, or the `core` pack.
