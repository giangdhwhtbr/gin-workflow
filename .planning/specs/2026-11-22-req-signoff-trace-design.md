# Requirement sign-off in git and a trace over every requirement

Epic: gin-workflow-ch2v
Kind: capability
Points: 8 (4 stories, 3 modules (record, archive, trace) and 2 outside sources (bd, gin-qa); medium: new JSON contract for gin-console)
Status: draft for user review.

## Goal and scope

Spec sign-off is a per-epic `requirement.confirmed` event in `.agent-workflow/runtime/events.jsonl` (`plugins/gin-workflow/src/scripts/workflow_core/lifecycle_cli.py:160`), which is gitignored and per machine; only team mode copies the gate into the epic bead's `gates` metadata (`team_beads.write_gate`, `team_beads.py:902`). `gin specs trace` takes only `--change` (`specs_cli.py:38`), reads one open change, and joins its ADDED and MODIFIED requirements to test files (`specs_trace.py:63`). Archiving moves the change folder to `docs/changes/archive/<date>-<change>/` (`specs_archive.py:72`) and the living spec keeps no record of which change or sign-off produced a requirement. Nothing joins a requirement to the beads that build it (`req:` labels) or to the gin-qa cases that prove it.

gin-console plans a requirements view for business analysts (epics `gin-console-rm-requirements` and `gin-console-rm-req-signoff`, which depends on the capability `req-signoff-trace`). Neither is built, and gin-console's roadmap leaves the JSON contract to this epic.

This epic records sign-off per requirement in git, and adds `gin specs trace --all` that returns, for every requirement, its sign-off, its changes, its beads, its gin-qa cases with their effective result, and its test files.

In scope:

- The requirement list with hashes in the `requirement.confirmed` event and in its bead mirror.
- `06-signoff.md`, written by `gin specs archive` into the archived change folder.
- `gin specs trace --all`, its JSON contract, and its text output.
- `docs/reference/cli.md` (the contract), `docs/guides/sdd.md`.

Out of scope:

- Editing a sign-off, and signing off one requirement apart from its change.
- The legacy layout, which has no REQ-IDs (`gin specs reqs` returns no requirement there).
- The requirement status of gin-console's matrix (covered, building, untested, failing): gin-console computes it from the raw data (`gin-console-rm-requirements`).
- Showing sign-off in `gin specs export` or `/gin:explain`.
- gin-console itself.
- `docs/changelog.md`, written at release time (`docs/contributing.md:115`).

Assumptions:

- `hash8` is the first 8 hex characters of `block_hash`, the form `gin specs reqs` and gin-qa's `REQ-<CAP>-<NNN>@<hash8>` pins already use.
- One `bd list --all --json` call per `trace --all` run is fast enough; the trace does not cache.
- gin-qa is found on `PATH` as `gin-qa`, as gin-qa's own skills call it; gin-workflow does not import gin-qa.
- A change folder keeps its `Epic:` line when archived (`git mv` of the whole folder), so an old archived change finds its sign-off through its epic.

## Requirements

### R1: Requirements in the sign-off event

- With `project.layout: sdd`, `gin record requirement-confirmed --workflow-id <epic>` adds `requirements` to the event payload when an open change has `Epic: <epic>` in its proposal: a list of `{id, hash8, op}` from the blocks of its `02-spec-delta.md`, where `op` is `added`, `modified`, or `removed`. For a `removed` block, `hash8` is the hash of the removed block.
- In team mode, the proof written to the epic bead's `gates` metadata (`requirement_confirmed`) carries the same `requirements` list.
- Without an open change for the epic, or with the legacy layout, the payload is unchanged and the record behaves as today.

### R2: `06-signoff.md` at archive

- `gin specs archive --change <change>` writes `06-signoff.md` into the archived folder and stages it with the move, so the archive commit carries it.
- The sign-off is taken from the change's epic (its `Epic:` line), in this order: the epic bead's `gates.requirement_confirmed`, then the newest local `requirement.confirmed` event with that workflow id, then a waiver of the `requirement_confirmed` gate for that workflow id.
- The file holds the lines `Epic: <epic>`, `Signed off: <at>`, `By: <actor>`, `Evidence: <evidence>`, `Source: beads|events`, and a table `| Requirement | hash8 | op |` with one row per requirement. A waiver writes `Waived: <reason>` and `By: <actor>` instead of `Signed off:` and `Evidence:`.
- The requirement rows come from the sign-off's `requirements` list. When the sign-off has none (recorded before this epic), they come from the archived delta's blocks, and the file says `Hashes: at archive`.
- When a requirement's hash at sign-off differs from its block in the archived delta, archive prints `warning: <REQ> changed after sign-off` on stderr and keeps the signed hash.
- Without any sign-off or waiver, archive prints `warning: <change>: no sign-off found; 06-signoff.md not written` and archives as today.
- A sign-off source that cannot be read (an unreadable event log, a failing `bd`) is skipped with a warning; archive never fails because of sign-off.

