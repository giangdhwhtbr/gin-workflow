# Epic kinds: capability, technical, parity

Workflow: epic-kinds
Status: confirmed by the user on 2026-11-12.

## Goal and scope

Every epic carries a kind, `capability`, `technical`, or `parity`, and the kind decides what `/gin:discuss` writes, what spec lint requires, and which roles approve the spec in team mode, so technical epics stop producing BA-style documents and waiting for BA or PM review, and 1-1 legacy ports need only a confirmed capture and the deltas.

Problem (user, 2026-11-12): in team mode, purely technical epics still go through the business spec flow (user stories, use cases, activity diagrams) and need BA lead and PM approval; the BA sits on the critical path of every epic, so a slow BA slows the whole team. Checked on master `51d4ba0d`:
- No epic classifier exists: roadmap epics carry only the `roadmap` label (`plugins/gin-workflow/src/skills/roadmap/SKILL.md:30`, `templates/epic.md`).
- `team.approvals.requirement_confirmed` is one policy for the whole project (`workflow_core/team.py:16-19,451,537,545`; schema `workflow_core/schemas.py:51-58`, `additionalProperties: False`); a spec PR is mapped to a spec file, never to an epic (`team.py:430-444`).
- `gin specs lint --spec` refuses a legacy-layout spec without user stories (`workflow_core/specs.py:99-100`); `lint_change` requires an activity diagram for each capability with an `ADDED` or `MODIFIED` block (`specs.py:498-501`) and a spec delta file.
- The `team` and `sdd` skills have 5 and 18 characters of budget left (`tests/workflow_core/test_token_budget.py`, 6,000 per shared skill).

In scope:
- The kind on roadmap entries, epic beads, and specs.
- Discuss output and lint per kind, in the legacy and SDD layouts.
- `team.approvals.requirement_confirmed` per kind.
- Docs and translations.

Out of scope:
- Work split by role and assignment (later epics).
- Showing the kind in `/gin:progress` or gin-console.
- Changing an epic's kind after its spec is confirmed: that needs a new `/gin:discuss`.

Confirmed decisions (user, 2026-11-12): approvals per kind are a map inside `requirement_confirmed`; a technical epic in the SDD layout has a design and may have an empty spec delta; a parity spec cites at least one confirmed legacy capture and writes stories or REQs only for the deltas.

## Requirements

R1. Kind values and default. An epic's kind is one of `capability`, `technical`, `parity`. An epic or spec without a kind is `capability`, so existing epics, specs, and configs behave as today.

R2. Kind on the bead. The epic bead carries the label `kind:<kind>`. `/gin:roadmap` writes it when it creates an epic; for an existing epic whose roadmap kind differs, it replaces the `kind:` label, except for an epic that is `in_progress` or adopted into a milestone, which keeps its label and gets a `[gin roadmap]` comment naming the difference (the existing rule for other fields). `/gin:discuss` on an epic without a `kind:` label asks for the kind once, unless the user's request already states it, and adds the label.

R3. Kind on the roadmap entry. Each roadmap epic entry has `Kind: capability|technical|parity`; `templates/epic.md` and the roadmap template carry the line. `/gin:roadmap` proposes the kind of each epic; a `<capability> integration` epic is `technical`.

R4. Kind in the spec. A legacy-layout design spec and an SDD `01-proposal.md` carry a `Kind: <kind>` line after `Epic:` (or `Workflow:`). `gin specs lint` reports a `Kind:` value outside the three kinds. `gin record requirement-confirmed --workflow-id <epic>` refuses when the spec's `Kind:` differs from the epic bead's `kind:` label, naming both.

R5. Technical design, legacy layout. `gin specs template technical-design.md` gives `# <title>`, `Epic:`/`Workflow:`, `Kind: technical`, `Status:`, and sections `## Goal and scope`, `## Approach`, `## Risks and rollback`, `## Testing`, `## Open Technical Questions`. `gin specs lint --spec` on a spec with `Kind: technical` does not require user stories; it still reports placeholders and the open-question format.

R6. Technical change, SDD layout. A change folder whose proposal says `Kind: technical` passes `gin specs lint --change` with an empty or missing `02-spec-delta.md` and without activity diagrams or use cases; any `ADDED`, `MODIFIED`, or `REMOVED` block it does contain is checked as today (statement, scenarios, base hash, activity diagram for its capability). `specs trace` and `specs archive` of a change with no requirement blocks report nothing to trace or merge and succeed.

R7. Parity spec. A spec with `Kind: parity` has a `Parity with:` line listing one or more asset folders (`assets/<date>/` of a capability, backticked). `gin specs lint` refuses a parity spec without that line, or one whose listed folder is missing, is not `Kind: legacy`, or is not confirmed (`Confirmed: <date>`). User stories (legacy layout) or requirement blocks (SDD) are written only for the deltas; a parity spec with no deltas needs none.

