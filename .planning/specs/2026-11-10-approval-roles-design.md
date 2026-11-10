# Approval roles without a single-holder deadlock

Epic: gin-workflow-approval-roles
Status: confirmed by the user on 2026-11-10.

## Goal and scope

A gate policy can require a role, not only accept one of several; no gate deadlocks because the pull request author is the only holder of a needed role; doctor warns about such gates; and the brownfield starter gives app areas an `fe_lead` and the tech lead a second approver.

The process review (`.planning/reviews/2026-11-07-process-review/synthesis.md`, cluster "Approval roles without a single-holder deadlock", P1) found (BE-LEAD-2, BE-LEAD-11, FE-LEAD-1, FE-LEAD-13, QA-4):
- A list policy means "one of": `check_approval` passes when `held & set(policy)` is not empty (`plugins/gin-workflow/src/scripts/workflow_core/team.py:485`), so the starter's `ship: [qe, be_lead]` lets the lead merge without QA.
- `_approver_roles` drops the pull request author's approval (`team.py:354-355`). In the brownfield starter every area is led by `be_lead`, held only by the tech lead, who writes the plans (`docs/starters/brownfield.md:47-54`, `docs/roles.md:22`), so `plan_approved: area_lead` deadlocks on the tech lead's own plans, and the tech lead approves every other gate.
- The schema accepts only role lists, plus `area_lead` for `plan_approved` (`plugins/gin-workflow/src/scripts/workflow_core/schemas.py:44-53`). Nothing detects a deadlocking gate.
- No consumer outside the CLI reads the policy; gin-console does not.

In scope:
- An `{all, any}` policy form for every gate.
- A fallback when the author is the only holder of a required role or of an area's lead role.
- A doctor warning for gates that can deadlock.
- The `fe_lead` role and the starter's areas and approvals; docs and skills.

Out of scope:
- `area_lead` for the `ship` gate (FE-LEAD-13): a ship pull request carries no area, and `any: [be_lead, fe_lead]` covers the lead review.
- Consuming-area leads approving a contract spec (FE-LEAD-5), and a frontend review checklist.
- Changing the existing waiver rules.

Confirmed summary (user, 2026-11-10): the `{all, any}` form with three anti-deadlock layers: the author-only-holder fallback, a doctor warning, and the existing `gin unblock` waiver for an absent holder, which applies to `requirement_confirmed` and `plan_approved` only; for `ship`, add a holder. The author never approves their own pull request.

## Requirements

R1. Each gate in `team.approvals` (`requirement_confirmed`, `plan_approved`, `ship`, `roadmap`, and the deprecated `verification_passed`) accepts, besides today's role list, an object `{all: [roles], any: [roles]}` with at least one non-empty key. `plan_approved` still accepts `area_lead`. A role list keeps its meaning (one of the roles) and its refusal text "missing approval from one of ...". Unknown object keys are refused.

R2. `validate_team` reports every role in `all` or `any` that no member holds, as it does for role lists today.

R3. With an object policy, the gate passes when every role in `all` has an approval from a member other than the author, and, when `any` is non-empty, at least one role in `any` has such an approval. Refusals name the missing roles: "missing approval from <role>" for each `all` role, and "missing approval from one of <roles>" for `any`.

R4. When the pull request author is the only member holding a role in `all`, that role is skipped for that pull request and `any` becomes required. The check output states "<role> skipped: the author is its only holder". When `any` is empty, the gate is refused with "<role> has no holder other than the author; add a holder or an `any` role".

R5. For `plan_approved: area_lead`, when the plan author is the only member holding an area's lead role, an approval from the lead role of another area satisfies that area. The check output states "<lead> for area <name> skipped: the author is its only holder; approved by <other lead>". With no other area, the gate is refused as today.

R6. `gin setup doctor` (the team checks) warns for each gate policy role in `all`, and each area lead role, that only one member holds, naming the gate and the role.

R7. `gate_roles`, `can_waive`, and `team init` CODEOWNERS treat an object policy as the union of its `all` and `any` roles.

R8. `docs/roles.md` adds an `fe_lead` row and stops naming the tech lead as backup approver for every gate. The brownfield starter adds an `fe_lead` member, makes the app area led by `fe_lead`, sets `ship: {all: [qe], any: [be_lead, fe_lead]}`, and replaces its single-holder note. `docs/reference/config.md`, `docs/guides/team.md`, and the `team` and `team-setup` skills document the object form, the fallback, and the waiver for an absent holder (`requirement_confirmed` and `plan_approved` only; for `ship`, add a holder). Skill and stage character budgets hold.

## User Stories

### US-1: QA sign-off is enforced
As a QA engineer, I want `ship` to require my approval, so that a lead cannot merge without QA.

Acceptance criteria:
- With `ship: {all: [qe], any: [be_lead, fe_lead]}`, a pull request approved only by `be_lead` is refused with "missing approval from qe".
- Approved by `qe` and `fe_lead`, it passes.
- With `ship: [qe, be_lead]`, a `be_lead` approval alone still passes (unchanged meaning).

### US-2: No deadlock for a sole holder
As the only QA engineer, I want my own test pull request to pass with a lead's approval, so that the gate never blocks forever.

Acceptance criteria:
- The `qe` author's pull request with a `be_lead` approval passes and the output says "qe skipped: the author is its only holder".
- With `ship: {all: [qe]}` and no `any`, it is refused with the "add a holder or an `any` role" message.
- With a second `qe` member, the fallback does not apply and that member must approve.

### US-3: The tech lead's plan gets approved
As the tech lead, I want another lead to approve my plan when I am the only lead of its area, so that my plans do not deadlock.

Acceptance criteria:
- A plan with a `backend` track, authored by the only `be_lead`, passes with an `fe_lead` approval, and the output names the substitution.
- With only one area in the team, it is refused as today.

### US-4: Warn before it blocks
As a tech lead setting up a team, I want doctor to list roles held by one member, so that I add a second holder before the first deadlock.

Acceptance criteria:
- With the brownfield starter team, doctor lists `qe` for `ship`, and `be_lead` and `fe_lead` as area leads with one holder.
- A team with two `qe` members gets no warning for `qe`.

## Errors and compatibility

- Existing role-list and `area_lead` configs keep their behaviour and refusal texts; existing tests stay green.
- A config using the object form is refused by older gin-workflow versions (schema), so the starter and docs state the minimum version.
- No Beads metadata changes. `team check --format json` gains an additive `notes` key (the reviewer note from Track 1); gin-console is unaffected.

## Testing

- `tests/workflow_core/test_team_gates.py`: object policy pass and refusal; `any` required; R4 fallback with and without `any`; second holder disables the fallback; R5 area-lead substitution; existing list policies unchanged.
- `tests/workflow_core/test_team_init.py`: CODEOWNERS with an object `ship` policy; doctor warnings for single holders.
- Schema tests for the object form and unknown keys.
- `tests/workflow_core/test_token_budget.py` for the skill budgets; `gin docs check` on changed docs.

## Open Technical Questions

## Assumptions

- "Holder" counts members in `team.members` with the role; a member listed but inactive still counts.
- The fallback is evaluated per pull request from its author login, as `_approver_roles` already identifies the author.
