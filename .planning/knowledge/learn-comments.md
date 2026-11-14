# Learn comments: stages post findings on the bead, ship writes knowledge

**Context**
Epic `gin-workflow-fgil` (2026-11-14). Knowledge was captured only during execute and reconciled at ship. Discuss and plan had no capture step and were told never to write to the bead. The ship reminder `_knowledge_warning` read `orchestration.ready` from the local `.agent-workflow/runtime/events.jsonl`, which is not shared, so it stayed silent on a machine that did not orchestrate. In team mode, what earlier stages learned on another member's machine was lost or invisible.

**Decision/Solution**
- The format lives in the `learn` skill: one fact per line, `[gin learn] <stage> <track-id|->: <fact>. Evidence: <file:line | command | bead>`.
- Where a learning goes:
  - With Beads and a bead for the workflow (a roadmap epic, an SDD epic, a standalone bead, or the epic orchestrate created), it is posted with `gin task comment`; a track's learning goes on its epic. In team mode, post and then `gin team sync`.
  - With no bead yet (discuss or plan of an ad-hoc workflow), it goes under `## Learnings` of the spec or plan.
  - A failed comment goes under `## Learnings` of the spec, which ship may still change after approval; without a spec, it goes in the handoff and is posted later.
  - With the markdown backend, the record is written directly, as before.
- Workers never post. `gin:developer` reports `Learnings`, an orchestrated worker returns `knowledge_candidates` (a list of mappings), and the dispatching session posts the `fact` and `evidence` of each.
- Discuss and plan may post `[gin learn]` and leave those comments out of their summaries, of `Comments considered:`, and of plan's new-comment check.
- Ship reconciles at the end of step 1, before the options, so the records land with a merge or a pull request. `.planning/knowledge/` joined the paths allowed after approval.
- `_knowledge_warning`, with Beads, reads the comments of the epic `gin state` resolved (the shared epic in team mode, else the recorded one). It warns `<n> learn comments not yet in <knowledge>` for learn comments newer than the last knowledge commit; a `created_at` that does not parse or has no UTC offset counts as newer. Any failure gives no warning. With the markdown backend, the local-event check stays.

**Consequences**
- With Beads, an epic without learn comments no longer gets the ship reminder; ship still runs reconcile.
- A learning reaches other machines only after `gin team sync` on both sides.
- Learnings are not code-reviewed until ship turns them into records.
- Python still parses no comment tag except `[gin learn]` in `_learn_comment_warning`; the other tags remain skill conventions.
- The reviewer does not post learnings (the review chain had 215 characters left); execute may post findings from a review report.

**References**
- `plugins/gin-workflow/src/scripts/workflow_core/lifecycle_cli.py` (`_knowledge_warning`, `_learn_comment_warning`, `_state_command`); `plugins/gin-workflow/src/skills/{learn,discuss,plan,execute,ship}/SKILL.md`; `plugins/gin-workflow/src/skills/execute/references/result-contract.md`; `plugins/gin-workflow/src/agents/developer.md`
- Tests: `tests/workflow_core/test_lifecycle_cli.py`, `tests/workflow_core/test_skill_routing.py`
- Docs: `docs/concepts/lifecycle.md`, `docs/guides/team.md`
- `.planning/specs/2026-11-14-learn-comments-design.md`, `.planning/plans/2026-11-14-learn-comments.md`
- Beads: `gin-workflow-fgil`, `.1`, `.2`
- Related: [epic-comments](epic-comments.md), [test-suite-speed](test-suite-speed.md)

**Scope**
Capturing and reconciling project knowledge in every lifecycle stage.
