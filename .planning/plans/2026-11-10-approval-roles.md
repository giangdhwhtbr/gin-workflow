# Plan: Approval roles without a single-holder deadlock

Spec: .planning/specs/2026-11-10-approval-roles-design.md
Epic: gin-workflow-approval-roles
Workflow: gin-workflow-approval-roles

## Objective

Gate policies accept `{all, any}`; a role in `all`, or an area's lead role, whose only holder is the pull request author is skipped with a note (with `any`, or another area's lead, required instead); doctor notes single-holder roles; the brownfield starter gets an `fe_lead` and `ship: {all: [qe], any: [be_lead, fe_lead]}`.

**Goal** (spec): a gate policy can require a role, not only accept one of several; no gate deadlocks because the pull request author is the only holder of a needed role; doctor warns about such gates; and the brownfield starter gives app areas an `fe_lead` and the tech lead a second approver.

**Architecture**: `team.py` gains small policy helpers (`policy_parts`, `policy_roles`, `_sole_holder`) used by `check_approval`, `gate_roles`, `_has_policy`, and `validate_team`; `check_approval` and `verify_gate` take an optional `notes` list that `team check` prints; `schemas.py` accepts the object form; `team_init.codeowners` and `doctor_report` use `policy_roles`. Docs, starter, and skills follow in Track 2.

**Tech Stack**: Python 3 standard library; unittest with `team_fixtures` (`TEAM`, `make_team_repo`, `fake_cli`, `gh_pr`, `run_cli`, `write`).

**Global Constraints** (spec, verbatim):
- Existing role-list and `area_lead` configs keep their behaviour and refusal texts; existing tests stay green.
- A config using the object form is refused by older gin-workflow versions (schema), so the starter and docs state the minimum version.
- No JSON output or Beads metadata changes; gin-console is unaffected.
- The author never approves their own pull request.
- Out of scope: `area_lead` for `ship`; consuming-area leads approving a contract spec; a frontend review checklist; changes to the waiver rules.

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
- Problem statement: list policies mean "one of"; a sole-holder author deadlocks a gate; the starter puts every approval on the tech lead.
- Success criteria: spec R1 to R8; US-1 to US-4 as tests.
- Constraints: Global Constraints above.
- Non-goals: see Global Constraints.

## Approach Options
### Option 1: `{all, any}` object with author fallback (confirmed)
- Summary: object policy beside lists; sole-holder fallback; doctor note; existing waiver for absence.
- Pros: backward compatible; readable config; no deadlock.
- Cons: schema change refused by older installs.

### Option 2: nested lists or a separate `ship_requires` key
- Summary: AND-of-ORs lists, or a second key per gate.
- Pros: fewer schema shapes (lists) or simplest evaluation (key).
- Cons: harder to read, or one gate split across two keys; rejected in `/discuss`.

### Recommended Approach
- Selected option: Option 1 (confirmed in `/discuss` on 2026-11-10).
- Rationale: meets R1 to R8 with backward compatibility.

## Scope
- In scope: R1 to R8.
- Out of scope: see Global Constraints.

## Execution Strategy

```yaml
execution_strategy:
  mode: direct
  workers:
    mode: sequential
  rationale: Track 2 documents and configures the policy form Track 1 ships; one lane.
```

## Tasks

`S` is `plugins/gin-workflow/src/scripts/workflow_core`.

### Track 1: Object policies, sole-holder fallback, and policy helpers
- **Dependencies**: none
- **Files**:
  - Modify `plugins/gin-workflow/src/scripts/workflow_core/schemas.py:14,44-53` (object policy)
  - Modify `plugins/gin-workflow/src/scripts/workflow_core/team.py:105-146` (`validate_team`), `:350-362` (keep `_approver_roles`), `:445-518` (`check_approval`, `gate_roles`, `_has_policy`), `/^def verify_gate/` (`notes` passthrough)
  - Modify `plugins/gin-workflow/src/scripts/workflow_core/team_cli.py:106-117` (`check` prints notes)
  - Modify `plugins/gin-workflow/src/scripts/workflow_core/team_init.py:34-52` (`codeowners` uses `policy_roles`)
  - Test `tests/workflow_core/test_team_gates.py`
  - Test `tests/workflow_core/test_team_init.py`
