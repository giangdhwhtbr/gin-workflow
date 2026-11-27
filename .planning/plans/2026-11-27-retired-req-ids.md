# Plan: Retired requirement IDs

Workflow: retired-req-ids
Spec: `.planning/specs/2026-11-27-retired-req-ids-design.md`

## Objective

A requirement ID that a spec review drops, or that a change removes, stays explained and taken. A change delta gets a `## RETIRED` section (heading and `Reason:`), archive writes it and every `REMOVED` block into `## Retired` of the living `spec.md`, `gin specs next-id` also counts every id that git history ever carried on a heading, every reader of living requirements skips retired ones (and gin-qa reports cases that still pin them), and `gin specs gaps [--into]` lists and drafts the entries for gaps that exist already. GitHub issue #39.

## Global Constraints

Copied from the spec (Out of scope, Errors and compatibility):

- Renumbering to close a gap; the skill forbids it.
- Writing `## Retired` entries for `REMOVED` blocks archived before this epic without a command run: `gin specs gaps` proposes them, a person runs it.
- A new state value in `trace --all`: retired ids keep state `removed`, the value gin-console's `State` literal accepts (`gin-console/backend/src/gin_console/requirements/models.py:5`).
- The legacy layout, which has no REQ-IDs.
- `docs/changelog.md`, written at release time (`docs/contributing.md:115`).
- `spec.md` and deltas without the new sections parse and lint as today.
- A `## Retired` block with a malformed heading is reported as malformed, as any block is today.
- `trace --all` keeps its state values; the `reason` key and the `retired` op are additions, and gin-console's `op` field is a plain string.
- History scan failures (no git, git log error) add a warning and fall back to the current sources; `next-id` never fails because of them.
- gin-qa and `gin specs` ship in this repository and install together, so the `RETIRED` section needs no version check in gin-qa.

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
- Problem statement: an id dropped from an open delta is gone from every tree, so `next_id` (`specs.py:1015`) hands it out again when it was the highest; archive deletes a `REMOVED` block from `spec.md` without a trace (`specs_archive.py:27`); no delta section can hold a dropped id (`specs.py:26`, `specs.py:881`).
- Success criteria: every acceptance criterion of US-1 to US-5 has a passing test; the full suite (`python3 -m pytest -n auto`) passes; `gin docs check` passes on every changed docs page.
- Constraints: the Global Constraints above.
- Non-goals: see Global Constraints.

