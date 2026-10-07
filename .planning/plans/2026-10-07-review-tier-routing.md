# Plan: Review tier routing

## Objective
Agents size each reviewer to the change: `gin-workflow reviewer --base SHA --implementer PROVIDER [--tier T]` prints the review tier and the ordered reviewer routes, and the `review` skill dispatches from that list. A low-tier (docs) review is no longer blocked when only the implementer's provider is available.

Spec: `.planning/specs/2026-10-07-review-tier-routing-design.md` (bead `gin-workflow-hv9`).

## Global Constraints (from the spec)
- The command is read-only and agent-facing: the `review` skill calls it; users keep invoking `/gin-workflow:review`.
- Inputs: `--tier` is the track's `Reasoning:` (default `medium`); `--implementer` is the provider that actually implemented the work.
- Raise rule: tier `low` + any non-documentation changed file → `medium`. Documentation: ends in `.md` or under `docs/`, unless a path segment is `skills`. Never lowered; no other rule.
- Independence: at `low` the implementer provider stays in the list; at `medium`/`high` it is removed. `require_independent: false` keeps every candidate; `allow_self_review_fallback` keeps its meaning.
- Exit 0 routes printed; exit 2 when `git diff <base>..HEAD` fails, no candidate resolves for the tier, or the list is empty after the independence filter.
- No new configuration keys, no runtime events, no JSON output, no reviewer dispatch.

## Model Guidance
- `default_model_class`: `standard_impl`
- `phase_guidance`:
  - `implement`: `standard_impl`
  - `review`: `standard_impl`
- `override_rule`: none; the boundaries are settled in the spec.

## Requirement Analysis
- Problem statement: the `review` skill names no reviewer tier, so every review runs high-tier, and provider independence blocks docs reviews when the other providers are out of quota.
- Success criteria: the command prints the tier and routes per the Global Constraints; the skill uses it; tests and docs checks pass.
- Constraints: reuse `resolve_assignment`, `load_effective_config`, `load_provider_local_config`, `REASONING_TIERS`; one module that holds its own `main`, as `rules.py` does.
- Non-goals: see the spec's Out of scope.

## Approach Options
### Option 1: CLI helper called by the skill
- Summary: one routing module with a thin `main`; the skill runs one command.
- Pros: deterministic, testable, a few lines of output per review.
- Cons: one more command to document.

### Option 2: Skill prose only
- Summary: describe the rules in the `review` skill; the agent reads the provider files itself.
- Pros: no code.
- Cons: more tokens per review, inconsistent application, untestable.

### Recommended Approach
- Selected option: Option 1 (confirmed in discuss).
- Reasoning: deterministic rules belong in code; the skill stays short.

## Scope
- In scope: `workflow_core/reviewer.py`, the `reviewer` entry in `workflow_core/cli.py`, `tests/workflow_core/test_reviewer.py`, the `review` skill, `docs/reference/cli.md`, `docs/concepts/providers.md`.
- Out of scope: the spec's Out of scope list.

## Execution Strategy

```yaml
execution_strategy:
  mode: direct
  workers:
    mode: sequential
  rationale: One small track; the skill and docs changes ship with the command they describe.
```

## Tasks

### Track 1: `gin-workflow reviewer` and the `review` skill

**Metadata:**
- Dependencies: none
- Provider role: `backend`
- Reasoning: `medium`
- Model class: `standard_impl`
- Estimated complexity: low

**Files:**
- Create: `plugins/gin-workflow/src/scripts/workflow_core/reviewer.py`
- Modify: `plugins/gin-workflow/src/scripts/workflow_core/cli.py` (command tuple and usage string, lines 69-70; dispatch after the `usage` branch, lines 82-84)
- Modify: `docs/reference/cli.md` (new section before `## \`gin-workflow usage\``; `test_docs_coverage.test_every_cli_subcommand_has_a_heading` requires it)
- Modify: `plugins/gin-workflow/src/skills/review/SKILL.md` (Requesting step 2, line 16)
- Modify: `docs/concepts/providers.md` (`## Independent review`, line 56)
- Test: `tests/workflow_core/test_reviewer.py`

**Interfaces:**
- `reviewer.is_docs(path: str) -> bool`
- `reviewer.review_tier(tier: str, changed: Sequence[str]) -> tuple[str, list[str]]` (tier, reasons)
- `reviewer.ReviewerError(Exception)`
- `reviewer.route(root: Path, base: str, *, tier: str, implementer: str, config: EffectiveConfig, local: Mapping[str, ProviderModelConfig]) -> dict[str, Any]` with keys `tier`, `reasons`, `independence`, `routes` (list of `(provider, model, effort)`)
- `reviewer.main(arguments: Sequence[str]) -> int`

