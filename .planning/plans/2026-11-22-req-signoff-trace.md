# Plan: Requirement sign-off in git and a trace over every requirement

Epic: gin-workflow-ch2v
Spec: `.planning/specs/2026-11-22-req-signoff-trace-design.md`

## Objective

With the SDD layout, `gin record requirement-confirmed` records each requirement of the change with its hash; `gin specs archive` writes the sign-off into the archived folder as `06-signoff.md`; `gin specs trace --all` returns every requirement with its changes, sign-off, beads, gin-qa cases, and tests as the JSON contract gin-console reads (schema 1).

## Global Constraints

Copied from the spec:

- Out of scope: editing a sign-off, and signing off one requirement apart from its change; the legacy layout, which has no REQ-IDs; the requirement status of gin-console's matrix (covered, building, untested, failing); showing sign-off in `gin specs export` or `/gin:explain`; gin-console itself; `docs/changelog.md`, written at release time.
- `hash8` is the first 8 hex characters of `block_hash`, the form `gin specs reqs` and gin-qa's `REQ-<CAP>-<NNN>@<hash8>` pins already use.
- One `bd list --all --json` call per `trace --all` run is fast enough; the trace does not cache.
- gin-qa is found on `PATH` as `gin-qa`; gin-workflow does not import gin-qa.
- A change folder keeps its `Epic:` line when archived, so an old archived change finds its sign-off through its epic.
- `gin specs trace --change` keeps its arguments, output, and exit codes. The `requirements` payload key is additive. `06-signoff.md` is a new file in archived folders only. Archive never fails because of sign-off.

## Route Rubric
- Choose the weakest model that can do the work.
- Raise the model for broad context or design judgement.
- Raise the effort for intrinsic difficulty: intricate logic, many edge cases, or long chains of steps.

| Kind of work | Model | Effort |
|---|---|---|
| Mechanical edits, documentation, boilerplate | weakest | `low` |
| Bounded implementation with a clear spec | middle | `medium` |
| Cross-module change, security, migration, concurrency | strongest | `high` |

Unclear requirements never raise the model or effort.

## Requirement Analysis
- Problem statement: sign-off is a gitignored, per-machine event per epic (`lifecycle_cli.py:160`); `gin specs trace` covers one open change and only test files (`specs_cli.py:38`, `specs_trace.py:63`); nothing joins a requirement to its beads or gin-qa cases.
- Success criteria: US-1 to US-4 of the spec pass as tests; existing `specs`, `lifecycle`, `team_gates`, and `gin-qa` tests stay green; docs tests pass.
- Constraints: the Global Constraints above. `skills/sdd/SKILL.md` (5,990 of 6,000 characters) and `skills/team/SKILL.md` (5,991) are not edited; no skill text changes in this epic.
- Non-goals: see Global Constraints.

## Approach Options
### Option 1: a `signoff` module shared by record, archive, and trace
- Summary: `workflow_core/signoff.py` owns the requirement list of a change, the sign-off sources (bead `gates`, local events, waiver), and the `06-signoff.md` format. `lifecycle_cli` adds the list to the event and to the bead mirror; `specs_archive` writes the file; a new `specs_trace_all.py` builds the trace.
- Pros: one home for the sign-off rules, so archive and trace read sources in the same order; `specs_trace.py` keeps `--change` untouched.
- Cons: a new module and a new trace module.

### Option 2: put everything in `specs_trace.py` and `specs_archive.py`
- Summary: the source lookup lives in archive and is copied into the trace.
- Pros: no new module.
- Cons: two copies of the source order and of the file format; `specs_trace.py` mixes the per-change trace with the full join.

### Recommended Approach
- Selected option: Option 1.
- Rationale: the spec's R2 and R3 read the same sources in the same order; one module keeps them consistent (`lean#reuse-existing`, `core#one-job`).

Decisions this plan takes against the spec text, for the user to confirm with the plan:
- A waiver's `06-signoff.md` also carries `At: <timestamp>`, so the trace can report when it was waived; the spec lists only `Waived:` and `By:`.
- The `cases` join is tested with a fake `gin-qa` in `tests/workflow_core/`, plus one test with the real gin-qa CLI in `tests/gin_qa/` (POSIX only, as the other gin-qa launcher tests); the spec named only the real CLI.
- `docs/guides/sdd.md` gets its section in Track 3, with the trace link, instead of with the archive change.

## Scope
- In scope: `workflow_core/signoff.py` and `workflow_core/specs_trace_all.py` (new), `lifecycle_cli.py`, `specs_archive.py`, `specs_cli.py`; `docs/reference/cli.md`, `docs/guides/sdd.md`; tests `test_signoff.py` and `test_specs_trace_all.py` (new), `test_lifecycle_cli.py`, `test_team_gates.py`, `test_specs_archive_trace.py`, `tests/gin_qa/test_trace_cases.py` (new).
- Out of scope: skills; `specs_trace.py` (`--change` unchanged); gin-qa code; `docs/changelog.md`; `plugins/gin-workflow/dist/`.

## Execution Strategy

```yaml
execution_strategy:
  mode: direct
  workers:
    mode: sequential
  rationale: Track 2 and Track 3 call the signoff module of Track 1, and Tracks 2 and 3 both edit specs_cli.py and docs/reference/cli.md; one session, solo work.
```

## Tasks

### Track 1: The `signoff` module and the requirements in the sign-off event
- **Dependencies**: none
- **Files**:
  - Create `plugins/gin-workflow/src/scripts/workflow_core/signoff.py`
  - Modify `plugins/gin-workflow/src/scripts/workflow_core/lifecycle_cli.py:200-204` (`_proof` passes `requirements` through)
  - Modify `plugins/gin-workflow/src/scripts/workflow_core/lifecycle_cli.py:389-391` (`_record_command` adds `requirements`)
  - Modify `docs/reference/cli.md:81` (the `requirement-confirmed` row)
  - Create `tests/workflow_core/test_signoff.py`
  - Test `tests/workflow_core/test_lifecycle_cli.py`
  - Test `tests/workflow_core/test_team_gates.py`
- **Interfaces** (produced):
  - `signoff.SIGNOFF_FILE = "06-signoff.md"`
  - `signoff.Signoff(at: str, actor: str, evidence: str, source: str, requirements: tuple[tuple[str, str, str], ...] | None, waived: bool = False)` with `hash_of(req_id) -> str | None` and `as_json(req_id) -> dict` (`at`, `actor`, `evidence`, `hash8`, `source`, `waived`)
  - `signoff.hash8(block: Block) -> str`; `signoff.change_requirements(root, change) -> list[dict[str, str]]`; `signoff.requirements_of(root, workflow_id) -> list[dict[str, str]] | None`
  - `signoff.from_gates(gates) -> Signoff | None`; `signoff.from_events(events, epic) -> Signoff | None`; `signoff.epic_signoff(gates, events, epic) -> Signoff | None`
  - `signoff.bead_gates(row) -> dict`; `signoff.load_gates(root, epic) -> tuple[dict, str | None]`; `signoff.load_events(root) -> tuple[list[WorkflowEvent], str | None]`
  - `signoff.render(found, epic, rows, *, hashes_at_archive=False) -> str`; `signoff.read_file(path) -> Signoff` (raises `ValueError`)
- **Provider role**: `backend`
- **Model:** `sonnet`
- **Effort:** `medium`
- **Why:** bounded new module with the code given below, plus two small edits to the record path; the edge cases (legacy layout, no change, frozen event payloads, waivers) are listed.
- **Acceptance criteria**: US-1 of the spec passes as tests; `python3 -m pytest tests/workflow_core/test_signoff.py tests/workflow_core/test_lifecycle_cli.py tests/workflow_core/test_team_gates.py tests/workflow_core/test_docs_coverage.py -q` passes.
- **Estimated complexity**: medium

Steps:

