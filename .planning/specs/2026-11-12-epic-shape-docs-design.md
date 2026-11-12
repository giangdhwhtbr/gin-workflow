# One epic rule, owner roles, and prompts that match the starter

Epic: gin-workflow-epic-shape-docs
Status: confirmed by the user on 2026-11-12.

## Goal and scope

The workspace guide, roles page, and brownfield starter state one epic per capability with one track per repository, who owns technical epics and milestone writes, and prompts that match the workspace layout.

The process review (`.planning/reviews/2026-11-07-process-review/synthesis.md`, clusters "One epic rule for features that span repositories", "Owner roles for technical epics and milestone writes", and "Prompt templates match the workspace starter"), checked again on master `7b105cff` on 2026-11-12:
- BA-3, BE-LEAD-8, FE-LEAD-12: `docs/guides/workspace.md:138` already says "One track per repository … a track never spans two repositories", but the starter's track table (`docs/starters/brownfield.md:371-378`) has no repository column and puts tracks 3 and 4 both in `web` (`apps/web-shop`), which the guide's wording forbids while `plan/SKILL.md` allows split tracks.
- QA-5: no page says where QA work lives; the starter already gives `qa` tracks inside the capability epic.
- FE-LEAD-11: no page describes a shared package; `library` exists only as a shape (`docs/reference/config.md`).
- BA-4, BE-LEAD-20, PM-8, FE-LEAD-5: only the BA runs `/gin:discuss` (`docs/roles.md:21`); the BA's discuss prompt asks for the REST contract (`brownfield.md:312,316,334`, `docs/reference/skills.md:179`); `workspace.md` ("Contract") freezes the contract at `requirement_confirmed`; the starter's `requirement_confirmed: [ba, be_lead]` leaves the consuming area's lead out.
- PM-3: `roles.md` gives milestone writes to the PM but says nothing of the tech lead's part in roadmap order and technical epics. BE-LEAD-19 is fixed (`brownfield.md:60`).
- PM-19, BA-18, QA-16, BE-LEAD-21, FE-LEAD-21: the starter prompts match the workspace, except the diagram label `T5["Track 5 legacy cutover"]`; `docs/reference/skills.md` still shows a monorepo setup, areas all led by `be_lead`, `ship [qe, be_lead]`, a REST contract in the discuss prompt, and plan tracks in `services/api/`, `apps/web/`, and `legacy/` (`skills.md:118-191`).

In scope:
- `docs/guides/workspace.md`, `docs/roles.md`, `docs/starters/brownfield.md`, `docs/reference/skills.md`, and their `.vi.md` translations.

Out of scope:
- Behaviour changes: each owning epic documents its own.
- An `area_lead` policy for `requirement_confirmed` or an epic kind on roadmap entries (code).
- The monorepo variant paragraph of the starter, which stays as the documented alternative.

Confirmed summary (user, 2026-11-12): `gin-workflow-roadmap-areas` (merge `609cd4ee`) already put the epic rule in `capability-epics.md` and `workspace.md:138` and made the confirmed spec the contract, with no separate contract epic, leaving the starter to this epic; `gin-workflow-approval-roles` (merge `c5f1970f`) added `{all, any}` policies, the `fe_lead` role, and the starter's `ship` policy, and left FE-LEAD-5 out of its scope. On master, cluster A is fixed in the guide but not the starter, QA-5 and FE-LEAD-11 are open; in cluster B only BE-LEAD-19 is fixed; in cluster C only `docs/reference/skills.md` and one diagram label are stale.

Confirmed decisions (user, 2026-11-12): the BA runs `/gin:discuss` for a capability epic and writes each contract detail as a technical question that the tech lead decides in `/gin:plan`; the plan pull request, approved by the lead of every area it touches, approves the contract; the BA approves only the business part of the spec; an area lead runs discuss for a purely technical epic.

Comments considered: 2, latest 2026-11-11T00:01:07Z

## Requirements

R1. Tracks per repository. `workspace.md` Limits states that a capability epic has at least one track in each repository it changes and that a track never spans two repositories; several tracks in one repository stay valid. The starter's track table gains a `Repo` column (`qa`, `services/catalog-api`, `apps/web-shop`, `services/order-api`), and its text names the epic rule with a link to the workspace guide.

R2. QA work. `workspace.md` states that QA work for a capability is one or more tracks in the `shape: qa` repository inside that capability's epic, not a separate epic.

R3. Shared packages. `workspace.md` gains a short section: a shared package is a `library` entry; a change to it is a track in that repository inside the capability epic that needs it; each app that adopts the change does so in its own track, which depends on the library track; publishing and version bumps follow the team's release practice (a convention), and gin pins no versions (the existing limit).

R4. Discuss owners. `roles.md` adds `/gin:discuss` to the Tech lead row for purely technical epics (for example an integration or platform epic), and states that the BA runs discuss for a capability epic. `docs/guides/team.md` is linked for the technical-question split, not restated.

