# Docs refresh: one coherent documentation pass after the BA flow and the rename

Epic: gin-workflow-docs-refresh
Workflow: gin-workflow-docs-refresh
Status: confirmed by the user on 2026-11-08.

## Goal and scope

After the BA-flow epics, the rename, the deadline forecast, and the roadmap pipeline shipped, the docs describe the shipped behaviour as one whole: a BA learns the job from one page, the starters walk the roadmap and milestone process in its real order with realistic prompts, and the reference and concept pages match the CLI, skills, and config.

Confirmed understanding (2026-11-08):

- All six dependencies are closed (`gin-workflow-spec-iterations`, `gin-workflow-ycg8`, `gin-workflow-ba-plugin`, `gin-workflow-bel0`, `gin-workflow-explain`, `gin-workflow-rename-gin`), and so are `gin-workflow-57fw` (deadline and forecast) and `gin-workflow-roadmap-pipeline` (way of working, spec-ahead, integration point), which the epic notes reference.
- The rename sweep is already done in the docs: no `gin-workflow:` skill prefix and no `gin-knowledge` remain. `docs/reference/cli.md` documents every command group and the new subcommands (`specs assets add|confirm`, `specs export`, `specs explain`, `milestone create|update --lanes`, `milestone estimate`); `docs/reference/skills.md` lists every skill by its plain name. The remaining work is restructuring and rewriting, plus an accuracy pass.
- `docs/roles.md` stays the overview (ownership table and reading lists) and links to the new BA page; task-ordered pages for the PM, tech lead, developer, and tester are a later epic (user decision 2026-11-08, option A).
- Delivery is split by page group, and each track writes the English page and its `.vi.md` pair together (user decision 2026-11-08, approach 1).
- Every Vietnamese text is written with the `vietnamese-language-skill` plugin (its `vietnamese-tech-writing` skill) (user requirement 2026-11-08).
- Scope addition (user, 2026-11-08, during plan review): a new page `docs/guides/git-flow.md` (`.vi.md`), the team's git agreement for team mode: branches, commits, creating and reviewing pull requests. It is written formally because a team adopts it as its agreement, and for members who are not technical (BA, tester). The agreement is host- and CLI-neutral; host procedures cover GitHub, GitLab, and AWS CodeCommit; AI support is an appendix.
- Team mode verifies pull requests on GitHub and GitLab only (`plugins/gin-workflow/src/scripts/workflow_core/team_host.py:13`). CodeCommit support is the separate epic `gin-workflow-uj2o` (not urgent); the page states the limitation.

Comments considered: 0. The epic description and its notes (latest 2026-11-08) are the input.

In scope: `docs/guides/ba.md`, `docs/roles.md`, `docs/starters/brownfield.md`, `docs/starters/greenfield.md`, `README.md`, `docs/guides/sdd.md`, `docs/reference/cli.md`, `docs/reference/skills.md`, `docs/reference/config.md`, `docs/concepts/architecture.md`, `docs/concepts/lifecycle.md`, the existing `.vi.md` pairs of these pages, the new `docs/guides/git-flow.md` and `git-flow.vi.md`, links to it from `docs/guides/team.md` and `docs/roles.md` (and their `.vi.md` pairs), the nav in `mkdocs.yml`, and the documentation table in `README.md`.

Out of scope:
- New behaviour; changes to skills, templates, or the CLI. A mismatch between docs and code becomes a bug bead on the epic that owns the code, not a fix here.
- New `.vi.md` pairs for pages that have none (`cli.md`, `config.md`, `troubleshooting.md`, `concepts/*`, `orchestrator/*`, `contributing.md`).
- Task-ordered role pages for roles other than the BA.
- The `gin-workflow` lines in `docs/reference/troubleshooting.md`: they describe the upgrade to 3.0 on purpose.
- CodeCommit support in team mode (`gin-workflow-uj2o`).

## Requirements

### R1. BA guide as one end-to-end page (track T1)

`docs/guides/ba.md` and `docs/guides/ba.vi.md` are rewritten as one page ordered by the BA's work:

1. **Role summary**: the skills the BA runs (`/gin-ba:capture`, `/gin-ba:mockup`, `/gin:discuss`, `/gin:explain`, `/gin:progress`), the files the BA owns, the branch (`spec/<epic>-<slug>` with the SDD layout), and the gate the BA's spec goes through (`requirement_confirmed`, approved by someone else in team mode).
2. **Steps in order**, each saying what the BA does and which files result: install `gin-ba` (one-time) → dated asset folder (`gin specs assets add`) → `/gin-ba:capture` for legacy behaviour → `/gin-ba:mockup` → the BA confirms (`Confirmed: <date>`, `gin specs assets confirm`) → `/gin:discuss` (capabilities-affected table, spec delta, diagrams, `Source:` lines, `gin specs lint`) → spec pull request and the `requirement_confirmed` gate → `gin specs export` (SRS) and `/gin:explain`.
3. **Conventions in one place**: a requirement change after plan approval goes in a new change folder with a `MODIFIED` block; capture legacy behaviour and the REST contract first; common mistakes (creating a second epic by hand, stories without acceptance criteria, missing legacy edge cases).
4. **Reading list**.

