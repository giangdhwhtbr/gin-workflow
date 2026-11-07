# Plan: Role-aware discuss: business-only questions for a business member, technical questions resolved at plan

Epic: gin-workflow-746z
Spec: .planning/specs/2026-11-07-role-aware-discuss-design.md

## Objective
In team mode, a member with no technical role who runs `/gin:discuss` is asked business questions only; each technical point becomes an open `TQ-<n>` question in the design doc. `/gin:plan` resolves every open question with the technical member running it, and `gin record plan-approved` refuses while one is open.

Architecture: `TeamConfig.technical(member)` in `workflow_core/team.py` feeds `project.team.me.technical` (`gin state`) and `gin team whoami`. `workflow_core/specs.py` gains a parser for `## Open Technical Questions` (used by `specs lint --spec`, `specs lint --change`, and the record check) and `design_doc(root, cfg, workflow_id)`, which finds the legacy spec by its `Epic:`/`Workflow:` line or the SDD change's `03-design.md`. `lifecycle_cli._record_command` refuses `plan-approved` before the team pull request checks. The skills `team`, `discuss`, and `plan` carry the behaviour; the templates `design-spec.md` and `design.md` carry the section.

Tech stack: Python 3 standard library, Markdown skills and docs, Python `unittest` tests run by `python3 -m pytest -n auto`.

