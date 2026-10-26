# Developer & Tech Lead Guide: Architecture, Worktrees & TDD Execution

This guide defines the engineering workflow for **Developers** and **Tech Leads** using `gin-workflow`. It covers how to decompose confirmed specifications into bounded tracks, develop within isolated Git worktrees, execute test-first implementations, resolve code reviews via the review ledger, and ship code safely.

---

## 1. Overview: The Developer Lifecycle in `gin-workflow`

Engineering work in `gin-workflow` is test-driven, isolated, and strictly bounded:

```text
Confirmed Spec (BA)
       │
       ▼
[/plan]         ──► Tech Lead decomposes spec into tracks with Area & Owner
       │
       ▼
[/orchestrate]  ──► Creates Beads tasks & isolated Git Worktrees (.planning/worktrees/)
       │
       ▼
[/execute]      ──► Developer claims task, writes tests first (# REQ-...), implements
       │
       ▼
[/review]       ──► Independent code review recorded in .planning/reviews/<bead>/
       │
       ▼
[/ship]         ──► Runs full test suite, archives spec deltas, and merges/opens PR
```

---

## 2. Core Engineering Activities

### Activity 1: Plan Architecture & Decomposition (`/gin-workflow:plan`)

Once a spec is confirmed by the BA (`requirement-confirmed`), the Tech Lead breaks it into executable tracks.

**Command:**
```text
/gin-workflow:plan auth
```

**Key Planning Principles:**
1. **Area Scoping (`Area:`):** Each track must declare which subsystem it touches (e.g., `Area: backend`, `Area: frontend`). Edits outside the declared area are rejected.
2. **Requirement Mapping (`Requirements:`):** Every track lists the requirement IDs it implements (e.g. `Requirements: REQ-AUTH-001, REQ-AUTH-002`).
3. **Owner Assignment (`Owner:`):** Specifies the engineer or subagent responsible for the track.
4. **Plan Verification:** The plan is verified with `gin-workflow team check-plan <plan>`. With `plan_approved: area_lead`, the Area Lead approves the plan PR (`plan/<topic>`).

---

### Activity 2: Orchestrate Isolated Workspaces (`/gin-workflow:orchestrate`)

Before writing any code, the Tech Lead or Developer orchestrates the plan.

**Command:**
```text
/gin-workflow:orchestrate auth
```

**What Happens Automatically:**
- **Beads Dependency Graph:** Generates parent and child tasks in Beads (`bd list --spec auth`) with dependencies mapped between tracks.
- **Git Worktree Isolation:** Prepares an isolated Git worktree under `.planning/worktrees/` on branch `feat/<topic>-t<N>`.
  > [!TIP]
  > **Why Worktrees?** Working in an isolated worktree prevents dependency pollution, uncommitted file conflicts, and allows multiple engineers or parallel AI subagents to build and test independently.

---

### Activity 3: Test-First Execution (`/gin-workflow:execute`)

Developers claim ready tasks and implement solutions using **Test-Driven Development (TDD)**.

1. **Find Ready Work:**
   ```bash
   gin-workflow team ready
   ```
2. **Claim the Task:**
   ```bash
   gin-workflow team claim <bead-id>
   ```
3. **Execute Implementation:**
   ```text
   /gin-workflow:execute <bead-id>
   ```

**TDD Rules in `gin-workflow`:**
- Write unit/integration tests **before** writing production code.
- Tag each test with its corresponding requirement ID:
  ```python
  def test_failed_login_lockout():
      # REQ-AUTH-003: Lock out after failed logins
      ...
  ```
- Implementation must touch only files within the track's declared `Area:`.

---

### Activity 4: Addressing Code Reviews (The Review Ledger)

When execution is complete, an independent AI reviewer reviews the track and records findings in `.planning/reviews/<bead>/`.

**Review Response Protocol:**
Do not agree blindly or implement changes without technical verification. For each finding in the ledger, the developer must:
1. **Verify Technically:** Check if the finding is accurate.
2. **Respond with Action:**
   - **Fix:** Update code and tests, then re-verify.
   - **Dispute:** Explain technically why the code is correct as designed.
   - **Defer:** Log an issue or waiver if out of current scope.
3. The track closes only when all findings in the ledger are addressed.

---

### Activity 5: Safe Delivery & Shipping (`/gin-workflow:ship`)

Once all tracks for an epic pass tests and review ledgers are clear, ship the feature.

**Command:**
```text
/gin-workflow:ship
```

**Ship Steps:**
1. **Full Verification Suite:** Runs linters, unit tests, integration tests, and checks `specs trace`.
2. **Spec Archival (`specs archive`):** Merges `spec-delta.md` into the living `docs/specs/<capability>/spec.md` and moves the change folder to `docs/changes/archive/`.
3. **Integration:** Merges the feature branch or opens the final Pull Request for QE approval.

---

## 3. Developer Prompt Templates

### Prompt 1: Decomposing a Spec into Independent Tracks
> "/gin-workflow:plan auth
> Decompose this confirmed spec into 2 independent tracks:
> - Track 1: Database models, migrations, and backend OAuth API endpoints (Area: backend).
> - Track 2: Frontend login modal and OAuth redirect handlers (Area: frontend).
> Ensure Track 2 depends on Track 1."

### Prompt 2: Executing a Claimed Bead Test-First
> "/gin-workflow:execute bd-auth-t1
> Inspect the requirement `REQ-AUTH-005` linked to this track. Write failing tests first under `tests/unit/auth/`, verify that they fail as expected, and then write the minimal implementation to make them pass."

### Prompt 3: Addressing Code Review Findings
> "/gin-workflow:review
> Review the findings in `.planning/reviews/bd-auth-t1/`. Let's verify finding #1 regarding potential token leakage in logs. Fix the logging sanitizer and re-run our test baseline."

---

## 4. Engineering Quality Checklist

Before submitting code for ship:
- [ ] Code touches only files within the assigned `Area:`.
- [ ] Every new requirement has a corresponding test tagged with `# REQ-...`.
- [ ] All tests pass locally inside the isolated Git worktree.
- [ ] No uncommitted files or leftover debugging logs remain.
- [ ] All review findings in `.planning/reviews/<bead>/` are resolved.
- [ ] `gin-workflow specs trace` reports 0 missing requirement tests.
