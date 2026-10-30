# Brownfield Modernization — Presentation Script

Speaker notes for `brownfield-modernization.html` and `brownfield-modernization.pptx`. The slides carry the headline
points; the detail below is what the presenter says aloud.

## 1. Modernizing Brownfield Systems with gin-workflow & SDD

- This is an end-to-end operational guide, from legacy discovery to incremental delivery.
- Three pillars: evidence discovery, contract-first SDD, gated execution.
- Evidence discovery: automated codebase analysis replaces tribal guesswork.
- Contract-first SDD: living requirement contracts (`spec.md`) are confirmed through pull requests before code is written.
- Gated execution: Git worktree isolation, test-driven development, independent review ledgers, and automated trace audits.

## 2. Discover the Legacy System from Evidence (`/tech-doc`)

- Legacy knowledge gap:
  - Original authors are gone; business rules exist only in code.
  - Wikis, READMEs, and diagrams lag years behind production.
  - Implicit database triggers, undocumented endpoints, and tangled call chains.
- `/tech-doc` scans code trees, database schemas, and API handlers directly.
- Output goes to `docs/codebase/` (with the SDD layout) in 10 structured modules, including `03-ARCHITECTURE.md`, `05-API.md`, `07-STACK.md`, and `04-STRUCTURE.md`.
- Every architectural conclusion cites exact file paths and line ranges; nothing is speculative.
- The baseline takes hours rather than weeks and seeds the product roadmap.

## 3. Sequence by Dependency, Start in Parallel

- `/tech-doc` output reveals call graphs and data dependencies across legacy modules.
- We start with modules that have zero or minimal upstream blockers, so work never deadlocks on architecture.
- Specs are worth the investment: coding on unconfirmed specs causes severe downstream rework.
- Developers do not wait for specs. Two streams run in parallel:
  - Engineering: make the legacy app run reliably in Docker, scaffold backend and frontend repos, set up CI/CD and the reverse proxy.
  - BA: business logic, edge cases, and acceptance scenarios for the first unblocked module.
- Milestones:
  - Sprint 1: working dev environments plus a confirmed spec ready for implementation.
  - Sprint 2: first modern vertical slice shipped behind a facade; the next spec is ready.
  - Sprint 3+: continuous incremental delivery with regression protection, retiring strangled legacy paths.

## 4. Who Does What, Stage by Stage

- The swim lanes show who acts in each stage: discuss, plan, orchestrate, execute (per track), and ship; the bottom row is the gate that closes each stage.
- People lanes: Requester (BA/PM), Area lead (owns the code area), Developer (runs the stages), Ship approver (team mode, e.g. QE).
- Agent lanes: Main agent (your harness session), Worker (gin-orchestrator, optional), Reviewer (fresh session or provider).
- Automation lane: git hooks and CI, with checks set by rigor.
- discuss: the agent asks, proposes, and writes the spec; the requester confirms → `requirement_confirmed`.
- plan: the agent writes tracks with role and tier; the area lead approves → `plan_approved`.
- orchestrate: the agent creates the epic, track beads, routes, and worktree → `orchestration_ready`.
- execute: per track, tests first; a worker may implement routed tracks; the reviewer records the ledger within capped cycles; humans do human-gate tracks; pre-commit runs lint and typecheck, pre-push runs tests, build, and e2e → `implementation_complete` once every track is closed.
- ship: the developer chooses merge, PR, keep, or discard; the ship approver approves the PR; the agent checks ledgers, merges, and cleans up → `shipped`.
- Orange lines mark where the agent waits for a human.

## 5. How AI-Drafted Specs Get Verified

- Strict EARS syntax: every requirement declares its condition with `SHALL` or `MUST`.
- Every requirement needs at least one concrete GIVEN / WHEN / THEN scenario; `specs lint` fails immediately when syntax or scenarios are missing.
- Spec changes are proposed on `spec/<epic>` and submitted as a pull request.
- The `requirement-confirmed` gate requires human BA approval on GitHub or GitLab; no planning or code proceeds until the spec PR merges.
- BAs save UI screenshots to `docs/specs/<cap>/assets/`; the agent reads wireframes to extract input fields, validation rules, and error states, and links the screenshots into the spec.
- The agent proposes and structures requirements; the BA retains sole authority to approve them.

## 6. Bounded Tracks, Isolated Worktrees, Routed Models