## Approach Options
### Option 1: retired entries keep the `### REQ-…:` heading under a `Retired` section
- Summary: `## RETIRED` in a delta and `## Retired` in `spec.md` hold `### REQ-<CAP>-<NNN>: <title>` plus `Reason:`. `parse_blocks` already records each block's section; `living_blocks` leaves retired blocks out and a new `retired_blocks` returns them.
- Pros: `_HEADING_LINE`, `ids_at_ref`, `scan_ids` and `git grep '^### REQ-'` see the id unchanged, so `next-id` counts it with no code; one filter covers every reader that goes through `living_blocks`.
- Cons: readers that call `parse_blocks` on `spec.md` directly need their own decision (listed in the spec's Testing risk).

### Option 2: a separate retired list per capability
- Summary: `docs/specs/<cap>/retired.md` or a table in `spec.md`.
- Pros: no reader of living blocks sees it.
- Cons: a new parser; `scan_ids`, `ids_at_ref` and the regexes need extending; another file to lint and archive.

### Recommended Approach
- Selected option: Option 1, confirmed in discuss.
- Rationale: the id scanners keep working unchanged and the filter sits in one place.

Decisions this plan takes against the spec text, for the user to confirm with the plan:
- Diagrams cite no REQ-ID (`lint_diagrams`, `specs.py:446`, checks mermaid kinds only), so only use-case lint gets the `is retired` message.
- `gin specs reqs` adds the `reason` key to every row: the `Reason:` value for `RETIRED` and `REMOVED` rows, null otherwise.
- The archive result's `retired` list holds the `RETIRED` ids; `REMOVED` ids stay in `removed`, though they also get a `## Retired` entry.
- `trace --all` adds no row for an id that only an open change's `## RETIRED` names; the row appears once the change is archived.
- `gin-qa cases new --req` of a retired id fails with `<id> is retired: <reason>` instead of `no such requirement`.
- `gaps --into` of a missing or archived change exits 2 with `unknown change`, as every other `--change` option does (`specs.find_change`), not 1.
- `docs/changelog.md` is not edited: the changelog is written at release time.

## Scope
- In scope: `workflow_core/specs.py`, `specs_archive.py`, `signoff.py`, `specs_reqs.py`, `specs_trace.py`, `specs_trace_all.py`, `specs_export.py`, `specs_explain.py`, `specs_cli.py`, `specs_gaps.py` (new); `gin_qa/reqs.py`, `gin_qa/cli.py`; templates `spec.md`, `spec-delta.md`; skills `sdd`, `qa-track`; `docs/guides/sdd.md`, `docs/guides/sdd.vi.md`, `docs/reference/cli.md`; their tests.
- Out of scope: `docs/changelog.md`; `plugins/*/dist/` (built by `install.sh`); gin-console; renumbering.

## Execution Strategy

```yaml
execution_strategy:
  mode: direct
  workers:
    mode: sequential
  rationale: Tracks 1, 2 and 5 all edit specs.py and Track 3 and 4 build on the RETIRED section of Track 1, so one track at a time on one branch avoids conflicts.
```

## Tasks

### Track 1: The retired section: parse, lint, sign-off, archive
- **Dependencies**: none
- **Files**:
  - Modify `plugins/gin-workflow/src/scripts/workflow_core/specs.py:26` (`DELTA_SECTIONS` gains `RETIRED`; `RETIRED_SECTION`, `_REASON`)
  - Modify `plugins/gin-workflow/src/scripts/workflow_core/specs.py:360-365` (`is_retired`, `living_blocks` skips retired, `retired_blocks`, `lint_retired`, `append_to_section`)
  - Modify `plugins/gin-workflow/src/scripts/workflow_core/specs.py:420-422` (`delta_blocks` message names every section)
  - Modify `plugins/gin-workflow/src/scripts/workflow_core/specs.py:652-690` (`lint_use_cases`: `is retired`)
  - Modify `plugins/gin-workflow/src/scripts/workflow_core/specs.py:692-707` (`lint_living`: retired blocks need only `Reason:`)
  - Modify `plugins/gin-workflow/src/scripts/workflow_core/specs.py:863-893` (`lint_change`: `RETIRED` rules, `ADDED` of a retired id)
  - Modify `plugins/gin-workflow/src/scripts/workflow_core/specs_archive.py:37-42` (`_append` inserts before `## Retired`)
  - Modify `plugins/gin-workflow/src/scripts/workflow_core/specs_archive.py:115-141` (`RETIRED` and `REMOVED` into `## Retired`; `retired` in the result)
  - Modify `plugins/gin-workflow/src/scripts/workflow_core/signoff.py:18` (`_ROW` accepts `retired`)
  - Modify `plugins/gin-workflow/src/templates/spec.md` (empty `## Retired` at the end)
  - Modify `plugins/gin-workflow/src/templates/spec-delta.md` (`## RETIRED` and its rule in the comment)
  - Modify `plugins/gin-workflow/src/skills/sdd/SKILL.md:13` (retire, never renumber)
  - Modify `docs/guides/sdd.md:27,55` and the matching lines of `docs/guides/sdd.vi.md` (format, lint, archive)
  - Modify `tests/workflow_core/specs_fixtures.py:120-121` (`delta(retired=...)`)
  - Test `tests/workflow_core/test_specs.py`
  - Test `tests/workflow_core/test_specs_archive_trace.py`
  - Test `tests/workflow_core/test_signoff.py`
  - Test `tests/workflow_core/test_specs_trace_all.py:158` (message text)
- **Interfaces**:
  - Produced: `specs.DELTA_SECTIONS = ("ADDED", "MODIFIED", "REMOVED", "RETIRED")`; `specs.RETIRED_SECTION = "Retired"`; `specs.is_retired(block: Block) -> bool`; `specs.retired_blocks(root: Path, cfg: Mapping[str, Any]) -> dict[str, tuple[Path, Block]]`; `specs.lint_retired(block: Block) -> list[str]`; `specs.append_to_section(lines: list[str], heading: str, entries: Sequence[Sequence[str]]) -> list[str]`; archive result key `retired: list[str]`; sign-off op `retired`.
  - Consumed: `specs.parse_blocks`, `specs.living_files`, `specs.in_flight_blocks`, `specs_archive._clean`.
- **Provider role**: `backend`
- **Model:** `opus`
- **Effort:** `high`
- **Why:** the format change crosses parse, lint, sign-off and archive, and every later track builds on it; archive's line surgery has several placement edge cases.
- **Acceptance criteria**: the tests of step 1 pass; `python3 -m pytest -n auto -q tests/workflow_core/test_specs.py tests/workflow_core/test_specs_archive_trace.py tests/workflow_core/test_signoff.py tests/workflow_core/test_specs_trace_all.py tests/workflow_core/test_specs_reqs.py tests/workflow_core/test_specs_export.py tests/workflow_core/test_specs_explain.py tests/workflow_core/test_specs_matter.py tests/gin_qa` reports no failure; `gin docs check docs/guides/sdd.md docs/guides/sdd.vi.md` prints `ok`.
- **Estimated complexity**: high

Steps:

1. Fixture and failing tests.

   In `tests/workflow_core/specs_fixtures.py` replace `delta`:

   ```python
   def delta(*, added: str = "", modified: str = "", removed: str = "", retired: str = "") -> str:
       text = f"# Spec Delta\n\n## ADDED\n\n{added}\n## MODIFIED\n\n{modified}\n## REMOVED\n\n{removed}"
       return text + (f"\n## RETIRED\n\n{retired}" if retired else "")
   ```

   In `tests/workflow_core/test_specs.py` add the module constant `RETIRED_003 = "### REQ-AUTH-003: Lock out\nReason: dropped in spec review\n"` below the imports, and these methods to `TestRepositoryCommands`:

   ```python
   def test_retired_block_needs_only_a_reason(self):
       change = make_change(self.root, spec_delta=delta(retired=RETIRED_003))
       self.assertEqual([], specs.lint_change(self.root, self.cfg, change))
       write(self.root, "docs/changes/ep-1-lockout/02-spec-delta.md", delta(retired="### REQ-AUTH-003: Lock out\n"))
       errors = specs.lint_change(self.root, self.cfg, change)
       self.assertTrue(any("REQ-AUTH-003 needs a 'Reason: <why>' line" in e for e in errors), errors)

   def test_retired_block_refuses_a_living_or_added_id(self):
       change = make_change(self.root, spec_delta=delta(retired="### REQ-AUTH-001: Sign in\nReason: x\n"))
       errors = specs.lint_change(self.root, self.cfg, change)
       self.assertTrue(any("REQ-AUTH-001 is in docs/specs/auth/spec.md; remove it with ## REMOVED" in e
                           for e in errors), errors)
       make_change(self.root, "ep-2-other", epic="ep-2")  # adds REQ-AUTH-003
       write(self.root, "docs/changes/ep-1-lockout/02-spec-delta.md", delta(retired=RETIRED_003))
       errors = specs.lint_change(self.root, self.cfg, change)
       self.assertTrue(any("REQ-AUTH-003 is added by ep-2-other" in e for e in errors), errors)

   def test_living_retired_section(self):
       write(self.root, "docs/specs/auth/spec.md", AUTH_SPEC + "\n## Retired\n\n" + RETIRED_003)
       self.assertEqual([], specs.lint_living(self.root, self.cfg))
       self.assertEqual({"REQ-AUTH-001", "REQ-AUTH-002"}, set(specs.living_blocks(self.root, self.cfg)))
       self.assertEqual({"REQ-AUTH-003"}, set(specs.retired_blocks(self.root, self.cfg)))
       change = make_change(self.root)  # ADDED REQ-AUTH-003
       errors = specs.lint_change(self.root, self.cfg, change)
       self.assertTrue(any("REQ-AUTH-003 is retired in docs/specs/auth/spec.md" in e for e in errors), errors)
       write(self.root, "docs/changes/ep-1-lockout/02-spec-delta.md", delta(retired=RETIRED_003))
       errors = specs.lint_change(self.root, self.cfg, change)
       self.assertTrue(any("REQ-AUTH-003 is already retired" in e for e in errors), errors)
       write(self.root, "docs/specs/auth/spec.md", AUTH_SPEC + "\n## Retired\n\n### REQ-AUTH-003: Lock out\n")
       self.assertTrue(any("REQ-AUTH-003 needs a 'Reason: <why>' line" in e
                           for e in specs.lint_living(self.root, self.cfg)))

   def test_use_case_citing_a_retired_id(self):
       write(self.root, "docs/specs/auth/spec.md", AUTH_SPEC + "\n## Retired\n\n" + RETIRED_003)
       write(self.root, "docs/specs/auth/use-cases/sign-in.md",
             "# Sign in\n\nActor: User\nRequirements: REQ-AUTH-003\n\n## Main flow\n\n1. Sign in\n")
       self.assertIn("docs/specs/auth/use-cases/sign-in.md: REQ-AUTH-003 is retired",
                     specs.lint_use_cases(self.root, self.cfg))
   ```

   Change `tests/workflow_core/test_specs.py:325` and `tests/workflow_core/test_specs_trace_all.py:158` to look for `"outside ## ADDED/MODIFIED/REMOVED/RETIRED"`.

   In `tests/workflow_core/test_specs_archive_trace.py`, in the class that tests `archive`, add (reuse its `setUp`, which writes `AUTH_SPEC`, and its commit helper):

   ```python
   def test_archive_writes_retired_entries(self):
       base = specs.requirement_hash(self.root, self.cfg, "REQ-AUTH-002")[1]
       removed = f"### REQ-AUTH-002: Reject wrong password\n<!-- base: {base} -->\nReason: merged into REQ-AUTH-001\n"
       change = make_change(self.root, spec_delta=delta(added=ADDED_BLOCK.replace("003", "004"), removed=removed,
                                                        retired="### REQ-AUTH-003: Lock out\nReason: dropped\n"))
       commit_all(self.root)
       result = archive(self.root, self.cfg, change)
       self.assertEqual(["REQ-AUTH-003"], result["retired"])
       self.assertEqual(["REQ-AUTH-002"], result["removed"])
       text = (self.root / "docs/specs/auth/spec.md").read_text(encoding="utf-8")
       head, retired = text.split("\n## Retired\n", 1)
       self.assertIn("### REQ-AUTH-004:", head)
       self.assertNotIn("REQ-AUTH-002", head)
       self.assertIn("### REQ-AUTH-002: Reject wrong password\nReason: merged into REQ-AUTH-001", retired)
       self.assertIn("### REQ-AUTH-003: Lock out\nReason: dropped", retired)
       self.assertNotIn("base:", retired)
       self.assertEqual([], specs.lint_living(self.root, self.cfg))

   def test_archive_adds_before_an_existing_retired_section(self):
       write(self.root, "docs/specs/auth/spec.md", AUTH_SPEC + "\n## Retired\n\n### REQ-AUTH-009: Old\nReason: x\n")
       change = make_change(self.root)
       commit_all(self.root)
       archive(self.root, self.cfg, change)
       text = (self.root / "docs/specs/auth/spec.md").read_text(encoding="utf-8")
       self.assertLess(text.index("### REQ-AUTH-003:"), text.index("## Retired"))
       self.assertTrue(text.rstrip().endswith("Reason: x"))
   ```

   In `tests/workflow_core/test_signoff.py` add a test that `signoff.change_requirements` of a delta with `retired="### REQ-AUTH-003: Lock out\nReason: x\n"` returns a row `{"id": "REQ-AUTH-003", "op": "retired", "hash8": <block_hash(block.text)[:8]>}`, and that a rendered `06-signoff.md` row `| REQ-AUTH-003 | <hash8> | retired |` reads back through the parser that uses `_ROW`.

2. Run `python3 -m pytest -q tests/workflow_core/test_specs.py tests/workflow_core/test_specs_archive_trace.py tests/workflow_core/test_signoff.py -k "retired or outside"`: the new tests fail.

3. Code in `specs.py`.

   ```python
   DELTA_SECTIONS = ("ADDED", "MODIFIED", "REMOVED", "RETIRED")
   # The living spec's section for retired ids; a delta spells it RETIRED.
   RETIRED_SECTION = "Retired"
   _REASON = re.compile(r"^Reason: \S", re.MULTILINE)
   ```

   Replace `living_blocks` and add the helpers next to it:

   ```python
   def is_retired(block: Block) -> bool:
       """A block under `## Retired` of a living spec or `## RETIRED` of a delta: a heading and a reason."""
       return block.section in (RETIRED_SECTION, "RETIRED")


   def _living_spec_blocks(root: Path, cfg: Mapping[str, Any], retired: bool) -> dict[str, tuple[Path, Block]]:
       found: dict[str, tuple[Path, Block]] = {}
       for path in living_files(root, cfg).values():
           for block in parse_blocks(path.read_text(encoding="utf-8"))[0]:
               if is_retired(block) == retired:
                   found.setdefault(block.id, (path, block))
       return found


   def living_blocks(root: Path, cfg: Mapping[str, Any]) -> dict[str, tuple[Path, Block]]:
       """Current requirements of the living specs; retired ones are left out."""
       return _living_spec_blocks(root, cfg, retired=False)


   def retired_blocks(root: Path, cfg: Mapping[str, Any]) -> dict[str, tuple[Path, Block]]:
       """Entries under `## Retired` of the living specs: ids that are gone and stay taken."""
       return _living_spec_blocks(root, cfg, retired=True)


   def lint_retired(block: Block) -> list[str]:
       """A retired or removed block needs a `Reason:` line; no statement or scenario."""
       return [] if _REASON.search(block.text) else [f"{block.id} needs a 'Reason: <why>' line"]


   def append_to_section(lines: list[str], heading: str, entries: Sequence[Sequence[str]]) -> list[str]:
       """`lines` with each entry appended, after a blank line, at the end of the `## <heading>` section; the section is
       added at the end of the file when missing. No entries: `lines` unchanged."""
       if not entries:
           return lines
       at = next((index for index, line in enumerate(lines) if line.strip() == f"## {heading}"), None)
       if at is None:
           while lines and not lines[-1].strip():
               lines.pop()
           lines = [*lines, "", f"## {heading}"]
           at = len(lines) - 1
       end = next((index for index in range(at + 1, len(lines)) if lines[index].startswith("## ")), len(lines))
       head, tail = lines[:end], lines[end:]
       while head and not head[-1].strip():
           head.pop()
       for entry in entries:
           head += ["", *entry]
       return head + (["", *tail] if tail else [])
   ```

   In `delta_blocks` the message becomes `f"... {block.id} is outside ## {'/'.join(DELTA_SECTIONS)}"`.

   In `lint_change`, after `in_flight = ...` add `retired = retired_blocks(root, cfg)`, and replace the section branches:

   ```python
           if block.section == "ADDED":
               if block.id in living:
                   errors.append(f"{where}: {block.id} already exists in {shown(root, living[block.id][0])}")
               elif block.id in retired:
                   errors.append(f"{where}: {block.id} is retired in {shown(root, retired[block.id][0])}; "
                                 "get a new id from gin specs next-id")
               errors += [f"{where}: {message}" for message in lint_block(block)]
           elif block.section == "RETIRED":
               if block.id in living:
                   errors.append(f"{where}: {block.id} is in {shown(root, living[block.id][0])}; remove it with ## REMOVED")
               elif block.id in retired:
                   errors.append(f"{where}: {block.id} is already retired in {shown(root, retired[block.id][0])}")
               elif block.id in in_flight:
                   errors.append(f"{where}: {block.id} is added by {' and '.join(c.name for c, _ in in_flight[block.id])}")
               errors += [f"{where}: {message}" for message in lint_retired(block)]
           elif block.section in ("MODIFIED", "REMOVED"):
               ...  # unchanged, except the Reason check:
               elif block.section == "REMOVED":
                   errors += [f"{where}: {message}" for message in lint_retired(block)]
   ```

   (The `MODIFIED`/`REMOVED` branch keeps its living, in-flight and base checks; only its `elif not re.search(r"^Reason: \S", ...)` line becomes the `lint_retired` call above, with the same message.)

   In `lint_living`, the last line of the block loop becomes:

   ```python
               errors += [f"{where}: {message}" for message in (lint_retired(block) if is_retired(block)
                                                                else lint_block(block))]
   ```

   In `lint_use_cases`, after `known = ...` add `retired = set(retired_blocks(root, cfg)) if paths else set()`, and the last line of the loop becomes:

   ```python
           errors += [f"{name}: {req} is retired" if req in retired
                      else f"{name}: {req} is not in a living spec or an open change" for req in ids if req not in known]
   ```

4. Code in `specs_archive.py`. Import `RETIRED_SECTION` and `append_to_section` from `.specs`. Replace `_append`:

   ```python
   def _append(lines: list[str], added: list[Block]) -> list[str]:
       """ADDED blocks at the end of the requirements: before `## Retired` when the spec has one."""
       at = next((index for index, line in enumerate(lines) if line.strip() == f"## {RETIRED_SECTION}"), len(lines))
       head, tail = lines[:at], lines[at:]
       while head and not head[-1].strip():
           head.pop()
       for block in added:
           head += ["", *_clean(block)]
       return head + (["", *tail] if tail else [])
   ```

   In `archive`, the merge line becomes:

   ```python
           texts[cap] = append_to_section(
               _append(_apply(lines, edits), [b for b in mine if b.section == "ADDED"]), RETIRED_SECTION,
               [_clean(b) for b in mine if b.section in ("REMOVED", "RETIRED")])
   ```

   `edits` must leave `RETIRED` out: `edits = {b.id: (b if b.section == "MODIFIED" else None) for b in mine if b.section in ("MODIFIED", "REMOVED")}`. The result gains `"retired": [b.id for b in blocks if b.section == "RETIRED"]`.

5. `signoff.py:18`: `(added|modified|removed|retired)` in `_ROW`. `change_requirements` and `hash8` need no change: `RETIRED` is in `DELTA_SECTIONS`, and its hash8 is its own block hash.

6. Templates. `templates/spec.md` ends with:

   ```markdown
   ## Requirements

   ## Retired
   ```

   `templates/spec-delta.md`: add after the REMOVED sentence of the comment the line `     A RETIRED block is the heading and "Reason: <why>": an id that never reached a living spec and was dropped; it stays taken.` and end the file with `## RETIRED` after `## REMOVED`, one blank line between.

7. Run the tests of step 2: they pass. Then run the acceptance command of this track and fix any test that compared a whole new `spec.md` or the old section message.

8. Skill and docs.
   - `skills/sdd/SKILL.md:13`, after `` `REMOVED` adds `Reason: <why>`. ``: `When the review drops a requirement that no living spec holds, move its block to `## RETIRED` with `Reason: <why>` instead of deleting it, so its number stays taken; never renumber to close a gap.`
   - `docs/guides/sdd.md:27`: `02-spec-delta.md       ADDED / MODIFIED / REMOVED / RETIRED requirements`.
   - `docs/guides/sdd.md`, after line 55, a bullet: `- A `RETIRED` block keeps the number of a requirement the review dropped before it reached a living spec: its heading and `Reason: <why>`, nothing else. Lint refuses it for an id that a living spec holds (use `REMOVED`), that is already retired, or that an open change adds, and refuses `ADDED` of a retired id. `gin specs archive` writes each `RETIRED` block, and each `REMOVED` block without its base line, under `## Retired` at the end of `spec.md`; new `ADDED` blocks go before that section. Readers of the living spec leave retired ids out.`
   - `docs/guides/sdd.vi.md`: the same two changes at its matching lines, in Vietnamese.
   - Run `gin docs check docs/guides/sdd.md docs/guides/sdd.vi.md`: `ok`.

9. Commit: `feat(specs): retired requirement ids in deltas and living specs (retired-req-ids)`.

### Track 2: `next-id` scans git history
- **Dependencies**: Track 1
- **Files**:
  - Modify `plugins/gin-workflow/src/scripts/workflow_core/specs.py:993-1012` (`history_ids`, `_shallow_date`; `scan_ids` adds history)
  - Modify `docs/reference/cli.md:150` (`next-id CAP` row)
  - Modify `docs/guides/sdd.md:51` and the matching line of `docs/guides/sdd.vi.md`
  - Test `tests/workflow_core/test_specs.py`
- **Interfaces**:
  - Produced: `specs.history_ids(root: Path, cfg: Mapping[str, Any]) -> tuple[set[str], list[str]]`; `scan_ids` returns history ids too.
  - Consumed: `specs._git`, `specs._local_ids`, `specs.ids_at_ref`.
- **Provider role**: `backend`
- **Model:** `sonnet`
- **Effort:** `medium`
- **Why:** one function in one module with the git command given; the edge cases (no commits, shallow clone, git error) are listed and each has a test.
- **Acceptance criteria**: the tests of step 1 pass; `python3 -m pytest -n auto -q tests/workflow_core/test_specs.py tests/workflow_core/test_specs_archive_trace.py` reports no failure; `gin docs check docs/reference/cli.md docs/guides/sdd.md docs/guides/sdd.vi.md` prints `ok`.
- **Estimated complexity**: medium

Steps:

1. Failing tests in `TestRepositoryCommands` of `tests/workflow_core/test_specs.py`:

   ```python
   def test_next_id_skips_an_id_deleted_in_history(self):
       commit_all(self.root)
       make_change(self.root)  # ADDED REQ-AUTH-003
       commit_all(self.root, "add REQ-AUTH-003")
       write(self.root, "docs/changes/ep-1-lockout/02-spec-delta.md", delta())
       commit_all(self.root, "drop REQ-AUTH-003")
       self.assertEqual(("REQ-AUTH-004", ["no git remote; scanned local worktrees only"]),
                        specs.next_id(self.root, self.cfg, "auth"))

   def test_next_id_counts_a_retired_only_id(self):
       write(self.root, "docs/specs/auth/spec.md", AUTH_SPEC + "\n## Retired\n\n### REQ-AUTH-005: Old\nReason: x\n")
       self.assertEqual("REQ-AUTH-006", specs.next_id(self.root, self.cfg, "auth")[0])

   def test_next_id_warns_in_a_shallow_clone(self):
       commit_all(self.root, "one")
       write(self.root, "docs/specs/auth/notes.md", "x\n")
       commit_all(self.root, "two")
       clone = Path(self.tmp.name) / "clone"
       git(Path(self.tmp.name), "clone", "-q", "--depth", "1", f"file://{self.root}", str(clone))
       req_id, warnings = specs.next_id(clone, self.cfg, "auth")
       self.assertEqual("REQ-AUTH-003", req_id)
       self.assertTrue(any(w.startswith("shallow clone; history before ") and w.endswith(" not scanned")
                           for w in warnings), warnings)

   def test_renumber_refuses_an_id_only_history_holds(self):
       commit_all(self.root)
       make_change(self.root, spec_delta=delta(added=ADDED_BLOCK.replace("003", "009")))
       commit_all(self.root, "add 009")
       change = make_change(self.root)  # rewrites the delta: ADDED REQ-AUTH-003 only
       commit_all(self.root, "drop 009")
       with self.assertRaisesRegex(SpecsError, "REQ-AUTH-009 is already used"):
           specs.renumber(self.root, self.cfg, change, "REQ-AUTH-003", "REQ-AUTH-009")
   ```

   `test_next_id_warns_without_remote` stays as it is: a repository without commits gets no history warning.

2. Run `python3 -m pytest -q tests/workflow_core/test_specs.py -k "next_id or renumber_refuses"`: the new tests fail.

3. Code in `specs.py`, above `scan_ids`:

   ```python
   _HISTORY_HEADING = re.compile(r"^[+-]### (REQ-[A-Z][A-Z0-9-]*-\d{3,}):", re.MULTILINE)


   def _shallow_date(root: Path) -> str:
       """The oldest commit date at the shallow boundary, `YYYY-MM-DD`, or `the clone depth` when git cannot tell."""
       listed = _git(root, "rev-parse", "--git-path", "shallow").stdout.strip()
       path = Path(root) / listed if listed else None
       hashes = path.read_text(encoding="utf-8").split() if path and path.is_file() else []
       dates = _git(root, "show", "-s", "--format=%cs", *hashes).stdout.split() if hashes else []
       return min(dates) if dates else "the clone depth"


   def history_ids(root: Path, cfg: Mapping[str, Any]) -> tuple[set[str], list[str]]:
       """Ids on a `### REQ-` heading that any commit of any ref added or deleted under the specs and changes folders."""
       if (_git(root, "rev-parse", "--verify", "--quiet", "HEAD").returncode != 0
               and not _git(root, "for-each-ref", "--count=1").stdout.strip()):
           return set(), []  # no commit yet: no history
       log = _git(root, "log", "--all", "--format=", "-p", "--unified=0", "-G", "^### REQ-",
                  "--", cfg["specs"], cfg["changes"])
       if log.returncode != 0:
           cause = next((line.strip() for line in log.stderr.splitlines() if line.strip()), f"exit {log.returncode}")
           return set(), [f"git log failed; history not scanned: {cause}"]
       warnings = []
       if _git(root, "rev-parse", "--is-shallow-repository").stdout.strip() == "true":
           warnings.append(f"shallow clone; history before {_shallow_date(root)} not scanned")
       return set(_HISTORY_HEADING.findall(log.stdout)), warnings
   ```

   `scan_ids` becomes:

   ```python
   def scan_ids(root: Path, cfg: Mapping[str, Any]) -> tuple[set[str], list[str]]:
       """Ids in this tree, every local worktree, every remote-tracking branch, and git history."""
       ids = _local_ids(root, cfg)
       warnings: list[str] = []
       listed = _git(root, "worktree", "list", "--porcelain")
       if listed.returncode != 0:
           return ids, ["not a git repository; scanned this tree only"]
       for line in listed.stdout.splitlines():
           if line.startswith("worktree "):
               ids |= _local_ids(Path(line[len("worktree "):]), cfg)
       if not _git(root, "remote").stdout.strip():
           warnings.append("no git remote; scanned local worktrees only")
       else:
           if _git(root, "fetch", "--quiet").returncode != 0:
               warnings.append("git fetch failed; remote branches may be stale")
           refs = _git(root, "for-each-ref", "--format=%(refname)", "refs/remotes").stdout.split()
           for ref in refs:
               if not ref.endswith("/HEAD"):
                   ids |= ids_at_ref(root, cfg, ref)
       found, more = history_ids(root, cfg)
       return ids | found, warnings + more
   ```

4. Run the tests of step 2: they pass. Run the acceptance command and fix any test that expected a deleted id to be handed out again.

5. Docs.
   - `docs/reference/cli.md:150`: `| `next-id CAP` | Next requirement id for a capability: one above the highest id that the working tree, the worktrees, the remote branches, or git history ever had on a heading, so a number is never handed out twice. A shallow clone adds the warning `shallow clone; history before <date> not scanned` |`
   - `docs/guides/sdd.md:51`: `- IDs are `REQ-<CAP>-<NNN>`; get the next one with `gin specs next-id <cap>`, which scans the working tree, the worktrees, the remote branches, and git history. A number once used, retired, or dropped is never handed out again, so a gap in the numbers is normal.`
   - `docs/guides/sdd.vi.md`: the same at its matching line.
   - Run `gin docs check docs/reference/cli.md docs/guides/sdd.md docs/guides/sdd.vi.md`: `ok`.

6. Commit: `feat(specs): next-id never hands out an id git history used (retired-req-ids)`.

### Track 3: Readers skip retired ids
- **Dependencies**: Track 1
- **Files**:
  - Modify `plugins/gin-workflow/src/scripts/workflow_core/specs_reqs.py:33-38` (`section: RETIRED`, `reason`)
  - Modify `plugins/gin-workflow/src/scripts/workflow_core/specs_trace.py:108-124` (`retired` list)
  - Modify `plugins/gin-workflow/src/scripts/workflow_core/specs_trace_all.py:102-104,134-143` (`reason`, retired rows)
  - Modify `plugins/gin-workflow/src/scripts/workflow_core/specs_export.py:330-356` (retired table, TOC without retired)
  - Modify `plugins/gin-workflow/src/scripts/workflow_core/specs_explain.py:193` (living spec skips retired)
  - Modify `plugins/gin-workflow/src/scripts/workflow_core/specs_cli.py:229-233` (`trace --change` text lists `retired:`)
  - Modify `docs/reference/cli.md:159,162,178-181` (trace, reqs, trace --all)
  - Modify `docs/guides/sdd.md:201` and the export paragraph near `:168`, and the matching lines of `docs/guides/sdd.vi.md`
  - Test `tests/workflow_core/test_specs_reqs.py`
  - Test `tests/workflow_core/test_specs_archive_trace.py`
  - Test `tests/workflow_core/test_specs_trace_all.py`
  - Test `tests/workflow_core/test_specs_export.py`
  - Test `tests/workflow_core/test_specs_explain.py`
- **Interfaces**:
  - Produced: `gin specs reqs` rows carry `reason: str | None` and `section: "RETIRED"` for retired entries; `trace()` result key `retired: list[{"id": str, "sources": list[str]}]`; `trace --all` rows carry `reason: str | None`.
  - Consumed: `specs.is_retired`, `specs.retired_blocks`, `specs.line_value`, `specs_trace.req_sources`.
- **Provider role**: `backend`
- **Model:** `sonnet`
- **Effort:** `medium`
- **Why:** five bounded edits, each in one reader with the code given; behaviour per reader is fixed by the spec's table.
- **Acceptance criteria**: the tests of step 1 pass; `python3 -m pytest -n auto -q tests/workflow_core/test_specs_reqs.py tests/workflow_core/test_specs_archive_trace.py tests/workflow_core/test_specs_trace_all.py tests/workflow_core/test_specs_export.py tests/workflow_core/test_specs_explain.py tests/workflow_core/test_specs_matter.py tests/workflow_core/test_specs.py tests/gin_qa` reports no failure; `gin docs check docs/reference/cli.md docs/guides/sdd.md docs/guides/sdd.vi.md` prints `ok`.
- **Estimated complexity**: medium

Steps:

1. Failing tests. Each uses the existing fixtures of its file and a living spec `AUTH_SPEC + "\n## Retired\n\n### REQ-AUTH-003: Lock out\nReason: dropped in review\n"`:
   - `test_specs_reqs.py`: the rows hold one row `{"id": "REQ-AUTH-003", "section": "RETIRED", "reason": "dropped in review"}` (compare those keys), and no `LIVING` row for it; a `LIVING` row has `reason` null. With an open change whose delta has `## RETIRED` with `### REQ-AUTH-004: X\nReason: y\n`, `requirements(..., change)` gives a row `section: "RETIRED"`, `reason: "y"`.
   - `test_specs_archive_trace.py`: write `tests/test_lock.py` with the text `# REQ-AUTH-003` and commit it; `specs_trace.trace` of a change that adds `REQ-AUTH-004` returns `retired == [{"id": "REQ-AUTH-003", "sources": ["tests/test_lock.py"]}]`, and the CLI `gin specs trace --change ep-1` prints `retired: REQ-AUTH-003 tests/test_lock.py` and keeps its exit status (0 when REQ-AUTH-004 is covered).
   - `test_specs_trace_all.py`: the row of `REQ-AUTH-003` has `state == "removed"`, `hash8 is None`, `source is None`, `reason == "dropped in review"`; a living row has `reason is None`.
   - `test_specs_export.py`: the exported HTML holds `Retired requirements` and a row with `REQ-AUTH-003`, `Lock out` and `dropped in review`, and no `href="#REQ-AUTH-003"` link in the TOC.
   - `test_specs_explain.py`: the explanation of capability `auth` holds no `REQ-AUTH-003` card; the explanation of an open change with a `## RETIRED` block shows a `RETIRED` group with that block.

2. Run those test files: the new tests fail.

3. Code.

   `specs_reqs.py` (import `is_retired`, `line_value`):

   ```python
   def _row(root: Path, path: Path, block: Block, change: str | None, epic: str | None = None) -> dict[str, Any]:
       retired = is_retired(block)
       section = "RETIRED" if retired else "LIVING" if change is None else block.section
       return {"id": block.id, "title": block.title, "capability": block.cap,
               "section": section, "change": change, "epic": epic,
               "type": block.type, "category": block.category,
               "hash": block_hash(block.text), "source": f"{shown(root, path)}:{block.start + 1}",
               "reason": line_value(block.text, "Reason") if section in ("RETIRED", "REMOVED") else None,
               "scenarios": scenarios(block)}
   ```

   `specs_trace.py`, `trace` (import `retired_blocks`):

   ```python
       wanted = [block.id for block in blocks if block.section in ("ADDED", "MODIFIED")]
       gone = sorted((set(retired_blocks(root, cfg)) | {block.id for block in blocks
                                                        if block.section in ("REMOVED", "RETIRED")}) - set(wanted))
       sources, skipped = req_sources(root, cfg, wanted + gone, refs)
       ...
       return {"change": change.name, "requirements": requirements,
               "missing": [row["id"] for row in requirements if row["status"] == "missing"],
               "retired": [{"id": req, "sources": sorted(sources[req])} for req in gone if sources[req]],
               "skipped": skipped}
   ```

   `specs_cli.py`, the `trace` text output adds, after the requirement lines:

   ```python
           lines += [f"retired: {row['id']} {' '.join(row['sources'])}" for row in result["retired"]]
   ```

   `specs_trace_all.py` (import `retired_blocks`, `line_value`): `_row` takes `reason: str | None = None` and puts `"reason": reason` in the row. Before the archived-`REMOVED` loop:

   ```python
       for req_id, (_, block) in retired_blocks(root, cfg).items():
           if req_id not in rows:
               rows[req_id] = _row(req_id, block.title, "removed", None, None,
                                   line_value(block.text, "Reason") or None)
   ```

   and the archived-`REMOVED` row passes `line_value(block.text, "Reason") or None` as its reason.

   `specs_export.py`, `_chapter`:

   ```python
       parsed = specs.parse_blocks(text)[0]
       blocks = [block for block in parsed if not specs.is_retired(block)]
       requirements = (_requirements(blocks, folder, _shown(spec, root), embed)
                       + _retired([block for block in parsed if specs.is_retired(block)]))
   ```

   with, next to `_requirements`:

   ```python
   def _retired(blocks: list[specs.Block]) -> str:
       """The retired ids of a capability with their reasons, so a gap in the numbers explains itself."""
       if not blocks:
           return ""
       rows = "".join(f"<tr><td>{escape(b.id)}</td><td>{escape(b.title)}</td>"
                      f"<td>{escape(specs.line_value(b.text, 'Reason'))}</td></tr>" for b in blocks)
       return ('\n<section class="retired-requirements"><h3>Retired requirements</h3><table>'
               f"<tr><th>Requirement</th><th>Title</th><th>Reason</th></tr>{rows}</table></section>")
   ```

   The TOC `links` keep iterating `blocks`, which no longer holds retired ones.

   `specs_explain.py:193`: `blocks = [block for block in specs.parse_blocks(text)[0] if not specs.is_retired(block)]`. `_change` uses `specs.DELTA_SECTIONS`, which holds `RETIRED` since Track 1, so a change's `RETIRED` blocks get their group with no code.

4. Run the tests of step 2: they pass. Run the acceptance command.

5. Docs.
   - `docs/reference/cli.md:162` (`reqs`): add `; a `## Retired` entry of a living spec or a `## RETIRED` block of a change has section `RETIRED`, and `reason` holds the `Reason:` of `RETIRED` and `REMOVED` rows (null otherwise)`.
   - `docs/reference/cli.md:159` (`trace --change`): add `; it lists under `retired` each test file that names a retired or removed id, without failing`.
   - `docs/reference/cli.md:178`: `` `removed` when an archived change removed it or a living spec lists it under `## Retired` ``; add a row `| `requirements[].reason` | The `Reason:` of a removed requirement; null otherwise |`; `:181`: op `` (`added`, `modified`, `removed`, or `retired`) ``.
   - `docs/guides/sdd.md:201`: `grouped under ADDED, MODIFIED, REMOVED, and RETIRED`; the chapter paragraph of the export (near `:168`) adds `Each chapter ends with a Retired requirements table (requirement, title, reason) when its spec.md has a ## Retired section; retired ids stay out of the contents and the traceability matrix.`
   - `docs/guides/sdd.vi.md`: the same at its matching lines.
   - Run `gin docs check docs/reference/cli.md docs/guides/sdd.md docs/guides/sdd.vi.md`: `ok`.

6. Commit: `feat(specs): reqs, trace, export and explain handle retired ids (retired-req-ids)`.

### Track 4: gin-qa plans no case for a retired id
- **Dependencies**: Track 3
- **Files**:
  - Modify `plugins/gin-qa/src/scripts/gin_qa/reqs.py:37,125-154` (`Effective.retired`; `resolve`)
  - Modify `plugins/gin-qa/src/scripts/gin_qa/cli.py:109-143` (`_scope`, `_work` reason)
  - Modify `plugins/gin-qa/src/scripts/gin_qa/cli.py:220-222` (`--req` of a retired id)
  - Modify `plugins/gin-workflow/src/skills/qa-track/SKILL.md:29` (skip `RETIRED`)
  - Test `tests/gin_qa/test_cases_cli.py`
  - Test `tests/gin_qa/test_cases_new.py`
- **Interfaces**:
  - Produced: `Effective.retired: dict[str, str]` (REQ-ID to reason); obsolete reason `retired: <reason>`; `--req` error `<id> is retired: <reason>`.
  - Consumed: the `section` and `reason` keys of `gin specs reqs` rows (Track 3).
- **Provider role**: `backend`
- **Model:** `sonnet`
- **Effort:** `medium`
- **Why:** bounded change in two gin-qa modules with the code given; the behaviour mirrors the existing `REMOVED` handling.
- **Acceptance criteria**: the tests of step 1 pass; `python3 -m pytest -n auto -q tests/gin_qa` reports no failure.
- **Estimated complexity**: low

Steps:

1. Failing tests in `tests/gin_qa/test_cases_cli.py`, class `TestChanges` (its `setUp` writes `AUTH_SPEC`):

   ```python
   def test_retired_requirement_gets_no_case_and_its_case_is_obsolete(self):
       write(self.root, "docs/specs/auth/spec.md",
             AUTH_SPEC + "\n## Retired\n\n### REQ-AUTH-003: Lock out\nReason: dropped in review\n")
       self.write_cases(case("TC-AUTH-001", self.ref("REQ-AUTH-001")), case("TC-AUTH-002", self.ref("REQ-AUTH-002")),
                        case("TC-AUTH-003", "REQ: REQ-AUTH-003@00000000"))
       work = self.run_json("plan", "auth")
       self.assertEqual([], work["missing"])
       self.assertEqual([("TC-AUTH-003", "retired: dropped in review")],
                        [(row["tc"], row["reason"]) for row in work["obsolete"]])
       self.assertIn("TC-AUTH-003: REQ-AUTH-003 retired: dropped in review", "\n".join(self.findings()))

   def test_change_retiring_an_id_scopes_it_out(self):
       make_change(self.root, spec_delta=delta(added=ADDED_BLOCK,
                                               retired="### REQ-AUTH-004: Old lockout\nReason: replaced\n"))
       work = self.run_json("plan", "--change", "ep-1")
       self.assertEqual(["REQ-AUTH-003"], [row["req"] for row in work["missing"]])
   ```

   In `tests/gin_qa/test_cases_new.py`, class `NewCase` (its `new` helper runs `gin-qa cases new auth --type manual --title <title>`):

   ```python
   def test_new_refuses_a_retired_requirement(self):
       write(self.root, "docs/specs/auth/spec.md",
             AUTH_SPEC + "\n## Retired\n\n### REQ-AUTH-003: Lock out\nReason: dropped\n")
       result = self.new("--req", "REQ-AUTH-003")
       self.assertNotEqual(0, result.returncode)
       self.assertIn("REQ-AUTH-003 is retired: dropped", result.stderr + result.stdout)
       self.nothing_written()
   ```

2. Run `python3 -m pytest -q tests/gin_qa/test_cases_cli.py tests/gin_qa/test_cases_new.py -k retired`: the new tests fail.

3. Code.

   `reqs.py`: `Effective` gains `retired: dict[str, str] = field(default_factory=dict)  # REQ-ID -> reason`. In `resolve`, first in the loop:

   ```python
           if row["section"] == "RETIRED":
               effective.reqs.pop(req, None)
               effective.retired[req] = row.get("reason") or ""
               continue
   ```

   and the docstring adds `a RETIRED row, living or in a change, retires the REQ.`

   `cli.py`, `_scope`:

   ```python
       if change:
           rows = specs_reqs(eff.project_root, change)["requirements"]
           gone = ("REMOVED", "RETIRED")
           return ({row["id"] for row in rows if row["section"] not in gone},
                   {row["id"] for row in rows if row["section"] in gone})
       if capability:
           return ({req for req, row in eff.reqs.items() if row["capability"] == capability},
                   {req for req in [*eff.removed, *eff.retired]
                    if req.split("-")[1:-1] == capability.upper().split("-")})
       return set(eff.reqs), set(eff.removed) | set(eff.retired)
   ```

   `_work`, the obsolete reason:

   ```python
                   reason = (f"retired: {eff.retired[req]}" if req in eff.retired
                             else f"removed by {eff.removed[req]}" if req in eff.removed else "does not exist")
   ```

   `cli.py:220`:

   ```python
       retired = [f"{req} is retired: {eff.retired[req]}" for req in reqs if req in eff.retired]
       if retired:
           raise ValueError("; ".join(retired))
       unknown = [req for req in reqs if req not in eff.reqs]
   ```

4. Run the tests of step 2: they pass. Run `python3 -m pytest -n auto -q tests/gin_qa`.

5. `skills/qa-track/SKILL.md:29`: `(skip `section: REMOVED` and `section: RETIRED`)`.

6. Commit: `feat(gin-qa): retired requirements get no case and make pinned cases obsolete (retired-req-ids)`.

### Track 5: `gin specs gaps [--into]`
- **Dependencies**: Track 1, Track 2
- **Files**:
  - Create `plugins/gin-workflow/src/scripts/workflow_core/specs_gaps.py`
  - Modify `plugins/gin-workflow/src/scripts/workflow_core/specs.py:969-978` (`_local_ids(..., archived=True)`)
  - Modify `plugins/gin-workflow/src/scripts/workflow_core/specs_cli.py:44,165` (`gaps` parser and dispatch)
  - Modify `docs/reference/cli.md:150-162` (`gaps` row)
  - Modify `docs/guides/sdd.md` (after the RETIRED bullet of Track 1) and the matching line of `docs/guides/sdd.vi.md`
  - Modify `plugins/gin-workflow/src/skills/sdd/SKILL.md:13` (`specs gaps`)
  - Create `tests/workflow_core/test_specs_gaps.py`
- **Interfaces**:
  - Produced: `specs_gaps.gaps(root: Path, cfg: Mapping[str, Any], cap: str | None = None) -> dict[str, Any]` returning `{"gaps": [{"id", "title", "reason", "change", "commit"}], "warnings": [...]}` where `commit` is `{"commit", "date", "subject", "title"}` or null; `specs_gaps.write_into(root: Path, change: Path, rows: Sequence[Mapping[str, Any]]) -> list[str]`; `specs_gaps.text_line(row: Mapping[str, Any]) -> str`; CLI `gin specs gaps [CAP] [--into CHANGE] [--format text|json]`, exit 0, 2 on a usage error.
  - Consumed: `specs.history_ids` (Track 2), `specs.append_to_section`, `specs.retired_blocks` (Track 1), `specs._local_ids`, `specs.ids_at_ref`, `specs._git`, `specs.delta_blocks`, `specs.change_file`, `specs.find_change`.
- **Provider role**: `backend`
- **Model:** `sonnet`
- **Effort:** `high`
- **Why:** a new module with the code given, but its set arithmetic over trees, refs and history and its git log parsing have many edge cases.
- **Acceptance criteria**: the tests of step 1 pass; `python3 -m pytest -n auto -q tests/workflow_core/test_specs_gaps.py tests/workflow_core/test_specs.py tests/workflow_core/test_docs_coverage.py` reports no failure; `gin docs check docs/reference/cli.md docs/guides/sdd.md docs/guides/sdd.vi.md` prints `ok`.
- **Estimated complexity**: medium

Steps:

1. Failing tests. Create `tests/workflow_core/test_specs_gaps.py`:

   ```python
   """`gin specs gaps`: requirement ids that were used and are gone without a `## Retired` entry."""

   from __future__ import annotations

   import contextlib
   import io
   import json
   from pathlib import Path
   import tempfile
   import unittest

   from specs_fixtures import (ADDED_BLOCK, AUTH_SPEC, commit_all, delta, make_change, make_repo, write,
                               write_activity)

   from workflow_core import specs, specs_cli, specs_gaps  # noqa: E402

   REMOVED_REASON = "merged into REQ-AUTH-001"


   class GapsTests(unittest.TestCase):
       def setUp(self):
           self.tmp = tempfile.TemporaryDirectory()
           self.root = make_repo(Path(self.tmp.name) / "repo")
           write(self.root, "docs/specs/auth/spec.md", AUTH_SPEC)
           write_activity(self.root)
           commit_all(self.root)
           self.cfg = specs.sdd_config(specs.load_config(self.root))

       def tearDown(self):
           self.tmp.cleanup()

       def drop_003_in_history(self):
           make_change(self.root)  # ADDED REQ-AUTH-003
           commit_all(self.root, "add REQ-AUTH-003")
           write(self.root, "docs/changes/ep-1-lockout/02-spec-delta.md", delta())
           commit_all(self.root, "drop REQ-AUTH-003")

       def archive_removed_002(self):
           write(self.root, "docs/changes/archive/2026-01-01-ep-0-merge/02-spec-delta.md",
                 delta(removed=f"### REQ-AUTH-002: Reject wrong password\n<!-- base: {'0' * 64} -->\n"
                               f"Reason: {REMOVED_REASON}\n"))
           write(self.root, "docs/specs/auth/spec.md", AUTH_SPEC.split("### REQ-AUTH-002")[0])
           commit_all(self.root, "archive ep-0")

       def test_lists_deleted_and_archived_ids_with_hints(self):
           self.drop_003_in_history()
           self.archive_removed_002()
           rows = specs_gaps.gaps(self.root, self.cfg, "auth")["gaps"]
           self.assertEqual(["REQ-AUTH-002", "REQ-AUTH-003"], [row["id"] for row in rows])
           self.assertEqual(("Reject wrong password", REMOVED_REASON, "2026-01-01-ep-0-merge", None),
                            (rows[0]["title"], rows[0]["reason"], rows[0]["change"], rows[0]["commit"]))
           self.assertEqual("", rows[1]["reason"])
           self.assertEqual(("drop REQ-AUTH-003", "Lock account after failed logins"),
                            (rows[1]["commit"]["subject"], rows[1]["commit"]["title"]))
           self.assertEqual(rows[1]["commit"]["title"], rows[1]["title"])

       def test_living_retired_and_added_ids_are_no_gaps(self):
           self.drop_003_in_history()
           make_change(self.root, "ep-2-again", epic="ep-2")  # ADDED REQ-AUTH-003 again
           self.assertEqual([], specs_gaps.gaps(self.root, self.cfg)["gaps"])
           write(self.root, "docs/changes/ep-2-again/02-spec-delta.md",
                 delta(retired="### REQ-AUTH-003: Lock out\nReason: dropped\n"))
           self.assertEqual([], specs_gaps.gaps(self.root, self.cfg)["gaps"])

       def test_into_writes_retired_blocks_and_never_spec_md(self):
           self.drop_003_in_history()
           self.archive_removed_002()
           before = (self.root / "docs/specs/auth/spec.md").read_text(encoding="utf-8")
           change = make_change(self.root, "ep-3-gaps", epic="ep-3", spec_delta=delta())
           out = io.StringIO()
           with contextlib.redirect_stdout(out):
               code = specs_cli.main(["gaps", "auth", "--into", "ep-3", "--repository", str(self.root),
                                      "--format", "json"])
           self.assertEqual(0, code)
           self.assertEqual(["REQ-AUTH-002", "REQ-AUTH-003"], json.loads(out.getvalue())["written"])
           text = (change / "02-spec-delta.md").read_text(encoding="utf-8")
           retired = text.split("## RETIRED", 1)[1]
           self.assertIn(f"### REQ-AUTH-002: Reject wrong password\nReason: {REMOVED_REASON}", retired)
           self.assertIn("### REQ-AUTH-003: Lock account after failed logins\nReason:\n", retired + "\n")
           errors = specs.lint_change(self.root, self.cfg, change)
           self.assertTrue(any("REQ-AUTH-003 needs a 'Reason: <why>' line" in e for e in errors), errors)
           self.assertFalse(any("REQ-AUTH-002 needs" in e for e in errors), errors)
           self.assertEqual(before, (self.root / "docs/specs/auth/spec.md").read_text(encoding="utf-8"))

       def test_text_output_and_unknown_change(self):
           self.drop_003_in_history()
           out = io.StringIO()
           with contextlib.redirect_stdout(out):
               self.assertEqual(0, specs_cli.main(["gaps", "--repository", str(self.root)]))
           self.assertRegex(out.getvalue(), r"^REQ-AUTH-003 deleted in [0-9a-f]+ \d{4}-\d{2}-\d{2} "
                                            r"drop REQ-AUTH-003: Lock account after failed logins$")
           with contextlib.redirect_stderr(io.StringIO()):
               self.assertEqual(2, specs_cli.main(["gaps", "--into", "ep-9", "--repository", str(self.root)]))
   ```

   Check that `specs_fixtures` puts the scripts folder on `sys.path` before `workflow_core` is imported, as the other spec tests rely on; if a test file in `tests/workflow_core` imports it differently, follow that file.

2. Run `python3 -m pytest -q tests/workflow_core/test_specs_gaps.py`: it fails (no `specs_gaps`).

3. Code.

   `specs.py`, `_local_ids` gains `archived`:

   ```python
   def _local_ids(tree: Path, cfg: Mapping[str, Any], *, archived: bool = True) -> set[str]:
       ids: set[str] = set()
       patterns = (("*/spec.md", cfg["specs"]), ("**/spec-delta.md", cfg["changes"]),
                   (f"**/{CHANGE_FILES['spec-delta']}", cfg["changes"]))
       for pattern, base in patterns:
           directory = Path(tree) / base
           if directory.is_dir():
               for path in directory.glob(pattern):
                   if not archived and base == cfg["changes"] and path.relative_to(directory).parts[0] == "archive":
                       continue
                   ids |= _ids_in(path.read_text(encoding="utf-8"))
       return ids
   ```

   Create `specs_gaps.py`:

   ```python
   """`gin specs gaps`: requirement ids that were used and are gone without a `## Retired` entry."""

   from __future__ import annotations

   from pathlib import Path
   import re
   from typing import Any, Mapping, Sequence

   from .atomic import atomic_write_many
   from .specs import (_CAP, _FULL_ID, Block, SpecsError, _git, _local_ids, append_to_section, cap_of, change_file,
                       changes_dir, delta_blocks, history_ids, ids_at_ref, line_value, shown)

   UNKNOWN_TITLE = "(title not found)"


   def _present(root: Path, cfg: Mapping[str, Any]) -> set[str]:
       """Ids on a heading of a living spec or an open change, in this tree, every worktree, and every remote-tracking
       branch; archived changes are left out, so an id only they hold is gone."""
       ids = _local_ids(root, cfg, archived=False)
       for line in _git(root, "worktree", "list", "--porcelain").stdout.splitlines():
           if line.startswith("worktree "):
               ids |= _local_ids(Path(line[len("worktree "):]), cfg, archived=False)
       archive = Path(cfg["changes"]) / "archive"
       for ref in _git(root, "for-each-ref", "--format=%(refname)", "refs/remotes").stdout.split():
           if not ref.endswith("/HEAD"):
               ids |= ids_at_ref(root, cfg, ref, exclude=archive)
       return ids


   def _archived_removals(root: Path, cfg: Mapping[str, Any]) -> dict[str, tuple[str, Block]]:
       """The REMOVED blocks of archived changes by id: (archived folder name, block); the newest folder wins."""
       archive = changes_dir(root, cfg) / "archive"
       found: dict[str, tuple[str, Block]] = {}
       for folder in sorted(p for p in archive.iterdir() if p.is_dir()) if archive.is_dir() else []:
           for block in delta_blocks(root, folder)[0]:
               if block.section == "REMOVED":
                   found[block.id] = (folder.name, block)
       return found


   def _last_commit(root: Path, cfg: Mapping[str, Any], req_id: str) -> dict[str, str] | None:
       """The newest commit that added or deleted the heading of `req_id`, with the title the heading had."""
       log = _git(root, "log", "--all", "-1", "-p", "--unified=0", "--format=%x00%h%x09%cs%x09%s",
                  "-G", f"^### {re.escape(req_id)}:", "--", cfg["specs"], cfg["changes"])
       if log.returncode != 0 or "\x00" not in log.stdout:
           return None
       header, _, patch = log.stdout.split("\x00", 1)[1].partition("\n")
       commit, day, subject = (header.split("\t", 2) + ["", ""])[:3]
       title = re.search(rf"^[+-]### {re.escape(req_id)}: (\S.*)$", patch, re.MULTILINE)
       return {"commit": commit, "date": day, "subject": subject, "title": title.group(1).strip() if title else ""}


   def _order(req_id: str) -> tuple[str, int]:
       prefix, number = _FULL_ID.match(req_id).groups()
       return prefix, int(number)


   def gaps(root: Path, cfg: Mapping[str, Any], cap: str | None = None) -> dict[str, Any]:
       """Each id that history or an archived change used and that no living spec, open change, or retired entry
       holds now, per capability in id order, with a hint: the archived REMOVED block, or the last commit."""
       if cap is not None and not _CAP.match(cap):
           raise SpecsError(f"capability {cap!r} must match [a-z][a-z0-9-]*")
       found, warnings = history_ids(root, cfg)
       removals = _archived_removals(root, cfg)
       rows = []
       for req_id in sorted((_local_ids(root, cfg) | found) - _present(root, cfg), key=_order):
           if cap is not None and cap_of(req_id) != cap:
               continue
           if req_id in removals:
               name, block = removals[req_id]
               rows.append({"id": req_id, "title": block.title, "reason": line_value(block.text, "Reason"),
                            "change": name, "commit": None})
           else:
               commit = _last_commit(root, cfg, req_id)
               rows.append({"id": req_id, "title": (commit or {}).get("title") or UNKNOWN_TITLE, "reason": "",
                            "change": None, "commit": commit})
       return {"gaps": rows, "warnings": warnings}


   def write_into(root: Path, change: Path, rows: Sequence[Mapping[str, Any]]) -> list[str]:
       """Append one `## RETIRED` block per row to the change's spec delta; an unknown reason leaves `Reason:` empty,
       which lint refuses until someone writes it. Returns the ids written."""
       path = change_file(change, "spec-delta")
       if not path.is_file():
           raise SpecsError(f"{shown(root, path)}: missing {path.name}")
       entries = [[f"### {row['id']}: {row['title']}", f"Reason: {row['reason']}".rstrip()] for row in rows]
       lines = append_to_section(path.read_text(encoding="utf-8").splitlines(), "RETIRED", entries)
       if entries:
           atomic_write_many({path: ("\n".join(lines).rstrip() + "\n").encode("utf-8")}, mode=0o644)
       return [row["id"] for row in rows]


   def text_line(row: Mapping[str, Any]) -> str:
       """`<id> removed by <change>: <reason>` or `<id> deleted in <commit> <date> <subject>: <title>`."""
       if row["change"]:
           return f"{row['id']} removed by {row['change']}: {row['reason']}"
       commit = row["commit"]
       if commit is None:
           return f"{row['id']} not found in history: {row['title']}"
       return f"{row['id']} deleted in {commit['commit']} {commit['date']} {commit['subject']}: {row['title']}"
   ```

   `specs_cli.py`: add the parser after `reqs`:

   ```python
       item = sub.add_parser("gaps", parents=[common])
       item.add_argument("cap", nargs="?")
       item.add_argument("--into")
   ```

   and, after the `next-id` branch (the layout is already `sdd` there):

   ```python
       if args.command == "gaps":
           from .specs_gaps import gaps, text_line, write_into

           result = gaps(root, cfg, args.cap)
           for warning in result["warnings"]:
               print(f"warning: {warning}", file=sys.stderr)
           if args.into:
               result["written"] = write_into(root, specs.find_change(root, cfg, args.into), result["gaps"])
           _emit(result, args.format, "\n".join(text_line(row) for row in result["gaps"]) or "no gaps")
           return 0
   ```

   `find_change` on a missing or archived change raises `SpecsError`, which `main` turns into exit 2.

4. Run the tests of step 2: they pass. Run the acceptance command.

5. Docs.
   - `docs/reference/cli.md`, a row after `next-id CAP`: `| `gaps [CAP] [--into C]` | List each requirement id that git history or an archived change used and that no living spec, open change, or `## Retired` entry holds now, with the archived `REMOVED` change and its reason, or the last commit that deleted the heading. `--into C` appends a `## RETIRED` block per id to change C's spec delta: the archived reason when there is one, else an empty `Reason:` that lint refuses until it is written. It never edits `spec.md`; an unknown or archived change exits 2 |`
   - `docs/guides/sdd.md`, after the `RETIRED` bullet of Track 1: `- Gaps from before retired ids existed: `gin specs gaps <cap>` lists them, and `gin specs gaps <cap> --into <change>` drafts their `RETIRED` blocks in an open change, which then goes through review and archive like any change.`
   - `docs/guides/sdd.vi.md`: the same at its matching line.
   - `skills/sdd/SKILL.md:13`, after the sentence of Track 1: `To explain gaps that exist already, run `specs gaps <cap> --into <change>` and write the empty reasons.`
   - Run `gin docs check docs/reference/cli.md docs/guides/sdd.md docs/guides/sdd.vi.md`: `ok`.

6. Commit: `feat(specs): gin specs gaps lists and drafts retired entries for old gaps (retired-req-ids)`.

## Integration
- **Branch**: `feat/retired-req-ids`
- **Merge strategy**: sequential

## Validation
- [ ] `python3 -m pytest -n auto` passes
- [ ] `gin docs check` passes on `docs/reference/cli.md`, `docs/guides/sdd.md`, `docs/guides/sdd.vi.md`
- [ ] Manual: in a scratch SDD repository, the issue #39 repro (add `REQ-AUTH-002`, commit, delete it, commit) makes `gin specs next-id auth` print `REQ-AUTH-003`, and `gin specs gaps auth` lists `REQ-AUTH-002` with the deleting commit

## Notes
- The user may override `Model:` and `Effort:` before plan approval.
- Provider roles describe responsibility rather than filename patterns.
- The Parent Bead stays open until the human-confirmed merge; each track bead closes once its tests and review pass.