Global Constraints (from the spec):
- A role is technical when it is the `lead` of an area or listed in an area's `roles`. A member holding no technical role is business-only. No new config key.
- Technical questions are resolved at the start of `plan`, not in a second discuss pass or a new stage.
- The CLI enforces it at `record plan-approved`, not only the skill text.
- Questions and their decisions both live in the design doc (legacy: the spec file; SDD: the change's `03-design.md`).
- With the SDD layout, plan fills only the empty `## Architecture`, `## Error Handling`, and `## Testing` sections of `03-design.md`; it never rewrites a section someone already wrote.
- Out of scope: a new lifecycle stage or gate, changes to `gin state` gates, a config key that classifies roles, checking that the technical sections of `03-design.md` are filled, gin-console.
- An open question is not a lint error: `record requirement-confirmed` still records a spec with open questions.
- No flag skips the plan-approved check; the way out is a `Decision:` line.
- Solo projects, technical members, `me: null`, and workflows without the section behave as today.
- Budgets (`tests/workflow_core/test_token_budget.py`): each stage chain at most 12,000 characters (plan is 10,696 today), `skills/team/SKILL.md` at most 6,000 (5,217 today); each stage skill keeps exactly one line containing `project.team`, and the `team` skill stays out of the stage chains.
- Every docs page follows `plugins/gin-workflow/src/references/docs-style.md` (no em or en dashes).

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
- Problem statement: discuss asks whoever runs it to choose technical approaches and confirm the technical design, so a BA in team mode faces questions they cannot answer; after the spec is confirmed, no stage lets a technical member settle open technical questions.
- Success criteria: US-1 to US-3 of the spec; the full suite passes.
- Constraints: see Global Constraints.
- Non-goals: the spec's "Out of scope".

## Approach Options
### Option 1: questions and decisions in the design doc, checked at record (chosen in discuss)
- Summary: discuss writes `- TQ-<n>: <question>` under `## Open Technical Questions`; plan adds an indented `Decision:` line under each; `record plan-approved` finds the design doc from the workflow id and refuses while a question has no decision.
- Pros: the design doc is found from the workflow id in every mode, including team mode where the plan evidence is a pull request URL; the decision sits next to its question; one parser serves lint and record.
- Cons: plan edits the confirmed design doc (its technical part only).

### Option 2: decisions in the plan
- Summary: the plan answers each `TQ-<n>` in a `## Technical Decisions` section; record compares the spec with the plan.
- Pros: the confirmed spec is never edited.
- Cons: in team mode `plan-approved` evidence is a pull request URL and `--plan` is optional, so the CLI cannot always find the plan.

### Recommended Approach
- Selected option: Option 1.
- Rationale: chosen by the user in discuss on 2026-11-07 (spec "Decisions confirmed with the user").

## Scope
- In scope: R1 to R6 of the spec.
- Out of scope: everything under the spec's "Out of scope".

## Execution Strategy

```yaml
execution_strategy:
  mode: direct
  workers:
    mode: sequential
  rationale: Tracks 1 and 2 are small and independent, and Track 3 documents both (the skills read `project.team.me.technical` and the docs describe the record refusal), so one track at a time keeps the review simple.
```

## Tasks

### Track 1: `technical` flag for the current member
- **Dependencies**: none
- **Files**:
  - Modify `plugins/gin-workflow/src/scripts/workflow_core/team.py:60-61` (new method `technical` after `areas_for`) and `:172-179` (`summary` adds `technical`)
  - Modify `plugins/gin-workflow/src/scripts/workflow_core/team_cli.py:100-105` (`whoami` payload and text)
  - Test `tests/workflow_core/test_schema_2_7.py` (new class `TestTechnicalMember`; `test_state_reports_team_and_me` expects `technical`; new `test_state_and_whoami_report_a_business_member`)
- **Interfaces**:
  - Consumes: `TeamConfig.areas`, `Area.lead`, `Area.roles`, `Member.roles`.
  - Produces: `TeamConfig.technical(self, member: Member) -> bool`; `summary(...)["me"]["technical"]: bool`; `gin team whoami --format json` key `technical: bool`, text suffix `; technical: yes|no`.
- **Provider role**: `backend`
- **Model:** `sonnet`
- **Effort:** `low`
- **Why:** one predicate and two call sites in one module pair, with the cases spelled out in the spec.
- **Acceptance criteria**:
  - Every test in `tests/workflow_core/test_schema_2_7.py` passes.
  - The full suite passes.
- **Estimated complexity**: low

#### Steps

1. In `tests/workflow_core/test_schema_2_7.py`, change the expected `me` of `test_state_reports_team_and_me` to:

```python
                          "me": {"email": "binh@corp.com", "roles": ["be_lead", "be_dev"], "areas": ["backend"],
                                 "technical": True},
```

2. In the same file, add to `TestTeamIdentityAndSolo`:

```python
    def test_state_and_whoami_report_a_business_member(self):
        make_team_repo(self.root, email="an@corp.com")
        me = json.loads(run_cli(self.root, "state", "--format", "json").stdout)["project"]["team"]["me"]
        self.assertEqual({"email": "an@corp.com", "roles": ["ba"], "areas": [], "technical": False}, me)
        self.assertFalse(json.loads(run_cli(self.root, "team", "whoami", "--format", "json").stdout)["technical"])
        self.assertIn("technical: no", run_cli(self.root, "team", "whoami").stdout)

    def test_whoami_reports_a_technical_member(self):
        make_team_repo(self.root)
        self.assertIn("technical: yes", run_cli(self.root, "team", "whoami").stdout)
```

3. Add a class after `TestSchema27`:

```python
class TestTechnicalMember(unittest.TestCase):
    def test_area_lead_and_area_role_are_technical_others_are_not(self):
        team = load_team({"team": RAW})
        self.assertEqual({"an@corp.com": False, "binh@corp.com": True, "chi@corp.com": True,
                          "dung@corp.com": False, "em@corp.com": True},
                         {email: team.technical(member) for email, member in team.members.items()})

    def test_area_without_roles_counts_only_its_lead(self):
        team = load_team({"team": {"members": {"a@b.c": {"roles": ["ba"], "login": "a"},
                                               "l@b.c": {"roles": ["lead"], "login": "l"}},
                                   "areas": {"api": {"paths": ["api/**"], "lead": "lead"}}}})
        self.assertEqual(["api"], team.areas_for(team.member("a@b.c")))
        self.assertFalse(team.technical(team.member("a@b.c")))
        self.assertTrue(team.technical(team.member("l@b.c")))

    def test_business_and_technical_roles_make_a_technical_member(self):
        members = {**RAW["members"], "an@corp.com": {"roles": ["ba", "be_dev"], "login": "an-ba"}}
        team = load_team({"team": {**RAW, "members": members}})
        self.assertTrue(team.technical(team.member("an@corp.com")))
```

4. Run `python3 -m pytest tests/workflow_core/test_schema_2_7.py -q`. Expected: the new and changed tests fail (`AttributeError: 'TeamConfig' object has no attribute 'technical'`, missing `technical` key).

5. In `team.py`, add after `areas_for`:

```python
    def technical(self, member: Member) -> bool:
        """True when one of the member's roles leads an area or is listed in an area's roles."""
        roles = set(member.roles)
        return any(area.lead in roles or bool(roles & set(area.roles)) for area in self.areas.values())
```

   and in `summary`:

```python
    me = None if member is None else {"email": member.email, "roles": list(member.roles),
                                      "areas": team.areas_for(member), "technical": team.technical(member)}
```

6. In `team_cli.py`, replace the `whoami` branch body:

```python
    if args.command == "whoami":
        payload = {"email": member.email, "login": member.login, "roles": list(member.roles),
                   "areas": team.areas_for(member), "technical": team.technical(member)}
        _emit(payload, args.format, f"{member.email} ({member.login}) roles: {', '.join(member.roles)}; "
                                    f"areas: {', '.join(payload['areas']) or '-'}; "
                                    f"technical: {'yes' if payload['technical'] else 'no'}")
        return 0
```

7. Run `python3 -m pytest tests/workflow_core/test_schema_2_7.py -q`. Expected: all pass. Then `python3 -m pytest -n auto -q`. Expected: all pass.

8. Commit: `feat(team): report whether the current member holds a technical role (gin-workflow-746z)`.

### Track 2: open technical questions: parser, lint, design doc lookup, plan-approved check, templates
- **Dependencies**: none
- **Files**:
  - Modify `plugins/gin-workflow/src/scripts/workflow_core/specs.py:5` (import `replace`), `:71-100` (`lint_design_spec` adds the section errors), new code after `:100` (`Question`, `technical_questions`, `design_doc`), `:334-371` (`lint_change` adds the design file's section errors)
  - Modify `plugins/gin-workflow/src/scripts/workflow_core/lifecycle_cli.py:252-273` (new `_open_questions`; `_record_command` refuses `plan-approved`)
  - Modify `plugins/gin-workflow/src/templates/design-spec.md` (append the section)
  - Modify `plugins/gin-workflow/src/templates/design.md` (append the section)
  - Test `tests/workflow_core/test_specs_technical_questions.py`
  - Test `tests/workflow_core/test_specs_design_lint.py`, `tests/workflow_core/test_lifecycle_cli.py` (unchanged, must pass)
- **Interfaces**:
  - Consumes: `specs.change_file`, `specs.find_change`, `specs.shown`, `specs.sdd_config`, `specs.SpecsError`, `lifecycle_cli.resolve_effective_config`.
  - Produces: `specs.Question(id: str, line: int, decision: str)` (frozen; `decision == ""` means open); `specs.technical_questions(path: Path, label: str | None = None) -> tuple[list[Question], list[str]]`; `specs.design_doc(root: Path, cfg: Mapping[str, Any], workflow_id: str) -> Path | None` (raises `SpecsError` for two legacy specs naming the id or an ambiguous change id); `gin record plan-approved` exit 1 `status: rejected` with message `plan-approved refused: open technical questions` followed by `<path>:<line>: TQ-<n>` lines, exit 2 `status: error` for `SpecsError`.
- **Provider role**: `backend`
- **Model:** `sonnet`
- **Effort:** `high`
- **Why:** bounded change with a clear spec across `specs.py` and `lifecycle_cli.py`, but the parser has many edge cases (comments, fences, section ends, orphan and empty decisions, duplicates) and it gates a lifecycle record, so effort is raised.
- **Acceptance criteria**:
  - Every test in `tests/workflow_core/test_specs_technical_questions.py` passes.
  - `tests/workflow_core/test_specs_design_lint.py` and `tests/workflow_core/test_lifecycle_cli.py` pass unchanged.
  - The full suite passes.
- **Estimated complexity**: medium

#### Steps

1. Write the failing tests `tests/workflow_core/test_specs_technical_questions.py`:

```python
"""Open technical questions: parser, lint, design doc lookup, and the plan-approved check (gin-workflow-746z)."""

from __future__ import annotations

import contextlib
import io
import json
from pathlib import Path
import tempfile
import unittest

from tests.workflow_core.specs_fixtures import make_change, make_repo, write, write_activity
from tests.workflow_core.team_fixtures import calls, fake_cli, make_team_repo, path_with, run_cli
from workflow_core import specs
from workflow_core.cli import main as cli_main

SPEC_PATH = ".planning/specs/2026-01-01-x-design.md"


def spec(questions: str, id_line: str = "Epic: ep-1") -> str:
    """A legacy spec whose first question sits on line 12."""
    return (f"# T\n\n{id_line}\n\n### US-1: a\n\nAcceptance criteria:\n- x\n\n"
            f"## Open Technical Questions\n\n{questions}")


class _Repo(unittest.TestCase):
    layout = "legacy"

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = make_repo(Path(self.tmp.name) / "r", layout=self.layout)

    def cfg(self):
        return specs.sdd_config(specs.load_config(self.root))


class TestParse(_Repo):
    def parse(self, text: str):
        return specs.technical_questions(write(self.root, "spec.md", text))

    def test_open_and_decided_questions(self):
        found, errors = self.parse(spec("- TQ-1: Table or JSON column?\n  Decision: a table, queried by date.\n"
                                        "- TQ-2: Which queue?\n"))
        self.assertEqual([], errors)
        self.assertEqual([("TQ-1", 12, "a table, queried by date."), ("TQ-2", 14, "")],
                         [(q.id, q.line, q.decision) for q in found])

    def test_format_errors(self):
        found, errors = self.parse(spec("- TQ-1: a\n  Decision:\n- TQ-1: b\nfree text\n  Decision: orphan\n"))
        self.assertEqual(["TQ-1", "TQ-1"], [q.id for q in found])
        self.assertEqual(4, len(errors), errors)
        for expected, error in zip((":13: TQ-1 has an empty Decision:", ":14: TQ-1 appears twice",
                                    ":15: not a question", ":16: Decision: without a question"), errors):
            self.assertIn(expected, error)

    def test_comments_fences_and_other_sections_are_ignored(self):
        found, errors = self.parse(spec("<!-- - TQ-9: in a comment\n     spanning lines -->\n"
                                        "```\n- TQ-8: in code\n```\n- TQ-1: real\n\n## Notes\n\n- TQ-7: elsewhere\n"))
        self.assertEqual([], errors)
        self.assertEqual([("TQ-1", 17)], [(q.id, q.line) for q in found])

    def test_no_section(self):
        self.assertEqual(([], []), self.parse("# T\n\ntext\n"))

    def test_label_names_the_file_in_errors(self):
        path = write(self.root, "spec.md", spec("stray\n"))
        self.assertTrue(specs.technical_questions(path, "x/spec.md")[1][0].startswith("x/spec.md:12: "))


class TestLint(_Repo):
    def test_legacy_lint_reports_format_but_not_open_questions(self):
        self.assertEqual([], specs.lint_design_spec(write(self.root, "open.md", spec("- TQ-1: a\n"))))
        errors = specs.lint_design_spec(write(self.root, "bad.md", spec("- TQ-1: a\n  Decision:\n")))
        self.assertEqual(1, len(errors))
        self.assertIn(":13: TQ-1 has an empty Decision:", errors[0])


class TestChangeLint(_Repo):
    layout = "sdd"

    def test_change_lint_reads_the_design_file(self):
        change = make_change(self.root)
        write_activity(self.root)
        before = specs.lint_change(self.root, self.cfg(), change)
        write(self.root, "docs/changes/ep-1-lockout/03-design.md",
              "# Design\n\n## Open Technical Questions\n\nstray\n")
        after = specs.lint_change(self.root, self.cfg(), change)
        self.assertEqual(["docs/changes/ep-1-lockout/03-design.md:5: not a question (- TQ-<n>: <question>) "
                          "or its Decision: line"], [error for error in after if error not in before])


class TestDesignDoc(_Repo):
    def test_legacy_spec_by_epic_or_workflow_line(self):
        first = write(self.root, SPEC_PATH, spec(""))
        second = write(self.root, ".planning/specs/2026-01-02-b-design.md", spec("", "Workflow: topic-b"))
        self.assertEqual(first, specs.design_doc(self.root, self.cfg(), "ep-1"))
        self.assertEqual(second, specs.design_doc(self.root, self.cfg(), "topic-b"))
        self.assertIsNone(specs.design_doc(self.root, self.cfg(), "ep-10"))
        self.assertIsNone(specs.design_doc(self.root, self.cfg(), "ep"))

    def test_legacy_without_specs_folder(self):
        self.assertIsNone(specs.design_doc(self.root, self.cfg(), "ep-1"))

    def test_two_legacy_specs_for_one_id_is_an_error(self):
        write(self.root, SPEC_PATH, spec(""))
        write(self.root, ".planning/specs/2026-01-02-b-design.md", spec(""))
        with self.assertRaisesRegex(specs.SpecsError, "several specs name ep-1: .planning/specs/2026-01-01"):
            specs.design_doc(self.root, self.cfg(), "ep-1")


class TestSddDesignDoc(_Repo):
    layout = "sdd"

    def test_change_design_file(self):
        make_change(self.root)
        self.assertIsNone(specs.design_doc(self.root, self.cfg(), "ep-1"))
        design = write(self.root, "docs/changes/ep-1-lockout/03-design.md", "# Design\n")
        self.assertEqual(design, specs.design_doc(self.root, self.cfg(), "ep-1"))
        self.assertIsNone(specs.design_doc(self.root, self.cfg(), "ep-2"))

    def test_ambiguous_change_is_an_error(self):
        make_change(self.root, "ep-1-a")
        make_change(self.root, "ep-1-b")
        with self.assertRaisesRegex(specs.SpecsError, "ambiguous"):
            specs.design_doc(self.root, self.cfg(), "ep-1")


class TestPlanApprovedCheck(_Repo):
    def setUp(self):
        super().setUp()
        self.spec = write(self.root, SPEC_PATH, spec("- TQ-1: Table or JSON column?\n"))

    def record(self, workflow: str = "ep-1"):
        err = io.StringIO()
        with contextlib.redirect_stderr(err), contextlib.redirect_stdout(io.StringIO()):
            code = cli_main(["record", "plan-approved", "--repository", str(self.root), "--evidence", "plan.md",
                             "--actor", "user", "--workflow-id", workflow])
        return code, err.getvalue()

    def gate(self, workflow: str = "ep-1") -> str:
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            cli_main(["state", "--repository", str(self.root), "--format", "json", "--workflow-id", workflow])
        return json.loads(out.getvalue())["gates"]["plan_approved"]

    def test_open_question_refuses_the_gate(self):
        code, err = self.record()
        self.assertEqual(1, code)
        self.assertIn("plan-approved refused: open technical questions", err)
        self.assertIn(f"{SPEC_PATH}:12: TQ-1", err)
        self.assertEqual("unmet", self.gate())

    def test_decided_questions_record_the_gate(self):
        self.spec.write_text(spec("- TQ-1: Table or JSON column?\n  Decision: a table.\n"), encoding="utf-8")
        self.assertEqual(0, self.record()[0])
        self.assertEqual("satisfied", self.gate())

    def test_workflow_without_design_doc_records_as_today(self):
        self.assertEqual(0, self.record("other")[0])
        self.assertEqual("satisfied", self.gate("other"))

    def test_two_specs_for_one_epic_is_a_usage_error(self):
        write(self.root, ".planning/specs/2026-01-02-y-design.md", spec(""))
        code, err = self.record()
        self.assertEqual(2, code)
        self.assertIn("several specs name ep-1", err)

    def test_check_runs_before_the_team_pull_request_check(self):
        root = make_team_repo(Path(self.tmp.name) / "team")
        write(root, SPEC_PATH, spec("- TQ-1: a\n"))
        bin_dir = Path(self.tmp.name) / "bin"
        fake_cli(bin_dir, "gh", [])
        result = run_cli(root, "record", "plan-approved", "--evidence", "https://github.com/org/app/pull/7",
                         "--workflow-id", "ep-1", env=path_with(bin_dir))
        self.assertEqual(1, result.returncode, result.stderr)
        self.assertIn("open technical questions", result.stderr)
        self.assertEqual([], calls(bin_dir))


if __name__ == "__main__":
    unittest.main()
```

   Line numbers in `test_comments_fences_and_other_sections_are_ignored`: lines 12-13 hold the comment, 14-16 the fence, 17 `- TQ-1: real`.

2. Run `python3 -m pytest tests/workflow_core/test_specs_technical_questions.py -q`. Expected: failures (`AttributeError: module 'workflow_core.specs' has no attribute 'technical_questions'`, and the record tests exit 0 instead of 1).

3. In `specs.py`, change line 5 to `from dataclasses import dataclass, replace` and add after `lint_design_spec`:

```python
_TQ_SECTION = "## Open Technical Questions"
_TQ = re.compile(r"^- (TQ-\d+): \S")
_DECISION = re.compile(r"^\s+Decision:(.*)$")
_COMMENT = re.compile(r"<!--.*?-->", re.DOTALL)
_LEGACY_SPECS = ".planning/specs"


@dataclass(frozen=True)
class Question:
    id: str
    line: int
    decision: str


def technical_questions(path: Path, label: str | None = None) -> tuple[list[Question], list[str]]:
    """Questions under `## Open Technical Questions` (an empty decision is open) and the section's format errors."""
    name = label or str(path)
    text = _COMMENT.sub(lambda found: "\n" * found.group().count("\n"), path.read_text(encoding="utf-8"))
    questions: list[Question] = []
    errors: list[str] = []
    inside = fenced = False
    for number, line in enumerate(text.splitlines(), 1):
        if line.lstrip().startswith("```"):
            fenced = not fenced
            continue
        if fenced:
            continue
        if re.match(r"^#{1,2} ", line):
            inside = line.strip() == _TQ_SECTION
            continue
        if not inside or not line.strip():
            continue
        question, decision = _TQ.match(line), _DECISION.match(line)
        if question:
            if any(item.id == question.group(1) for item in questions):
                errors.append(f"{name}:{number}: {question.group(1)} appears twice")
            questions.append(Question(question.group(1), number, ""))
        elif decision and questions and questions[-1].line == number - 1:
            answer = decision.group(1).strip()
            if not answer:
                errors.append(f"{name}:{number}: {questions[-1].id} has an empty Decision:")
            questions[-1] = replace(questions[-1], decision=answer)
        elif decision:
            errors.append(f"{name}:{number}: Decision: without a question on the line above")
        else:
            errors.append(f"{name}:{number}: not a question (- TQ-<n>: <question>) or its Decision: line")
    return questions, errors


def design_doc(root: Path, cfg: Mapping[str, Any], workflow_id: str) -> Path | None:
    """The workflow's design doc: the SDD change's design file, or the one legacy spec naming the workflow."""
    root = Path(root)
    if cfg["layout"] == "sdd":
        try:
            design = change_file(find_change(root, cfg, workflow_id), "design")
        except SpecsError as error:
            if "ambiguous" in str(error):
                raise
            return None
        return design if design.is_file() else None
    named = re.compile(rf"^(?:Epic|Workflow): {re.escape(workflow_id)}$", re.MULTILINE)
    folder = root / _LEGACY_SPECS
    found = [path for path in sorted(folder.glob("*.md"))
             if named.search(path.read_text(encoding="utf-8"))] if folder.is_dir() else []
    if len(found) > 1:
        raise SpecsError(f"several specs name {workflow_id}: {', '.join(shown(root, path) for path in found)}")
    return found[0] if found else None
```

   In `lint_design_spec`, after the final `close()` call add `errors += technical_questions(path)[1]`. In `lint_change`, replace the `return` line with:

```python
    design = change_file(change, "design")
    questions = technical_questions(design, shown(root, design))[1] if design.is_file() else []
    return errors + questions + _untracked_citations(root, change) + lint_iterations(root, cfg) + lint_diagrams(root, cfg)
```

4. In `lifecycle_cli.py`, add after `_spec_lint_errors`:

```python
def _open_questions(repo_path: Path, workflow_id: str) -> list[str]:
    """`<path>:<line>: TQ-<n>` for each open technical question in the workflow's design doc."""
    from .specs import design_doc, sdd_config, shown, technical_questions

    if not (repo_path / ".agent-workflow/config.yaml").is_file():
        return []
    config = resolve_effective_config(repo_path, write=False).config.to_dict()
    design = design_doc(repo_path, sdd_config(config), workflow_id)
    if design is None:
        return []
    questions, _ = technical_questions(design)
    return [f"{shown(repo_path, design)}:{item.line}: {item.id}" for item in questions if not item.decision]
```

   and in `_record_command`, after the `requirement-confirmed` lint block and before `store = ...`:

```python
    if args.gate == "plan-approved":
        from .specs import SpecsError

        try:
            open_questions = _open_questions(Path(args.repository).resolve(), args.workflow_id)
        except SpecsError as error:
            return {"status": "error", "message": str(error)}, 2
        if open_questions:
            return {"status": "rejected", "message": "plan-approved refused: open technical questions\n"
                    + "\n".join(open_questions)}, 1
```

5. Append to `templates/design-spec.md` and to `templates/design.md`:

```markdown

## Open Technical Questions

<!-- In team mode, a discuss run by a member with no technical role lists each technical point it does not
     decide here, one per line: `- TQ-1: <question>`. Plan asks the technical member about each one and adds an
     indented `Decision: <answer>` line right under it. `gin record plan-approved` refuses while a question has no
     decision. Leave the section empty when there is none. -->
```

6. Run `python3 -m pytest tests/workflow_core/test_specs_technical_questions.py tests/workflow_core/test_specs_design_lint.py tests/workflow_core/test_lifecycle_cli.py -q`. Expected: all pass. Then `python3 -m pytest -n auto -q`. Expected: all pass.

7. Commit: `feat(specs): open technical questions in the design doc block plan-approved (gin-workflow-746z)`.

### Track 3: skills and docs
- **Dependencies**: Track 1, Track 2
- **Files**:
  - Modify `plugins/gin-workflow/src/skills/team/SKILL.md:16-20` (`## discuss` and `## plan`)
  - Modify `plugins/gin-workflow/src/skills/discuss/SKILL.md:21` (step 2 points to the `team` skill) and `:27` (step 5 drops `project.team`)
  - Modify `plugins/gin-workflow/src/skills/plan/SKILL.md:16` (step 1 resolves open questions)
  - Modify `docs/guides/team.md:56-57`, `docs/guides/team.vi.md` (the same two table rows)
  - Modify `docs/roles.md` (`## Keeping work apart`), `docs/roles.vi.md` (the same section)
  - Modify `docs/concepts/lifecycle.md:12` (`plan` row) and `:95` (team mode bullet)
  - Modify `docs/reference/cli.md:69` (`plan-approved`), `:132` (`lint`), `:181` (`whoami`)
  - Create `tests/workflow_core/test_role_aware_skills.py`
  - Test `tests/workflow_core/test_token_budget.py`, `tests/workflow_core/test_docs_coverage.py` (unchanged, must pass)
- **Interfaces**:
  - Consumes: `project.team.me.technical` (Track 1); the `## Open Technical Questions` format, `Decision:` lines, and the `record plan-approved` refusal (Track 2).
  - Produces: skill and docs text only.
- **Provider role**: `docs`
- **Model:** `sonnet`
- **Effort:** `medium`
- **Why:** instruction text that changes agent behaviour under tight character budgets (team skill has about 780 characters left, the plan chain about 1,300), plus five docs pages; judgement on wording, no logic.
- **Acceptance criteria**:
  - `tests/workflow_core/test_role_aware_skills.py`, `test_token_budget.py`, and `test_docs_coverage.py` pass.
  - `gin docs check docs/guides/team.md docs/guides/team.vi.md docs/roles.md docs/roles.vi.md docs/concepts/lifecycle.md docs/reference/cli.md` reports no finding.
  - The full suite passes.
- **Estimated complexity**: low

#### Steps

1. Write the failing test `tests/workflow_core/test_role_aware_skills.py`:

```python
"""Skill text for role-aware discuss and plan (gin-workflow-746z)."""

from __future__ import annotations

from pathlib import Path
import unittest

SRC = Path(__file__).resolve().parents[2] / "plugins/gin-workflow/src"


def section(text: str, heading: str) -> str:
    start = text.index(heading)
    end = text.find("\n## ", start + len(heading))
    return text[start:] if end == -1 else text[start:end]


class TestRoleAwareSkills(unittest.TestCase):
    def test_team_discuss_limits_a_business_member_to_business_questions(self):
        text = section((SRC / "skills/team/SKILL.md").read_text(encoding="utf-8"), "## discuss")
        for needle in ("project.team.me.technical", "business questions", "- TQ-<n>: <question>",
                       "## Open Technical Questions"):
            self.assertIn(needle, text)

    def test_team_plan_puts_the_design_doc_in_the_plan_pull_request(self):
        text = section((SRC / "skills/team/SKILL.md").read_text(encoding="utf-8"), "## plan")
        self.assertIn("Decision:", text)

    def test_discuss_reads_the_team_skill_before_asking(self):
        text = (SRC / "skills/discuss/SKILL.md").read_text(encoding="utf-8")
        clarify = next(line for line in text.splitlines() if "**Clarify**" in line)
        self.assertIn("`team` skill", clarify)

    def test_plan_resolves_open_questions_first(self):
        text = (SRC / "skills/plan/SKILL.md").read_text(encoding="utf-8")
        step = next(line for line in text.splitlines() if line.startswith("1. "))
        for needle in ("## Open Technical Questions", "Decision:", "03-design.md", "record plan-approved"):
            self.assertIn(needle, step)


if __name__ == "__main__":
    unittest.main()
```

2. Run `python3 -m pytest tests/workflow_core/test_role_aware_skills.py -q`. Expected: 4 failures.

3. `skills/team/SKILL.md`, `## discuss`: add a second paragraph:

```markdown
When `project.team.me.technical` is false, ask only business questions (purpose, users, rules, edge cases, validation, acceptance criteria, scope); propose no approach, present no technical design, and never ask the runner to choose or confirm a technical option. Write each technical point as `- TQ-<n>: <question>` under the design doc's `## Open Technical Questions` (the spec, or `03-design.md` with the SDD layout), not as an assumption; plan resolves them.
```

   `## plan`: append to its paragraph: `The plan PR also carries the design doc's new `Decision:` lines and, with the SDD layout, the filled `03-design.md` sections.`

4. `skills/discuss/SKILL.md`: step 2 starts `2. **Clarify** — in team mode, read the `team` skill first: it decides which questions you ask. One question per message, ...` (keep the rest of the line). In step 5, replace `With `project.team.enabled`, spec review and the `requirement-confirmed` evidence follow the `team` skill.` by `In team mode, spec review and the `requirement-confirmed` evidence also follow the `team` skill.` so the file keeps exactly one line containing `project.team`. If that line count would drop to zero, put `project.team.enabled` in the step 2 sentence (`with `project.team.enabled`, read the `team` skill first`) and keep step 5 free of it.

5. `skills/plan/SKILL.md`, step 1: append:

```markdown
If the design doc (the spec, or `03-design.md` with the SDD layout) has a `- TQ-<n>:` line under `## Open Technical Questions` without an indented `Decision:` line, ask the user about each in turn (one per message, 2–3 options, lead with your recommendation), write `Decision: <answer>` under it, and carry the decisions into Approach Options; with the SDD layout then fill each empty `## Architecture`, `## Error Handling`, and `## Testing` section of `03-design.md` and leave written sections unchanged. Commit these edits with the plan; `record plan-approved` refuses while a question is open.
```

6. Docs, following `references/docs-style.md`:
   - `docs/guides/team.md` row `discuss`: append `When the member running discuss holds no technical role (no area `lead` and no role in an area's `roles`; `gin team whoami` shows `technical: no`), discuss asks business questions only and writes each technical point as `- TQ-<n>: <question>` under the design doc's `## Open Technical Questions`.` Row `plan`: append `Plan first settles each open `TQ-<n>` with the member running it and writes `Decision:` under it; the plan pull request carries those lines and, with the SDD layout, the filled `03-design.md` sections.` Translate both into the same rows of `docs/guides/team.vi.md`.
   - `docs/roles.md`, `## Keeping work apart`: add the bullet `Technical questions: in team mode a BA running `/gin:discuss` is asked business questions only; each technical point becomes an open `TQ-<n>` in the design doc, and the tech lead settles them at the start of `/gin:plan`. `record plan-approved` refuses while one is open.` Translate it into `docs/roles.vi.md`.
   - `docs/concepts/lifecycle.md` row `plan`: after `Writes`, insert `first settles each open technical question (`TQ-<n>`) of the design doc, then writes`. Team mode bullet: append `; a member with no technical role gets business questions only in `discuss`, and `plan` settles the technical questions it leaves.`
   - `docs/reference/cli.md` row `plan-approved`: append `. Refused (exit 1, nothing recorded) while the workflow's design doc has a `- TQ-<n>:` line under `## Open Technical Questions` without an indented `Decision:` line; the design doc is the legacy spec in `.planning/specs/` with `Epic: <id>` or `Workflow: <id>`, or the SDD change's `03-design.md`; two legacy specs naming the id exit 2`. Row `lint`: append `; `--spec` and `--change` also check `## Open Technical Questions` (`- TQ-<n>: <question>` lines, unique ids, at most one non-empty indented `Decision:` line right below each); an open question is not an error`. Row `whoami`: `Show your member entry, roles, areas, and whether you hold a technical role (an area `lead` or a role in an area's `roles`), from `git config user.email``.

7. Run `python3 -m pytest tests/workflow_core/test_role_aware_skills.py tests/workflow_core/test_token_budget.py tests/workflow_core/test_docs_coverage.py -q` and `gin docs check docs/guides/team.md docs/guides/team.vi.md docs/roles.md docs/roles.vi.md docs/concepts/lifecycle.md docs/reference/cli.md`. Expected: all pass, no finding. Then `python3 -m pytest -n auto -q`. Expected: all pass.

8. Commit: `docs(team): business-only discuss and technical questions settled at plan (gin-workflow-746z)`.

## Integration
- **Branch**: feat/role-aware-discuss
- **Merge strategy**: sequential

## Validation
- [ ] `python3 -m pytest -n auto -q` passes
- [ ] `python3 -m pytest tests/workflow_core/test_schema_2_7.py tests/workflow_core/test_specs_technical_questions.py tests/workflow_core/test_role_aware_skills.py tests/workflow_core/test_token_budget.py tests/workflow_core/test_docs_coverage.py -q` passes
- [ ] Manual: in a scratch team repo with `git config user.email` set to a `ba` member, `gin team whoami` prints `technical: no`; a legacy spec with `Epic: ep-1` and an open `- TQ-1:` makes `gin record plan-approved --workflow-id ep-1 --evidence plan.md` exit 1 naming `TQ-1`; adding `  Decision: x` under it lets the same command record the gate

## Notes
- `Model:` and `Effort:` are chosen from the main harness catalog using the route rubric.
- The Parent Bead `gin-workflow-746z` stays open until the human-confirmed merge; track beads close after tests and review pass.
- `.planning/specs/` already holds two specs with `Epic: gin-workflow-f7g`; that shipped workflow will never record `plan-approved` again, so the new usage error does not affect it.