R5. Contract details as technical questions. The starter's discuss section and prompt drop the REST contract from the BA's input and say that discuss records each contract detail (path, method, fields, error codes) as `- TQ-<n>:` under `## Open Technical Questions`, which plan answers with `Decision:` lines; `brownfield.md:334` ("Write the REST contract of each endpoint the same way…") moves to the plan section as the tech lead's work.

R6. Contract approval. `workspace.md` "Contract" says: the business part of the capability's spec is frozen at `requirement_confirmed`; the contract details are frozen at `plan_approved`, when every technical question has a decision and the plan pull request is approved by the lead of each area it touches (`plan_approved: area_lead`), so the providing and the consuming area both approve it; a contract change after plan approval goes back through `/gin:discuss`.

R7. Spec approval in the starter. The starter's approvals become `requirement_confirmed: {all: [ba], any: [be_lead, fe_lead]}`. Its explanation states, per the fallback in `docs/guides/team.md` (Approval policies): when An (the only `ba`) authors a spec, the `ba` role is skipped with a note and Binh or Hoa approves; when a lead authors a technical epic's spec, An approves and the other lead approves. The sentence "An no second `ba`, so Binh approves their … spec pull requests" is replaced accordingly.

R8. Roadmap duties. `roles.md` states that the PM owns the deadline, scope, and milestone writes (`team.permissions.milestone`), and that the tech lead approves the roadmap's order and technical epics through the `roadmap` approval (`[pm, be_lead]` in the starter).

R9. Prompt templates. `docs/reference/skills.md` matches the starter: setup answers `workspace` with the starter's repositories; team-setup lists `fe_lead` for Hoa, the starter's areas (`legacy/shop-portal/**`, `services/**`, `apps/**`, `qa/**`) with `web` led by `fe_lead`, and the starter's approvals (R7 and the existing `ship` object); the discuss prompt has no REST contract; the plan prompt gives each track `Repo:` and file paths inside that repository, Track 5 in area `api` with `Repo: services/order-api`, and no track in `legacy/`. The starter's track diagram labels Track 5 "router cutover".

R10. Translations and checks. Each changed page's `.vi.md` carries the same facts; every heading keeps its English anchor; `gin docs check` passes on every changed page; every new link and anchor resolves.

## User Stories

### US-1: One rule for epics that span repositories
As a tech lead planning a capability with a service, an app, and QA work, I want the guide and the starter to show one epic with tracks per repository, so that I do not split one capability into several epics.

Acceptance criteria:
- `workspace.md` Limits states at least one track per repository changed and no track across two repositories, and allows several tracks in one repository.
- `workspace.md` states that QA work is tracks in the `qa` repository inside the capability epic.
- `workspace.md` describes a shared `library` package change as a track in the capability epic with dependent app tracks, and labels publishing as a convention.
- The starter's track table has a `Repo` column and links the epic rule.

### US-2: The contract is decided and approved by technical leads
As a BA without a technical role, I want to write requirements and leave contract details as technical questions, so that the API contract is decided and approved by the leads who build and consume it.

Acceptance criteria:
- The starter's discuss prompt has no REST contract, and its text says contract details become `- TQ-<n>:` lines decided in plan.
- `workspace.md` "Contract" says the business part freezes at `requirement_confirmed` and the contract details at `plan_approved`, approved by the lead of each area the plan touches.
- The starter shows `requirement_confirmed: {all: [ba], any: [be_lead, fe_lead]}` with an explanation that matches the fallback in `docs/guides/team.md`.
- `roles.md` lists `/gin:discuss` for the tech lead for purely technical epics.

### US-3: Clear roadmap duties
As a PM, I want the roles page to say what I own and what the tech lead approves on the roadmap, so that milestone and ordering decisions have one owner each.

Acceptance criteria:
- `roles.md` says the PM owns the deadline, scope, and milestone writes, and the tech lead approves order and technical epics through the `roadmap` approval.

### US-4: Prompts that work in the starter's workspace
As a team copying prompts from the skills reference, I want them to use the starter's workspace layout, so that no prompt creates a monorepo setup or a track in the frozen legacy repository.

Acceptance criteria:
- `docs/reference/skills.md` setup, team-setup, discuss, and plan prompts match R9.
- No prompt in `docs/reference/skills.md` or `docs/starters/brownfield.md` puts a track in `legacy/`.
- The starter's diagram labels Track 5 "router cutover".

## Errors and compatibility

- Docs only: no code, schema, or skill file changes.
- The starter's `requirement_confirmed` object form needs gin-workflow 3.1 or later, as its `ship` policy already does; the text says so once.
- `.vi.md` pages keep the English anchors of every heading, so links from other pages keep working.

## Testing

- `gin docs check` on each changed page and translation.
- `python3 -m pytest tests/workflow_core/test_docs_coverage.py tests/workflow_core/test_walkthrough_docs.py -q`, and any test that reads `docs/reference/skills.md` or the starter (`grep -rln "skills.md\|brownfield.md" tests`).
- The starter's config block validates: the `team` block from `brownfield.md` loads through the config schema (a short `python3` check or the existing walkthrough test).
- Full suite on push: `python3 -m pytest -n auto`.

## Open Technical Questions