### R3: `gin specs trace --all`

- `gin specs trace --all [--format text|json]`; `--all` and `--change` are mutually exclusive, and one of them is required. `--change` keeps its current behaviour and output.
- JSON output, `schema: 1`:

  ```json
  {"schema": 1, "layout": "sdd",
   "requirements": [{
     "id": "REQ-AUTH-001", "title": "Lock out after five failed logins", "capability": "auth",
     "state": "living", "hash8": "1a2b3c4d", "source": "docs/specs/auth/spec.md:12",
     "changes": [{"change": "ep-1-lockout", "epic": "ep-1", "op": "added", "archived": "2026-11-20",
                  "signoff": {"at": "2026-11-18T09:00:00Z", "actor": "ba@corp.com",
                              "evidence": "https://host/org/repo/pull/12", "hash8": "1a2b3c4d",
                              "source": "git", "waived": false}}],
     "signoff": {"change": "ep-1-lockout", "at": "2026-11-18T09:00:00Z", "actor": "ba@corp.com",
                 "evidence": "https://host/org/repo/pull/12", "hash8": "1a2b3c4d", "source": "git",
                 "waived": false, "current": true},
     "beads": [{"id": "ep-1.2", "title": "Lockout counter", "status": "closed"}],
     "cases": [{"id": "TC-AUTH-001", "effective_result": "passed"}],
     "tests": ["tests/test_auth.py", "docs/changes/archive/2026-11-20-ep-1-lockout/05-tests.md#TC-AUTH-001"]}],
   "warnings": [], "skipped": []}
  ```

- The requirement set:
  - every block of the living specs, `state: living`;
  - every ADDED block of an open change whose id is not living, `state: proposed`, with `hash8` and `source` from the delta;
  - every requirement removed by an archived change and not living, `state: removed`, with `hash8` and `source` null.
- `changes`: every open and archived change whose `02-spec-delta.md` names the requirement, archived ones first in archive-date order, then open ones by name. `archived` is the date prefix of the archived folder, null for an open change. `op` is the delta section in lower case.
- A change's `signoff` comes from, in order: its `06-signoff.md` (`source: git`); for an open change, or an archived change without the file, its epic's bead `gates.requirement_confirmed` (`source: beads`), then the newest local `requirement.confirmed` event of the epic (`source: events`), then a waiver (`waived: true`, `evidence` holding the reason). Its `hash8` is the requirement's hash at sign-off, or null when the sign-off lists no hashes.
- The requirement's `signoff` is the last change entry with a sign-off, plus `change` and `current`. `current` is true when its `hash8` equals the requirement's `hash8`, false when they differ, and null when either is null. `signoff` is null when no change has one.
- `beads`: every bead with the label `req:<id>`, in any status, sorted by id, from one `bd list --all --json` call. `null` with the markdown task backend or when `bd` is missing or fails; the failure adds a `warnings` entry.
- `cases`: the rows of `gin-qa cases export --format json` (run in the repository root) whose `reqs` contain the id, as `{id, effective_result}`, sorted by id. `null` when `gin-qa` is not on `PATH` or exits non-zero, with a `warnings` entry.
- `tests`: the test files that name the id (the rule of `req_sources`, `specs_trace.py:38`, for every id), then the `05-tests.md#<case>` rows of open and archived changes that name it, sorted. Workspace children that cannot be listed go to `skipped`, as today.
- A malformed `06-signoff.md` adds a `warnings` entry and the change falls back to the next source.
- Exit codes: 0 for the report, whatever the coverage; 2 for a usage or configuration error. With the legacy layout the command prints `{"schema": 1, "layout": "legacy", "requirements": [], "warnings": [], "skipped": []}` and exits 0.
- Text output: one line per requirement, `<id> <state> signoff:<yes|stale|waived|no> beads:<n|-> cases:<n|-> tests:<n>`, where `-` marks a null source, then one line per warning.

### R4: Documentation

- `docs/reference/cli.md`: the `gin specs trace` entry documents `--all` with a table of every JSON field and its meaning; this table is the contract gin-console reads, and other pages link to it. The `archive` entry names `06-signoff.md`; the `record` entry names the `requirements` payload.
- `docs/guides/sdd.md`: a short section on where sign-off lives (event and bead before archive, `06-signoff.md` after) and how to read it with `gin specs trace --all`.

## User Stories

