---
name: ship
description: Perform one approved delivery action after verification.
---

# Ship Skill

Perform exactly one delivery stage.

## Required inputs

- resolved `EffectiveConfig`
- `ArtifactRegistry`
- `ContextManifest(stage="ship")`
- native-harness `ApprovalDecision`

The caller must obtain `EffectiveConfig` through
`load_effective_config(repository)`. If setup is required, stop and instruct
the user to run `/setup` once. Never run setup or resolve raw configuration
from this lifecycle skill.

## Execution

1. Require `verification_passed`, terminal review evidence, and the canonical handoff record.
2. Apply the `finishing-a-development-branch` methodology.
3. Revalidate reviewed tree identity and every protected-action approval immediately before use.
4. Use the approval and evidence managers for commit, push, upgrade, data movement, or other protected delivery actions. Optional notification and knowledge reconciliation remain provider-backed.
5. Use task-tracking and workspace capabilities for durable closure and cleanup; workspace metadata never proves completion.
6. If this repository is itself distributed as a plugin/marketplace source that other repositories on this host install from (as `gin-workflow` is), refresh every installed platform's local snapshot before treating the shipped fix as available elsewhere: harness plugin managers cache a copy at install time and do not pick up new commits on their own, so a consumer can keep failing on an already-fixed bug against a stale cache. See the README's Troubleshooting entry for the refresh command; this step is a no-op for ordinary application repositories.
7. Query open and unblocked tasks using the task-tracking capability. Group ready tasks by dependency readiness and non-overlapping file scope, and recommend the next tasks in the handoff summary—explicitly identifying which tasks can be executed concurrently in parallel (including task IDs, titles, plan context, and worktree isolation recommendations) and formatting the exact runnable slash command under `Next commands:` (e.g. `/gin-workflow:execute <task-id-1> <task-id-2> <task-id-3>`).
8. Return `shipped` state without invoking another lifecycle stage.