1. Write the failing tests.

   Create `tests/workflow_core/test_signoff.py`:

   ```python
   """Requirement sign-off: the requirement list of a gate, its sources, and 06-signoff.md."""

   from __future__ import annotations

   from pathlib import Path
   import sys
   import tempfile
   import unittest

   sys.path.insert(0, str(Path(__file__).resolve().parent))

   from specs_fixtures import ADDED_BLOCK, AUTH_SPEC, delta, make_change, make_repo, write  # noqa: E402
   from workflow_core import signoff, specs  # noqa: E402
   from workflow_core.events import WorkflowEvent  # noqa: E402

   REMOVED = "### REQ-AUTH-002: Reject wrong password\n<!-- base: {base} -->\nReason: folded into REQ-AUTH-001\n"
   WAIVER = {"gate": "requirement_confirmed", "gate_class": "process", "reason": "spike", "scope_hash": "s",
             "waived_by": "lead", "follow_up_task_id": None}


   def event(event_type: str, workflow_id: str, payload: dict) -> WorkflowEvent:
       return WorkflowEvent.create(event_type=event_type, workflow_id=workflow_id, actor="ba", payload=payload)


   class TestRequirements(unittest.TestCase):
       def setUp(self):
           self.tmp = tempfile.TemporaryDirectory()
           self.root = make_repo(Path(self.tmp.name) / "repo")
           write(self.root, "docs/specs/auth/spec.md", AUTH_SPEC)
           self.cfg = specs.sdd_config(specs.load_config(self.root))

       def tearDown(self):
           self.tmp.cleanup()

       def test_each_delta_block_is_listed_with_its_hash(self):
           base = specs.requirement_hash(self.root, self.cfg, "REQ-AUTH-002")[1]
           make_change(self.root, spec_delta=delta(added=ADDED_BLOCK, removed=REMOVED.format(base=base)))
           added = specs.parse_blocks(ADDED_BLOCK)[0][0]
           self.assertEqual([{"id": "REQ-AUTH-003", "hash8": specs.block_hash(added.text)[:8], "op": "added"},
                             {"id": "REQ-AUTH-002", "hash8": base[:8], "op": "removed"}],
                            signoff.requirements_of(self.root, "ep-1"))

       def test_no_list_without_a_change_or_with_the_legacy_layout(self):
           make_change(self.root)
           self.assertIsNone(signoff.requirements_of(self.root, "ep-2"))
           legacy = make_repo(Path(self.tmp.name) / "legacy", layout="legacy")
           self.assertIsNone(signoff.requirements_of(legacy, "ep-1"))


   class TestSources(unittest.TestCase):
       def test_bead_gates_come_first(self):
           gates = {"requirement_confirmed": {"pr_url": "https://h/pull/1", "actor": "an@corp.com",
                                              "at": "2026-11-01T00:00:00Z",
                                              "requirements": [{"id": "REQ-AUTH-003", "hash8": "1a2b3c4d", "op": "added"}]}}
           found = signoff.epic_signoff(gates, [event("requirement.confirmed", "ep-1", {"evidence": "x"})], "ep-1")
           self.assertEqual(("beads", "an@corp.com", "https://h/pull/1", "1a2b3c4d"),
                            (found.source, found.actor, found.evidence, found.hash_of("REQ-AUTH-003")))

       def test_newest_event_of_the_epic_then_its_waiver(self):
           events = [event("requirement.confirmed", "ep-1", {"evidence": "old"}),
                     event("requirement.confirmed", "ep-1", {"evidence": "new", "requirements": [
                         {"id": "REQ-AUTH-003", "hash8": "1a2b3c4d", "op": "added"}]}),
                     event("requirement.confirmed", "ep-2", {"evidence": "other"})]
           found = signoff.epic_signoff({}, events, "ep-1")
           self.assertEqual(("events", "new", "1a2b3c4d", False),
                            (found.source, found.evidence, found.hash_of("REQ-AUTH-003"), found.waived))
           waived = signoff.epic_signoff({}, [event("gate.waived", "ep-3", WAIVER)], "ep-3")
           self.assertEqual((True, "spike", "lead", None), (waived.waived, waived.evidence, waived.actor, waived.requirements))
           self.assertIsNone(signoff.epic_signoff({}, events, "ep-9"))

       def test_no_event_log_is_no_warning(self):
           with tempfile.TemporaryDirectory() as tmp:
               self.assertEqual(([], None), signoff.load_events(Path(tmp)))


   class TestFile(unittest.TestCase):
       def test_round_trip_and_malformed(self):
           found = signoff.Signoff(at="2026-11-18T09:00:00Z", actor="ba", evidence="spec.md", source="events",
                                   requirements=(("REQ-AUTH-003", "1a2b3c4d", "added"),))
           with tempfile.TemporaryDirectory() as tmp:
               path = Path(tmp) / signoff.SIGNOFF_FILE
               path.write_text(signoff.render(found, "ep-1", [{"id": "REQ-AUTH-003", "hash8": "1a2b3c4d", "op": "added"}]),
                               encoding="utf-8")
               text = path.read_text(encoding="utf-8")
               for line in ("Epic: ep-1", "Signed off: 2026-11-18T09:00:00Z", "By: ba", "Evidence: spec.md",
                            "Source: events", "| REQ-AUTH-003 | 1a2b3c4d | added |"):
                   self.assertIn(line, text)
               self.assertNotIn("Hashes: at archive", text)
               read = signoff.read_file(path)
               self.assertEqual(("git", "ba", "2026-11-18T09:00:00Z", "1a2b3c4d", False),
                                (read.source, read.actor, read.at, read.hash_of("REQ-AUTH-003"), read.waived))
               waiver = signoff.Signoff(at="2026-11-19T00:00:00Z", actor="lead", evidence="spike", source="events",
                                        requirements=None, waived=True)
               path.write_text(signoff.render(waiver, "ep-1", [{"id": "REQ-AUTH-003", "hash8": "1a2b3c4d", "op": "added"}],
                                              hashes_at_archive=True), encoding="utf-8")
               read = signoff.read_file(path)
               self.assertEqual((True, "spike", "lead", "2026-11-19T00:00:00Z"), (read.waived, read.evidence, read.actor, read.at))
               self.assertIn("Hashes: at archive", path.read_text(encoding="utf-8"))
               path.write_text("# Sign-off\n\nBy: ba\n", encoding="utf-8")
               with self.assertRaises(ValueError):
                   signoff.read_file(path)
   ```

   In `tests/workflow_core/test_lifecycle_cli.py`, add after the existing imports:

   ```python
   from tests.workflow_core.specs_fixtures import ADDED_BLOCK, AUTH_SPEC, make_change, make_repo, write
   from workflow_core import specs
   ```

   and a new class at the end of the file (before any `if __name__ == "__main__":` block):

   ```python
   class TestRequirementsInTheSignOff(unittest.TestCase):
       """`record requirement-confirmed` lists the change's requirements with their hashes (SDD layout)."""

       def setUp(self):
           self.tmp = tempfile.TemporaryDirectory()
           self.root = make_repo(Path(self.tmp.name) / "repo")
           write(self.root, "docs/specs/auth/spec.md", AUTH_SPEC)

       def tearDown(self):
           self.tmp.cleanup()

       def record(self, root: Path, workflow_id: str) -> dict:
           code = cli_main(["record", "requirement-confirmed", "--repository", str(root), "--evidence",
                            "docs/changes/ep-1-lockout", "--actor", "ba", "--workflow-id", workflow_id])
           self.assertEqual(0, code)
           return WorkflowEventStore(root / ".agent-workflow/runtime/events.jsonl").read_all()[-1].to_dict()["payload"]

       def test_the_event_lists_the_change_requirements(self):
           make_change(self.root)
           added = specs.parse_blocks(ADDED_BLOCK)[0][0]
           self.assertEqual([{"id": "REQ-AUTH-003", "hash8": specs.block_hash(added.text)[:8], "op": "added"}],
                            self.record(self.root, "ep-1")["requirements"])

       def test_no_list_without_a_change_or_with_the_legacy_layout(self):
           make_change(self.root)
           self.assertNotIn("requirements", self.record(self.root, "ep-2"))
           legacy = make_repo(Path(self.tmp.name) / "legacy", layout="legacy")
           self.assertNotIn("requirements", self.record(legacy, "ep-1"))
   ```

   In `tests/workflow_core/test_team_gates.py`, add after the `team_fixtures` imports:

   ```python
   from specs_fixtures import ADDED_BLOCK, AUTH_SPEC, delta  # noqa: E402
   ```

   and in `TestSharedGates`, after `test_record_writes_the_proof_into_the_epic_bead`:

   ```python
       def test_requirement_confirmed_mirrors_the_requirements(self):
           config = self.root / ".agent-workflow/config.yaml"
           config.write_text(config.read_text() + "artifacts:\n  layout: sdd\n")
           resolve_effective_config(self.root)
           write(self.root, "docs/specs/auth/spec.md", AUTH_SPEC)
           delta_path = "docs/changes/e-1-lockout/02-spec-delta.md"
           write(self.root, "docs/changes/e-1-lockout/01-proposal.md", "# Lockout\n\nEpic: e-1\n")
           write(self.root, delta_path, delta(added=ADDED_BLOCK))
           self.gh(gh_pr(author="binh-dev", files=[delta_path], reviews=[("an-ba", "APPROVED", "c1")]))
           self.bd({"e-1": {"id": "e-1", "issue_type": "epic", "status": "open", "metadata": {}}})
           result = run_cli(self.root, "record", "requirement-confirmed", "--evidence", PR, "--workflow-id", "e-1",
                            env=self.env)
           self.assertEqual(0, result.returncode, result.stderr)
           gates = json.loads(self.bd_updates()[-1][4].removeprefix("gates="))
           mirrored = gates["requirement_confirmed"]["requirements"]
           self.assertEqual(["REQ-AUTH-003"], [row["id"] for row in mirrored])
           self.assertEqual(self.events()[-1]["payload"]["requirements"], mirrored)
   ```

