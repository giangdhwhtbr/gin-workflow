# QA & QE Guide: Authoring Test Cases and E2E Automation with AI

This guide is a practical, step-by-step handbook for **Quality Assurance (QA)** and **Quality Engineering (QE)** professionals using `gin-workflow` and the `gin-qa` add-on. It explains how to quickly learn, adopt, and integrate AI into your daily test design, regression tracking, and end-to-end automation workflows.

---

## 1. Why QA Loves This Workflow

In traditional workflows, QA engineers often struggle with:
1. **Outdated test cases:** The BA or Dev updates requirements, but test documentation falls behind.
2. **Disconnected automation:** E2E scripts break or drift away from actual business requirements.
3. **Manual test authoring:** Writing hundreds of repetitive test steps by hand.

`gin-qa` solves this by linking test cases directly to living spec requirement IDs (`REQ-<CAP>-<NNN>`) and content hashes (`@hash`). If a requirement changes, the system flags exactly which test cases need attention.

```
Living Spec (spec.md)              QA Test Cases (qa/cases/)           E2E Automation (qa/e2e/)
[ REQ-AUTH-001@a1b2c3d4 ]  ──►  [ TC-AUTH-001: Valid Login ]  ──►  [ 01-valid-login.spec.ts ]
                                 Pinned hash: a1b2c3d4                Playwright + Screenshots
```

---

## 2. The 3 Core QA Activities

### Activity 1: Author Test Cases from Specs (`/gin-qa:cases`)

When the BA confirms a spec, QA generates and refines test cases in `qa/cases/<capability>.md`.

**Command:**
```text
/gin-qa:cases auth
```

**How It Works:**
The agent reads all `REQ-...` blocks in `docs/specs/auth/spec.md` (or `docs/changes/<epic>/spec-delta.md`) and formats them into structured test cases:

```markdown
### TC-AUTH-001: Successful login with email and password
REQ: REQ-AUTH-001@a1b2c3d4
Type: e2e
Priority: high
Preconditions:
- Registered user exists with verified email
Steps:
1. Navigate to `/login`
2. Enter valid email and password
3. Click "Sign In"
Expected:
- User is redirected to dashboard
- Session cookie is stored
```

- **`Type` options:** `e2e` (candidates for Playwright automation), `integration`, or `manual`.
- **`REQ:` tag:** Links the test to the exact requirement ID and SHA hash of the spec text.

---

### Activity 2: Detect Spec Drift (`gin-qa cases plan`)

When requirements change, QA does not need to manually compare Git diffs. Run:

```bash
gin-qa cases plan
```

The CLI scans all specs and categorizes test cases into:
- **`missing`**: New requirements that have no test cases yet.
- **`stale`**: Requirements whose text or scenarios changed since the test case was pinned.
- **`obsolete`**: Requirements that were deleted from the specification.

To update stale cases, run `/gin-qa:cases <capability>` with the prompt to refresh stale cases, then pin the new hashes:
```bash
gin-qa cases pin TC-AUTH-001
```

---

### Activity 3: Autonomous E2E Playwright Automation (`/gin-qa:e2e`)

For test cases marked with `Type: e2e`, `gin-qa` turns them into runnable Playwright specs.

**Command:**
```text
/gin-qa:e2e auth
```

**What the AI Agent Does:**
1. Launches the application locally.
2. Steps through each action against the live UI, checking ARIA snapshots (`NN.aria.yml`) and screenshots.
3. Generates readable, robust Playwright test files in `qa/e2e/auth/`.
4. Runs tests via `gin-qa e2e run` and stores step screenshots and `result.json` in `qa/evidence/`.

---

## 3. Daily QA Prompt Templates

Here are ready-to-use prompts to guide the AI agent during test authoring:

### Prompt 1: Generating Deep Test Coverage (Positive & Negative)
> "/gin-qa:cases auth
> Please analyze `docs/specs/auth/spec.md` and generate comprehensive test cases for each requirement. Include:
> - Happy paths (standard user flow)
> - Negative scenarios (invalid credentials, expired tokens, locked accounts)
> - Boundary values (empty inputs, max length passwords)
> - Security checks (SQL injection in input fields, brute force lockout)"

### Prompt 2: Reviewing Developer Implementation
> "The developer has submitted PR #45 for `AUTH-101-social-login`.
> Please inspect the diff against `docs/specs/auth/spec.md` and `qa/cases/auth.md`. Verify that all scenarios described in the test cases are covered by unit, integration, or E2E tests."

### Prompt 3: Diagnosing an E2E Failure
> "/gin-qa:e2e auth
> Run the E2E suite. If any test fails, inspect the screenshot in `qa/evidence/` and the ARIA snapshot, determine whether the failure is a test bug or a code regression, and propose the fix."

---

## 4. Team Quality Rules (`qa/guidelines.md`)

Teams can customize QA rules by editing `qa/guidelines.md` (created automatically on first run). Examples of rules you can enforce:
- Every `P1` requirement must have at least one `e2e` case.
- Test step descriptions must use standard action verbs (`Navigate`, `Enter`, `Click`, `Verify`).
- E2E tests must rely on ARIA roles (`getByRole`, `getByLabel`) rather than brittle CSS selectors.

---

## 5. QA Ship Approval Checklist

When team mode is enabled (`team.approvals.ship: [qe]`), a QE team member approves the developer's PR before it can be merged:

- [ ] All requirements in the change have corresponding test cases (`gin-qa cases plan` reports 0 missing).
- [ ] No test cases are in `stale` status.
- [ ] `gin-qa cases check` exits with code 0.
- [ ] E2E Playwright suite passes with evidence recorded in `qa/evidence/`.
- [ ] Review comment posted on the PR confirming verification evidence.

---

## 6. Customizing Test Templates & Metadata Fields

To add custom metadata fields (such as `Jira:`, `Severity:`, `Component:`) or configure repository-specific test authoring guidelines, see the [Customizing Templates Guide](customizing-templates.md).
