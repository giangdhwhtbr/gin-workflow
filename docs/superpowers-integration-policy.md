# Superpowers Integration Policy

This document defines how `gin-workflow` skills use `superpowers:*` skills.

If any overlay skill's own "Gin Workflow Overlay" section conflicts with this document, the overlay skill's explicit statement wins for that skill — but the overlay must still comply with the rules below rather than silently inheriting a conflicting default from its base skill.

## The Rule

`superpowers:*` skills invoked directly or via a `gin-workflow` overlay skill are used for their reasoning and process guidance only — how to think through a problem, what questions to ask, how to sequence work, what a good design or plan looks like.

They are not used for their default artifact-output behavior. Specifically:

1. **Artifact location and naming are always superseded.** Any file path, directory, or naming convention a base `superpowers:*` skill proposes (for example, writing a spec or plan under `docs/superpowers/...`) is replaced by `gin-workflow` conventions. Durable planning and design artifacts live under `.planning/...` (for example `.planning/plans/`, `.planning/specs/`), never under `docs/superpowers/...`.
2. **Git commit and push defaults are always superseded.** A base skill's instruction to commit or push (unconditionally, as part of "finishing a step") does not carry authority on its own. Committing and pushing remain subject to this repo's explicit-authorization-before-commit rule (`AGENTS.md`), regardless of what the base skill's checklist says.

## Why This Exists

`superpowers:brainstorming`'s default checklist step writes a design doc to `docs/superpowers/specs/YYYY-MM-DD-<topic>-design.md` and commits it. `gin-workflow`'s `discovering-work` overlay (which extends `brainstorming`) did not override that default, so design docs produced during `/discuss` landed outside the `.planning/` convention and were committed without explicit authorization. This document exists so that gap does not recur as new overlay skills are added for other `superpowers:*` skills.

## How Overlay Authors Apply This

An overlay skill must not rely on this document alone to redirect behavior. Each overlay's own "Gin Workflow Overlay" section must state the concrete redirected path or behavior explicitly, the same way `writing-plans` states plans are saved to `.planning/plans/` rather than `docs/superpowers/plans/`. This document records the general rule and rationale; each overlay records the specific application of it for its own base skill.
