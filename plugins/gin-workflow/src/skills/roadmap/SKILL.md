---
name: roadmap
description: Turn the tech-doc set or a product brief into a confirmed roadmap file and dependent Beads epics, optionally under a dated milestone; reconcile both on re-run.
---

# Roadmap

On `/roadmap` only. Outside the lifecycle: it records no gate. One question per message. Never write the roadmap file or touch Beads before the PM explicitly confirms the roadmap.

## Before you start
1. If `.agent-workflow/generated/effective-config.yaml` does not exist in the main checkout (the parent of `git rev-parse --path-format=absolute --git-common-dir`), stop: tell the user to run `/setup` once and do nothing else.
2. `gin-workflow state --format json` gives `project.stage` and `project.layout`. The roadmap file is `.planning/roadmap.md`, or `docs/roadmap.md` with `project.layout: sdd`.
3. `brownfield` or `legacy` prefers the tech-doc folder (`.planning/codebase/`, or `artifacts.codebase`, default `docs/codebase/`, with the SDD layout). If the folder is missing, recommend `/tech-doc` once in one sentence, then ask for a product brief (a path or the text). `greenfield` needs a product brief: ask for a path or the text.

## With --milestone <id>
1. Before anything else run `gin-workflow milestone show <id> --json`. A non-zero exit or `status: closed` stops the skill: report the message. In team mode, also stop when `project.team.permissions.milestone` in `gin-workflow state --format json` lists roles and none is in `project.team.me.roles`; name the roles. `project.team.me` is null when the git user is not a member, so the check stops. `permissions` is absent when team mode is off, so no check applies.
2. In step 4, propose `Estimate: <working days>` for every epic of the milestone, from your analysis. Never ask the PM for estimates; they do not count against `project.max_questions`. Revise them on request.
3. Adoption: take the beads of `gin-workflow task list --label roadmap --type epic --limit 0 --json` with status `open` or `in_progress` and no `parent`. Propose which join the milestone, each with an estimate (the remaining working days for `in_progress`). The PM may add or drop epics and change estimates. Never propose a closed epic. Never change an adopted epic's title, description, or dependencies.
4. In step 5, the file groups epics under `## Milestone: <title>`, with `Milestone: <id>` and `Estimate: <days>` per epic. Epics without a milestone go under `## Unassigned`. A file without these lines is still valid input.
5. In step 6, after the sync (and after the roadmap PR merges when `team.approvals.roadmap` lists roles), set membership with `gin-workflow milestone move <epic>... --to <id>` and estimates with `gin-workflow milestone estimate <epic> <days>`. Set them no other way. When a `gin-workflow milestone move` or `estimate` call exits non-zero, stop and report its message and which epics were already set. The messages are: a denied role (exit 2) naming the roles; `pull failed, nothing written`; `moved <epics>; <epic> failed: ...` for a partial move; and `<change> written locally but not pushed`. A re-run continues, and Beads wins.
6. On a re-run, Beads wins for membership and estimates. Compare `gin-workflow milestone show <id> --json` with the file and report each difference (for example "E1 estimate: file 5, Beads 8") without writing Beads.

## Steps
1. **Read** every file of the tech-doc folder, subsystem subfolders included, yourself (no subagent summaries: epic dependencies come from reading across files), or the product brief; then living specs (or `.planning/specs/`), the roadmap file if it exists, and `gin-workflow task list --label roadmap --type epic --all --json` (Beads copies a parent's labels to its children, so tracks also carry `roadmap`; `--type epic` keeps them out). With `.codegraph/`, check load-bearing claims with `codegraph explore`.
2. **Clarify** with the PM (at most `project.max_questions` questions (`gin-workflow state --format json`, default 8); at the cap, say the scope is too large or unclear and propose splitting it into smaller epics, or list the rest as assumptions): business goals, milestones, team capacity, operating constraints (downtime, data migration), exclusions. Do not number questions against the cap (no `2/8`): it is a ceiling, not a target; ask only what changes the roadmap.
3. **Propose 2–3 ways to split the work** (for example by bounded context, by risk, by business value) with trade-offs; lead with your recommendation.
4. **Present the roadmap**. Each epic: title, `Epic: <id>`, `Goal:`, `Scope:`, `Out of scope:`, `Depends on:` (epic ids), `Evidence:` (tech-doc file and section, or the brief), `Risks:`. A new id (one not yet in the roadmap file) is `<prefix>-<slug>` (`gin-workflow task config get issue_prefix`; slug of lowercase letters, digits, and hyphens) and never changes once written; when `gin-workflow task show <id>` finds a bead, choose another slug. Check that dependencies are acyclic. On a re-run, present only what differs from the file and Beads. Revise until the PM explicitly confirms.
5. **Write** the file from `gin-workflow specs template roadmap.md` on branch `roadmap/<topic>` and commit. A plain `/roadmap` omits the milestone heading and the `Milestone:` and `Estimate:` lines, and puts its epics under `## Unassigned`. When `team.approvals.roadmap` in `.agent-workflow/config.yaml` lists roles: push, ask approval, open the pull request, and return `awaiting_roadmap_review`. On the next run, take the PR URL from the PM or `gh pr list --head roadmap/<topic>`, then `gin-workflow team check <pr-url> --gate roadmap`: exit 0 continues with the merged file on the base branch; exit 1 shows the reasons and stops. Never work around a rejection.
6. **Sync Beads** for each epic in the file, after `gin-workflow task show <id> --json` (only an explicit not-found result means missing; any other failure stops the sync):
   - missing: `gin-workflow task create --id <id> --type epic --labels roadmap -d "<description>" "<title>"`;
   - existing, an epic labelled `roadmap`: `gin-workflow task update <id> --title "<title>" -d "<description>"`. Never `gin-workflow task create --id` an existing id: it replaces the bead and erases its description;
   - existing without the `roadmap` label or not an epic: an id collision; stop and report it, never update that bead;
   - the description comes from `gin-workflow specs template epic.md`;
   - dependencies: `gin-workflow task dep add <epic> <dependency>` for each `Depends on:` id; `gin-workflow task dep remove <epic> <dependency>` for a dependency on a `roadmap`-labelled epic that the file no longer lists (`gin-workflow task dep list <epic> --json`);
   - an epic that is `in_progress` or closed, or `open` and adopted into a milestone (in Beads, or in the confirmed roadmap: `milestone move` runs after this sync): warn and leave its title, description, and dependencies unchanged;
   - an epic labelled `roadmap` that the file no longer lists: report it and ask; never close or delete an epic;
   - a failing `gin-workflow task` call: stop and report which epics were synced; a re-run continues from there.
7. **Sprint** (when asked): `gin-workflow task update <epic> --add-label sprint:<name>` for each chosen epic.
8. **Report**: the roadmap path, epics created and updated, dependency changes, `gin-workflow task ready` epics, the next step `/discuss <epic-id>`, and `gin-workflow setup refresh` to update the links in `AGENTS.md`.