**Steps:**

1. Write `tests/workflow_core/test_reviewer.py`:

```python
"""`gin-workflow reviewer`: review tier and ordered reviewer routes (agent-facing, read-only)."""

from __future__ import annotations

import io
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))

from team_fixtures import git, write  # noqa: E402
from workflow_core import reviewer  # noqa: E402
from workflow_core.models import EffectiveConfig  # noqa: E402
from workflow_core.provider_config import ProviderModelConfig  # noqa: E402
from workflow_core.reviewer import ReviewerError, is_docs, review_tier, route  # noqa: E402

LOCAL = {
    "antigravity": ProviderModelConfig("antigravity", "agy", {"low": "g-low", "medium": "g-mid", "high": "g-high"}),
    "claude": ProviderModelConfig("claude", "claude", {"low": "haiku", "medium": "sonnet", "high": "opus"}),
    "codex": ProviderModelConfig("codex", "codex", {"low": "luna", "medium": "sol", "high": "astra"}),
}


def config(root: Path, preferred=("antigravity",), fallback=("codex", "claude"), **review) -> EffectiveConfig:
    return EffectiveConfig({
        "schema_version": "2.3", "harness": "claude",
        "routing": {"roles": {"review": {"preferred": list(preferred), "fallback": list(fallback)}},
                    "review": {"require_independent": True, "allow_self_review_fallback": False, **review}},
    }, root)


class ReviewTierTests(unittest.TestCase):
    def test_docs_detection(self):
        self.assertTrue(is_docs("README.md"))
        self.assertTrue(is_docs("docs/guide/setup.txt"))
        self.assertFalse(is_docs("plugins/x/src/skills/review/SKILL.md"))
        self.assertFalse(is_docs("src/app.py"))

    def test_low_with_only_docs_stays_low(self):
        self.assertEqual(("low", []), review_tier("low", ["README.md", "docs/a.md"]))

    def test_low_with_code_or_skill_becomes_medium(self):
        self.assertEqual(("medium", ["low track changes non-docs files: src/app.py"]),
                         review_tier("low", ["README.md", "src/app.py"]))
        self.assertEqual("medium", review_tier("low", ["plugins/x/skills/y/SKILL.md"])[0])

    def test_medium_and_high_never_change_and_empty_diff_keeps_the_tier(self):
        self.assertEqual(("medium", []), review_tier("medium", ["src/app.py"]))
        self.assertEqual(("high", []), review_tier("high", ["README.md"]))
        self.assertEqual(("low", []), review_tier("low", []))


class RouteTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name) / "repo"
        self.root.mkdir()
        git(self.root, "init", "-q", "-b", "main")
        git(self.root, "commit", "-q", "--allow-empty", "-m", "base")
        self.base = git(self.root, "rev-parse", "HEAD").strip()

    def change(self, path: str) -> None:
        write(self.root, path, "x\n")
        git(self.root, "add", path)
        git(self.root, "commit", "-q", "-m", path)

    def providers(self, tier: str, implementer: str = "claude", cfg: EffectiveConfig | None = None) -> list[str]:
        out = route(self.root, self.base, tier=tier, implementer=implementer, config=cfg or config(self.root),
                    local=LOCAL)
        return [f"{provider} {model}" for provider, model, _ in out["routes"]]

    def test_low_docs_review_keeps_the_implementer_provider(self):
        self.change("docs/a.md")
        self.assertEqual(["antigravity g-low", "codex luna", "claude haiku"], self.providers("low"))

    def test_low_track_changing_code_reviews_at_medium_without_the_implementer(self):
        self.change("src/app.py")
        out = route(self.root, self.base, tier="low", implementer="claude", config=config(self.root), local=LOCAL)
        self.assertEqual(("medium", "provider"), (out["tier"], out["independence"]))
        self.assertEqual(["low track changes non-docs files: src/app.py"], out["reasons"])
        self.assertEqual(["antigravity g-mid", "codex sol"], self.providers("low"))

    def test_require_independent_false_keeps_the_implementer(self):
        self.assertIn("claude sonnet", self.providers("medium", cfg=config(self.root, require_independent=False)))

    def test_empty_list_after_the_filter_is_an_error_unless_self_review_is_allowed(self):
        only_codex = config(self.root, preferred=("codex",), fallback=())
        with self.assertRaisesRegex(ReviewerError, "no reviewer route independent of codex at tier high"):
            self.providers("high", "codex", only_codex)
        allowed = config(self.root, preferred=("codex",), fallback=(), allow_self_review_fallback=True)
        self.assertEqual(["codex astra"], self.providers("high", "codex", allowed))

    def test_bad_base_is_an_error(self):
        self.base = "nope"
        with self.assertRaisesRegex(ReviewerError, "git diff nope..HEAD failed"):
            self.providers("low")

    def test_cli_prints_routes_and_exits_2_on_a_bad_base(self):
        self.change("docs/a.md")

        def run(base: str) -> tuple[int, str]:
            out = io.StringIO()
            with mock.patch.object(reviewer, "load_effective_config", return_value=config(self.root)), \
                    mock.patch.object(reviewer, "load_provider_local_config", return_value=LOCAL), \
                    mock.patch("sys.stdout", out), mock.patch("sys.stderr", out):
                code = reviewer.main(["--base", base, "--implementer", "claude", "--tier", "low",
                                      "--repository", str(self.root)])
            return code, out.getvalue()

        self.assertEqual((0, "tier low; independence session\nantigravity g-low\ncodex luna\nclaude haiku\n"),
                         run(self.base))
        code, text = run("nope")
        self.assertEqual(2, code)
        self.assertIn("git diff nope..HEAD failed", text)
```