2. Run `python3 -m pytest tests/workflow_core/test_signoff.py tests/workflow_core/test_lifecycle_cli.py tests/workflow_core/test_team_gates.py -q`. Expected: `test_signoff.py` fails to import (`cannot import name 'signoff'`); `test_the_event_lists_the_change_requirements` fails with `KeyError: 'requirements'`; `test_requirement_confirmed_mirrors_the_requirements` fails with `KeyError: 'requirements'`.

3. Create `plugins/gin-workflow/src/scripts/workflow_core/signoff.py`:

   ```python
   """Requirement sign-off of a change: the requirement list a gate records, where a sign-off is read from, and the
   `06-signoff.md` file that archive writes."""

   from __future__ import annotations

   from dataclasses import dataclass
   from pathlib import Path
   import re
   from typing import Any, Mapping, Sequence

   from .checkout import main_checkout
   from .events import EventPersistenceError, WorkflowEvent, WorkflowEventStore
   from .specs import (DELTA_SECTIONS, Block, SpecsError, block_hash, change_epic, delta_blocks, line_value, load_config,
                       open_changes, sdd_config)
   from .waivers import WAIVER_EVENT_TYPE

   SIGNOFF_FILE = "06-signoff.md"
   _ROW = re.compile(r"^\|\s*(REQ-[A-Z][A-Z0-9-]*-\d{3,})\s*\|\s*([0-9a-f]{8})\s*\|\s*(added|modified|removed)\s*\|\s*$")


   @dataclass(frozen=True)
   class Signoff:
       """A change's sign-off: when, by whom, on what evidence, and the requirement hashes it covered."""

       at: str
       actor: str
       evidence: str
       source: str  # git, beads, or events
       requirements: tuple[tuple[str, str, str], ...] | None  # (id, hash8, op); None when the record lists none
       waived: bool = False

       def hash_of(self, req_id: str) -> str | None:
           return next((pinned for item, pinned, _ in self.requirements or () if item == req_id), None)

       def as_json(self, req_id: str) -> dict[str, Any]:
           return {"at": self.at, "actor": self.actor, "evidence": self.evidence, "hash8": self.hash_of(req_id),
                   "source": self.source, "waived": self.waived}


   def hash8(block: Block) -> str:
       """The hash a sign-off pins, 8 hex: the living block's base for a REMOVED block, else the block's own hash."""
       return (block.base if block.section == "REMOVED" and block.base else block_hash(block.text))[:8]


   def change_requirements(root: Path, change: Path) -> list[dict[str, str]]:
       """`{id, hash8, op}` for each block of the change's spec delta, in file order."""
       blocks, _ = delta_blocks(root, change)
       return [{"id": block.id, "hash8": hash8(block), "op": block.section.lower()}
               for block in blocks if block.section in DELTA_SECTIONS]


   def requirements_of(root: Path, workflow_id: str) -> list[dict[str, str]] | None:
       """The requirement list of a `requirement.confirmed` event: the delta rows of each open change whose proposal
       says `Epic: <workflow_id>`, with the SDD layout; None without setup, the SDD layout, or such a change."""
       try:
           cfg = sdd_config(load_config(root))
       except ValueError:  # SpecsError (no setup) and ConfigValidationError (invalid config) both derive from it
           return None
       if cfg["layout"] != "sdd":
           return None
       found: list[dict[str, str]] | None = None
       for change in open_changes(root, cfg):
           try:
               epic = change_epic(change)
           except SpecsError:  # a proposal without an `Epic:` line belongs to no workflow
               continue
           if epic == workflow_id:
               found = [*(found or []), *change_requirements(root, change)]
       return found


   def _requirements(value: Any) -> tuple[tuple[str, str, str], ...] | None:
       """A stored `requirements` list (an event payload is frozen into a tuple); None when absent."""
       if not isinstance(value, (list, tuple)):
           return None
       return tuple((str(item["id"]), str(item["hash8"]), str(item["op"])) for item in value
                    if isinstance(item, Mapping) and item.get("id") and item.get("hash8") and item.get("op"))


   def from_gates(gates: Mapping[str, Any]) -> Signoff | None:
       """The `requirement_confirmed` proof of an epic bead's `gates` metadata."""
       proof = gates.get("requirement_confirmed")
       if not isinstance(proof, Mapping):
           return None
       return Signoff(at=str(proof.get("at") or ""), actor=str(proof.get("actor") or ""),
                      evidence=str(proof.get("pr_url") or ""), source="beads",
                      requirements=_requirements(proof.get("requirements")))


   def from_events(events: Sequence[WorkflowEvent], epic: str) -> Signoff | None:
       """The epic's newest local `requirement.confirmed` event, else its newest `requirement_confirmed` waiver."""
       mine = [event for event in events if event.workflow_id == epic and isinstance(event.payload, Mapping)]
       confirmed = [event for event in mine if event.event_type == "requirement.confirmed"]
       if confirmed:
           event = confirmed[-1]
           return Signoff(at=event.timestamp, actor=event.actor or "", evidence=str(event.payload.get("evidence") or ""),
                          source="events", requirements=_requirements(event.payload.get("requirements")))
       waived = [event for event in mine
                 if event.event_type == WAIVER_EVENT_TYPE and event.payload.get("gate") == "requirement_confirmed"]
       if waived:
           event = waived[-1]
           return Signoff(at=event.timestamp, actor=str(event.payload.get("waived_by") or event.actor or ""),
                          evidence=str(event.payload.get("reason") or ""), source="events", requirements=None,
                          waived=True)
       return None


   def epic_signoff(gates: Mapping[str, Any], events: Sequence[WorkflowEvent], epic: str) -> Signoff | None:
       """An epic's sign-off: its bead's `gates`, then its newest local event, then its waiver."""
       return from_gates(gates) or from_events(events, epic)


   def bead_gates(row: Mapping[str, Any] | None) -> dict[str, Any]:
       """The `gates` metadata of a bead row; {} without a row."""
       from .team_beads import gates_of

       return gates_of(row) if isinstance(row, Mapping) else {}


   def load_gates(root: Path, epic: str) -> tuple[dict[str, Any], str | None]:
       """The epic bead's `gates`: ({}, None) without Beads, ({}, warning) when the tracker cannot answer."""
       from .tasks import backend, query_result

       try:
           if backend(root) != "beads":
               return {}, None
       except ValueError as error:  # ConfigValidationError: an invalid effective config
           return {}, f"bead {epic} unreadable: {error}"
       shown, cause = query_result(root, ["show", epic])
       if cause:
           return {}, f"bead {epic} unreadable: {cause}"
       return bead_gates(shown[0] if isinstance(shown, list) and shown else shown), None


   def load_events(root: Path) -> tuple[list[WorkflowEvent], str | None]:
       """The main checkout's event log: ([], None) without one, ([], warning) when it cannot be read."""
       path = main_checkout(Path(root)) / ".agent-workflow" / "runtime" / "events.jsonl"
       if not path.is_file():
           return [], None
       try:
           return WorkflowEventStore(path).read_all(), None
       except (EventPersistenceError, OSError, ValueError) as error:
           return [], f"event log unreadable: {error}"


   def render(found: Signoff, epic: str, rows: Sequence[Mapping[str, str]], *, hashes_at_archive: bool = False) -> str:
       """The text of `06-signoff.md`."""
       if found.waived:
           head = [f"Waived: {found.evidence}", f"By: {found.actor}", f"At: {found.at}"]
       else:
           head = [f"Signed off: {found.at}", f"By: {found.actor}", f"Evidence: {found.evidence}"]
       lines = ["# Sign-off", "", f"Epic: {epic}", *head, f"Source: {found.source}"]
       if hashes_at_archive:
           lines.append("Hashes: at archive")
       lines += ["", "| Requirement | hash8 | op |", "|---|---|---|",
                 *(f"| {row['id']} | {row['hash8']} | {row['op']} |" for row in rows)]
       return "\n".join(lines) + "\n"


   def read_file(path: Path) -> Signoff:
       """A `06-signoff.md` as a sign-off from git; ValueError when a required line or every row is missing."""
       text = Path(path).read_text(encoding="utf-8")
       rows = tuple((found.group(1), found.group(2), found.group(3))
                    for found in map(_ROW.match, text.splitlines()) if found)
       waived, signed, actor = line_value(text, "Waived"), line_value(text, "Signed off"), line_value(text, "By")
       if not actor or not (waived or signed) or not rows:
           raise ValueError("needs a By: line, a Signed off: or Waived: line, and at least one requirement row")
       if waived:
           return Signoff(at=line_value(text, "At"), actor=actor, evidence=waived, source="git", requirements=rows,
                          waived=True)
       return Signoff(at=signed, actor=actor, evidence=line_value(text, "Evidence"), source="git", requirements=rows)
   ```