- Each track in `plan.md` is bound to a directory, e.g. `Area: modern_api` vs `Area: legacy_core`; a plan track that crosses areas is rejected by `gin-workflow team check-plan`.
- Each track maps to target requirements, e.g. `Requirements: REQ-AUTH-001`.
- `/orchestrate` creates an isolated Git worktree under `.planning/worktrees/` for each track, so developers and parallel agents build and test without branch contention.
- Downstream tracks unlock in Beads when their upstream tracks close.
- The plan gives each track a role and a reasoning tier (`low`, `medium`, `high`); with gin-orchestrator installed, routing maps the pair to a harness and model, which removes developer trial and error.

## 7. Code Traced Back to the Spec

- Walk the chain: requirement `REQ-AUTH-003` in the living spec → `plan.md` track → failing test tagged `# REQ-AUTH-003` → `specs trace` gate.
- Developers claim tracks with `gin-workflow team claim <bead>`.
- Implementation is not accepted without prior failing unit and integration tests tagged with the exact requirement ID.
- Before completion, `gin-workflow specs trace` cross-references every requirement scenario against test sources; missing or untested scenarios block the ship gate.

## 8. Independent Review, Recorded in a Ledger

- An isolated review agent inspects the track's diff against architecture rules, test coverage, and security criteria.
- Findings are stored in the review ledger under `.planning/reviews/<bead>/` with line numbers and risk ratings.
- Review iterations are capped to prevent circular debates.
- Engineers do not passively accept AI findings; each one is verified and gets a disposition:
  - Fix: correct the code and test baseline, then re-verify.
  - Dispute: give technical reasoning that the code is correct as designed.
  - Defer: record a formal issue or a signed architectural waiver.

## 9. Evidence Over Self-Assessment

- No agent certifies its own work; every claim needs observable proof.
- Tests pass: test output with 0 failures, not an earlier run.
- Bug fixed: the original symptom's test goes red, then green, not just "code changed".
- Agent completed: the diff checked, not the agent's word.
- Requirements met: the requirement checklist checked, not just passing tests.
- Waiting for merge: a pushed branch and a real PR link, not uncommitted code.
- Handoff rule: every report states what changed, what was validated, what was waived with reasons, bead statuses, remaining risks, and next commands.

## 10. Focused QA with `gin-qa`

- Unconstrained AI tools generate hundreds of trivial tests; QA gets overwhelmed triaging noise and delivery slows.
- `qa/guidelines.md` sets policy: only critical user journeys get `Type: e2e`; edge cases use unit or integration tests.
- Test cases store the hash of their requirement (`REQ-AUTH-001@hash`).
- `gin-qa cases plan` sorts cases into `missing` (new requirements needing cases), `stale` (requirements changed since last review), and `obsolete` (deleted requirements).
- Unchanged cases are untouched; QA reviews only the deltas.

## 11. Token Economics: Three Levers

- Shift left: tokens spent during `discuss` to clarify and confirm specs give the highest return. Logic discovered missing late in a brownfield system ripples across legacy modules and burns tokens on repeated debug and re-review cycles.
- Complexity routing: under-powered models fail on complex decoupling and loop on retries; over-powered models waste budget on boilerplate.
- Local CLI offloading: `specs lint`, `specs trace`, `specs hash`, and gate checks run in the local Python CLI and return compact status instead of reading raw code. Clean stage handoffs and isolated worktrees keep conversation context small.
- Illustrative ratio (not a measured figure): roughly 1,000 tokens of upfront spec clarity can prevent 50,000+ tokens of downstream rework and retries. Replace with measured numbers from `/report` when available.

## 12. Ship Safely, Keep Specs Alive

- Pre-ship verification runs the full test suite, lint, typecheck, and `specs trace`.
- `specs archive` merges requirements from `spec-delta.md` into `docs/specs/<cap>/spec.md`.
- The change proposal folder moves to `docs/changes/archive/` with its full audit trail.
- The final integration PR requires QE approval (`team.approvals.ship: [qe]`).
- `docs/specs/` remains the single source of truth; as modern modules ship, legacy paths are disabled and cleaned up; requirements evolve with the code, so there is no documentation debt.

## 13. The Modernization Governance Blueprint

- Recap the four outcomes: verifiable specs, parallel start, code parity, focused QA.
- Specs use EARS grammar with mandatory GIVEN/WHEN/THEN scenarios, verified through BA pull requests.
- Pilot ask: a 2-week sprint on one bounded capability (e.g. Authentication or Order Intake) to establish baseline velocity and demonstrate production-grade delivery.