### US-1: Sign-off remembers what was signed
As a business analyst, I want the sign-off of a change to record each requirement with the hash I approved, so that a later edit shows the requirement as no longer signed off.

Acceptance criteria:
- With the SDD layout and an open change `ep-1-lockout` (`Epic: ep-1`) whose delta adds `REQ-AUTH-001`, `gin record requirement-confirmed --workflow-id ep-1 --evidence <path> --actor ba` writes an event whose payload has `requirements: [{"id": "REQ-AUTH-001", "hash8": "<first 8 of its block hash>", "op": "added"}]`.
- In team mode the same list is in the epic bead's `gates.requirement_confirmed`.
- With the legacy layout the payload has no `requirements` key.

### US-2: Sign-off is in git after archive
As a teammate on another machine, I want the sign-off of an archived change in the repository, so that I can see who approved it without that person's event log.

Acceptance criteria:
- After the record of US-1, `gin specs archive --change ep-1-lockout` writes `docs/changes/archive/<date>-ep-1-lockout/06-signoff.md` with `Signed off:`, `By: ba`, `Evidence:`, `Source: events`, and the row `| REQ-AUTH-001 | <hash8> | added |`, and `git status` shows it staged.
- With the requirement edited after sign-off, archive prints `warning: REQ-AUTH-001 changed after sign-off` and the file keeps the signed hash.
- With a waived `requirement_confirmed` gate, the file has `Waived: <reason>`.
- Without any sign-off, archive prints `no sign-off found; 06-signoff.md not written`, writes no file, and still archives.
- A sign-off event without `requirements` gives rows from the delta and the line `Hashes: at archive`.

### US-3: One trace over every requirement
As a business analyst, I want `gin specs trace --all --format json` to list every requirement with its sign-off, beads, cases, and tests, so that gin-console can show the requirements view without joining sources itself.

Acceptance criteria:
- In a repository with a living requirement from an archived change with `06-signoff.md`, a proposed requirement in an open change with a local sign-off event, and a requirement removed by an archived change, the output has three rows with `state` `living`, `proposed`, and `removed`, and signoff `source` `git`, `events`, and that of the removing change.
- A living requirement whose block changed after its sign-off has `signoff.current: false` and the text line shows `signoff:stale`.
- A bead labelled `req:REQ-AUTH-001` appears in that requirement's `beads` with its id, title, and status.
- A gin-qa case pinning `REQ-AUTH-001` appears in `cases` with its `effective_result`.
- A test file naming `REQ-AUTH-001` and a `05-tests.md` row of an archived change both appear in `tests`.
- `gin specs trace --all --change ep-1` exits 2.

### US-4: The trace degrades instead of failing
As a tool that reads the trace, I want a missing source to be reported, not to fail the command, so that the requirements view still shows what is known.

Acceptance criteria:
- Without `gin-qa` on `PATH`, every row has `cases: null`, `warnings` names gin-qa, and the command exits 0.
- With the markdown task backend, every row has `beads: null` and the command exits 0.
- A malformed `06-signoff.md` adds a warning and the change's sign-off comes from the event log.
- With the legacy layout the command prints an empty `requirements` list and exits 0.

## Errors and compatibility

- `gin specs trace --change` keeps its arguments, output, and exit codes; scripts and skills that call it are unchanged.
- The `requirements` payload key is additive; older readers of `events.jsonl` and of bead `gates` ignore it.
- `06-signoff.md` is a new file in archived folders only; `gin specs new` does not create it, and `gin specs lint` does not require it.
- A change archived before this epic gets no `06-signoff.md`; its sign-off is read from the bead or the local event log through its `Epic:` line, so it shows `source: beads` or `source: events`, or null on a machine without either.
- gin-console needs no change until `gin-console-rm-req-signoff` reads the contract. At ship, `bd ship req-signoff-trace` marks the capability for its external dependency.

## Testing

- Unit tests for R1: the payload of `record requirement-confirmed` with the SDD layout, without an open change, and with the legacy layout; the team mirror's `requirements` (with a patched bead writer).
- Unit tests for R2 in a temporary SDD repository: the file from an event, from bead gates (patched reader), from a waiver, without sign-off, with a changed requirement, and with an event without `requirements`; the file is staged.
- Unit and CLI tests for R3 in a temporary SDD repository with living, proposed, removed, archived, and stale requirements; `beads` through a fake `bd` list (patched), and through a real `bd` behind the skip guard; `cases` through the repository's `plugins/gin-qa/src/scripts/gin-qa` put on `PATH`; the null sources of US-4; the legacy layout; the usage errors.
- The existing `gin specs trace --change` tests stay unchanged and pass.
- Docs tests: `test_docs_coverage.py` and the style check pass with the new `cli.md` content.

## Open Technical Questions