4. Edit `lifecycle_cli.py`.
   - `_proof` (lines 200-204) becomes:

     ```python
     def _proof(payload: Mapping[str, Any], actor: str, at: str) -> dict[str, Any]:
         return {"pr_url": payload.get("pr_url", ""), "merge_commit": payload.get("merge_commit", ""),
                 "approvers": [a.get("email", "") for a in payload.get("approvers", []) if isinstance(a, Mapping)],
                 **({"pull_requests": payload["pull_requests"]} if "pull_requests" in payload else {}),
                 **({"requirements": payload["requirements"]} if "requirements" in payload else {}),
                 "actor": actor, "at": at}
     ```
   - in `_record_command`, between `payload = {**base_payload, "evidence": evidence, **team_payload}` and `if args.epic:`, insert:

     ```python
         if args.gate == "requirement-confirmed":
             from .signoff import requirements_of

             requirements = requirements_of(Path(args.repository).resolve(), args.workflow_id)
             if requirements is not None:
                 payload["requirements"] = requirements
                 if team_payload:
                     team_payload = {**team_payload, "requirements": requirements}
     ```

5. Edit `docs/reference/cli.md`, the `requirement-confirmed` row of the `gin record` table:

   ```text
   and in team mode it uses the policy of that kind |
   ```
   →
   ```text
   and in team mode it uses the policy of that kind. With `artifacts.layout: sdd`, the event lists each requirement of the epic's open change as `requirements: [{id, hash8, op}]`, and team mode copies the list into the epic bead's `gates` |
   ```

6. Run `python3 -m pytest tests/workflow_core/test_signoff.py tests/workflow_core/test_lifecycle_cli.py tests/workflow_core/test_team_gates.py tests/workflow_core/test_docs_coverage.py -q`. Expected: all pass.

7. Commit: `git add plugins/gin-workflow/src/scripts/workflow_core/signoff.py plugins/gin-workflow/src/scripts/workflow_core/lifecycle_cli.py docs/reference/cli.md tests/workflow_core/test_signoff.py tests/workflow_core/test_lifecycle_cli.py tests/workflow_core/test_team_gates.py && git commit -m "feat(signoff): requirement-confirmed lists each requirement with its hash (gin-workflow-ch2v)"` with the attribution trailer.

### Track 2: `gin specs archive` writes `06-signoff.md`
- **Dependencies**: Track 1
- **Files**:
  - Modify `plugins/gin-workflow/src/scripts/workflow_core/specs_archive.py:1-14` (imports)
  - Modify `plugins/gin-workflow/src/scripts/workflow_core/specs_archive.py:103-109` (write the sign-off after the move; add `_write_signoff`)
  - Modify `plugins/gin-workflow/src/scripts/workflow_core/specs_cli.py:191-199` (the `archive` branch prints warnings)
  - Modify `docs/reference/cli.md:154` (the `archive --change C` row)
  - Test `tests/workflow_core/test_specs_archive_trace.py`
- **Interfaces**:
  - Consumed: `signoff.SIGNOFF_FILE`, `signoff.change_requirements`, `signoff.load_gates`, `signoff.load_events`, `signoff.epic_signoff`, `signoff.render`, `signoff.hash8` (Track 1).
  - Produced: `archive(...)` returns two more keys, `signoff` (the written path, or None) and `warnings` (list of str); `specs_archive._write_signoff(root, folder, name, epic, delta_rows) -> tuple[str | None, list[str]]`.
- **Provider role**: `backend`
- **Model:** `sonnet`
- **Effort:** `medium`
- **Why:** one function added to the archive path with the code given; the cases (event, bead, waiver, none, changed hash, no hash list) are each tested.
- **Acceptance criteria**: US-2 of the spec passes as tests; `python3 -m pytest tests/workflow_core/test_specs_archive_trace.py tests/workflow_core/test_specs.py tests/workflow_core/test_docs_coverage.py -q` passes with every existing test unchanged.
- **Estimated complexity**: medium

Steps:

1. Write the failing tests. In `tests/workflow_core/test_specs_archive_trace.py`, add to the imports:

   ```python
   from workflow_core import signoff  # noqa: E402
   from workflow_core.events import WorkflowEvent, WorkflowEventStore  # noqa: E402
   ```

   and add this class after `TestArchive`:

   ```python
   class TestArchiveSignoff(unittest.TestCase):
       """`archive` writes the change's sign-off into the archived folder as 06-signoff.md."""

       def setUp(self):
           self.tmp = tempfile.TemporaryDirectory()
           self.root = make_repo(Path(self.tmp.name) / "repo")
           write(self.root, "docs/specs/auth/spec.md", AUTH_SPEC)
           write_activity(self.root)
           write(self.root, "docs/specs/README.md", "# Specs\n\n## Capabilities\n- [auth](auth/spec.md)\n")
           self.cfg = specs.sdd_config(specs.load_config(self.root))
           self.change = make_change(self.root)
           commit_all(self.root)
           self.folder = self.root / "docs/changes/archive/2026-10-03-ep-1-lockout"

       def tearDown(self):
           self.tmp.cleanup()

       def log(self, event_type: str, payload: dict) -> None:
           path = self.root / ".agent-workflow/runtime/events.jsonl"
           path.parent.mkdir(parents=True, exist_ok=True)
           WorkflowEventStore(path).append(WorkflowEvent.create(event_type=event_type, workflow_id="ep-1", actor="ba",
                                                                payload=payload))

       def text(self) -> str:
           return (self.folder / signoff.SIGNOFF_FILE).read_text(encoding="utf-8")

       def test_signoff_from_the_event_log_is_written_and_staged(self):
           requirements = signoff.requirements_of(self.root, "ep-1")
           self.log("requirement.confirmed", {"evidence": "docs/changes/ep-1-lockout", "requirements": requirements})
           result = archive(self.root, self.cfg, self.change, today=TODAY)
           for line in ("Epic: ep-1", "By: ba", "Evidence: docs/changes/ep-1-lockout", "Source: events",
                        f"| REQ-AUTH-003 | {requirements[0]['hash8']} | added |"):
               self.assertIn(line, self.text())
           self.assertNotIn("Hashes: at archive", self.text())
           self.assertEqual(([], "docs/changes/archive/2026-10-03-ep-1-lockout/06-signoff.md"),
                            (result["warnings"], result["signoff"]))
           self.assertIn("A  docs/changes/archive/2026-10-03-ep-1-lockout/06-signoff.md",
                         git(self.root, "status", "--porcelain"))

       def test_a_requirement_changed_after_signoff_keeps_the_signed_hash(self):
           self.log("requirement.confirmed", {"evidence": "e", "requirements": [
               {"id": "REQ-AUTH-003", "hash8": "00000000", "op": "added"}]})
           result = archive(self.root, self.cfg, self.change, today=TODAY)
           self.assertEqual(["REQ-AUTH-003 changed after sign-off"], result["warnings"])
           self.assertIn("| REQ-AUTH-003 | 00000000 | added |", self.text())

       def test_a_waiver_is_written(self):
           self.log("gate.waived", {"gate": "requirement_confirmed", "gate_class": "process", "reason": "spike",
                                    "scope_hash": "s", "waived_by": "lead", "follow_up_task_id": None})
           archive(self.root, self.cfg, self.change, today=TODAY)
           for line in ("Waived: spike", "By: lead", "Hashes: at archive", "| REQ-AUTH-003 |"):
               self.assertIn(line, self.text())

       def test_an_event_without_requirements_takes_the_delta_hashes(self):
           self.log("requirement.confirmed", {"evidence": "e"})
           archive(self.root, self.cfg, self.change, today=TODAY)
           pinned = signoff.hash8(specs.parse_blocks(ADDED_BLOCK)[0][0])
           self.assertIn("Hashes: at archive", self.text())
           self.assertIn(f"| REQ-AUTH-003 | {pinned} | added |", self.text())

       def test_bead_gates_win_over_the_event_log(self):
           self.log("requirement.confirmed", {"evidence": "local"})
           gates = {"requirement_confirmed": {"pr_url": "https://h/pull/1", "actor": "an@corp.com",
                                              "at": "2026-10-02T00:00:00Z"}}
           with mock.patch.object(signoff, "load_gates", return_value=(gates, None)):
               archive(self.root, self.cfg, self.change, today=TODAY)
           for line in ("Source: beads", "By: an@corp.com", "Evidence: https://h/pull/1"):
               self.assertIn(line, self.text())

       def test_without_a_signoff_archive_warns_and_writes_no_file(self):
           result = archive(self.root, self.cfg, self.change, today=TODAY)
           self.assertEqual((["ep-1-lockout: no sign-off found; 06-signoff.md not written"], None),
                            (result["warnings"], result["signoff"]))
           self.assertFalse((self.folder / signoff.SIGNOFF_FILE).exists())
           self.assertTrue((self.folder / "02-spec-delta.md").is_file())

       def test_cli_prints_the_warning(self):
           done = subprocess.run([sys.executable, str(LAUNCHER), "specs", "archive", "--change", "ep-1",
                                  "--repository", str(self.root)], capture_output=True, text=True)
           self.assertEqual(0, done.returncode, done.stderr)
           self.assertIn("warning: ep-1-lockout: no sign-off found; 06-signoff.md not written", done.stderr)
   ```