R8. Approval per kind. `team.approvals.requirement_confirmed` accepts, besides today's role list or `{all, any}` policy, a map `{capability: <policy>, technical: <policy>, parity: <policy>}` with at least the `capability` key. A missing kind key uses the `capability` policy. The single-policy form applies to every kind. The schema validates the map; `team.strict` treats the map as a policy.

R9. Kind lookup for approval. `gin team check --gate requirement_confirmed <url>` and `gin record requirement-confirmed` choose the policy for the epic's kind: from the `--workflow-id` epic bead's `kind:` label when given, else from the `Kind:` line of the spec the pull request changes, else `capability`. The waiver path (`gin unblock --gate requirement_confirmed`) accepts a holder of any role in the policy chosen for that kind.

R10. Skills. The rules for each kind live in one new shared reference, `plugins/gin-workflow/src/references/epic-kinds.md`, linked from the `discuss`, `team`, and `sdd` skills in at most one short line each, so every stage chain and shared skill stays within its budget. For a technical epic, discuss asks only technical questions and writes the technical design; for a parity epic, it reads the confirmed legacy folders and asks only about the deltas.

R11. Docs. `docs/concepts/lifecycle.md` (gates and variations), `docs/guides/team.md` (approval policies with a per-kind example), `docs/reference/config.md` (`team.approvals.requirement_confirmed` map), `docs/reference/cli.md` (`specs template technical-design.md`, lint rules), `docs/roles.md`, `docs/guides/ba.md`, `docs/guides/sdd.md`, and `docs/starters/brownfield.md` (example map `capability: {all: [ba], any: [be_lead, fe_lead]}`, `technical: [be_lead, fe_lead]`, `parity: [ba]`) describe the kinds, with their `.vi.md` translations.

## User Stories

### US-1: A technical epic without BA documents or BA approval
As a tech lead in team mode, I want a technical epic to produce a technical design and need only the leads' approval, so that it does not wait for the BA or the PM.

Acceptance criteria:
- `gin specs template technical-design.md` prints the sections of R5.
- `gin specs lint --spec` on a `Kind: technical` spec with no user stories prints `ok`.
- With `requirement_confirmed: {capability: [ba], technical: [be_lead]}` and an epic labelled `kind:technical`, `gin record requirement-confirmed` accepts a spec pull request approved by a `be_lead` and not by a `ba`.
- In the SDD layout, a `Kind: technical` change with an empty spec delta and no activity diagram passes `gin specs lint --change`, and its archive succeeds.

### US-2: A parity epic starts from the confirmed capture
As a BA on a migration, I want a 1-1 port to need only the confirmed legacy capture and the deltas, so that developers start without waiting for a full spec.

Acceptance criteria:
- `gin specs lint --spec` on a `Kind: parity` spec with `Parity with:` naming a confirmed `Kind: legacy` folder and no user stories prints `ok`.
- The same spec naming an unconfirmed folder, a non-legacy folder, or a missing folder fails lint naming the folder and the reason.
- A `Kind: parity` spec without `Parity with:` fails lint.

### US-3: The kind is set once and checked
As a PM, I want the roadmap to give each epic a kind that the spec and the approval follow, so that the team does not argue about which flow applies.

Acceptance criteria:
- `/gin:roadmap` writes `Kind:` in each entry and the `kind:<kind>` label on the epics it creates.
- `gin record requirement-confirmed --workflow-id <epic>` refuses a spec whose `Kind:` differs from the epic's label, naming both.
- An epic and spec without a kind follow today's capability flow and approval.

### US-4: Existing configs keep working
As a tech lead with an existing team config, I want my single `requirement_confirmed` policy to keep applying, so that adding kinds changes nothing until I opt in.

Acceptance criteria:
- A config with `requirement_confirmed: [ba, be_lead]` validates and applies that policy to every kind.
- A config with the map form validates; a map without `capability`, or with an unknown kind key, is refused with a message naming the key.

## Errors and compatibility

- Default `capability` everywhere: no change for epics, specs, or configs without a kind.
- The map form is new configuration: a project using it needs this gin version; older gin refuses it at schema validation. Docs say so.
- `kind:` labels are new; every current reader of epic labels tolerates extra labels (milestone, team ready); gin-console reads no labels.
- A spec/bead kind mismatch is a refusal with both values named, never a silent choice.
- Skill budgets stay within limits (`tests/workflow_core/test_token_budget.py`).

## Testing

- `tests/workflow_core/test_specs.py` (and the SDD archive/trace tests): lint per kind (technical without stories, parity with and without a valid capture, invalid `Kind:`), empty technical spec delta through lint, trace, and archive.
- `tests/workflow_core/test_team*.py` / schema tests: the map form validates, defaults to `capability`, refuses a map without `capability` or with an unknown key; policy choice by bead label, by spec `Kind:`, and the default; waiver roles per kind.
- Lifecycle CLI test: `record requirement-confirmed` refuses a kind mismatch.
- Roadmap sync is skill text: check the skill wording and `templates/epic.md`; budget tests for every chain.
- `gin docs check` on changed pages; full suite `python3 -m pytest -n auto`.

## Open Technical Questions
