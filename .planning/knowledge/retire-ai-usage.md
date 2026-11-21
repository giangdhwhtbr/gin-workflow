# AI usage tracking retired; `usage:` ignored

**Context**
Epic `gin-workflow-wkwb` (2026-11-21, spec `.planning/specs/2026-11-21-retire-ai-usage-design.md`, gin 3.4.0). The user decided it while discussing `gin-workflow-04wv`, which would have collected usage on every close. Measured on the build machine: `gin usage collect` took about 36 s per bead and 57 s per 6-track epic (Claude logs about 9 s, Codex logs about 5 s, about 20 s in `usage_logs.inside()`, called about 400k times). `execute` and `ship` called it per worker result, per track close and at the merge, about 10 minutes per 6-track epic. The figures also missed most of the work: `gin-workflow-u5mt` stored $0.48 with only `discuss`, and `/quick` gates recorded under `default-workflow` gave its beads 0 tokens.

**Decision/Solution**
- `gin usage`, `workflow_core/usage*.py`, the price catalog, the `report` skill, and the usage steps of `execute`, `ship` and `milestone-close` are gone. `milestone-close` no longer computes `cost_per_epic` and `rework`; it compares only the metrics both `Metrics:` lines hold.
- `gin routes dispatch` reads no budget and has no exit 3.
- `usage:` stays valid in schema 2.11 and is ignored: `USAGE_IGNORED_NOTICE` (`configuration.py`) appears once in `gin state` warnings and once in `gin setup doctor` actions. No schema bump, no migration.
- `Worktree` and `worktrees()` moved to `checkout.py`; `close_guard` still needs them for review ledgers in linked worktrees.
- A global install rebuilds its folders, so no stale skill stays. A project install removes `.opencode/skills/gin-report`, and removes `skills/report` under `.claude`, `.agents` and `.codex` only when its `SKILL.md` contains `Report AI usage`, because gin-qa's `report` skill shares the folder name.
- Quality signals (reopens, bugs, review cycles, rejections, findings, waivers) are not replaced in gin-workflow. gin-console computes them from files it reads (`gin-console-5c4`): reopens are the closes in `interactions.jsonl` minus one, which matched `ai_usage.quality` for 435 of 439 gin-workflow beads.

**Consequences**
- Nothing writes `metadata.ai_usage` any more; values already stored stay on the beads.
- gin-console Reports read `ai_usage` until `gin-console-5c4` ships (parent `gin-harness-1u3`).
- `tests/workflow_core/test_retired_usage_sweep.py` fails on any `gin usage`, `ai_usage`, `budget_usd`, `/gin:report` or usage-module mention outside `docs/changelog.md` and `schemas.py`. It misses prose such as "usage reports"; grep for those by hand.

**References**
- `plugins/gin-workflow/src/scripts/workflow_core/{checkout,configuration,lifecycle_cli,setup_service,routes,cli}.py`, `install.sh` and `install.ps1` (`remove_legacy_project_install`, `Remove-LegacyProjectInstall`)
- Tests: `tests/workflow_core/test_usage_retired.py`, `test_checkout.py`, `test_retired_usage_sweep.py`, `tests/install_smoke_test.sh`
- Beads: `gin-workflow-wkwb`, `gin-workflow-04wv` (superseded), `gin-console-5c4`, `gin-harness-1u3`
- History: [usage-collect](usage-collect.md)

**Scope**
AI usage tracking, the `usage:` config key, and the installers' removal of gin's `report` skill.