2. Run `python3 -m pytest tests/workflow_core/test_specs_archive_trace.py -q`. Expected: the seven new tests fail (`KeyError: 'warnings'` or a missing `06-signoff.md`); the existing tests pass.

3. Edit `specs_archive.py`.
   - imports (lines 11-13) become:

     ```python
     from . import signoff
     from .atomic import atomic_write_many
     from .specs import (Block, SpecsError, block_hash, change_epic, delta_blocks, in_flight_blocks, lint_change,
                         living_blocks, parse_blocks, render, shown, specs_dir, template_text, _BASE)
     ```
   - add after `move()`:

     ```python
     def _write_signoff(root: Path, folder: Path, name: str, epic: str | None,
                        delta_rows: list[dict[str, str]]) -> tuple[str | None, list[str]]:
         """Write `06-signoff.md` into the archived folder from the epic's sign-off and stage it: (its path or None,
         warnings). A missing or unreadable source is a warning; archive never fails because of sign-off."""
         missing = f"{name}: no sign-off found; {signoff.SIGNOFF_FILE} not written"
         if epic is None:
             return None, [missing]
         gates, gate_warning = signoff.load_gates(root, epic)
         events, event_warning = signoff.load_events(root)
         warnings = [warning for warning in (gate_warning, event_warning) if warning]
         found = signoff.epic_signoff(gates, events, epic)
         if found is None:
             return None, [*warnings, missing]
         rows = ([{"id": item, "hash8": pinned, "op": op} for item, pinned, op in found.requirements]
                 if found.requirements is not None else delta_rows)
         current = {row["id"]: row["hash8"] for row in delta_rows}
         warnings += [f"{row['id']} changed after sign-off" for row in rows
                      if row["id"] in current and current[row["id"]] != row["hash8"]]
         path = folder / signoff.SIGNOFF_FILE
         path.write_text(signoff.render(found, epic, rows, hashes_at_archive=found.requirements is None),
                         encoding="utf-8")
         subprocess.run(["git", "add", "--", str(path)], cwd=root, capture_output=True, check=False)
         return shown(root, path), warnings
     ```
   - at the end of `archive()`, replace:

     ```python
         atomic_write_many(writes, mode=0o644)
         move(root, change, Path(root) / target)
         return {"change": change.name, "archived_to": target.as_posix(),
     ```
     with:

     ```python
         try:
             epic: str | None = change_epic(change)
         except SpecsError:  # a proposal without an `Epic:` line names no sign-off
             epic = None
         delta_rows = signoff.change_requirements(root, change)
         atomic_write_many(writes, mode=0o644)
         move(root, change, Path(root) / target)
         written, warnings = _write_signoff(root, Path(root) / target, change.name, epic, delta_rows)
         return {"change": change.name, "archived_to": target.as_posix(), "signoff": written, "warnings": warnings,
     ```
     (the rest of the returned dict is unchanged).

4. Edit `specs_cli.py`, the `archive` branch: after `return _findings(conflict.errors, args.format, "ok")` and before `_emit(result, ...)`, insert:

   ```python
           for warning in result["warnings"]:
               print(f"warning: {warning}", file=sys.stderr)
   ```

5. Edit `docs/reference/cli.md`, the `archive --change C` row:

   ```text
   and in its `use-cases/` under `## Use Cases` |
   ```
   →
   ```text
   and in its `use-cases/` under `## Use Cases`. It then writes `06-signoff.md` into the archived folder from the sign-off of the change's epic (its bead's `gates`, else its newest local `requirement.confirmed` event, else a waiver) and stages it. Without a sign-off, or for a requirement changed after sign-off, it prints a warning on stderr |
   ```

6. Run `python3 -m pytest tests/workflow_core/test_specs_archive_trace.py tests/workflow_core/test_specs.py tests/workflow_core/test_docs_coverage.py -q`. Expected: all pass.

7. Commit: `git add plugins/gin-workflow/src/scripts/workflow_core/specs_archive.py plugins/gin-workflow/src/scripts/workflow_core/specs_cli.py docs/reference/cli.md tests/workflow_core/test_specs_archive_trace.py && git commit -m "feat(specs): archive writes the change's sign-off as 06-signoff.md (gin-workflow-ch2v)"` with the attribution trailer.

### Track 3: `gin specs trace --all` and its contract
- **Dependencies**: Track 2
- **Files**:
  - Create `plugins/gin-workflow/src/scripts/workflow_core/specs_trace_all.py`
  - Modify `plugins/gin-workflow/src/scripts/workflow_core/specs_cli.py:38` (`trace` takes `--change` or `--all`)
  - Modify `plugins/gin-workflow/src/scripts/workflow_core/specs_cli.py:104-114` (the `trace --all` branch after `reqs`)
  - Modify `docs/reference/cli.md:141-162` (layout sentence, `trace --all` row, exit codes, new `Requirement trace` section)
  - Modify `docs/guides/sdd.md:217-219` (new `Sign-off` section before `## Epic kinds`)
  - Create `tests/workflow_core/test_specs_trace_all.py`
  - Create `tests/gin_qa/test_trace_cases.py`
- **Interfaces**:
  - Consumed: `signoff.load_events`, `signoff.epic_signoff`, `signoff.bead_gates`, `signoff.read_file`, `signoff.SIGNOFF_FILE`, `Signoff.as_json`, `signoff.requirements_of` (tests) (Track 1); `archive` writing `06-signoff.md` (Track 2, used by the tests); `specs_trace.req_sources`, `specs_trace._tests_md_rows`; `tasks.backend`, `tasks.query_result`.
  - Produced: `specs_trace_all.SCHEMA = 1`; `specs_trace_all.trace_all(root, cfg) -> dict`; `specs_trace_all.text_line(row) -> str`; `specs_trace_all._gin_qa() -> str | None` (patched in tests); `gin specs trace --all [--format text|json]`.
- **Provider role**: `backend`
- **Model:** `sonnet`
- **Effort:** `high`
- **Why:** joins five sources (living specs, open and archived changes, sign-off, beads, gin-qa, tests) with null and fallback rules per source; the code is given, but many edge cases interact.
- **Acceptance criteria**: US-3 and US-4 of the spec pass as tests; `python3 -m pytest tests/workflow_core/test_specs_trace_all.py tests/workflow_core/test_specs_archive_trace.py tests/gin_qa/test_trace_cases.py tests/workflow_core/test_docs_coverage.py -q` passes; `gin specs trace --change` tests are unchanged.
- **Estimated complexity**: high

Steps:

