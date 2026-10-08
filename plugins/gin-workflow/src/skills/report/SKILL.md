---
name: report
description: Report AI usage per bead or epic — tokens and estimated cost per model and lifecycle stage, next to quality signals (reopens, bugs found later, review cycles, rejections, findings, waivers) — without mutating anything.
---

## Before you start
1. If `.agent-workflow/generated/effective-config.yaml` does not exist in the main checkout (the parent of `git rev-parse --path-format=absolute --git-common-dir`; linked worktrees have none), stop: tell the user to run `/setup` once and do nothing else. (`capabilities: {}` is a valid config.)
2. Read [references/stage-contract.md](../../references/stage-contract.md) now: it defines the gate CLI, valid evidence, approval, and git rules this stage relies on.

# Report

Read-only usage report. Summaries are written into each bead's metadata (`ai_usage`) when the bead closes (`execute`) or the epic ships (`ship`); this skill only reads them.

1. Scope from the request: one bead (`--bead <id>`), an epic and its tracks (`--epic <id>`), a sprint's epics and their tracks (`--sprint <name>`, epics labelled `sprint:<name>`), beads closed since a date (`--since YYYY-MM-DD`), or every collected bead (no flag).
2. Run `gin-workflow usage report <scope> --format json`. Exit 2 means `bd` is missing or failed: show the error and stop.
3. Present:
   - Each bead: cost, title, and its quality signals.
   - Totals per model (input, output, cache read, cache write, cost) and per stage (`discuss`, `plan`, `orchestrate`, `execute`, `review`, `verify`, `ship`, `quick`).
   - Rework next to cost: reopens, bugs with `discovered-from` the bead, review cycles, rejections, findings by severity, gate waivers.
   - `unpriced` models: their tokens count, their cost does not; prices live in `.agent-workflow/usage-prices.yaml` (USD per million tokens).
   - `unattributed` usage: work that matched no bead or gate.
   - `not_collected` beads: offer `gin-workflow usage collect --bead <id>` for each, and run it only if the user agrees.
4. Say what the numbers are: estimates from local Claude Code and Codex logs on the machine that collected them. Antigravity usage is not measured.
5. Never change beads, prices, or logs, and never chain into another stage.
