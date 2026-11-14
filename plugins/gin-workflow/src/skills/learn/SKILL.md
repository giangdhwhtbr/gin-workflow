---
name: learn
description: Use to capture durable decisions, constraints, and lessons during work, and to reconcile project knowledge at ship.
---

# Knowledge

Knowledge lives in `.planning/knowledge/` (the configured `artifacts.knowledge`) as small Markdown records. Short facts that every session needs go in `gin task remember "<fact>"`. Knowledge is looked up on demand and never copied wholesale into a stage's context.

## Capture (any stage)
1. Capture only reusable knowledge: compatibility constraints, environment limits, architectural decisions, counterintuitive APIs, and debugging lessons that will recur. Do not capture routine steps, transient worker state, private reasoning, or self-assessment.
2. One line per fact: `[gin learn] <stage> <track-id|->: <fact>. Evidence: <file:line | command | bead>`. `<stage>` is `discuss`, `plan`, `orchestrate`, `execute`, `review`, `ship`; `-` means no track.
3. With the Beads backend and a bead for the workflow (a roadmap epic, an SDD epic, a standalone bead, or the epic orchestrate created), run `gin task comment <bead> "<line>"`; a track's learning goes on its epic. In team mode run `gin team sync` after posting. A failed comment never blocks the stage: put the line under `## Learnings` of the spec; without a spec (a standalone bead), put it in the handoff and post it once the tracker works again.
4. With no bead yet (discuss or plan of an ad-hoc workflow), append the line under `## Learnings` at the end of the spec or plan.
5. With the markdown backend (no comments), write or update the record directly as in Reconcile, and mention it in the bead notes (`gin task update <id> --notes`).
6. Workers never post: the dispatching session posts each `Learnings` item of `gin:developer` and each `knowledge_candidates` entry (`fact`, `evidence`) of an orchestrated worker as `[gin learn] execute <track-id>:`.

## Reconcile (ship, before the options)
1. In team mode run `gin team sync`. Collect every `[gin learn]` comment of the epic (`gin task comments <epic> --json`) and the `## Learnings` lines of the spec and plan; with none, say so in one sentence.
2. Search first (`grep -ril "<topic>" .planning/knowledge`, `gin task memories <keyword>`); update an existing record instead of duplicating it, and merge duplicate learnings.
3. Write or update `.planning/knowledge/<topic>.md` with **Context**, **Decision/Solution**, **Consequences**, **References** (paths, beads), and **Scope**. For an architectural decision, start from `gin specs template adr.md`.
4. Update related records with an evidence-backed summary and correct contradictions or stale statements.
5. Commit the records on the feature branch. Close beads only after the records are written, or after a skipped update is stated in the handoff. If the knowledge location is unavailable, say so in the handoff.