1. Write the failing tests.

   Create `tests/workflow_core/test_specs_trace_all.py`:

   ```python
   """`gin specs trace --all`: every requirement with its changes, sign-off, beads, cases, and tests."""

   from __future__ import annotations

   from datetime import date
   import json
   from pathlib import Path
   import subprocess
   import sys
   import tempfile
   import unittest
   from unittest import mock

   sys.path.insert(0, str(Path(__file__).resolve().parent))

   from specs_fixtures import (ADDED_BLOCK, AUTH_SPEC, LAUNCHER, commit_all, delta, make_change, make_repo,  # noqa: E402
                               write, write_activity)
   from team_fixtures import fake_cli  # noqa: E402
   from workflow_core import signoff, specs, specs_trace_all  # noqa: E402
   from workflow_core.events import WorkflowEvent, WorkflowEventStore  # noqa: E402
   from workflow_core.specs_archive import archive  # noqa: E402

   TODAY = date(2026, 10, 3)
   PROPOSED = ADDED_BLOCK.replace("REQ-AUTH-003", "REQ-AUTH-004").replace("Lock account after failed logins",
                                                                          "Second factor")
   REMOVED = "### REQ-AUTH-002: Reject wrong password\n<!-- base: {base} -->\nReason: folded into REQ-AUTH-001\n"
   TESTS_MD = ("| TC | REQ | type | evidence |\n|---|---|---|---|\n"
               "| TC-AUTH-003 | REQ-AUTH-003 | manual | passed |\n")


   class TestTraceAll(unittest.TestCase):
       def setUp(self):
           self.tmp = tempfile.TemporaryDirectory()
           self.root = make_repo(Path(self.tmp.name) / "repo")
           write(self.root, "docs/specs/auth/spec.md", AUTH_SPEC)
           write_activity(self.root)
           write(self.root, "docs/specs/README.md", "# Specs\n\n## Capabilities\n- [auth](auth/spec.md)\n")
           self.cfg = specs.sdd_config(specs.load_config(self.root))
           no_qa = mock.patch.object(specs_trace_all, "_gin_qa", return_value=None)
           no_qa.start()
           self.addCleanup(no_qa.stop)

       def tearDown(self):
           self.tmp.cleanup()

       def signed_change(self, name: str, epic: str, spec_delta: str) -> Path:
           change = make_change(self.root, name, epic=epic, spec_delta=spec_delta)
           path = self.root / ".agent-workflow/runtime/events.jsonl"
           path.parent.mkdir(parents=True, exist_ok=True)
           WorkflowEventStore(path).append(WorkflowEvent.create(
               event_type="requirement.confirmed", workflow_id=epic, actor="ba",
               payload={"evidence": name, "requirements": signoff.requirements_of(self.root, epic)}))
           return change

       def build(self) -> None:
           """REQ-AUTH-003 added and REQ-AUTH-002 removed by archived, signed changes; REQ-AUTH-004 proposed by an
           open, signed change; a test file names REQ-AUTH-001."""
           base = specs.requirement_hash(self.root, self.cfg, "REQ-AUTH-002")[1]
           lockout = self.signed_change("ep-1-lockout", "ep-1", delta(added=ADDED_BLOCK))
           write(self.root, "docs/changes/ep-1-lockout/05-tests.md", TESTS_MD)
           commit_all(self.root)
           archive(self.root, self.cfg, lockout, today=TODAY)
           cleanup = self.signed_change("ep-2-cleanup", "ep-2", delta(removed=REMOVED.format(base=base)))
           commit_all(self.root)
           archive(self.root, self.cfg, cleanup, today=TODAY)
           self.signed_change("ep-3-mfa", "ep-3", delta(added=PROPOSED))
           write(self.root, "tests/test_auth.py", "def test_sign_in():  # REQ-AUTH-001\n    pass\n")
           commit_all(self.root)

       def rows(self) -> dict[str, dict]:
           return {row["id"]: row for row in specs_trace_all.trace_all(self.root, self.cfg)["requirements"]}

       def test_living_proposed_and_removed_rows_carry_their_signoff(self):
           self.build()
           rows = self.rows()
           self.assertEqual({"REQ-AUTH-001": "living", "REQ-AUTH-002": "removed", "REQ-AUTH-003": "living",
                             "REQ-AUTH-004": "proposed"}, {req: row["state"] for req, row in rows.items()})
           lockout = rows["REQ-AUTH-003"]["signoff"]
           self.assertEqual(("git", "ep-1-lockout", True), (lockout["source"], lockout["change"], lockout["current"]))
           self.assertEqual([("ep-1-lockout", "ep-1", "added", "2026-10-03")],
                            [(c["change"], c["epic"], c["op"], c["archived"]) for c in rows["REQ-AUTH-003"]["changes"]])
           removed = rows["REQ-AUTH-002"]
           self.assertEqual((None, None, "git", "ep-2-cleanup", None),
                            (removed["hash8"], removed["source"], removed["signoff"]["source"],
                             removed["signoff"]["change"], removed["signoff"]["current"]))
           proposed = rows["REQ-AUTH-004"]
           self.assertEqual(("events", None, True),
                            (proposed["signoff"]["source"], proposed["changes"][0]["archived"], proposed["signoff"]["current"]))
           self.assertIsNone(rows["REQ-AUTH-001"]["signoff"])
           self.assertEqual(["tests/test_auth.py"], rows["REQ-AUTH-001"]["tests"])
           self.assertEqual(["docs/changes/archive/2026-10-03-ep-1-lockout/05-tests.md#TC-AUTH-003"],
                            rows["REQ-AUTH-003"]["tests"])

       def test_a_requirement_edited_after_signoff_is_stale(self):
           self.build()
           spec = self.root / "docs/specs/auth/spec.md"
           spec.write_text(spec.read_text(encoding="utf-8").replace("for 15 minutes", "for 30 minutes"),
                           encoding="utf-8")
           row = self.rows()["REQ-AUTH-003"]
           self.assertIs(False, row["signoff"]["current"])
           self.assertIn("signoff:stale", specs_trace_all.text_line(row))

       def test_beads_come_from_req_labels_and_gates_from_the_epic_bead(self):
           self.build()
           gates = {"requirement_confirmed": {"pr_url": "https://h/pull/3", "actor": "an@corp.com",
                                              "at": "2026-10-02T00:00:00Z"}}
           listed = [{"id": "ep-1.2", "title": "Lockout counter", "status": "closed", "labels": ["req:REQ-AUTH-003"]},
                     {"id": "ep-1.3", "title": "Other", "status": "open", "labels": ["req:REQ-AUTH-001"]},
                     {"id": "ep-3", "title": "MFA", "status": "open", "labels": [],
                      "metadata": {"gates": json.dumps(gates)}}]
           with mock.patch.object(specs_trace_all, "backend", return_value="beads"), \
                   mock.patch.object(specs_trace_all, "query_result", return_value=(listed, None)):
               rows = self.rows()
           self.assertEqual([{"id": "ep-1.2", "title": "Lockout counter", "status": "closed"}], rows["REQ-AUTH-003"]["beads"])
           self.assertEqual([], rows["REQ-AUTH-004"]["beads"])
           self.assertEqual(("beads", "https://h/pull/3", None),
                            (rows["REQ-AUTH-004"]["signoff"]["source"], rows["REQ-AUTH-004"]["signoff"]["evidence"],
                             rows["REQ-AUTH-004"]["signoff"]["current"]))

       def test_cases_come_from_gin_qa_export(self):
           self.build()
           stub = fake_cli(Path(self.tmp.name) / "bin", "gin-qa", [{"argv": ["cases", "export"], "stdout": {"cases": [
               {"id": "TC-AUTH-002", "reqs": [{"id": "REQ-AUTH-001", "hash8": "x"}], "effective_result": "outdated"},
               {"id": "TC-AUTH-001", "reqs": [{"id": "REQ-AUTH-001", "hash8": "y"}], "effective_result": "passed"}]}}])
           with mock.patch.object(specs_trace_all, "_gin_qa", return_value=str(stub)):
               result = specs_trace_all.trace_all(self.root, self.cfg)
           rows = {row["id"]: row for row in result["requirements"]}
           self.assertEqual([{"id": "TC-AUTH-001", "effective_result": "passed"},
                             {"id": "TC-AUTH-002", "effective_result": "outdated"}], rows["REQ-AUTH-001"]["cases"])
           self.assertEqual([], rows["REQ-AUTH-003"]["cases"])
           self.assertEqual([], result["warnings"])

       def test_missing_sources_are_null_with_a_warning(self):
           self.build()
           result = specs_trace_all.trace_all(self.root, self.cfg)
           self.assertTrue(all(row["cases"] is None and row["beads"] is None for row in result["requirements"]))
           self.assertEqual(["cases: gin-qa not found on PATH"], result["warnings"])
           with mock.patch.object(specs_trace_all, "backend", return_value="beads"), \
                   mock.patch.object(specs_trace_all, "query_result", return_value=(None, "bd not found")):
               self.assertIn("beads: bd not found", specs_trace_all.trace_all(self.root, self.cfg)["warnings"])

       def test_a_malformed_signoff_file_falls_back_to_the_event_log(self):
           self.build()
           (self.root / "docs/changes/archive/2026-10-03-ep-1-lockout/06-signoff.md").write_text("# Sign-off\n",
                                                                                              encoding="utf-8")
           result = specs_trace_all.trace_all(self.root, self.cfg)
           row = next(row for row in result["requirements"] if row["id"] == "REQ-AUTH-003")
           self.assertEqual("events", row["signoff"]["source"])
           self.assertTrue(any("06-signoff.md" in warning for warning in result["warnings"]))

       def test_legacy_layout_has_no_requirements(self):
           legacy = make_repo(Path(self.tmp.name) / "legacy", layout="legacy")
           cfg = specs.sdd_config(specs.load_config(legacy))
           self.assertEqual({"schema": 1, "layout": "legacy", "requirements": [], "warnings": [], "skipped": []},
                            specs_trace_all.trace_all(legacy, cfg))

       def test_cli_all_excludes_change_and_prints_json_and_text(self):
           self.build()

           def run(*args: str) -> subprocess.CompletedProcess[str]:
               return subprocess.run([sys.executable, str(LAUNCHER), "specs", "trace", *args, "--repository",
                                      str(self.root)], capture_output=True, text=True)

           self.assertEqual(2, run("--all", "--change", "ep-3").returncode)
           self.assertEqual(2, run().returncode)
           done = run("--all", "--format", "json")
           self.assertEqual(0, done.returncode, done.stderr)
           self.assertEqual((1, "sdd"), (json.loads(done.stdout)["schema"], json.loads(done.stdout)["layout"]))
           self.assertIn("REQ-AUTH-004 proposed signoff:yes beads:- cases:", run("--all").stdout)
   ```

   Create `tests/gin_qa/test_trace_cases.py`:

   ```python
   """`gin specs trace --all` joins the cases of the real gin-qa CLI."""

   from __future__ import annotations

   import contextlib
   import io
   import json
   import os
   from pathlib import Path
   import sys
   import unittest
   from unittest import mock

   sys.path.insert(0, str(Path(__file__).resolve().parent))
   sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "plugins/gin-qa/src/scripts"))

   from qa_fixtures import QA_LAUNCHER, TOOLS_PATH, case  # noqa: E402
   from test_cases_cli import QaCase  # noqa: E402
   from workflow_core import cli as gin_cli  # noqa: E402


   @unittest.skipIf(os.name == "nt", "runs the gin-qa launcher through its #! line")
   class TestTraceJoinsCases(QaCase):
       def test_a_pinned_case_shows_with_its_effective_result(self):
           self.write_cases(case("TC-AUTH-001", self.ref("REQ-AUTH-001")))
           search = os.pathsep.join([str(self.bin), str(QA_LAUNCHER.parent), TOOLS_PATH])
           out = io.StringIO()
           with mock.patch.dict(os.environ, {"PATH": search}), contextlib.redirect_stdout(out):
               code = gin_cli.main(["specs", "trace", "--all", "--repository", str(self.root), "--format", "json"])
           self.assertEqual(0, code)
           rows = {row["id"]: row for row in json.loads(out.getvalue())["requirements"]}
           self.assertEqual([{"id": "TC-AUTH-001", "effective_result": "not run"}], rows["REQ-AUTH-001"]["cases"])
           self.assertEqual([], rows["REQ-AUTH-002"]["cases"])
   ```

