# Epic shape and contract ownership in a workspace

**Context**
Epic `gin-workflow-epic-shape-docs` (2026-11-12), process review clusters "One epic rule", "Owner roles for technical epics and milestone writes", and "Prompt templates match the workspace starter". The starter's track table broke the guide's "one track per repository", only the BA ran discuss and the BA's prompt asked for the REST contract, and `docs/reference/skills.md` still showed a monorepo and `legacy/` tracks.

**Decision/Solution**
- A capability epic has at least one track in each repository it changes; one repository may hold several tracks; QA work is tracks in the `shape: qa` repository of the same epic; a shared `library` change is a track the app tracks depend on (`docs/guides/workspace.md` Limits and Shared packages; `roadmap/references/capability-epics.md` agrees).
- The BA runs discuss for a capability epic; an area lead runs it for a purely technical epic (`docs/roles.md`). In team mode, when the runner has no technical role, contract details become `- TQ-<n>:` lines; plan answers them and `plan_approved` (area leads) freezes them; otherwise `requirement_confirmed` freezes them with the spec (`workspace.md` Contract).
- The starter uses `requirement_confirmed: {all: [ba], any: [be_lead, fe_lead]}`: the BA approves the business part, a lead approves the technical part, and the sole-holder fallback covers the author. Since [epic-kinds](epic-kinds.md) this is the starter's `capability` policy; `technical` needs only `be_lead` or `fe_lead`, and `parity` needs `ba`.

**Consequences**
- No code changed: the contract approval by consuming leads comes from `plan_approved: area_lead`, not from a new `requirement_confirmed` policy.
- When the plan author is the only lead of an area, `plan_approved: area_lead` skips that lead once another area's lead approves; starter text must say so.
- review-ledger cannot move an IMPORTANT finding out of `deferral-proposed` when the human declines the deferral, and `cleanup` skips open beads; the ledger was removed with `git rm` and recreated (bug `gin-workflow-syug`). Do not propose a deferral for an IMPORTANT finding before the user decides.

**References**
- Docs: `docs/guides/workspace.md`, `docs/roles.md`, `docs/starters/brownfield.md`, `docs/reference/skills.md`, and `.vi.md` pairs; `plugins/gin-workflow/src/skills/roadmap/references/capability-epics.md`
- `.planning/specs/2026-11-12-epic-shape-docs-design.md`, `.planning/plans/2026-11-12-epic-shape-docs.md`
- Beads: `gin-workflow-epic-shape-docs`, `.1`, `.2`; bug `gin-workflow-syug`
- Related: [approval-policies](approval-policies.md), [review-ledger-cycle-limit](review-ledger-cycle-limit.md)

**Scope**
How epics, tracks, and API contracts are owned and approved in a workspace, and the starter's worked example.
