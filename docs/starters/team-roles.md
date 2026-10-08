# Team Roles Guide: PM, BA, Dev & Tester

This guide details how cross-functional teams with **Product Managers (PM)**, **Business Analysts (BA)**, **Developers (Dev)**, and **Testers (QA/QE)** collaborate smoothly using **Claude Code** and **`gin-workflow`** without friction, overlapping edits, or Git conflicts.

---

## 1. Separation of Concerns Matrix

In team mode, each area of the repository has a lead role, each track belongs to one area, and each gate can require approval from a specific role. The matrix below is a suggested split of responsibilities; `gin-workflow` enforces only what `team.areas` and `team.approvals` configure.

| Role | Primary Skills | File / Folder Scope | Git Branch Convention | Quality Gate Owned |
|---|---|---|---|---|
| **PM** (Product Manager) | `/roadmap`, `/progress`, `/report` | `.planning/roadmap.md` or `docs/roadmap.md` | `roadmap/<topic>` (roadmap pull request) | `roadmap` (approves the roadmap pull request) |
| **BA** (Business Analyst) | `/discuss`, `/progress`, `/tech-doc` | `docs/specs/`, `docs/changes/` | `spec/<topic>` (spec pull request) | `requirement_confirmed` |
| **Dev / Tech Lead** | `/plan`, `/orchestrate`, `/execute`, `/verify`, `/ship`, `/review` | `src/`, `services/`, `.planning/plans/` | `feat/<epic>-<area>` (isolated in worktrees) | `plan_approved` |
| **Tester / QE** | `/gin-qa:cases`, `/gin-qa:e2e`, `/verify`, `/progress` | `qa/cases/`, `qa/e2e/`, `qa/evidence/` | reviews the developer's PR | `verification_passed` |

---

## 2. The PM (Product Manager) Workflow

PMs own the long-term plan: which epics exist, in what order, and which go into the next sprint.

### Step-by-Step Activities:
1. **Build the Roadmap (`/gin-workflow:roadmap <goal>`):**
   - Claude reads the whole tech-doc set (or a product brief), asks about goals and constraints, proposes how to split the work, and writes `.planning/roadmap.md` (`docs/roadmap.md` with the SDD layout) after the PM confirms.
   - With `team.approvals.roadmap: [pm]` the roadmap is a pull request (`roadmap/<topic>`) approved by a member with a listed role who is not its author; then the epics `<prefix>-rm-<slug>` and their dependencies are created in Beads.
2. **Plan a Sprint:**
   - Label the chosen epics `sprint:<name>` (ask `/gin-workflow:roadmap Label <epic> for sprint <name>`).
3. **Review the Sprint:**
   - `/gin-workflow:progress sprint <name>` shows status per epic; `/gin-workflow:report --sprint <name>` shows usage and cost.

---

## 3. The BA (Business Analyst) Workflow

BAs own requirements, acceptance criteria, and business logic verification.

### Step-by-Step Activities:
1. **Clarify Requirements (`/gin-workflow:discuss <feature>` or `/gin-workflow:discuss <epic-id>` for a roadmap epic):**
   - BA initiates the discussion session with Claude.
   - Claude clarifies scope, constraints, and edge cases, then formats the output into a specification with unique requirement IDs (`REQ-<MODULE>-001`) in a change folder `docs/changes/<epic>-<slug>/` (`proposal.md`, `spec-delta.md`, `design.md`) with the SDD layout, or `.planning/specs/` otherwise.
2. **Review & Approve Spec:**
   - The spec is committed on a spec branch (`spec/<topic>`) and opened as a Pull Request.
   - With `team.approvals.requirement_confirmed: [ba]`, the requirement gate is recorded with the PR URL only after the PR is merged and approved by a member with the `ba` role who is not its author.
3. **Traceability:**
   - BAs can use `/progress` at any time to monitor which requirements have been planned, implemented, or shipped.

---

## 4. The Developer & Tech Lead Workflow

Developers and Tech Leads own system architecture, implementation tracks, unit testing, and code delivery.