2. Run `python3 -m pytest tests/workflow_core/test_specs_trace_all.py tests/gin_qa/test_trace_cases.py -q`. Expected: `test_specs_trace_all.py` fails to import (`cannot import name 'specs_trace_all'`); `test_trace_cases.py` fails with exit code 2 from `gin specs trace` (`--change` is required).

3. Create `plugins/gin-workflow/src/scripts/workflow_core/specs_trace_all.py`:

   ```python
   """`gin specs trace --all`: every requirement with its changes, sign-off, beads, gin-qa cases, and tests (schema 1)."""

   from __future__ import annotations

   import json
   from pathlib import Path
   import re
   import shutil
   import subprocess
   from typing import Any, Mapping, Sequence

   from . import signoff
   from .events import WorkflowEvent
   from .specs import (SpecsError, block_hash, cap_of, change_epic, change_file, changes_dir, delta_blocks,
                       living_blocks, open_changes, shown)
   from .specs_trace import _tests_md_rows, req_sources
   from .tasks import backend, query_result

   SCHEMA = 1
   _DATED = re.compile(r"^(\d{4}-\d{2}-\d{2})-(.+)$")


   def _gin_qa() -> str | None:
       return shutil.which("gin-qa")


   def _changes(root: Path, cfg: Mapping[str, Any]) -> list[tuple[Path, str, str | None]]:
       """(folder, change name, archive date or None): every archived change, oldest first, then every open one."""
       base = changes_dir(root, cfg) / "archive"
       archived = []
       for folder in (sorted(base.iterdir()) if base.is_dir() else []):
           named = _DATED.match(folder.name)
           if folder.is_dir() and named and change_file(folder, "spec-delta").is_file():
               archived.append((folder, named.group(2), named.group(1)))
       return [*archived, *((folder, folder.name, None) for folder in open_changes(root, cfg))]


   def _beads(root: Path) -> tuple[list[Mapping[str, Any]] | None, str | None]:
       """Every bead row; (None, None) without Beads, (None, warning) when bd cannot answer."""
       try:
           if backend(root) != "beads":
               return None, None
       except ValueError as error:  # ConfigValidationError: an invalid effective config
           return None, f"beads: {error}"
       rows, cause = query_result(root, ["list", "--all", "--limit", "0"])
       if cause or not isinstance(rows, list):
           return None, f"beads: {cause or 'unexpected bd list output'}"
       return [row for row in rows if isinstance(row, Mapping)], None


   def _cases(root: Path) -> tuple[dict[str, list[dict[str, Any]]] | None, str | None]:
       """REQ id -> `{id, effective_result}` of each gin-qa case that pins it; (None, warning) without gin-qa."""
       executable = _gin_qa()
       if executable is None:
           return None, "cases: gin-qa not found on PATH"
       try:
           done = subprocess.run([executable, "cases", "export", "--format", "json", "--repository", str(root)],
                                 cwd=root, text=True, capture_output=True, check=False, timeout=300)
       except (OSError, subprocess.SubprocessError) as error:
           return None, f"cases: gin-qa failed: {error}"
       if done.returncode != 0:
           first = next((line.strip() for line in done.stderr.splitlines() if line.strip()), "")
           return None, f"cases: gin-qa exited {done.returncode}" + (f": {first}" if first else "")
       try:
           rows = json.loads(done.stdout)["cases"]
       except (ValueError, KeyError, TypeError) as error:
           return None, f"cases: unreadable gin-qa output: {error}"
       found: dict[str, list[dict[str, Any]]] = {}
       for row in rows:
           for ref in row.get("reqs") or ():
               found.setdefault(str(ref.get("id")), []).append(
                   {"id": row.get("id"), "effective_result": row.get("effective_result")})
       return found, None


   def _signoff(root: Path, folder: Path, archived: str | None, epic: str | None,
                beads_by_id: Mapping[str, Mapping[str, Any]], events: Sequence[WorkflowEvent],
                warnings: list[str]) -> signoff.Signoff | None:
       """A change's sign-off: its `06-signoff.md` when archived, else (or when that file is malformed) its epic's."""
       path = folder / signoff.SIGNOFF_FILE
       if archived is not None and path.is_file():
           try:
               return signoff.read_file(path)
           except (OSError, UnicodeDecodeError, ValueError) as error:
               warnings.append(f"{shown(root, path)}: {error}")
       if epic is None:
           return None
       return signoff.epic_signoff(signoff.bead_gates(beads_by_id.get(epic)), events, epic)


   def _row(req_id: str, title: str, state: str, digest: str | None, source: str | None) -> dict[str, Any]:
       return {"id": req_id, "title": title, "capability": cap_of(req_id), "state": state, "hash8": digest,
               "source": source, "changes": []}


   def _current(signed: str | None, now: str | None) -> bool | None:
       return None if signed is None or now is None else signed == now


   def trace_all(root: Path, cfg: Mapping[str, Any]) -> dict[str, Any]:
       """Every living, proposed, and removed requirement with its changes, sign-off, beads, cases, and tests."""
       if cfg["layout"] != "sdd":
           return {"schema": SCHEMA, "layout": cfg["layout"], "requirements": [], "warnings": [], "skipped": []}
       events, event_warning = signoff.load_events(root)
       beads, bead_warning = _beads(root)
       cases, case_warning = _cases(root)
       warnings = [warning for warning in (event_warning, bead_warning, case_warning) if warning]
       beads_by_id = {str(row.get("id")): row for row in beads or ()}
       changes = []
       for folder, name, archived in _changes(root, cfg):
           blocks, errors = delta_blocks(root, folder)
           warnings += errors
           try:
               epic: str | None = change_epic(folder)
           except SpecsError:  # a proposal without an `Epic:` line names no sign-off
               epic = None
           found = _signoff(root, folder, archived, epic, beads_by_id, events, warnings)
           changes.append((folder, name, archived, epic, blocks, found))
       rows = {req_id: _row(req_id, block.title, "living", block_hash(block.text)[:8],
                            f"{shown(root, path)}:{block.start + 1}")
               for req_id, (path, block) in living_blocks(root, cfg).items()}
       for folder, _, archived, _, blocks, _ in changes:
           for block in blocks:
               if archived is None and block.section == "ADDED" and block.id not in rows:
                   rows[block.id] = _row(block.id, block.title, "proposed", block_hash(block.text)[:8],
                                         f"{shown(root, change_file(folder, 'spec-delta'))}:{block.start + 1}")
       for _, _, archived, _, blocks, _ in changes:
           for block in blocks:
               if archived is not None and block.section == "REMOVED" and block.id not in rows:
                   rows[block.id] = _row(block.id, block.title, "removed", None, None)
       for _, name, archived, epic, blocks, found in changes:
           for block in blocks:
               if block.id in rows:
                   rows[block.id]["changes"].append({"change": name, "epic": epic, "op": block.section.lower(),
                                                     "archived": archived,
                                                     "signoff": found.as_json(block.id) if found else None})
       tests, skipped = req_sources(root, cfg, rows)
       for folder, *_ in changes:
           tests_md = change_file(folder, "tests")
           for case, ids, evidence in _tests_md_rows(tests_md):
               if evidence and evidence != "-":
                   for req_id in ids & rows.keys():
                       tests[req_id].append(f"{shown(root, tests_md)}#{case}")
       for req_id, row in rows.items():
           last = next((entry for entry in reversed(row["changes"]) if entry["signoff"]), None)
           row["signoff"] = None if last is None else {**last["signoff"], "change": last["change"],
                                                       "current": _current(last["signoff"]["hash8"], row["hash8"])}
           row["beads"] = None if beads is None else sorted(
               ({"id": str(bead.get("id")), "title": bead.get("title", ""), "status": bead.get("status", "")}
                for bead in beads if f"req:{req_id}" in (bead.get("labels") or ())), key=lambda bead: bead["id"])
           row["cases"] = None if cases is None else sorted(cases.get(req_id, []), key=lambda item: str(item["id"]))
           row["tests"] = sorted(tests[req_id])
       return {"schema": SCHEMA, "layout": "sdd", "requirements": [rows[req_id] for req_id in sorted(rows)],
               "warnings": warnings, "skipped": skipped}


   def _count(items: list[Any] | None) -> str:
       return "-" if items is None else str(len(items))


   def text_line(row: Mapping[str, Any]) -> str:
       """`<id> <state> signoff:<yes|stale|waived|no> beads:<n|-> cases:<n|-> tests:<n>`."""
       found = row["signoff"]
       state = ("no" if found is None else "waived" if found["waived"] else "stale" if found["current"] is False
                else "yes")
       return (f"{row['id']} {row['state']} signoff:{state} beads:{_count(row['beads'])} "
               f"cases:{_count(row['cases'])} tests:{len(row['tests'])}")
   ```

