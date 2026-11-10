# Plan: Process review with five role personas

Spec: .planning/specs/2026-11-07-process-review-design.md
Epic: gin-workflow-process-review
Workflow: gin-workflow-process-review

## Objective

Five AI personas (PM, BA, QA, backend lead, frontend lead) each write a report on how the gin-workflow lifecycle reads from their seat on the `shop-portal` JSP to Spring Boot + React workspace scenario, and the main session merges the findings into `synthesis.md`, a prioritized list of proposed epics for a later `/gin:roadmap`. Everything lives under `.planning/reviews/2026-11-07-process-review/` on `feat/process-review`.

**Goal** (spec): find out how the gin-workflow lifecycle reads to the people who would run it on a real legacy modernization, before more features are added to it.

**Architecture**: a review kit (plan, brief, report template, five prompts) is written first; five independent persona runs read it plus the repository and each write one report; the main session synthesizes. No code; no beads beyond this plan's tracks.

**Tech Stack**: Markdown; the Claude harness native Agent tool (`general-purpose`, `opus`, effort `high`) for persona runs; `python3` standard library for the structural checks.

**Global Constraints** (spec, verbatim):
- Any change to plugins, CLI, docs, or tests. Changes found by the review become separate epics. (out of scope)
- gin-console. (out of scope)
- Running gin-workflow on a fixture repository. Personas read and reason; they do not execute stages. (out of scope)
- Everything lives under `.planning/reviews/2026-11-07-process-review/`. All files are in English.
- The five runs are independent and may run in parallel; no persona reads another persona's report.
- The synthesis does not create beads.
- `.planning/roadmap.md` is not edited by this epic.
- A report that does not follow `report-template.md` is re-run for that role, not patched by hand.
- Nothing here changes installed plugins, `.agent-workflow/`, or gin-console input; the deliverables are markdown under `.planning/reviews/` only.

## Route Rubric
- Choose the weakest model that can do the work.
- Raise the model for broad context or design judgement.
- Raise the effort for intrinsic difficulty: intricate logic, many edge cases, or long chains of steps.

| Kind of work | Model | Effort |
|---|---|---|
| Mechanical edits, documentation, boilerplate | weakest | `low` |
| Bounded implementation with a clear spec | middle | `medium` |
| Cross-module change, security, migration, concurrency | strongest | `high` |

Unclear requirements never raise the model or effort.

## Requirement Analysis
- Problem statement: the lifecycle has grown (workspace, BA plugin, QA plugin, deadline forecast, spec-ahead milestones) without a read-through from each role's seat on a realistic multi-repository modernization.
- Success criteria: spec R1–R7 and US-1..US-3 acceptance criteria; the checks in Validation pass.
- Constraints: see Global Constraints.
- Non-goals: fixing anything the review finds; running stages on a fixture; human reviewers.

## Approach Options
### Option 1: three tracks (kit, runs, synthesis)
- Summary: Track 1 writes the kit; Track 2 launches the five persona runs in parallel inside one track; Track 3 synthesizes.
- Pros: matches the spec's single session launch (US-1); one review of all five reports catches cross-report gaps; few beads.
- Cons: a weak report is re-run inside Track 2's review cycle rather than as its own bead.

### Option 2: seven tracks (kit, one track per role, synthesis)
- Summary: each persona run is its own track and bead, run in parallel.
- Pros: a reviewer can reject one role's report as its own unit.
- Cons: five beads whose whole implementation is one agent call; execute would wrap each persona in a developer subagent, a second layer around the persona prompt.

### Recommended Approach
- Selected option: Option 1.
- Rationale: the spec already provides per-role re-runs (US-1: re-running one role overwrites only that report), so per-role beads add tracking without adding control.

## Scope
- In scope: spec R1–R6 files; checks of R7 (already met: epic parent `gin-workflow-96sx`, estimate 480 minutes).
- Out of scope: see Global Constraints.

## Execution Strategy

```yaml
execution_strategy:
  mode: direct
  workers:
    mode: sequential
  rationale: Each track consumes the previous track's files (kit -> reports -> synthesis); parallelism lives inside Track 2 as five independent agent runs.
```

## Tasks

Paths below are relative to `.planning/reviews/2026-11-07-process-review/` (written `$D`) unless they start with another top-level directory.