The page links to `sdd.md` and `team.md` for mechanics instead of repeating them. It describes the SDD layout; one sentence says the legacy layout has no dated asset folders. The existing mermaid flow and the `Source:` example are kept, updated if needed. The nav entry in `mkdocs.yml` changes from `BA add-on` to `Business analyst` (and its Vietnamese nav translation). `docs/roles.md` and `roles.vi.md` link the BA row and the BA reading list to the new page.

### R2. Starters: roadmap and milestone process in order (track T2)

`docs/starters/brownfield.md` and `brownfield.vi.md` describe the roadmap process in this order, replacing the current `Capacity: ... Sizes: ...` milestone prompt:

1. `/gin:roadmap` for the whole project writes `Deadline:` and `AI capacity:` in `## Constraints`, a `## Way of working` section, and an `Estimate:` per epic (stored in Beads via `gin milestone estimate`); its report compares the forecast with the deadline.
2. `gin milestone create [--lanes N]`, then `/gin:roadmap --milestone <id>` picks ready epics into the sprint and writes `Spec ready by:` and `Integration point:`; a sprint's lanes may differ from the project capacity.
3. `gin milestone list` prints the forecast line (finish against deadline) over every open epic, and `gin milestone show` warns `spec_not_ready`; repeat per sprint.

### R3. Starters: realistic prompts per stage (track T2)

In `docs/starters/brownfield.md`, `greenfield.md`, and their `.vi.md` pairs, every stage that shows a prompt gets a realistic multi-line prompt for the page's scenario, carrying what the skill cannot infer from code (goals, constraints, sequencing intent, exclusions). The `Put in the prompt:` line stays as the checklist.

- The roadmap prompt carries business input only: goal, deadline, fixed constraints, non-goals, cutover. No `Team:` line (the skill reads roles from `team.members`) and no sequencing bullets (the skill proposes the way of working). For the shop-portal scenario: `Goal: replace the catalog, cart and checkout JSP flows with the Spring Boot REST API and the React SPA. Deadline: <date>. The Oracle schema stays; no downtime; each module cuts over behind the facade. Non-goals: reporting screens.`
- Every command and flag in a prompt exists in the current `--help` output.

### R4. Accuracy pass (track T3)

`README.md`, `docs/guides/sdd.md`, `docs/reference/cli.md`, `docs/reference/skills.md`, `docs/reference/config.md`, `docs/concepts/architecture.md`, `docs/concepts/lifecycle.md`, and the existing `.vi.md` pairs are checked against the shipped behaviour with `/tech-doc`-grade evidence: `gin <group> --help` at flag level, the skill sources under `plugins/*/src/skills/`, and the config schema. Only mismatches are fixed. The BA stages and the `gin-ba` plugin appear where the flow is described (architecture and lifecycle). The track records the mismatches found as a table with `file:line` evidence in its bead notes; a mismatch that is a code bug becomes a bug bead on the owning epic.

### R5. Vietnamese text

Every `.vi.md` change is written with the `vietnamese-tech-writing` skill of the `vietnamese-language-skill` plugin: the impersonal technical register, English kept for code, identifiers, commands, and established terms. A `.vi.md` page keeps the heading structure of its English pair.

### R7. Team git agreement (track T5)

New `docs/guides/git-flow.md` and `git-flow.vi.md`, titled `Team git agreement`, written as a formal agreement (SHALL for obligations), for readers who are not technical. Sections, in order:

