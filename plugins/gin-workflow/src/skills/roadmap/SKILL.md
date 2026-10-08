---
name: roadmap
description: Turn the tech-doc set or a product brief into a confirmed roadmap file and dependent Beads epics; reconcile both on re-run.
---

# Roadmap

On `/roadmap` only. Outside the lifecycle: it records no gate. One question per message. Never write the roadmap file or touch Beads before the PM explicitly confirms the roadmap.

## Before you start
1. If `.agent-workflow/generated/effective-config.yaml` does not exist in the main checkout (the parent of `git rev-parse --path-format=absolute --git-common-dir`), stop: tell the user to run `/setup` once and do nothing else.
2. `gin-workflow state --format json` gives `project.stage` and `project.layout`. The roadmap file is `.planning/roadmap.md`, or `docs/roadmap.md` with `project.layout: sdd`.
3. `brownfield` or `legacy` needs the tech-doc folder (`.planning/codebase/`, or `artifacts.codebase`, default `docs/codebase/`, with the SDD layout); if it is missing, stop and recommend `/tech-doc`. `greenfield` needs a product brief: ask for a path or the text.

## Steps
1. **Read** every file of the tech-doc folder, subsystem subfolders included, yourself (no subagent summaries: epic dependencies come from reading across files), or the product brief; then living specs (or `.planning/specs/`), the roadmap file if it exists, and `bd list --label roadmap --all --json`. With `.codegraph/`, check load-bearing claims with `codegraph explore`.
2. **Clarify** with the PM: business goals, milestones, team capacity, operating constraints (downtime, data migration), exclusions.
3. **Propose 2–3 ways to split the work** (for example by bounded context, by risk, by business value) with trade-offs; lead with your recommendation.
4. **Present the roadmap**. Each epic: title, `Epic: <id>`, `Goal:`, `Scope:`, `Out of scope:`, `Depends on:` (epic ids), `Evidence:` (tech-doc file and section, or the brief), `Risks:`. A new id is `<prefix>-rm-<slug>` (`bd config get issue_prefix`; slug of lowercase letters, digits, and hyphens) and never changes once written. Check that dependencies are acyclic. On a re-run, present only what differs from the file and Beads. Revise until the PM explicitly confirms.
5. **Write** the file from `gin-workflow specs template roadmap.md` on branch `roadmap/<topic>` and commit. When `team.approvals.roadmap` in `.agent-workflow/config.yaml` lists roles: push, ask approval, open the pull request, and return `awaiting_roadmap_review`. On the next run, take the PR URL from the PM or `gh pr list --head roadmap/<topic>`, then `gin-workflow team check <pr-url> --gate roadmap`: exit 0 continues with the merged file on the base branch; exit 1 shows the reasons and stops. Never work around a rejection.
6. **Sync Beads** for each epic in the file, after `bd show <id> --json` (only an explicit not-found result means missing; any other failure stops the sync):
   - missing: `bd create --id <id> --type epic --labels roadmap -d "<description>" "<title>"`;
   - existing: `bd update <id> --title "<title>" -d "<description>"`. Never `bd create --id` an existing id: it replaces the bead and erases its description;
   - the description comes from `gin-workflow specs template epic.md`;
   - dependencies: `bd dep add <epic> <dependency>` for each `Depends on:` id; `bd dep remove <epic> <dependency>` for a dependency on a `roadmap`-labelled epic that the file no longer lists (`bd dep list <epic> --json`);
   - an epic that is `in_progress` or closed: warn and leave its title, description, and dependencies unchanged;
   - an epic labelled `roadmap` that the file no longer lists: report it and ask; never close or delete an epic;
   - a failing `bd` call: stop and report which epics were synced; a re-run continues from there.
7. **Sprint** (when asked): `bd update <epic> --add-label sprint:<name>` for each chosen epic.
8. **Report**: the roadmap path, epics created and updated, dependency changes, `bd ready` epics, and the next step `/discuss <epic-id>`.
