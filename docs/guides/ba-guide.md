# Business Analyst (BA) Guide: Defining Specifications with AI & Visual Assets

This guide defines the official workflow for **Business Analysts (BA)** using `gin-workflow` under the **Spec-Driven Development (SDD)** layout. It covers how BAs collaborate with the AI agent to clarify requirements, structure living specs, and automatically attach visual assets (screenshots, UI mockups, diagrams) into requirement specifications.

---

## 1. Overview: The BA Role in Spec-Driven Development (SDD)

In `gin-workflow`, requirements are treated as first-class, living artifacts tracked directly in Git:

- **Living Specs (`docs/specs/<capability>/spec.md`):** The single source of truth describing the current, active behavior of each capability in the system.
- **Change Proposals (`docs/changes/<epic>-<slug>/`):** The working area for in-flight features or modifications created during `/discuss`. Contains `proposal.md`, `spec-delta.md`, and `design.md`.
- **Requirement IDs (`REQ-<CAP>-<NNN>`):** Atomic, trackable requirements with strict acceptance criteria (EARS statements and GIVEN/WHEN/THEN scenarios) that tests and tasks link to.

---

## 2. Organizing Visual Assets (Screenshots & Mockups)

When defining user interfaces and workflows, visual evidence provides critical context for engineers and automated tests.

### Directory Convention

Store visual assets inside the capability's dedicated directory:

```text
docs/
  specs/
    auth/
      spec.md                    <-- Living specification (Single source of truth)
      assets/                    <-- Permanent visual assets for this capability
        login-form.png
        mfa-challenge.png
        oauth-providers.svg
```

### In-Flight Change Assets

If the screenshots are temporary or strictly tied to a new feature proposal being reviewed in a Pull Request, you can also store them directly in the change folder:

```text
docs/
  changes/
    AUTH-101-social-login/
      proposal.md
      spec-delta.md
      design.md
      assets/                    <-- Proposal-specific mockups
        google-login-mockup.png
```

### Asset Guidelines
- **File formats:** Use `.png`, `.jpg`, `.svg`, or `.webp`.
- **Naming:** Use kebab-case descriptive names indicating action and state (e.g. `cart-checkout-empty.png`, `user-profile-editing.png`). Avoid generic default names (e.g. `Screenshot 2026-10-26.png`).
- **Tooling Compatibility:** `gin-workflow specs lint`, `trace`, and `archive` only inspect `spec.md` and `spec-delta.md`. Asset files are safely preserved and will never cause lint or build failures.

---

## 3. The AI-Assisted Workflow (`/discuss`)

AI agents in `gin-workflow` are multimodal. When provided with visual assets, the agent reads UI components, form fields, validation states, and layout flows directly from the image.

### Step 1: Copy Assets into the Directory
Before or during requirement discussion, save your UI mockups or screenshots into:
```bash
docs/specs/<capability>/assets/
```

### Step 2: Run `/discuss` with Context
Initiate the discussion stage and explicitly point the agent to the assets:

```text
/gin-workflow:discuss auth
```

**Prompt Example:**
> "I have added wireframes for the new social login feature into `docs/specs/auth/assets/`. Please inspect `google-login-mockup.png` and `github-login-mockup.png`, analyze the UI fields and buttons, and propose the required requirements for social authentication."

### Step 3: Automated Requirement Generation & Asset Embedding
The agent executes the following steps:
1. **Multimodal Inspection:** Reads the image files using workspace tools to extract buttons, form inputs, error labels, and conditional displays.
2. **Drafts Requirements:** Generates EARS statements and GIVEN/WHEN/THEN scenarios.
3. **Embeds Markdown Links:** Inserts relative markdown image links directly under the corresponding requirement heading in `spec-delta.md` (or `spec.md`).

**Example of Generated Requirement:**

```markdown
### REQ-AUTH-005: Social Login Options
WHEN an unauthenticated user opens the login dialog, the system SHALL display OAuth buttons for Google and GitHub.

<!-- Wireframe asset reference: assets/google-login-mockup.png -->

#### Scenario: Display social login buttons
- GIVEN an unauthenticated user
- WHEN navigating to the login screen
- THEN "Continue with Google" and "Continue with GitHub" options are visible
```

### Step 4: Spec Review & Confirmation
- Run `gin-workflow specs lint --change <epic>` to verify syntax and requirement ID formatting.
- Review the generated `proposal.md` and `spec-delta.md`.
- Confirm the spec via chat (`chat` mode) or review and merge the spec Pull Request (`pr` mode).

### Step 5: Archival into Living Specs (`/ship`)
When developers complete implementation and tests, the feature is shipped via `/gin-workflow:ship`. The `specs archive` command merges the requirements and their embedded asset links into the living `docs/specs/<capability>/spec.md` permanently.

---

## 4. BA Quality Checklist

Before confirming any requirement specification:
- [ ] Each requirement has a valid ID allocated by `gin-workflow specs next-id <cap>`.
- [ ] Requirements contain at least one `SHALL` or `MUST` statement.
- [ ] Every requirement includes at least one complete `#### Scenario:` with `GIVEN`, `WHEN`, and `THEN` steps.
- [ ] Visual assets referenced in markdown exist on disk and paths are relative (e.g., `assets/screen.png`).
- [ ] `gin-workflow specs lint` exits with code 0.

---

## 5. Customizing Spec Templates

To adapt specification templates or add team-specific fields (e.g., Jira ticket IDs, compliance tags), see the [Customizing Templates Guide](customizing-templates.md).
