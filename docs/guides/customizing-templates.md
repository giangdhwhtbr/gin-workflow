# Customizing Templates Guide: BA Specs & QA Test Cases

This guide explains how to customize and override the built-in templates used by `gin-workflow` and `gin-qa`. By leveraging the template override system, teams can tailor BA specification formats, add custom metadata (such as Jira ticket IDs, severity levels, or component tags), and adapt test case conventions to match their organization's standards.

---

## 1. How Template Overrides Work

`gin-workflow` uses a deterministic hierarchy when looking up templates:

```text
.agent-workflow/templates/<name>   ──► Project Override (Takes highest precedence)
               ▲
               │ (falls back to)
plugins/gin-workflow/src/templates/ ──► Built-in Plugin Defaults
```

Whenever a command needs a template, it checks `.agent-workflow/templates/` at your repository root first. If a file with the same name exists there, it is used instead of the built-in default.

### Inspecting Built-in Templates
You can inspect the exact contents of any built-in template using the CLI:

```bash
gin-workflow specs template <template-name>
```

Available templates:
- **BA Specs & SDD:** `spec.md`, `spec-delta.md`, `proposal.md`, `design.md`, `user-story.md`, `tests.md`, `adr.md`, `specs-README.md`
- **Team Conventions:** `team/pull_request_template.md`, `team/commit-msg`, `team/github-ci.yml`, `team/gitlab-ci.yml`

---

## 2. Customizing BA Specification Templates

To override a template for Business Analysts, create the `.agent-workflow/templates/` folder and place your customized template inside it.

### Step-by-Step Walkthrough

1. **Create the templates directory:**
   ```bash
   mkdir -p .agent-workflow/templates
   ```

2. **Export the default template:**
   ```bash
   gin-workflow specs template spec.md > .agent-workflow/templates/spec.md
   ```

3. **Customize the template:**
   Edit `.agent-workflow/templates/spec.md`. You can add custom sections, compliance checklists, or asset guidelines:

   ```markdown
   # {{capability}}

   ## Purpose
   [Describe the business purpose and capability goals]

   ## Compliance & Security
   - GDPR / Data Privacy Level: [Standard | Sensitive]
   - Audit Logging Required: [Yes | No]

   ## Visual Assets & UI References
   Screenshots and wireframes are stored in `assets/`:
   <!-- Add diagrams or wireframe links here -->

   ## Requirements
   <!-- Living requirements will be appended or managed here -->
   ```

4. **Customize User Stories (`user-story.md`):**
   ```bash
   gin-workflow specs template user-story.md > .agent-workflow/templates/user-story.md
   ```
   Example customized format:
   ```markdown
   ### User Story: {{title}}
   AS A {{role}}
   I WANT TO {{action}}
   SO THAT {{benefit}}

   **Jira Ticket:** {{jira_id}}
   **Business Value:** [High | Medium | Low]

   #### Acceptance Criteria
   - [ ] Criteria 1
   ```

5. **Verify the override:**
   Run `gin-workflow specs template spec.md` — it will immediately output your customized version from `.agent-workflow/templates/spec.md`.

---

## 3. Customizing QA Test Case Templates & Guidelines

The `gin-qa` add-on provides two mechanisms for customization: **Guidelines** (`qa/guidelines.md`) and **Custom Metadata Fields**.

### Mechanism A: The Rulebook (`qa/guidelines.md`)
On first use, `/gin-qa:cases` creates `qa/guidelines.md`. The AI Agent reads this file before drafting test cases, and its rules override default behaviors.

Edit `qa/guidelines.md` to customize:
- **Language:** Enforce Vietnamese, English, or bilingual test steps.
- **Extra Fields:** Declare team-specific metadata tags.
- **E2E Rules:** Define sign-in mechanisms (e.g. `storageState`), test user fixtures, or locator strategies.

Example `qa/guidelines.md`:
```markdown
# Test case guidelines

Rules for writing test cases in this repository:
- Language: English
- One user action per step.
- Type: e2e for browser flows, integration for API/service tests, manual otherwise.
- Priority: high | medium | low.

## Extra Fields
- Jira: JIRA-NNNN ticket reference
- Severity: Blocker | Critical | Major | Minor
- Component: Frontend | Backend | PaymentGateway
- Automated: Yes | No

## E2E Rules (`/gin-qa:e2e`)
- Playwright: @playwright/test 1.49 or later.
- Authentication: Reuse authentication state from `playwright/.auth/user.json`.
- Locators: Always prefer `page.getByRole(...)` or `page.getByLabel(...)`.
```

### Mechanism B: Custom Metadata Fields in Test Cases
The `gin-qa` parser dynamically preserves any arbitrary `Key: Value` line in test case headers. When the AI agent generates test cases, it will include the extra fields declared in your guidelines:

```markdown
### TC-AUTH-005: Lockout after 5 failed login attempts
REQ: REQ-AUTH-003@8f2d1e0a
Type: e2e
Priority: high
Jira: PROJ-1024
Severity: Critical
Component: Authentication
Automated: Yes

Preconditions:
- User account `test@example.com` exists and is active.

Steps:
1. Navigate to `/login`
2. Submit invalid password 5 consecutive times

Expected:
- Account is locked for 15 minutes
- Notification email is sent to `test@example.com`
```

When running `gin-qa cases export --format json`, all custom fields (`Jira`, `Severity`, `Component`, etc.) are preserved in the JSON output, allowing direct integration into test management tools (e.g. TestRail, Xray, Allure).

---

## 4. Customizing E2E Test Fixtures (`evidence.ts`)

When running `/gin-qa:e2e`, the agent initializes the fixture file:
```text
qa/e2e/evidence.ts
```

This file is created once and is yours to edit. You can customize:
- Global setup and teardown logic.
- Automated API seeding before running UI steps.
- Custom screenshot dimensions or masking of sensitive fields.
- Additional browser recording configurations.

---

## 5. Summary Cheat Sheet

| Artifact | Default Location | How to Customize | Effect |
|---|---|---|---|
| **Living Spec Template** | Built-in | Copy to `.agent-workflow/templates/spec.md` | New specs created by `/discuss` or `specs archive` adopt this layout. |
| **User Story Template** | Built-in | Copy to `.agent-workflow/templates/user-story.md` | Changes in `/discuss` use your story & ticket fields. |
| **Change Proposal / Delta** | Built-in | Copy to `.agent-workflow/templates/proposal.md` or `spec-delta.md` | Tailors the proposal structure in `docs/changes/`. |
| **QA Guidelines** | `qa/guidelines.md` | Edit `qa/guidelines.md` directly | Controls language, extra test fields, priority rules, and locator policies. |
| **QA Extra Fields** | Dynamic | Define in `qa/guidelines.md` | Added to test cases and exported to JSON without breaking CLI checks. |
| **Playwright Evidence Fixture** | Built-in template | Edit `qa/e2e/evidence.ts` directly | Customizes how E2E tests run, record ARIA snapshots, and capture screenshots. |