### Track 1: Review kit (README, brief, report template, five prompts)
- **Dependencies**: none
- **Files**:
  - Create `.planning/reviews/2026-11-07-process-review/README.md`
  - Create `.planning/reviews/2026-11-07-process-review/brief.md`
  - Create `.planning/reviews/2026-11-07-process-review/report-template.md`
  - Create `.planning/reviews/2026-11-07-process-review/prompts/pm.md`, `.planning/reviews/2026-11-07-process-review/prompts/ba.md`, `.planning/reviews/2026-11-07-process-review/prompts/qa.md`, `.planning/reviews/2026-11-07-process-review/prompts/be-lead.md`, `.planning/reviews/2026-11-07-process-review/prompts/fe-lead.md`
  - Create `.planning/reviews/2026-11-07-process-review/check.py` (structural checks used by Validation and README)
- **Provider role**: `docs`
- **Model:** `sonnet`
- **Effort:** `medium`
- **Why:** documentation from a detailed spec, but the brief must state shipped behaviour accurately (workspace, deadline forecast, spec-ahead milestones) and the prompts steer five expensive runs; above the weakest route.
- **Interfaces**:
  - Stage list (consumed by prompts, template, reports, `check.py`): exactly these 14 stages, in this order, as `### <n>. <name>` headings in each report's Walkthrough: `1. Setup and workspace`, `2. Team setup`, `3. Tech-doc`, `4. Legacy capture and mockups`, `5. Roadmap and milestones`, `6. Discuss`, `7. Plan`, `8. Orchestrate and worktrees`, `9. Execute and rules`, `10. Review`, `11. Test`, `12. Ship`, `13. Quick`, `14. Progress and report`.
  - Finding ID: `<ROLE>-<n>` with ROLE in `PM`, `BA`, `QA`, `BE-LEAD`, `FE-LEAD`; n from 1.
  - Evidence cell: one or more backticked `path:line` or `path:start-end`, path relative to the repository root.
  - `python3 $D/check.py kit|reports|synthesis`, run from the repository root; prints one line per problem and exits 1 on any, else prints `ok` and exits 0.