- **Provider role**: `backend`
- **Model:** `sonnet`
- **Effort:** `high`
- **Why:** gate approval logic is security-relevant with several edge cases (author exclusion, sole holder, empty `any`, area substitution) and must keep every existing refusal text.
- **Interfaces**:
  - `team.policy_parts(policy: Any) -> tuple[list[str], list[str]]` returning `(all_roles, any_roles)`: a list gives `([], list)`, a mapping gives its `all`/`any`, anything else `([], [])`.
  - `team.policy_roles(policy: Any, team: TeamConfig) -> set[str]`: `area_lead` gives the area leads; otherwise the union of `policy_parts`.
  - `team._sole_holder(team: TeamConfig, role: str, author: Member | None) -> bool`: true when `author` holds `role` and no other member does.
  - `check_approval(..., notes: list[str] | None = None)`; `verify_gate(..., notes: list[str] | None = None)` passes it through.
  - `team check --format json` payload adds `"notes": [...]` (additive); text output prints each note as `note: <text>` before the result line.
- **Steps**:
  1. Failing tests in `tests/workflow_core/test_team_gates.py`, new class `TestObjectPolicies(GateCase)` above the `__main__` guard (not between a decorator and its class; no duplicate name). Each test rewrites the team block with `make_team_repo(..., team=...)` based on `team_fixtures.TEAM` with a different `approvals` block, and uses `self.gh(gh_pr(...))` and `self.check_ship()` like `test_ship_needs_qe_approval_on_local_head`:
     - `test_all_requires_each_role`: `ship: {all: [qe], any: [be_lead, fe_lead]}`; approval only by `binh-dev` (be_lead) on head → exit 1, stdout contains `missing approval from qe`; approvals by `dung-qe` and `chi-fe` on head → exit 0.
     - `test_any_required_with_all`: same policy; approval only by `dung-qe` → exit 1, `missing approval from one of be_lead, fe_lead`.
     - `test_list_policy_unchanged`: `ship: [qe, be_lead]`; approval only by `binh-dev` → exit 0.
     - `test_sole_holder_author_falls_back_to_any`: `ship: {all: [qe], any: [be_lead]}`; PR author `dung-qe` (the only `qe`), approval by `binh-dev` → exit 0 and stdout contains `note: qe skipped: the author is its only holder`.
     - `test_sole_holder_without_any_is_refused`: `ship: {all: [qe]}`; author `dung-qe`, approval by `binh-dev` → exit 1, `qe has no holder other than the author; add a holder or an `any` role`.
     - `test_second_holder_disables_fallback`: add member `eve@corp.com: {roles: [qe], login: eve-qe}`; `ship: {all: [qe], any: [be_lead]}`; author `dung-qe`, approval by `binh-dev` → exit 1, `missing approval from qe`.
     - `test_area_lead_author_substituted_by_other_lead`: `plan_approved: area_lead`; the existing plan fixture's track in area `backend`; PR author `binh-dev` (only `be_lead`), approval by `chi-fe` (fe_lead) on the plan PR → `record plan-approved` passes and the stderr or stdout note names `be_lead for area backend skipped: the author is its only holder; approved by fe_lead`. Mirror the existing `plan-approved` tests for setup (files, merged state).
     - `test_object_policy_unknown_key_is_refused`: `ship: {every: [qe]}` → `gin setup validate` (or the config load the existing schema tests use; search `additionalProperties` tests) reports the unknown key.
     In `tests/workflow_core/test_team_init.py` add `test_codeowners_with_object_requirement_policy`: `requirement_confirmed: {all: [ba], any: [be_lead]}` → the spec directory line lists the `ba` and `be_lead` holders' logins.
  2. Run `python3 -m pytest tests/workflow_core/test_team_gates.py tests/workflow_core/test_team_init.py -q -n auto -k "ObjectPolic or object_requirement"` → fails.
  3. `schemas.py`: after `_ROLES` add
     ```python
     _POLICY = {"type": "object", "properties": {"all": _ROLES, "any": _ROLES}, "additionalProperties": False,
                "minProperties": 1}
     _GATE = {"anyOf": [_ROLES, _POLICY]}
     ```
     and use `_GATE` for `requirement_confirmed`, `ship`, `verification_passed`, `roadmap`, and `{"anyOf": [{"const": "area_lead"}, _ROLES, _POLICY]}` for `plan_approved`.
  4. `team.py` helpers (near `gate_roles`):
     ```python
     def policy_parts(policy: Any) -> tuple[list[str], list[str]]:
         """(roles that must each approve, roles of which one must approve)."""
         if isinstance(policy, Mapping):
             return list(policy.get("all") or []), list(policy.get("any") or [])
         if isinstance(policy, list):
             return [], list(policy)
         return [], []


     def policy_roles(policy: Any, team: TeamConfig) -> set[str]:
         if policy == "area_lead":
             return {area.lead for area in team.areas.values()}
         required, optional = policy_parts(policy)
         return set(required) | set(optional)


     def _sole_holder(team: TeamConfig, role: str, author: Member | None) -> bool:
         return author is not None and role in author.roles and all(
             member is author for member in team.members.values() if role in member.roles)
     ```
     `gate_roles` becomes `return policy_roles(team.approvals.get(gate, []), team)`. `_has_policy` becomes `policy == "area_lead" and bool(areas) or bool(set().union(*policy_parts(policy)))` using the two lists. In `validate_team`, replace `if isinstance(policy, list): needed += ...` with `needed += [(role, f"team.approvals.{gate}") for role in set().union(*policy_parts(policy))]`, add `errors.append(f"team.approvals.{gate}: all and any are both empty")` when the policy is a mapping and both lists are empty, and build `approving` (aws_identity check) with `policy_parts` for every policy.
  5. `check_approval`: add `notes: list[str] | None = None`; append a note only when a list was passed (`if notes is not None`). Compute `author = team.by_identity(pr.author, adapter(team.host).identity_key)`. Replace the `area_lead` branch body with:
     ```python
     others = sorted(held & {a.lead for a in team.areas.values() if a.lead != area.lead})
     if area is not None and area.lead not in held:
         if _sole_holder(team, area.lead, author) and others:
             if notes is not None:
                 notes.append(f"{area.lead} for area {name} skipped: the author is its only holder; "
                              f"approved by {others[0]}")
         else:
             reasons.append(f"missing approval from {area.lead} for area {name}")
     ```
     (compute `others` inside the loop after `area` is known). Add the mapping branch before the list branch:
     ```python
     elif isinstance(policy, Mapping):
         required, optional = policy_parts(policy)
         need_any = bool(optional)
         for role in required:
             if role in held:
                 continue
             if _sole_holder(team, role, author):
                 if not optional:
                     reasons.append(f"{role} has no holder other than the author; add a holder or an `any` role")
                 elif notes is not None:
                     notes.append(f"{role} skipped: the author is its only holder")
                 continue
             reasons.append(f"missing approval from {role}")
         if need_any and not held & set(optional):
             reasons.append(f"missing approval from one of {', '.join(optional)}")
     ```
     Keep the list branch unchanged. Add `Mapping` to the typing import if missing.
  6. `verify_gate` gains `notes: list[str] | None = None` and passes it to `check_approval`. In `team_cli.py` `check`: `notes: list[str] = []`, pass `notes=notes`, add `"notes": notes` to the JSON payload, and for text output print `note: <text>` lines before the existing line.
  7. `team_init.codeowners`: replace `spec_roles = (set(requirement) if isinstance(requirement, list) else set()) | leads` with `spec_roles = policy_roles(requirement, team) | leads` (import `policy_roles` from `.team`).
  8. Run step 2 → passes; run `python3 -m pytest tests/workflow_core/test_team_gates.py tests/workflow_core/test_team_init.py tests/workflow_core/test_lifecycle_cli.py -q -n auto` → passes with every existing refusal text unchanged.
  9. Commit: `feat(team): all/any approval policies with a sole-holder fallback (gin-workflow-approval-roles)`.
