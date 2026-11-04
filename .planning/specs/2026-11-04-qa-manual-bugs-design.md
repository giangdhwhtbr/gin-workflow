# gin-qa manual runs and bug logging

Epic: gin-workflow-qa-manual-bugs
Status: confirmed by the user on 2026-11-04. Amended the same day after the plan review, with the user's choice: the epic of a `Workflow:` spec comes from `gin-workflow state`, `/gin-qa:run` offers an epic picker, the open-bug check comes before the epic lookup, the epic bead must exist, and the description goes on stdin.

## Goal and scope

A tester walks the manual cases of a capability, records `passed`, `failed`, or `blocked` on each, and on a failure files a bug bead linked to the epic the case was written for, so the usage report counts the bug against that work.

In scope:
- `gin-qa cases bug <TC-ID>` in `plugins/gin-qa/src/scripts/gin_qa/` (`cases.py`, `cli.py`): finds the epic of a manual case, files the bug through `gin-workflow task create`, and records the result through the existing `record_result` write path.
- An `epic` key on each row of `gin-workflow specs reqs --format json` (`workflow_core/specs_reqs.py`, from `specs.change_epic`), and on `gin-workflow state --format json` (the epic recorded at `orchestration-ready` for the workflow id).
- The skill `/gin-qa:run <capability>`.
- `docs/guides/qa.md`, `docs/reference/cli.md`, `docs/reference/skills.md`, `docs/roles.md`, and the last line of the `cases` skill.

Out of scope: syncing bugs to Jira or Notion; test cycles or runs as beads; copying evidence files; adding the new actual result or evidence to a bug that is still open; runners for non-manual types.

## Requirements

Finding the epic
- A case with a `Source:` field (legacy layout): the spec file named before `#` in `Source:`, relative to the repository and inside it, is read. Its `Epic: <id>` line gives the epic; without one, its `Workflow: <topic>` line gives the `epic` of `gin-workflow state --workflow-id <topic> --format json`.
- A case with `REQ:` fields (sdd layout): `gin-workflow specs reqs` gives each REQ's `epic`, the `Epic:` line of the change folder that holds it, or `null` for a living REQ or a change whose proposal has no `Epic:` line. The case's epic is the first non-null `epic` among its REQs, in the order they are listed.
- `--discovered-from <bead>` replaces the epic found.
- When no epic is found and none is given, the command exits 2 with `gin-qa: no epic for <TC-ID>; pass --discovered-from <bead>` and writes nothing.

`gin-qa cases bug <TC-ID> --actual TEXT [--evidence REF]... [--external-ref REF] [--discovered-from BEAD] [--run REF] [--repository P] [--format text|json]`
- Only a case whose type is `manual` is accepted.
- `--actual`, each `--evidence`, `--external-ref`, `--discovered-from`, and `--run` are non-empty, single-line, and printable, the same check `cases result` applies to `--run` and `--bug`.
- When the case's `Bug:` names a bead that `gin-workflow task show <bead> --json` reports as not closed, no bug is filed and no epic is needed: the case is recorded `failed` with that bug, and the output has `"created": false` and `"epic": null`. This check comes before the epic lookup.
- Before filing, the epic must be a bead `task show` can read: a bead the tracker does not have exits 2 with `<epic>: no such bead`; any other `task show` failure exits 2 with its stderr.
- Otherwise the command runs `gin-workflow task create -t bug --title "<TC-ID>: <case title>" --body-file - --deps discovered-from:<epic> -p <priority> [--external-ref REF] --json` with the description on stdin (a Windows `.cmd` shim cuts an argument at its first newline), and reads the new bead id from its output.
  - Priority: case `Priority: high` → 1, `medium` → 2, `low` → 3, none → 2.
  - The description is Markdown with, in order: the case file path and line, `Run`, `Previous bug` (when the case named a bug that is closed, unknown, or not a bead), and the sections Preconditions, Test data, Steps (numbered), Expected, Actual, Evidence (one bullet per `--evidence`); empty sections are left out.
