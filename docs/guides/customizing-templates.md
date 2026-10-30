# Customizing templates

Override the templates gin-workflow and gin-qa write from, and the rules gin-qa follows, to match your team's formats.

## How overrides work

`gin-workflow` looks templates up in this order:

```text
.agent-workflow/templates/<name>   ──► project override (used first)
               ▲
               │ (falls back to)
the plugin's templates/            ──► built-in default
```

A command that needs a template checks `.agent-workflow/templates/` at the repository root first. A file with the same name there replaces the built-in default (`template_text` in `workflow_core/specs.py`).

### Built-in templates

Print any built-in template with:

```bash
gin-workflow specs template <template-name>
```

Available templates:
- Specs, stories, and roadmap: `spec.md`, `spec-delta.md`, `proposal.md`, `design.md`, `design-spec.md`, `user-story.md`, `epic.md`, `roadmap.md`, `tests.md`, `adr.md`, `specs-README.md`
- Codebase documentation (`/gin-workflow:tech-doc`): `codebase/<FILE>.md`, for example `codebase/05-API.md`
- Team conventions: `team/pull_request_template.md`, `team/commit-msg`, `team/github-ci.yml`, `team/gitlab-ci.yml`

| Template | Used by | Override file |
|---|---|---|
| Roadmap | `/gin-workflow:roadmap` | `.agent-workflow/templates/roadmap.md` |
| Epic description | `/gin-workflow:roadmap` | `.agent-workflow/templates/epic.md` |
| User story | `/gin-workflow:discuss` | `.agent-workflow/templates/user-story.md` |
| Design spec (legacy layout) | `/gin-workflow:discuss` | `.agent-workflow/templates/design-spec.md` |
| Proposal, spec delta, design, tests (SDD layout) | `specs new`, which `/gin-workflow:discuss` runs | `.agent-workflow/templates/<file>` |
| `spec.md` | `specs archive` (a new capability) and `/gin-workflow:migrate-specs` | `.agent-workflow/templates/spec.md` |
| `specs-README.md` | `specs archive` and `specs migrate` | `.agent-workflow/templates/specs-README.md` |
| `codebase/*` | `/gin-workflow:tech-doc` | `.agent-workflow/templates/codebase/<FILE>.md` |
| `team/*` | `gin-workflow team init` | `.agent-workflow/templates/team/<file>` |

## Spec, story, and roadmap templates

To override a template, create the `.agent-workflow/templates/` folder and put your version inside it. This example overrides the spec and user story templates.

1. Create the templates directory:
   ```bash
   mkdir -p .agent-workflow/templates
   ```

2. Export the default template:
   ```bash
   gin-workflow specs template spec.md > .agent-workflow/templates/spec.md
   ```

3. Edit `.agent-workflow/templates/spec.md`. You can add sections, compliance checklists, or asset guidelines:

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

4. Customize user stories in `.agent-workflow/templates/user-story.md`:
   ```bash
   gin-workflow specs template user-story.md > .agent-workflow/templates/user-story.md
   ```
   Example format:
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

5. Verify the override by running `gin-workflow specs template spec.md`. It prints your version from `.agent-workflow/templates/spec.md`.

The `{{...}}` placeholders in `spec.md`, the SDD files, and the `team/*` files are filled by `gin-workflow` commands. The agent fills the story, roadmap, and epic templates, so placeholders you invent there stay as text for the agent to complete.

## Test case guidelines and fields

The gin-qa add-on is customized through the guidelines file (`qa/guidelines.md`) and extra metadata fields.

### The guidelines file

On first use, `/gin-qa:cases` creates `qa/guidelines.md`. The agent reads this file before drafting test cases, and its rules override the defaults.

Edit `qa/guidelines.md` to customize:
- Language: Enforce Vietnamese, English, or bilingual test steps.
- Extra fields: Declare team-specific metadata tags.
- End-to-end rules: Define sign-in mechanisms (such as `storageState`), test user fixtures, or locator strategies.

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

### Extra fields

The gin-qa parser keeps any other `Key: value` line in a test case header. The agent adds the extra fields declared in your guidelines when it writes test cases:

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

`gin-qa cases export --format json` lists every custom field (`Jira`, `Severity`, `Component`, and others) under `fields` in its JSON output.

## The end-to-end evidence fixture

`gin-qa e2e init`, which `/gin-qa:e2e` runs, copies the fixture to `qa/e2e/evidence.ts`. The file belongs to your repository, so edit it freely, but keep the shape of the `result.json` it writes: `gin-qa e2e check` and `gin-qa e2e export` read it.