4. Edit `specs_cli.py`.
   - the `trace` parser (line 38):

     ```python
         sub.add_parser("trace", parents=[common]).add_argument("--change", required=True)
     ```
     →
     ```python
         item = sub.add_parser("trace", parents=[common])
         scope = item.add_mutually_exclusive_group(required=True)
         scope.add_argument("--change")
         scope.add_argument("--all", action="store_true")
     ```
   - in `_run`, right after the `reqs` branch (its `return 0`) and before `if args.command == "lint" and args.spec:`, insert:

     ```python
         if args.command == "trace" and args.all:
             from .specs_trace_all import text_line, trace_all

             result = trace_all(root, cfg)
             _emit(result, args.format, "\n".join([*(text_line(row) for row in result["requirements"]),
                                                   *(f"warning: {item}" for item in result["warnings"]),
                                                   *(f"skipped: {item}" for item in result["skipped"])]))
             return 0
     ```

5. Edit `docs/reference/cli.md`. Each replacement gives the old text, then the new text.
   - the layout sentence under the `gin specs` usage block:

     ```text
     Every command except `template`, `migrate`, `reqs` without `--change`, and `lint --spec` requires that layout;
     ```
     →
     ```text
     Every command except `template`, `migrate`, `reqs` without `--change`, `trace --all`, and `lint --spec` requires that layout;
     ```
   - insert this row right after the `trace --change C` row:

     ```text
     | `trace --all` | List every requirement with its changes, sign-off, beads, gin-qa cases, and tests ([Requirement trace](#requirement-trace)) |
     ```
   - the exit codes line:

     ```text
     1 findings (lint errors, untraced requirements, archive conflicts,
     ```
     →
     ```text
     1 findings (lint errors, untraced requirements of `trace --change`, archive conflicts,
     ```
   - insert this section between that exit codes line and `## \`gin docs\`` (the heading line `## ` followed by `gin docs` in backticks), with a blank line before and after:

     ````markdown
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
     | `changes[].signoff` | `at`, `actor`, `evidence`, `hash8` (the hash at sign-off, null when unknown), `source`, and `waived`; null without a sign-off |
     | `requirements[].signoff` | The last change sign-off, plus `change` and `current`: true when its `hash8` equals the requirement's, false when it differs, null when either is null |
     | `requirements[].beads` | `{id, title, status}` of each bead labelled `req:<id>`; null with the markdown task backend or when `bd` fails |
     | `requirements[].cases` | `{id, effective_result}` of each gin-qa case that pins the requirement, from `gin-qa cases export`; null without gin-qa |
     | `requirements[].tests` | Test files that name the id, and the `05-tests.md#<case>` rows of open and archived changes |
     | `warnings`, `skipped` | Sources that could not be read; workspace children that could not be listed |

     A change's sign-off comes from its `06-signoff.md` (`source: git`), else its epic bead's `gates` (`beads`), else the newest local `requirement.confirmed` event of the epic (`events`). A `requirement_confirmed` waiver comes last, with `waived: true` and the reason in `evidence`. The text output prints one line per requirement: `<id> <state> signoff:<yes|stale|waived|no> beads:<n|-> cases:<n|-> tests:<n>`.
     ````

6. Edit `docs/guides/sdd.md`: insert this section right before `## Epic kinds { #epic-kinds }`, with a blank line after it:

   ```markdown
   ## Sign-off

   A change's sign-off is the `requirement-confirmed` gate of its epic. The gate records each requirement of the spec delta with the first 8 hex characters of its hash, so a requirement edited after sign-off shows as stale. Until archive, the sign-off lives in the local event log and, in team mode, in the epic bead's `gates`. `specs archive` writes it into the archived folder as `06-signoff.md`, so it is in git. `gin specs trace --all` reads all three; see [Requirement trace](../reference/cli.md#requirement-trace).
   ```

7. Run `python3 -m pytest tests/workflow_core/test_specs_trace_all.py tests/workflow_core/test_specs_archive_trace.py tests/gin_qa/test_trace_cases.py tests/workflow_core/test_docs_coverage.py tests/workflow_core/test_specs.py -q`. Expected: all pass.

8. Commit: `git add plugins/gin-workflow/src/scripts/workflow_core/specs_trace_all.py plugins/gin-workflow/src/scripts/workflow_core/specs_cli.py docs/reference/cli.md docs/guides/sdd.md tests/workflow_core/test_specs_trace_all.py tests/gin_qa/test_trace_cases.py && git commit -m "feat(specs): trace --all joins sign-off, beads, cases, and tests per requirement (gin-workflow-ch2v)"` with the attribution trailer.

## Integration
- **Branch**: `feat/req-signoff-trace` (worktree `.claude/worktrees/req-signoff-trace`)
- **Merge strategy**: sequential

## Validation
- [ ] `python3 -m pytest -n auto` passes (the pre-push hook runs it once, at ship).
- [ ] Manual, in a scratch SDD repository: `gin record requirement-confirmed --workflow-id <epic> ...` shows `requirements` in the event; `gin specs archive --change <epic>` writes and stages `06-signoff.md`; `gin specs trace --all --format json` shows the requirement with `signoff.source: git`.
- [ ] At ship: `bd -C gin-workflow ship req-signoff-trace` after the epic closes, so `gin-console-rm-req-signoff` sees the capability.

## Notes
- The Parent Bead `gin-workflow-ch2v` stays open until the merge into `master` is confirmed; tracks close when their tests and review pass.
- `docs/changelog.md` gets its entry at the next release (`docs/contributing.md:115`).
- The user may override `Model:` and `Effort:` before plan approval.