2. Run: `PYTHONPATH=plugins/gin-workflow/src/scripts:tests python3 -m unittest tests.workflow_core.test_reviewer </dev/null` → fails with `ImportError: cannot import name 'reviewer' from 'workflow_core'`.

3. Create `plugins/gin-workflow/src/scripts/workflow_core/reviewer.py`:

```python
"""`gin-workflow reviewer` (agent-facing): the review tier and ordered reviewer routes; exit 2 when none."""

from __future__ import annotations

import argparse
from pathlib import Path, PurePosixPath
import subprocess
import sys
from typing import Any, Mapping, Sequence

from .assignments import AssignmentRequest, AssignmentResolutionError, resolve_assignment
from .configuration import ConfigValidationError, load_effective_config
from .models import EffectiveConfig
from .provider_config import (REASONING_TIERS, ProviderLocalConfigError, ProviderModelConfig,
                              load_provider_local_config)


class ReviewerError(Exception):
    """The reviewer routes cannot be determined (exit 2)."""


def is_docs(path: str) -> bool:
    parts = PurePosixPath(path).parts
    return "skills" not in parts and (path.endswith(".md") or parts[:1] == ("docs",))


def review_tier(tier: str, changed: Sequence[str]) -> tuple[str, list[str]]:
    """Raise a low tier to medium when the diff changes anything but documentation; never lower."""
    code = [path for path in changed if not is_docs(path)]
    if tier != "low" or not code:
        return tier, []
    return "medium", [f"low track changes non-docs files: {', '.join(code[:3])}"]


def route(root: Path, base: str, *, tier: str, implementer: str, config: EffectiveConfig,
          local: Mapping[str, ProviderModelConfig]) -> dict[str, Any]:
    diff = subprocess.run(["git", "diff", "--name-only", f"{base}..HEAD"], cwd=root, capture_output=True,
                          text=True, check=False)
    if diff.returncode != 0:
        raise ReviewerError(f"git diff {base}..HEAD failed: {diff.stderr.strip()}")
    tier, reasons = review_tier(tier, diff.stdout.splitlines())
    try:
        candidates = resolve_assignment(
            AssignmentRequest("reviewer", "review", tier, config.harness or implementer), config, local)
    except AssignmentResolutionError as error:
        raise ReviewerError(str(error)) from error
    review = (config.get("routing") or {}).get("review") or {}
    independent = bool(review.get("require_independent", True)) and tier != "low"
    routes = [c for c in candidates if not independent or c.provider != implementer]
    if not routes and review.get("allow_self_review_fallback"):
        routes = list(candidates)
    if not routes:
        raise ReviewerError(f"no reviewer route independent of {implementer} at tier {tier}")
    return {"tier": tier, "reasons": reasons, "independence": "provider" if independent else "session",
            "routes": [(c.provider, c.model, c.effort) for c in routes]}


def main(arguments: Sequence[str]) -> int:
    parser = argparse.ArgumentParser(prog="gin-workflow reviewer")
    parser.add_argument("--base", required=True)
    parser.add_argument("--implementer", required=True)
    parser.add_argument("--tier", choices=REASONING_TIERS, default="medium")
    parser.add_argument("--repository", type=Path, default=Path.cwd())
    args = parser.parse_args(list(arguments))
    root = args.repository.resolve()
    try:
        out = route(root, args.base, tier=args.tier, implementer=args.implementer,
                    config=load_effective_config(root), local=load_provider_local_config(root))
    except (ReviewerError, ConfigValidationError, ProviderLocalConfigError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 2
    lines = [f"tier {out['tier']}; independence {out['independence']}"]
    lines += [f"reason: {reason}" for reason in out["reasons"]]
    lines += [" ".join(filter(None, item)) for item in out["routes"]]
    print("\n".join(lines))
    return 0
```

