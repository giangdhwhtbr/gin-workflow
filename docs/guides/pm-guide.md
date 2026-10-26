# Product Manager (PM) Guide: Roadmaps, Sprint Planning & AI Governance

This guide defines the practical workflow for **Product Managers (PM)** using `gin-workflow`. It covers how PMs collaborate with the AI agent to turn product goals into durable roadmaps, manage sprints, track delivery progress, and govern AI resource costs and quality metrics.

---

## 1. The PM's Role in `gin-workflow`

In `gin-workflow`, the PM owns the high-level roadmap and release strategy:

- **Strategic Roadmaps (`docs/roadmap.md`):** High-level breakdown of goals into sequenced, dependent epics.
- **Sprint Management:** Grouping epics into delivery cycles using sprint labels (`sprint:<name>`).
- **AI Cost & Quality Governance:** Tracking AI token usage, estimated costs per model, and release quality indicators across the team.

```
Product Vision / Brief
          │
          ▼
[/roadmap] ──► Generates docs/roadmap.md & Beads Epics with Dependencies
          │
          ▼
[/progress] ──► Monitors in-flight Sprints & Blockers without touching code
          │
          ▼
[/report]   ──► Measures AI token costs & quality signals (review cycles, bugs)
```

---

## 2. Core PM Activities

### Activity 1: Author & Reconcile the Roadmap (`/gin-workflow:roadmap`)

PMs initiate roadmaps from product goals, market requirements, or technical modernization briefs.

**Command:**
```text
/gin-workflow:roadmap Build user authentication and billing integration
```

**What the AI Agent Does:**
1. Analyzes the existing codebase architecture and previous epics.
2. Formulates a proposed roadmap file (`docs/roadmap.md` under SDD, or `.planning/roadmap.md`).
3. Breaks down goals into sequenced Epics with clear dependencies (e.g., Epic 2 depends on Epic 1).
4. Creates corresponding parent tasks in Beads (`bd list --type epic`).

**Roadmap Pull Request (Team Mode):**
With `team.approvals.roadmap: [pm]`, the roadmap is proposed on branch `roadmap/<topic>` as a Pull Request. Another team member with the `pm` role approves and merges the PR before Beads epics are scheduled.

---

### Activity 2: Plan and Monitor Sprints (`/gin-workflow:progress`)

PMs manage team capacity and sprint backlogs without needing to manually create Jira subtasks.

1. **Assign Epics to a Sprint:**
   Tag epics with a sprint label:
   ```bash
   gin-workflow task label <epic-id> sprint:2026-q4-s1
   ```
   *(Or simply ask the agent: "Label epic AUTH-01 for sprint 2026-q4-s1")*

2. **Check Sprint Progress:**
   Check sprint health and blockers at any time without mutating repository state:
   ```text
   /gin-workflow:progress sprint 2026-q4-s1
   ```
   The agent reports:
   - Status of every epic in the sprint (Backlog, In Progress, Review, Shipped).
   - Any blocked tracks and their dependency blockers.
   - Open waivers or pending reviews.

---

### Activity 3: AI Usage & Quality Reporting (`/gin-workflow:report`)

`gin-workflow` tracks token usage and quality metrics for every lifecycle stage and AI model.

**Command:**
```text
/gin-workflow:report --sprint 2026-q4-s1
```

**Metrics Provided:**
- **AI Token & Cost Breakdown:** Total input/output tokens and estimated dollar cost broken down by model (e.g., Claude 3.5 Sonnet, Gemini 1.5 Pro) and stage (`discuss`, `plan`, `execute`, `review`).
- **Quality Indicators:**
  - Number of independent review cycles required per track.
  - Rejection rates and finding counts in the review ledger.
  - Reopened tasks or post-ship bug fixes.
  - Number of architectural waivers requested.

---

## 3. Ready-to-Use PM Prompts

### Prompt 1: Converting a Product Brief into a Roadmap
> "/gin-workflow:roadmap
> Here is our Q1 goal: We need to transition from single-tenant auth to multi-tenant workspace isolation with role-based access control (RBAC). 
> Please analyze the current auth capabilities and break this goal into 3-4 phased epics with dependency links."

### Prompt 2: Checking Sprint Status & Blockers
> "/gin-workflow:progress sprint 2026-q4-s1
> What epics are currently in progress? Are there any blocked tracks waiting on external dependencies or pending code reviews?"

### Prompt 3: Monthly AI Cost & ROI Analysis
> "/gin-workflow:report --sprint 2026-q4-s1
> Provide a summary of our AI spending for this sprint. Which epic consumed the most execution tokens, and did higher AI usage correlate with higher code review finding rates?"

---

## 4. PM Quality & Release Checklist

- [ ] Strategic goals are decomposed into clear, dependent epics in `docs/roadmap.md`.
- [ ] Epics are tagged with the active sprint label (`sprint:<name>`).
- [ ] Requirements are confirmed by the BA (`requirement-confirmed` gate passed) before engineering teams plan tracks.
- [ ] Sprint progress is reviewed weekly with `/gin-workflow:progress`.
- [ ] Token costs and review cycles are audited per sprint with `/gin-workflow:report`.
