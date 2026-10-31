---
name: plan
description: Turn a confirmed requirement into a durable, Beads-ready implementation plan with routed tracks.
---

## Before you start
1. If `.agent-workflow/generated/effective-config.yaml` does not exist in the main checkout (the parent of `git rev-parse --path-format=absolute --git-common-dir`; linked worktrees have none), stop: tell the user to run `/setup` once and do nothing else. (`capabilities: {}` is a valid config.)
2. Read [references/stage-contract.md](../../references/stage-contract.md) now: it defines the gate CLI, valid evidence, approval, and git rules this stage relies on.

# Plan

Write a plan an engineer with zero context could execute: exact files, code, commands, and expected output. DRY, YAGNI, TDD.

## Steps

1. Require `requirement_confirmed` (`gin-workflow state`). If objectives, constraints, non-goals, or success criteria are unclear, stop and return to `discuss`. If the spec spans independent subsystems, propose one plan per subsystem.
2. Save to `.planning/plans/YYYY-MM-DD-<feature>.md` (with `project.layout: sdd`: `<change>/04-plan.md` plus per-track `Requirements:`, per the `gin-sdd` skill; user preference overrides) using the format in [plan-schema.md](plan-schema.md). Start with Goal, Architecture, Tech Stack, and **Global Constraints** copied verbatim from the spec. Commit the plan on the spec's `feat/<topic>` branch.
3. Map files first: each file one responsibility; files that change together live together; follow existing patterns.
4. Size tracks: the smallest unit with its own test cycle that a reviewer could reject independently. Fold setup, config, and docs into the track that needs them. Steps are 2–5 minutes each: failing test → run (fail) → minimal code → run (pass) → commit (stage-contract Git).
5. Give each track Metadata (dependencies, `Provider role:`, `Model:`, `Effort:` [omitted when catalog lists no efforts], `Why:`, and `Human gate:` when a person must act: credentials, production access, a manual or third-party approval), Files (create/modify/test with line ranges), and Interfaces (exact names and types consumed and produced).
   With `project.team.enabled`, tracks add `Area:`/`Owner:` and the plan is approved through a PR (the `gin-team` skill).
6. Route selection: choose `Model:` and `Effort:` from the main harness catalog using the rubric (weakest model/`low` effort for mechanical edits and boilerplate; middle model/`medium` effort for bounded implementation with a clear spec; strongest model/`high` effort for cross-module change, security, migration, concurrency). Explain the choice in `Why:`. Unclear requirements never raise model or effort: ask the user or return to `discuss`. Send code lookups and behavior checks to `gin-workflow:agent-researcher` (weakest/`low` for locating code, middle/`medium` for cross-module checks), which returns `file:line` citations. Declare `execution_strategy` exactly as in the schema.
7. Distinguish the Parent Bead (the deliverable/epic) from Track Beads (work units). "Remain open until human-confirmed merge" applies only to the Parent Bead; tracks close after tests and review pass so dependents unblock.
8. **No placeholders**: no TBD/TODO, "add error handling", "write tests for the above", "similar to Task N", steps without code, or references to undefined names.
9. Self-review against the spec: every requirement maps to a track, no placeholders, names and signatures consistent across tracks. Fix inline.
10. Validate that every track has a configured provider role, `Model:`, and `Effort:` from the catalog; report every problem in track order and fix before asking for approval.
11. Ask for explicit approval (stage-contract Approvals), then `gin-workflow record plan-approved --evidence <plan-path> --actor <user-id> --workflow-id <id>` (the spec's `Epic:` or `Workflow:` id).

## Exit

Return `plan_approved`. Do not orchestrate.