- It then records `failed`, the run (`--run`, else the case's current `Run`, else none), and the bug id through `record_result`, and prints `<TC-ID> failed <bug>` (`--format json`: `{"tc", "bug", "epic", "created", "file"}`).

`/gin-qa:run <capability>`
- Preconditions as in the other gin-qa skills: `gin-workflow` and `gin-qa` on `PATH`.
- It asks the tester once for a run reference (default `manual <YYYY-MM-DD>`, UTC), then shows each `.manual.md` case of the capability in ID order, one at a time: title, preconditions, test data, steps, expected, and its current result and bug.
- The tester answers `passed`, `failed`, `blocked`, or `skip`. `passed` and `blocked` run `gin-qa cases result <TC-ID> <status> --run <ref>`; `skip` writes nothing; `failed` asks for the actual result, evidence references, and an optional external tracker reference, then runs `gin-qa cases bug`.
- When `cases bug` reports no epic or no such bead, the skill lists the open epics (`gin-workflow task list --type epic --json`) for the tester to pick one, or to give another bead id, and runs it again with `--discovered-from`.
- At the end it reports the counts per status and each bug filed or reused.
- It never edits case files directly and never files a bug on its own judgement.

## User Stories

### US-1: Walk the manual cases of a capability
As a tester, I want `/gin-qa:run <capability>` to take me through each manual case and record what I report, so that every case file carries its latest manual result.

Acceptance criteria:
- The skill shows the `.manual.md` cases of the capability in ID order, one at a time, with preconditions, test data, steps, and expected.
- `passed` and `blocked` are recorded through `gin-qa cases result` with the run reference given at the start.
- `skip` leaves the case file unchanged.
- The skill ends with the count of passed, failed, blocked, and skipped cases and the bugs filed or reused.

### US-2: File a bug linked to the work it came from
As a tester, I want a failed manual case to file a bug bead linked to the case's epic, so that the bug shows up in that epic's usage report.

Acceptance criteria:
- `gin-qa cases bug <TC-ID> --actual ...` on a legacy case creates a bug with `discovered-from:<epic>` where `<epic>` is the `Epic:` line of the spec named in `Source:`, or the epic recorded for its `Workflow:` id.
- On an sdd case the epic comes from the change folder of the case's first REQ that has one.
- The bug's description holds the case's steps, expected, the actual result, and each evidence reference.
- The case file then has `Result: failed`, the run, and `Bug: <new bead id>`.

### US-3: Do not file a bug twice
As a tester, I want a case that fails again while its bug is open to keep that bug, so that a re-run does not create duplicates.

Acceptance criteria:
- When the case's `Bug:` bead is not closed, no bead is created and the output says `created: false`.
- When that bead is closed, a new bug is filed and its description names the previous bug.

### US-4: Decide the link when no epic is known
As a tester, I want to be asked which bead a bug belongs to when the case has no epic, so that every bug filed through gin-qa is linked.

Acceptance criteria:
- With no epic found and no `--discovered-from`, `cases bug` exits 2 and leaves the case file and Beads unchanged.
- `/gin-qa:run` then lists the open epics, asks the tester to pick one or give a bead id, and files the bug with `--discovered-from <id>`.

### US-5: Point to an external tracker
As a tester on a team with its own tracker, I want to attach the tracker's ticket to the bug, so that the bead and the ticket can be found from each other.

Acceptance criteria:
- `--external-ref <ref>` is passed to `gin-workflow task create --external-ref <ref>`.

## Errors and compatibility

- Exit codes follow the gin-qa contract: 0 recorded, 2 usage or environment error. Exit 2, with nothing written, for an unknown case, a case whose type is not `manual`, an invalid option value, no epic, or an unreadable spec named in `Source:`.
- When `gin-workflow task create` fails (no Beads, or a task backend without `--deps`), the command exits 2, passes on its stderr, and leaves the case file unchanged.
- When the bug is created but recording the result fails, the command exits 2 and names the new bead on stderr so the tester can run `gin-qa cases result <TC-ID> failed --bug <id>`; the bead is not deleted.
- A `Bug:` value that is not a bead, or that `task show` cannot read, counts as no open bug: a new bug is filed and the old value is named as the previous bug.
- `specs reqs` and `state` only gain a key; `cases export`, `e2e export`, and `report` output stay unchanged, so gin-console is not affected.
- gin-qa `VERSION` becomes `0.8` and the plugin `0.9.0`; gin-workflow gets a patch bump. The gin-workflow core still never mentions gin-qa.

## Testing

`tests/gin_qa/test_cases_bug.py`, with a stub `gin-workflow` on `PATH` that records its arguments and answers `task show`, `task create`, and `specs reqs`:
- a legacy case: the epic comes from the spec's `Epic:` line, or from `state` for a `Workflow:` spec; `task create` gets `-t bug`, `--deps discovered-from:<epic>`, the mapped priority, and a description with every section; the case file ends with `failed`, the run, and the new bug;
- an sdd case: the epic comes from the first REQ with a non-null `epic`;
- `--discovered-from` replaces the found epic; `--external-ref` is passed through;
- no epic: exit 2, no `task create`, case file unchanged;
- an open bug: no `task create`, `created: false`, bug kept; a closed bug: a new bug that names the previous one;
- `task create` fails: exit 2, case file unchanged;
- a non-manual case and an empty `--actual`: exit 2.

`tests/workflow_core`: `specs reqs` rows carry `epic` for a REQ in a change and `null` for a living REQ; `state --format json` carries the epic recorded at `orchestration-ready`, else `null`.

`tests/gin_qa/test_packaging.py` lists the `run` skill; the skill descriptions stay within the 1,000-character budget; `docs/reference/skills.md` names `run`.