4. In `workflow_core/cli.py`, add `"reviewer"` to the command tuple and the usage string at lines 69-70, and after the `usage` branch:

```python
    if argv[0] == "reviewer":
        from .reviewer import main as reviewer_main
        return reviewer_main(argv[1:])
```

5. In `docs/reference/cli.md`, before `## \`gin-workflow usage\``:

~~~markdown
## `gin-workflow reviewer`

```
gin-workflow reviewer --base SHA --implementer PROVIDER [--tier low|medium|high]
```

Called by the `review` skill to pick the reviewer; you do not need to run it. Prints the review tier and the reviewer routes in order. `--tier` is the track's reasoning (default `medium`); a `low` track whose diff since `--base` changes anything but documentation (`*.md` or `docs/`, excluding `skills/`) is reviewed at `medium`. At `low` the implementer's provider may review in a fresh session; at `medium` and `high` it is excluded unless `routing.review.require_independent` is false.

Exit codes: 0 routes printed; 2 bad `--base`, no route for the tier, or no independent route.
~~~

6. In `review/SKILL.md` Requesting step 2, replace "Dispatch an independent reviewer with a fresh context:" with "Pick the reviewer with `gin-workflow reviewer --base <ledger base> --implementer <provider> --tier <track reasoning>` and dispatch the first available route with its model, trying the next on a quota, rate-limit, or timeout failure (exit 2 means `human_decision_required`); actor id `reviewer:<provider>`, or `reviewer:<provider>:session-<id>` for the implementer's provider. Give it a fresh context:". Keep the rest of the step unchanged.

7. In `docs/concepts/providers.md` `## Independent review`, append to the paragraph at line 56: "The reviewer's tier follows the track's reasoning; a `low` track whose diff changes more than documentation is reviewed at `medium`. A `low`-tier review accepts a fresh session of the implementer's provider. `gin-workflow reviewer` computes the tier and the route order for the `review` skill."

8. Run: `PYTHONPATH=plugins/gin-workflow/src/scripts:tests python3 -m unittest tests.workflow_core.test_reviewer tests.workflow_core.test_docs_coverage tests.workflow_providers.test_harness_packaging </dev/null` → `OK`; full suite `PYTHONPATH=plugins/gin-workflow/src/scripts timeout 600 python3 -m unittest tests/test_all.py </dev/null` → `OK (skipped=3)`; `bash tests/install_smoke_test.sh </dev/null` → exit 0; then `./install.sh --platform all`.

9. Commit on the feature branch: `feat(review): size reviewers by track tier with gin-workflow reviewer`.

**Acceptance criteria:**
- Every test in `test_reviewer.py` passes; docs coverage and packaging checks pass (the `review` skill stays within its instruction budget); the full suite passes.
- Independent review approves.

## Integration
- **Branch**: `feat/review-tier-routing`
- **Merge strategy**: sequential

## Validation
- [ ] `PYTHONPATH=plugins/gin-workflow/src/scripts timeout 600 python3 -m unittest tests/test_all.py </dev/null` → `OK (skipped=3)`
- [ ] `bash tests/install_smoke_test.sh </dev/null` → exit 0
- [ ] Manual: on the feature branch, `gin-workflow reviewer --base master --implementer claude --tier low` prints `tier medium; independence provider`, a `reason: low track changes non-docs files: ...` line, and no `claude` route

## Notes
- This track changes code, so its own review runs at `medium` whatever tier it declares.
- Model guidance is planning metadata, not Beads state. Concrete providers and models are resolved at orchestration.
- The parent bead stays open until the human-confirmed merge; the track bead closes after tests and review pass.
