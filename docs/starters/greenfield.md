# Greenfield Project Starter

This guide walks you through bootstrapping and developing a brand-new project from scratch using **Claude Code** and **`gin-workflow`**.

---

## 1. Prerequisites & Initialization

Ensure you have Git, Python 3, and Beads installed:

```bash
# 1. Initialize a new git repository
git init my-awesome-project
cd my-awesome-project

# 2. Initialize Beads task tracking
bd init

# 3. Install the gin-workflow plugin for Claude Code
curl -sSL https://raw.githubusercontent.com/giangdhwhtbr/gin-workflow/master/remote-install.sh | bash -s -- --platform claude
```

Verify the installation:

```bash
gin-workflow --version
```

---

## 2. One-Time Setup (`/gin-workflow:setup`)

Inside Claude Code, run setup to configure your project foundation:

```text
/gin-workflow:setup
```

The interactive setup will detect your environment and ask:
- **Project stage:** Select `greenfield`.
- **Project shape & stack:** Choose the shape (`frontend`, `backend`, `fullstack`, or `library`) and describe the technologies you intend to use (e.g., TypeScript, Python, React, FastAPI).
- **Rigor:** Select `standard` (recommended: Git worktrees for parallel work, independent review, and lint, typecheck, test, and build checks) or `strict` (always a worktree, a review ledger, and E2E/accessibility checks when configured).
- **Provider mode:** Choose `single` (baseline with Claude Code).
- **Verification commands:** Confirm your lint, typecheck, test, and build commands (can be updated later in `.agent-workflow/config.yaml`).

Commit the generated `.agent-workflow/config.yaml` to your repository:

```bash
git add .agent-workflow/config.yaml
git commit -m "chore: setup gin-workflow configuration"
```

---

## 3. Establish the Architectural Baseline

Before writing business features, establish your architectural foundations (folder structure, core dependencies, database connections, and CI/CD).

### Step 3.1: Clarify Architecture in Discuss
Use `/discuss` to define your high-level architecture:

```text
/gin-workflow:discuss Project architecture, folder structure, and tech stack foundation
```

Claude will propose 2-3 architectural approaches, evaluate tradeoffs, and write a spec to `.planning/specs/` (with the SDD layout, a change folder under `docs/changes/`, plus an Architecture Decision Record in `docs/adr/` for an architecture decision). Review and confirm the design to record `requirement-confirmed`.

### Step 3.2: Plan Foundation Tracks
Run `/plan` to decompose the foundation into testable tracks:

```text
/gin-workflow:plan project-scaffolding
```

Typical greenfield tracks include:
1. Directory structure & core configurations (`tsconfig`, linter, formatters).
2. Database schema migrations & connection pool setup.
3. Base application server with `/health` endpoint and logging.
4. CI workflow file for automated test checks.

Approve the plan to record `plan-approved`.

### Step 3.3: Orchestrate & Execute
Run `/orchestrate` and `/execute` to build the foundation test-first:

```text
/gin-workflow:orchestrate project-scaffolding
/gin-workflow:execute
```

Claude implements each track inside an isolated Git worktree, writes tests first, conducts review, and closes each track bead.

### Step 3.4: Verify & Ship Foundation
```text
/gin-workflow:verify
/gin-workflow:ship
```

Choose **merge locally** to merge the baseline foundation into `master`/`main`.

---

## 4. Feature Development Flow (Spec-Driven Development)

For greenfield projects, we strongly recommend enabling the Spec-Driven Development (SDD) layout in `.agent-workflow/config.yaml`:

```yaml
project:
  stage: greenfield
  layout: sdd
```

Every new feature moves through a clean, reproducible cycle:

```text
                       Discuss
                ┌─────────────────────┐
                │ /gin-workflow:discuss│
                │ writes change spec  │
                └──────────┬──────────┘
                           │ requirement-confirmed
                           ▼
                         Plan
                ┌─────────────────────┐
                │ /gin-workflow:plan  │
                │ breaks into tracks  │
                └──────────┬──────────┘
                           │ plan-approved
                           ▼
                      Orchestrate
                ┌─────────────────────────┐
                │/gin-workflow:orchestrate│
                │ creates beads & worktree│
                └──────────┬──────────────┘
                           │ orchestration-ready
                           ▼
                        Execute
                ┌─────────────────────┐
                │/gin-workflow:execute│ ◄──┐ (Repeat per track)
                │ test-first, review  │ ───┘
                └──────────┬──────────┘
                           │ implementation-complete
                           ▼
                        Verify
                ┌─────────────────────┐
                │/gin-workflow:verify │
                │ tests, spec check   │
                └──────────┬──────────┘
                           │ verification-passed
                           ▼
                         Ship
                ┌─────────────────────┐
                │ /gin-workflow:ship  │
                │ PR/Merge & archive  │
                └─────────────────────┘
```

1. **Discuss (`/gin-workflow:discuss <feature>`):** Creates a change folder `docs/changes/<epic>-<slug>/` holding `proposal.md`, `spec-delta.md`, and `design.md`, with explicit, traceable requirement IDs (`REQ-<MODULE>-001`).
2. **Plan (`/gin-workflow:plan <feature>`):** Maps requirements to implementation tracks and files.
3. **Orchestrate (`/gin-workflow:orchestrate <feature>`):** Sets up task beads and an isolated Git worktree.
4. **Execute (`/gin-workflow:execute`):** Builds the tracks test-first with independent review checkpoints.
5. **Verify (`/gin-workflow:verify`):** Verifies all tests, builds, and checks off every requirement line-by-line against fresh command evidence.
6. **Ship (`/gin-workflow:ship`):** Archives the change's spec delta into the living project specs (`docs/specs/<capability>/spec.md`) on the feature branch, then merges or opens a pull request.

---

## 5. Next Steps

- **Collaborating with a team?** Read the [Team Roles Guide](team-roles.md).
- **Need automated E2E tests?** Check out the [QA Add-on Guide](../guides/qa.md).
- **Want to scale to multi-agent workers?** Explore [Multi-Agent Routing](../advanced/multi-agent-routing.md).
