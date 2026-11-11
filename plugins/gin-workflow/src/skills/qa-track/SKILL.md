---
name: qa-track
description: Use in /execute for a track routed to the `qa` provider role, to write or update gin-qa cases, automated tests, or e2e specs, validate them with gin-qa, and commit them like any track.
---

# QA track

A track whose plan entry has `Provider role: qa` changes QA files in the QA home (gin-qa's `cases/`, test globs, or `e2e/`). Execute dispatches it like any track; these rules add to execute, they do not replace it.

1. Dispatch `gin:developer` at the track's route. Its instructions are the gin-qa skill that matches the track's files: `gin-qa:cases` for case files, `gin-qa:tests` for automated tests, `gin-qa:e2e` for Playwright specs. Pass `gin rules --files <case and test files>` as for any track.
2. The track runs in its worktree: the `qa` child's worktree in a workspace, else the feature worktree. gin-qa finds the QA home from there.
3. Validate before review: `gin-qa cases check --change <epic>`; add `gin-qa tests check` when the track changed tests and `gin-qa e2e check` when it changed e2e specs. Exit 1 lists findings: fix them before review.
4. gin-qa skills never commit. The developer commits the track's files on the track branch with the track's bead in the message, as execute requires.
5. Review and close follow execute's Complete steps.