- **Acceptance criteria**: R1 to R5, R7; US-1, US-2, US-3 as the tests above; existing team tests pass unchanged.
- **Estimated complexity**: medium

### Track 2: Doctor note, fe_lead, starter, and docs
- **Dependencies**: Track 1
- **Files**:
  - Modify `plugins/gin-workflow/src/scripts/workflow_core/team_init.py:158-197` (`doctor_report` notes)
  - Modify `docs/roles.md:18-24`
  - Modify `docs/starters/brownfield.md:40-60,150-155`
  - Modify `docs/reference/config.md:171`
  - Modify `docs/guides/team.md:21,36,55,60`
  - Modify `plugins/gin-workflow/src/skills/team/SKILL.md`, `plugins/gin-workflow/src/skills/team-setup/SKILL.md`
  - Test `tests/workflow_core/test_team_init.py`
- **Provider role**: `backend`
- **Model:** `sonnet`
- **Effort:** `medium`
- **Why:** one small doctor addition plus documentation; the team skill sits at 5,992 of 6,000 characters, so its edit needs a matching cut.
- **Interfaces**: `team_init.single_holder_notes(team: TeamConfig) -> list[str]`, each `"<gate>: <role> has one holder (<login>)"` for roles in `all`, and `"area <name>: lead <role> has one holder (<login>)"` for area leads.
- **Steps**:
  1. Failing test in `tests/workflow_core/test_team_init.py`: `test_doctor_notes_single_holders` builds a team like the brownfield starter (pm, ba, be_lead, two be_dev, fe_lead holder, one qe) with `ship: {all: [qe], any: [be_lead, fe_lead]}` and areas led by `be_lead` and `fe_lead`, calls `single_holder_notes(team)`, and asserts entries for `ship: qe`, `area ... be_lead`, `area ... fe_lead`; a variant with a second `qe` member has no `ship: qe` entry. Run → fails.
  2. Add `single_holder_notes` in `team_init.py`:
     ```python
     def single_holder_notes(team: TeamConfig) -> list[str]:
         from .team import policy_parts

         def holders(role: str) -> list[str]:
             return sorted(member.login or member.email for member in team.members.values() if role in member.roles)

         notes = []
         for gate, policy in sorted(team.approvals.items()):
             for role in policy_parts(policy)[0]:
                 found = holders(role)
                 if len(found) == 1:
                     notes.append(f"{gate}: {role} has one holder ({found[0]})")
         for name, area in sorted(team.areas.items()):
             found = holders(area.lead)
             if len(found) == 1:
                 notes.append(f"area {name}: lead {area.lead} has one holder ({found[0]})")
         return notes
     ```
     In `doctor_report`, `notes = host.doctor_notes() + single_holder_notes(team)` (keep the existing `report["note"] = "; ".join(notes)`). Run → passes.
  3. Docs and starter:
     - `docs/roles.md`: add a row `| Frontend lead | fe_lead | ... |` after the tech lead row, stating it leads app areas and approves their plans; change the tech lead row so it no longer says "backup approver for roadmap, requirement_confirmed, and ship when a role has one holder" and instead points to the sole-holder fallback in `guides/team.md`.
     - `docs/starters/brownfield.md`: in the team block add an `fe_lead` role to the frontend developer member (or a new member) so the starter has one `fe_lead`; set the `web` area `lead: fe_lead`; set `ship: {all: [qe], any: [be_lead, fe_lead]}`; replace the single-holder note (line 60) with one sentence on the fallback and the doctor note; update the approvals recap near lines 150-155; state "needs gin-workflow 3.1 or later" (or the version that ships this) next to the object form.
     - `docs/reference/config.md:171`: document the three forms: role list (one of), `{all, any}`, and `area_lead` for `plan_approved`, with the sole-holder fallback in one sentence.
     - `docs/guides/team.md` (21, 36, 55, 60): object form, fallback, the doctor note, and "an absent holder: `gin unblock` with a reason and a follow-up bead".
     - Skills: `team/SKILL.md` line 12 or 17: one clause "`{all, any}` requires each `all` role; a sole-holder author's role is skipped with a note" paid for by an equal cut that drops no rule (quote before/after in the commit message); `team-setup/SKILL.md:11`: mention the object form when asking approvals. Run `wc -m` on both; each at most 6000; run the budget report; every stage chain at most 12000.
     - Run `gin docs check docs/roles.md docs/starters/brownfield.md docs/reference/config.md docs/guides/team.md` → no findings.
  4. Run `python3 -m pytest tests/workflow_core/test_team_init.py tests/workflow_core/test_token_budget.py -q` → passes; run `python3 -m pytest -n auto -q` → passes.
  5. Commit: `docs(team): fe_lead, all/any ship policy in the starter, doctor single-holder note (gin-workflow-approval-roles)`.
- **Acceptance criteria**: R6, R8; US-4; budgets hold; docs check clean.
- **Estimated complexity**: low

## Integration
- **Branch**: `feat/approval-roles`
- **Merge strategy**: sequential

## Validation
- [ ] `python3 -m pytest -n auto -q` passes (pre-push runs it).
- [ ] `python3 -m pytest tests/workflow_core/test_token_budget.py -q` passes.
- [ ] `gin docs check` on the changed docs reports no findings.

## Notes
- Omit `Effort:` when the catalog lists no efforts.
- The user may override `Model:` and `Effort:` before plan approval.
- Provider roles describe responsibility rather than filename patterns.
- Deliverable merge-holds (e.g. "remain open until human-confirmed merge") apply exclusively to the Parent Bead. Individual track beads must close upon passing tests and code review to unblock downstream dependent tracks.
- Test hygiene from earlier reviews: new classes above the `__main__` guard, never between a decorator and its class, no duplicate class names; check `--collect-only` counts.
- Budget lesson: every cut in a skill is quoted before/after and checked for a dropped rule.
