# Approval policies: all/any, sole-holder fallback, and what can be waived

**Context**
Epic `gin-workflow-approval-roles` (2026-11-10), from the process review P1 cluster "Approval roles without a single-holder deadlock". A role list in `team.approvals` meant "one of" (`team.py` `check_approval`), so `ship: [qe, be_lead]` let a lead merge without QA. `_approver_roles` drops the author's approval, so a gate whose only role holder is the author deadlocks; the brownfield starter's single `be_lead` led every area and wrote the plans.

**Decision/Solution**
- Every gate accepts a role list (one of, unchanged), or `{all: [...], any: [...]}` (schema `_POLICY`, `additionalProperties: false`, `minProperties: 1`); `plan_approved` also keeps `area_lead`. Helpers: `team.policy_parts`, `team.policy_roles`, `team._sole_holder`; `gate_roles`, `can_waive`, `_has_policy`, `validate_team`, and CODEOWNERS use them.
- Each `all` role needs a non-author approval. When the author is the only holder of an `all` role, the role is skipped with the note "<role> skipped: the author is its only holder" and `any` must still approve; with no `any`, the refusal is "<role> has no holder other than the author; add a holder or an `any` role".
- `area_lead`: when the plan author is the only holder of an area's lead role, another area's lead approval substitutes, with a note naming it.
- `check_approval`/`verify_gate` take an optional `notes` list; `team check` prints `note: ...` and adds `notes` to its JSON. `record` does not store notes.
- `gin setup doctor` appends `single_holder_notes` (roles in `all` and area leads with one holder) to the host note.
- Waivers: only process gates (`requirement_confirmed`, `plan_approved`, `orchestration_ready`) can be waived, by a member holding a role in the gate's policy, when the user decides. `ship`/`shipped` cannot be waived; an absent sole holder is handled by adding a second holder to `team.members`. Agents never waive on their own (team skill rule).
- Starter: Hoa holds `fe_lead`, the `web` area is led by `fe_lead`, `ship: {all: [qe], any: [be_lead, fe_lead]}`; needs gin-workflow 3.1 or later.

**Consequences**
- The `/discuss` design claimed `gin unblock` as the third anti-deadlock layer for every gate; review found `shipped` is non-waivable, and the spec and docs were corrected. Check `NON_WAIVABLE_GATES` before proposing a waiver path.
- The doctor `note` field is now host notes joined with single-holder notes by "; "; the CodeCommit host note itself contains "; ", so tests compare the first two segments.
- team `SKILL.md` is at 5,993 of 6,000 characters.

**References**
- `plugins/gin-workflow/src/scripts/workflow_core/{team,schemas,team_cli,team_init}.py`; tests `tests/workflow_core/test_team_gates.py` (`TestObjectPolicies`), `test_team_init.py` (`TestSingleHolderNotes`)
- Docs: `docs/guides/team.md` (Approval policies), `docs/reference/config.md`, `docs/roles.md`, `docs/starters/brownfield.md`
- `.planning/specs/2026-11-10-approval-roles-design.md`, `.planning/plans/2026-11-10-approval-roles.md`
- Beads: `gin-workflow-approval-roles`, `.1`, `.2`
- Related: [process-review](process-review.md), [team-hosts](team-hosts.md)

**Scope**
Team-mode gate approval policies and the brownfield starter's team block.