### Step-by-Step Activities:
1. **Plan Architecture & Decomposition (`/gin-workflow:plan <feature>`):**
   - Tech Lead breaks the confirmed spec into tracks, assigning `Area:` and `Owner:` for each track.
   - Files are strictly bounded within defined areas (e.g. `Area: backend` only touches `services/backend/**`).
   - `team check-plan <plan>` must pass; with `plan_approved: area_lead`, the area lead approves the plan PR (`plan/<topic>`) and the gate is recorded with its URL after merge.
2. **Orchestrate (`/gin-workflow:orchestrate <feature>`):**
   - Creates a Beads task for each track, labelled `track:<N>,area:<area>` and assigned to its owner, with dependency links.
   - Prepares an isolated Git worktree under `.planning/worktrees/`.
3. **Execute Test-First (`/gin-workflow:execute`):**
   - Developer runs `gin-workflow team deps`, picks from `gin-workflow team ready`, and claims the track bead (`gin-workflow team claim <bead>`).
   - Work is performed test-first inside the isolated worktree on branch `feat/<epic>-<area>`.
   - Claude requests an independent code review; review findings must be addressed in the review ledger before the track closes.
4. **Ship Delivery (`/gin-workflow:ship`):**
   - Once all tracks pass verification, Tech Lead merges or opens the final Pull Request.

---

## 5. The Tester / QA Workflow

Testers own test case authoring, requirement coverage tracking, and automated E2E validation using the `gin-qa` add-on.

### Step-by-Step Activities:
1. **Generate Test Cases (`/gin-qa:cases <capability>`):**
   - Tester runs `/gin-qa:cases` to map requirements from the BA's spec directly into test cases in `qa/cases/<capability>.md`.
   - Each test case references the exact requirement and its content hash:
     ```markdown
     ### TC-CHECKOUT-001: Card payment with 3D Secure
     REQ: REQ-PAY-003@8f2d1e0a
     Type: e2e
     Priority: high
     Preconditions:
     - User has items in cart
     Steps:
     1. Proceed to checkout and select credit card
     Expected:
     - 3D Secure prompt appears
     ```
2. **Detect Drift (`gin-qa cases plan`):**
   - If the BA updates a requirement, `gin-qa cases plan` instantly flags which test cases are `stale`, `missing`, or `obsolete`.
3. **Automate E2E Scenarios (`/gin-qa:e2e <capability>`):**
   - Generates and executes Playwright tests under `qa/e2e/`.
   - Collects screenshots, ARIA snapshots, and run reports into `qa/evidence/`.
4. **Approve Verification Gate:**
   - With `team.approvals.verification_passed: [qe]`, the QE/Tester approves the latest commit of the developer's PR; a commit pushed after the approval needs a new approval.

---

## 6. Built-in Safeguards Against Conflicts

To ensure zero friction across team members:

1. **Requirement Changes Go Through a New Change** (team convention):
   - Once a plan is approved, avoid editing the in-flight spec. With the SDD layout, a requirement change becomes a new change folder whose `MODIFIED` block carries the hash of the requirement it replaces, and `gin-qa cases plan` shows which test cases went stale.
2. **Test Separation** (team convention):
   - Developers own unit and integration tests next to the code they change.
   - Testers own acceptance cases and E2E scenarios inside `qa/**`. Put each in its own area in `team.areas` so plans keep them apart.
3. **Git Worktree Isolation:**
   - Every developer works in an isolated Git worktree created by `orchestrate`. Edits on one track never contaminate another developer's workspace.
4. **Exclusive Beads Claims:**
   - In team mode, a track bead is claimed with `gin-workflow team claim <bead>`; the claim fails if someone else already holds it, so pick another.
5. **PR-Proven Gates:**
   - A gate with roles in `team.approvals` is recorded only with a PR URL that the Git host confirms is merged (or open, for `verification_passed`) and approved by a member with a listed role, never by its author.

---

## 7. Next Steps

- **Want the whole flow with example prompts per role?** See the [Brownfield Walkthrough](brownfield-walkthrough.md).
- **New project setup?** See the [Greenfield Starter](greenfield.md).
- **Modernizing an existing app?** See the [Brownfield & Modernization Starter](brownfield-modernize.md).
- **Full Team Mode Configuration:** See [Team Guide](../guides/team.md).
