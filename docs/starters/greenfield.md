# Greenfield project starter

This guide bootstraps a new project with Claude Code and `gin-workflow`, from an empty repository to the first feature.

---

## Prerequisites and initialization

Install the [dependencies](../../README.md#dependencies) first; Beads is optional.

```bash
# 1. Initialize a new git repository
git init my-awesome-project
cd my-awesome-project

# 2. Install the gin-workflow plugin for Claude Code
curl -sSL https://raw.githubusercontent.com/giangdhwhtbr/gin-workflow/master/remote-install.sh | bash -s -- --platform claude
```

Verify the installation:

```bash
gin-workflow --version
```

---

## One-time setup

Inside Claude Code, run setup:

```text
/gin-workflow:setup
```

Setup detects your environment and asks:
- Project type: confirm stage `greenfield`, the shape (`frontend`, `backend`, `fullstack`, or `library`), and the stack.
- Rigor: setup suggests `easy` (no worktree, self-check review). `standard` adds worktrees for parallel work and independent review; `strict` always uses a worktree and a review ledger.
- Stack intent: the technologies you plan to use, for example TypeScript, Python, React, or FastAPI. Setup asks this instead of verify commands, which you can add later in `.agent-workflow/config.yaml`.
- Task tracking: `markdown` (local files) or `beads`, which needs `bd`. Markdown is the default.

Everything runs in the harness you opened (`provider_mode: single`).

Commit the generated `.agent-workflow/config.yaml` to your repository:

```bash
git add .agent-workflow/config.yaml
git commit -m "chore: setup gin-workflow configuration"
```

---

## Architectural baseline

Before writing business features, set up the foundations: folder structure, core dependencies, database connections, and CI.

### Clarify the architecture in discuss
Use `/gin-workflow:discuss` to define the high-level architecture:

```text
/gin-workflow:discuss Project architecture, folder structure, and tech stack foundation
```

Claude proposes 2-3 approaches, weighs the tradeoffs, and writes a spec to `.planning/specs/` (with the SDD layout, a change folder under `docs/changes/`, plus an Architecture Decision Record in `docs/adr/` for an architecture decision). Review and confirm the design to record `requirement-confirmed`.

### Plan the foundation tracks
Run `/gin-workflow:plan` to split the foundation into testable tracks:

```text
/gin-workflow:plan project-scaffolding
```

Typical tracks:
1. Directory structure & core configurations (`tsconfig`, linter, formatters).
2. Database schema migrations & connection pool setup.
3. Base application server with `/health` endpoint and logging.
4. CI workflow file for automated test checks.

Approve the plan to record `plan-approved`.

### Orchestrate and execute
Run `/gin-workflow:orchestrate` and `/gin-workflow:execute` to build the foundation test-first:

```text
/gin-workflow:orchestrate project-scaffolding
/gin-workflow:execute
```

Claude implements each track in an isolated Git worktree, writes tests first, reviews, and closes the track.

### Ship the foundation
```text
/gin-workflow:ship
```

Choose merge locally to merge the foundation into `master` or `main`.

---

## Feature flow with spec-driven development

For greenfield projects, setup proposes the Spec-Driven Development (SDD) layout; to set or change it, edit `.agent-workflow/config.yaml`:

```yaml
project:
  stage: greenfield
artifacts:
  layout: sdd
```

Every feature moves through the same cycle:

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
                │ creates tasks & worktree│
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
                         Ship
                ┌─────────────────────┐
                │ /gin-workflow:ship  │
                │ PR/Merge & archive  │
                └─────────────────────┘
```

1. `/gin-workflow:discuss <feature>` creates a change folder `docs/changes/<epic>-<slug>/` holding `01-proposal.md`, `02-spec-delta.md`, and `03-design.md`, with traceable requirement IDs (`REQ-<MODULE>-001`).
2. `/gin-workflow:plan <feature>` maps requirements to tracks and files.
3. `/gin-workflow:orchestrate <feature>` sets up the track tasks and an isolated Git worktree.
4. `/gin-workflow:execute` builds the tracks test-first with independent review checkpoints.
5. `/gin-workflow:ship` archives the change's spec delta into the living project specs (`docs/specs/<capability>/spec.md`) on the feature branch, then merges or opens a pull request.

---

## Next steps

- Several epics: start from a product brief with `/gin-workflow:roadmap`.
- A team: [team roles](../roles.md).
- Automated end-to-end tests: the [QA add-on](../guides/qa.md).
- Worker harnesses: the [gin-orchestrator](../orchestrator/README.md) extension.
