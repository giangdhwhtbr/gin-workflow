# Team Roles Guide: BA, Dev & Tester

This guide details how cross-functional teams with **Business Analysts (BA)**, **Developers (Dev)**, and **Testers (QA/QE)** collaborate smoothly using **Claude Code** and **`gin-workflow`** without friction, overlapping edits, or Git conflicts.

---

## 1. Separation of Concerns Matrix

`gin-workflow` enforces the principle of **Single State Ownership**: every file, task, and quality gate has exactly one owning role.

| Role | Primary Skills | File / Folder Scope | Git Branch Convention | Quality Gate Owned |
|---|---|---|---|---|
| **BA** (Business Analyst) | `/discuss`, `/gin-sdd`, `/progress`, `/tech-doc` | `docs/specs/`, `docs/changes/` | `spec/<feature>` or `change/<feature>` | `requirement_confirmed` |
| **Dev / Tech Lead** | `/plan`, `/orchestrate`, `/execute`, `/verify`, `/ship`, `/review` | `src/`, `services/`, `.planning/plans/` | `feat/<epic>-<area>` (isolated in worktrees) | `plan_approved` |
| **Tester / QE** | `/gin-qa:cases`, `/gin-qa:e2e`, `/verify`, `/progress` | `qa/cases/`, `qa/e2e/`, `qa/evidence/` | `qa/<feature>` or review on dev PR | `verification_passed` |

---

## 2. The BA (Business Analyst) Workflow

BAs own requirements, acceptance criteria, and business logic verification.

### Step-by-Step Activities:
1. **Clarify Requirements (`/gin-workflow:discuss <feature>`):**
   - BA initiates the discussion session with Claude.
   - Claude clarifies scope, constraints, and edge cases, then formats the output into a specification with unique requirement IDs (`REQ-<MODULE>-001`) under `docs/changes/<epic>/spec.md` (or `docs/specs/`).
2. **Review & Approve Spec:**
   - BA opens a Pull Request for the spec branch (`spec/<feature>`).
   - With `team.approvals.requirement_confirmed: [ba]`, the requirement gate is recorded only when the BA approves and merges the spec PR.
3. **Traceability:**
   - BAs can use `/progress` at any time to monitor which requirements have been planned, implemented, or shipped.

---

## 3. The Developer & Tech Lead Workflow

Developers and Tech Leads own system architecture, implementation tracks, unit testing, and code delivery.

### Step-by-Step Activities:
1. **Plan Architecture & Decomposition (`/gin-workflow:plan <feature>`):**
   - Tech Lead breaks the confirmed spec into tracks, assigning `Area:` and `Owner:` for each track.
   - Files are strictly bounded within defined areas (e.g. `Area: backend` only touches `services/backend/**`).
   - The Area Lead approves the plan PR to record `plan_approved`.
2. **Orchestrate (`/gin-workflow:orchestrate <feature>`):**
   - Creates Beads task units for each track with dependency links (`team deps`).
   - Automatically prepares an isolated Git worktree under `.agent-workflow/worktrees/`.
3. **Execute Test-First (`/gin-workflow:execute`):**
   - Developer claims the track bead (`team claim <bead>`).
   - Work is performed test-first inside the isolated worktree.
   - Claude requests an independent code review; review findings must be addressed in the review ledger before the track closes.
4. **Ship Delivery (`/gin-workflow:ship`):**
   - Once all tracks pass verification, Tech Lead merges or opens the final Pull Request.

---

## 4. The Tester / QA Workflow

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
   - With `team.approvals.verification_passed: [qe]`, the QE/Tester reviews the developer's PR and attached test evidence before approving the gate.

---

## 5. Built-in Safeguards Against Conflicts

To ensure zero friction across team members:

1. **Spec Freeze During Execution:**
   - Once a plan is approved, the spec is frozen. If the BA needs to change a requirement, submit a new change proposal rather than modifying an in-flight spec.
2. **Strict Test Separation:**
   - Developers own unit and integration tests located alongside code in `src/**/__tests__/`.
   - Testers own acceptance cases and E2E scenarios inside `qa/**`. Neither role edits the other's test files.
3. **Git Worktree Isolation:**
   - Every developer works in an isolated Git worktree created by `orchestrate`. Edits on one track never contaminate another developer's workspace.
4. **Exclusive Beads Claims:**
   - In shared team mode, task beads are locked via `team claim <bead>`. No two team members or agents can execute the same bead concurrently.
5. **PR-Proven Gates:**
   - Approvals are cryptographically proven through Git host Pull Request reviews, preventing accidental or unauthorized gate progression.

---

## 6. Next Steps

- **New project setup?** See the [Greenfield Starter](greenfield.md).
- **Modernizing an existing app?** See the [Brownfield & Modernization Starter](brownfield-modernize.md).
- **Full Team Mode Configuration:** See [Team Guide](../guides/team.md).