1. **Purpose and scope**: the agreement binds every member of a project with team mode on; it complements [team mode](team.md), which holds the mechanics.
2. **Terms**: branch, base branch, commit, pull request (merge request on GitLab), review, approve, request changes, merge, conflict; one plain sentence each.
3. **Branches**: the base branch is protected and no member commits to it; one branch per piece of work, named by kind: `roadmap/<topic>`, `spec/<topic>` (`spec/<epic>-<slug>` with the SDD layout), `plan/<topic>`, `feat/<topic>-t<N>`, `chore/<topic>`.
4. **Commits**: messages follow the team's convention (`team.commit_convention`), checked by the commit-msg hook (`gin team hooks`).
5. **Pull requests**: a table artifact → branch → approving role → gate, from `team.approvals` (`roadmap`, `requirement_confirmed`, `plan_approved`, `ship`); what a pull request carries (the template fields, including `Plan:` and `Tracks:`, and a link to the bead or spec).
6. **Review**: who reviews what; a checklist per role (BA reviews a spec: stories with acceptance criteria, `Source:` lines, legacy edge cases; tester reviews a developer's pull request: acceptance criteria met, test evidence present; tech lead reviews a plan); how to approve and how to request changes; a reviewer responds within one working day (a recommended default the team may change).
7. **Approval and merge rules**: no member approves their own pull request; an approval counts only on the latest commit, so a push after approval needs a new approval; a pull request merges only with the required approvals and passing CI; the author merges and deletes the branch.
8. **Conflicts and changes after approval**: the author updates the branch from the base and asks for review again; a requirement change after plan approval goes in a new change folder.
9. **Host procedures**: GitHub and GitLab, each with the web steps (create, review, approve, merge) and the equivalent `gh` / `glab` commands; AWS CodeCommit with the console steps (approval rule template, approve, merge) and the limitation that gin cannot verify a CodeCommit pull request, so gates with roles cannot be recorded from it yet.
10. **Appendix: AI support**: sample prompts that ask the agent to commit, push, and open a pull request, summarise a pull request to review, or address review comments.

The page is in the `mkdocs.yml` nav (next to Team mode) and the `README.md` documentation table; `team.md` and `roles.md` (and their `.vi.md` pairs) link to it.

### R6. Final checks (track T4)

- `gin docs check` passes on every page changed by the epic.
- `mkdocs build --strict` passes, run from a temporary virtualenv with the plugins `mkdocs.yml` needs.
- `gin setup refresh` leaves the `AGENTS.md` links current; any change it makes is committed.

## User Stories

### US-1: Learn the BA job from one page
As a BA, I want one page that walks my work in order, so that I do not have to piece it together from five pages.

Acceptance criteria:
- `docs/guides/ba.md` has the four parts of R1 in that order, and each step names the command or skill and the files it produces.
- The page links to `sdd.md` and `team.md` for mechanics and repeats none of their sections.
- `roles.md` and the nav lead to the page under the name `Business analyst`.

### US-2: Follow the roadmap process as it ships
As a PM, I want the brownfield starter to walk deadline, estimates, lanes, milestone selection, and the forecast in order, so that I run the process without reading the CLI reference first.

Acceptance criteria:
- The brownfield roadmap and milestone sections follow the three steps of R2 and no longer show the `Capacity: ... Sizes: ...` prompt.
- Each command shown exists in `gin milestone --help` or `gin --help`.

### US-3: Copy a prompt that works
As a member starting a stage, I want a realistic prompt for my scenario, so that I learn what the skill needs from me.

Acceptance criteria:
- Every stage prompt in both starters is multi-line and carries the inputs listed in its `Put in the prompt:` line.
- The roadmap prompt has no `Team:` line and no sequencing bullets.

### US-4: Trust the reference pages
As any reader, I want the reference and concept pages to match the shipped CLI, skills, and config, so that a command I copy works.

Acceptance criteria:
- The T3 bead notes hold the mismatch table with `file:line` evidence, and every row is fixed or linked to a bug bead.
- Architecture and lifecycle show the BA stages and the `gin-ba` plugin where the flow is described.

### US-5: Read natural Vietnamese
As a Vietnamese reader, I want each `.vi.md` page to read as native technical Vietnamese with the same structure as the English page, so that both languages say the same thing.

Acceptance criteria:
- Every changed `.vi.md` was written with `vietnamese-tech-writing`.
- Each changed `.vi.md` has the same heading count and order as its English pair.

### US-6: Follow one git agreement as a non-technical member
As a BA or tester, I want one formal page that says how the team branches, opens, reviews, approves, and merges pull requests, step by step on our host, so that I follow the team's agreement without knowing git.

Acceptance criteria:
- `docs/guides/git-flow.md` has the ten sections of R7 in that order, and every term it uses is defined in its Terms section.
- Each host section gives the web steps for create, review, approve, and merge; GitHub and GitLab also give the CLI commands.
- The CodeCommit section states that gin cannot verify a CodeCommit pull request yet.
- The page is reachable from the nav, `README.md`, `team.md`, and `roles.md`.

## Errors and compatibility

- Per-epic docs already on `master` are kept unless they are wrong; the rewrite builds on them instead of reverting them.
- Anchors other pages link to (for example `brownfield.md#discuss-an-epic`, `sdd.md#diagrams`, `team.md#join-it-member`) keep working; `mkdocs build --strict` catches a broken one.
- The nav rename keeps the file path `guides/ba.md`, so external links stay valid.

## Testing

- `gin docs check <changed pages>` and `mkdocs build --strict` (R6).
- Heading-count parity between each changed page and its `.vi.md` pair.
- For R3, each command in a prompt checked against `--help`.
- Docs-only change: no full test-suite baseline is needed.

## Open Technical Questions