- **Steps**:
  1. Write `report-template.md` with exactly this skeleton (R4):
     ```markdown
     # Process review report: <role>

     - Role: <role>
     - Date: <YYYY-MM-DD>
     - Model: <model and effort>
     - Files read: <every repository path read, one per line or comma-separated>

     ## Walkthrough

     ### 1. Setup and workspace
     - What I would do:
     - Unclear:
     - Missing:

     (repeat for every stage 2..14 of brief.md, same three bullets; a stage you skip keeps its heading and says "Skipped: <why>")

     ## Findings

     | ID | Stage | Severity | Evidence | Suggested change |
     |---|---|---|---|---|
     | <ROLE>-1 | <n. stage name> | blocker, major, or minor | `path:line` | <one concrete change> |

     ## Top 3 changes

     1. <finding ID>: <why first>

     ## Questions for other roles

     - <role>: <question>
     ```
     The template must list all 14 stage headings explicitly (not "repeat").
  2. Write `brief.md` (R2): sections `## Legacy system`, `## Target`, `## Repository layout`, `## Team`, `## Milestone`, `## Operating model to validate`, `## Questions`, `## Stages`. Facts to state:
     - Legacy: JSP monolith `shop-portal`, one database, server-rendered screens, frozen under `legacy/shop-portal/`.
     - Target: `services/order-api/`, `services/catalog-api/` (Spring Boot), `apps/web-shop/`, `apps/web-admin/` (React), `qa/automation/` (Playwright).
     - Layout: parent workspace repository with `docs/`, `.planning/`, `.agent-workflow/config.yaml` and its `workspace.repos` manifest; every child cloned at its manifest path and gitignored (cite `docs/guides/workspace.md`).
     - Team: six members with roles `pm`, `ba`, `be_lead`, `be_dev`, `fe_dev`, `qe` (same names as `docs/starters/brownfield.md`; cite the lines after checking them).
     - Milestone: one two-week milestone with three epics: `catalog-api contract` (contract epic), `catalog-api browse endpoints` (service, depends on the contract), `web-shop catalog pages` (app, depends on the contract); each carries `area:<name>`.
     - Operating model: tech lead owns the roadmap and milestone reviews; every roadmap epic stays in one area (one child repository); contract epics close before dependent service and UI epics; each member picks a ready epic of their area and runs `/discuss` to `/ship` on their own machine; area lead, BA and QA approve through pull requests (`docs/guides/git-flow.md`). Personas say where it breaks: epic size, cross-area coherence, review load, who writes the spec of a technical epic.
     - Questions (all personas): which directory each role opens and runs `gin` from; whether the per-track worktree of one child repository is enough for a backend engineer; how a feature spanning one service and one app is planned, executed, reviewed and shipped; whether the frozen legacy repository is reachable where tech-doc and discuss need it.
     - PM question: whether the shipped deadline tracking (roadmap `Deadline:` and `AI capacity:` lines, `gin milestone create --lanes`, the forecast line of `gin milestone list`, the `overflow`, `late`, `spec_not_ready` warnings of `gin milestone show`; `docs/reference/cli.md` `gin milestone` section) lets the team see a hard deadline next to sprint milestones.
     - PM and BA question: whether spec-ahead sequencing works (BA confirms milestone N+1 specs while developers build milestone N, `Spec ready by:`; each milestone ends with an `Integration point:`; `plugins/gin-workflow/src/skills/roadmap/SKILL.md`).
     - Stages: the 14-stage list from Interfaces, each with the skills or commands it covers (setup + `gin workspace clone/status`; team-setup; tech-doc; gin-ba capture, mockup; roadmap + `gin milestone`; discuss; plan; orchestrate + worktrees; execute + rules; review; gin-qa cases, run, e2e, tests, report; ship; quick; progress + report).
  3. Write the five prompts (R3), each with these sections in this order: `## Identity and concerns`, `## Task`, `## Mandatory reading`, `## Evidence rules`, `## Output`. Core reading list in every prompt: `docs/starters/brownfield.md`, `docs/concepts/lifecycle.md`, `docs/roles.md`, `docs/guides/team.md`, `docs/guides/workspace.md`, `docs/guides/git-flow.md`, `docs/reference/skills.md`, then the role list from spec R3 (BA adds `docs/guides/use-cases.md`). Task: read `brief.md` and walk every stage in order, saying what you would do, what is unclear, what is missing, what you would change. Evidence rules: stay in role; read the listed files before writing; cite `file:line` for every finding; say "not found" rather than assume a feature exists; a listed file that does not exist is a `minor` finding with the missing path as evidence; do not modify the repository. Output: write only `$D/reports/<role>.md` following `report-template.md`; do not read other files under `$D/reports/`.
  4. Write `check.py` (below) and `README.md` (R1): goal, scope, the five roles; a table with one row per role: prompt file, inputs (`brief.md`, `report-template.md`), agent type `general-purpose`, model `opus`, effort `high`, report path; the launch recipe (one Agent call per role in a single message, prompt = the role's prompt file content followed by "Inputs: brief.md and report-template.md under $D; write $D/reports/<role>.md"); re-running one role = the same call for that role, which overwrites only its report; definition of done (five reports pass `check.py reports`, `synthesis.md` passes `check.py synthesis`); the manual verification list from the spec Testing section with the `check.py` commands.
     ```python
     """Structural checks for the process review. Run from the repository root."""
     import pathlib, re, subprocess, sys

     D = pathlib.Path(".planning/reviews/2026-11-07-process-review")
     ROLES = ["pm", "ba", "qa", "be-lead", "fe-lead"]
     STAGES = 14
     PROMPT_SECTIONS = ["## Identity and concerns", "## Task", "## Mandatory reading", "## Evidence rules", "## Output"]
     REPORT_SECTIONS = ["## Walkthrough", "## Findings", "## Top 3 changes", "## Questions for other roles"]
     CORE = ["docs/starters/brownfield.md", "docs/concepts/lifecycle.md", "docs/roles.md", "docs/guides/team.md",
             "docs/guides/workspace.md", "docs/guides/git-flow.md", "docs/reference/skills.md"]
     ID = r"(?:PM|BA|QA|BE-LEAD|FE-LEAD)-\d+"
     problems = []

     def headings(text):
         return [line for line in text.splitlines() if line.startswith("## ")]

     def kit():
         for name in ["README.md", "brief.md", "report-template.md"]:
             if not (D / name).is_file():
                 problems.append(f"missing {name}")
         for role in ROLES:
             text = (D / "prompts" / f"{role}.md").read_text()
             if headings(text) != PROMPT_SECTIONS:
                 problems.append(f"prompts/{role}.md sections {headings(text)}")
             for path in CORE:
                 if path not in text:
                     problems.append(f"prompts/{role}.md lacks {path}")

     def tracked():
         return set(subprocess.run(["git", "ls-files"], capture_output=True, text=True, check=True).stdout.split())

     def findings(role):
         text = (D / "reports" / f"{role}.md").read_text()
         section = text.split("\n## Findings", 1)[1].split("\n## ", 1)[0]
         return re.findall(rf"^\|\s*({ID})\s*\|(.*)$", section, re.M)

     def reports():
         files = tracked()
         for role in ROLES:
             path = D / "reports" / f"{role}.md"
             if not path.is_file():
                 problems.append(f"missing reports/{role}.md")
                 continue
             text = path.read_text()
             if [h for h in headings(text) if h in REPORT_SECTIONS] != REPORT_SECTIONS:
                 problems.append(f"reports/{role}.md sections {headings(text)}")
                 continue
             walk = text.split("\n## Walkthrough", 1)[1].split("\n## ", 1)[0]
             if len(re.findall(r"^### \d+\. ", walk, re.M)) != STAGES:
                 problems.append(f"reports/{role}.md does not have {STAGES} stage sub-sections")
             rows = findings(role)
             if not rows:
                 problems.append(f"reports/{role}.md has no findings rows")
             for fid, rest in rows:
                 for ev in re.findall(r"`([^`\s]+?):\d+(?:-\d+)?`", rest):
                     if ev not in files:
                         print(f"note: {fid} evidence not tracked: {ev}")

     def synthesis():
         text = (D / "synthesis.md").read_text()
         for h in ["## Clusters", "## Conflicts", "## Dropped", "## Carry into /gin:roadmap"]:
             if h not in text:
                 problems.append(f"synthesis.md lacks {h}")
         def part(h):
             return text.split(h, 1)[1].split("\n## ", 1)[0] if h in text else ""
         accounted = part("## Clusters") + part("## Dropped")
         files = tracked()
         for role in ROLES:
             for fid, rest in findings(role):
                 count = len(re.findall(rf"(?<![\w-]){re.escape(fid)}(?![\w-])", accounted))
                 if count != 1:
                     problems.append(f"{fid} appears {count} times in Clusters and Dropped")
                 missing = [e for e in re.findall(r"`([^`\s]+?):\d+(?:-\d+)?`", rest) if e not in files]
                 if missing and not re.search(rf"(?<![\w-]){re.escape(fid)}(?![\w-]).*no evidence", part("## Dropped")):
                     problems.append(f"{fid} cites untracked {missing} but is not dropped with 'no evidence'")

     {"kit": kit, "reports": reports, "synthesis": synthesis}[sys.argv[1]]()
     print("\n".join(problems) or "ok")
     sys.exit(1 if problems else 0)
     ```
  5. Run `python3 .planning/reviews/2026-11-07-process-review/check.py kit` → expect `ok`. Run `python3 .planning/reviews/2026-11-07-process-review/check.py reports` → expect exit 1 with `missing reports/...` lines (reports not written yet).
  6. Check every repository path named in `brief.md` and the prompts exists: `grep -ohE '`(docs|plugins)/[^`:]+`' $D/brief.md $D/prompts/*.md | tr -d '`' | sort -u | xargs -I{} sh -c 'test -e {} || echo MISSING {}'` → expect no output.
  7. Commit: `docs(reviews): process review kit (gin-workflow-process-review)`.
- **Acceptance criteria**: spec R1–R4; `check.py kit` prints `ok`; no missing path in step 6; README names, per role, prompt, inputs, agent type, model, effort, report path (US-1).
- **Estimated complexity**: medium

### Track 2: Five persona runs
- **Dependencies**: Track 1
- **Files**:
  - Create `.planning/reviews/2026-11-07-process-review/reports/pm.md`, `.planning/reviews/2026-11-07-process-review/reports/ba.md`, `.planning/reviews/2026-11-07-process-review/reports/qa.md`, `.planning/reviews/2026-11-07-process-review/reports/be-lead.md`, `.planning/reviews/2026-11-07-process-review/reports/fe-lead.md`
- **Provider role**: `general`
- **Model:** `opus`
- **Effort:** `high`
- **Why:** the spec fixes the persona route (R5: strongest model, effort `high`); each persona reads 10–20 files and judges a whole lifecycle from one role.
- **Interfaces**: consumes Track 1 prompts, `brief.md`, `report-template.md`, the stage list and finding ID format; produces five reports that `check.py reports` accepts.
- **Steps**:
  1. Launch the five runs in one message, as the README recipe says: native Agent tool, `subagent_type: general-purpose`, `model: opus`, effort `high`, prompt = `prompts/<role>.md` content plus the inputs line. The persona itself writes its report; the track's implementer does not edit report content.
  2. Run `python3 .planning/reviews/2026-11-07-process-review/check.py reports` → expect `ok` (note lines about untracked evidence are allowed; synthesis drops those findings).
  3. For any role the check rejects, or whose report misses the workspace questions (be-lead, fe-lead: US-2), re-run that role only; never patch a report by hand.
  4. Commit: `docs(reviews): five persona reports (gin-workflow-process-review)`.
- **Acceptance criteria**: spec R5, US-2; `check.py reports` prints `ok`; the be-lead and fe-lead reports each answer every workspace question of `brief.md`.
- **Estimated complexity**: medium

### Track 3: Synthesis
- **Dependencies**: Track 2
- **Files**:
  - Create `.planning/reviews/2026-11-07-process-review/synthesis.md`
- **Provider role**: `general`
- **Model:** `opus`
- **Effort:** `medium`
- **Why:** merging and clustering findings across five reports needs broad judgement (strongest model); the procedure itself is spelled out, so effort stays `medium`.
- **Interfaces**: consumes the Findings tables of the five reports; produces `synthesis.md` with sections `## Clusters`, `## Conflicts`, `## Dropped`, `## Carry into /gin:roadmap` that `check.py synthesis` accepts.
- **Steps**:
  1. Write `synthesis.md` (R6): a short intro (date, reports read); `## Clusters` with one `### <proposed epic title>` per cluster, each with `Goal:` (one line), `Raised by:` (roles), `Priority:` (`P1` when it holds a blocker, `P2` a major, `P3` minor only), `Findings:` (originating IDs; duplicates collapsed into one cluster, every ID listed once); `## Conflicts` stating opposite asks between roles without resolving them (IDs may repeat here); `## Dropped` with `- <ID>: <reason>`, using the reason `no evidence` for any finding whose evidence path is not tracked; `## Carry into /gin:roadmap`, the ordered list of cluster titles to bring to the next roadmap run.
  2. Run `python3 .planning/reviews/2026-11-07-process-review/check.py synthesis` → expect `ok`.
  3. Confirm R7 without editing anything: `gin task show gin-workflow-process-review --json` shows parent `gin-workflow-96sx` and `estimated_minutes` 480; `git diff master --stat -- .planning/roadmap.md` prints nothing; `git diff master --stat` lists only paths under `.planning/reviews/2026-11-07-process-review/`, the spec and this plan.
  4. Commit: `docs(reviews): process review synthesis (gin-workflow-process-review)`.
- **Acceptance criteria**: spec R6, R7, US-3; `check.py synthesis` prints `ok`; no bead created by this track.
- **Estimated complexity**: medium

## Integration
- **Branch**: `feat/process-review`
- **Merge strategy**: sequential

## Validation
- [ ] `python3 .planning/reviews/2026-11-07-process-review/check.py kit` prints `ok`
- [ ] `python3 .planning/reviews/2026-11-07-process-review/check.py reports` prints `ok`
- [ ] `python3 .planning/reviews/2026-11-07-process-review/check.py synthesis` prints `ok`
- [ ] `git diff master --stat` touches only `.planning/reviews/2026-11-07-process-review/`, `.planning/specs/2026-11-07-process-review-design.md`, `.planning/plans/2026-11-09-process-review.md`
- [ ] No full test-suite baseline or run: the epic changes only markdown under `.planning/` and one standalone check script there.
- [ ] Manual: read one report end to end and confirm it reads from the role's seat (US-2).

## Notes
- `Model:` and `Effort:` are chosen from the main harness catalog using the route rubric.
- Omit `Effort:` when the catalog lists no efforts.
- Unclear requirements never raise the model or effort; ask the user or return to `discuss`.
- The user may override `Model:` and `Effort:` before plan approval.
- Provider roles describe responsibility rather than filename patterns.
- Deliverable merge-holds (e.g. "remain open until human-confirmed merge") apply exclusively to the Parent Bead. Individual track beads must close upon passing tests and code review to unblock downstream dependent tracks.
- Cost: Track 2 is five `opus`/`high` runs, the largest cost of the epic.
- `check.py` is a review artifact, not product code: it lives with the review and is not added to the test suite.
