# Plan: Review tier routing

## Objective
Agents size each reviewer to the change: `gin-workflow reviewer --bead ID --base SHA` returns the review tier and the ordered reviewer routes, and the `review` skill dispatches from that list. A low-tier (docs) review is no longer blocked when only the implementer's provider is available.

Spec: `.planning/specs/2026-10-07-review-tier-routing-design.md` (bead `gin-workflow-hv9`).

## Global Constraints (from the spec)
- The command is read-only and agent-facing: the `review` skill calls it; users keep invoking `/gin-workflow:review`.
- Base tier: `requested.reasoning` of the bead's assignment entry; without one, `medium` with reason `no assignment manifest`, implementer = main harness.
- Raise rule: base `low` + any non-documentation changed file → `medium`. Documentation: ends in `.md` or under `docs/`, unless a path segment is `skills`. Never lowered; no other rule.
- Independence: at `low` the implementer provider stays in the list; at `medium`/`high` it is removed. `require_independent: false` keeps every candidate; `allow_self_review_fallback` keeps its meaning.
- Exit 0 routes printed; exit 2 for bead not found, bad `--base`, failed `git diff`, unresolvable tier, or an empty list after the independence filter.
- No new configuration keys, no runtime events, no reviewer dispatch.

## Model Guidance
- `default_model_class`: `standard_impl`
- `phase_guidance`:
  - `implement`: `standard_impl`
  - `review`: `standard_impl`
  - `docs`: `cheap_simple`
- `override_rule`: none; the boundaries are settled in the spec.

## Requirement Analysis
- Problem statement: the `review` skill names no reviewer tier, so every review runs high-tier, and provider independence blocks docs reviews when the other providers are out of quota.
- Success criteria: the command returns the tier and routes per the Global Constraints; the skill uses it; tests and docs checks pass.
- Constraints: reuse `resolve_assignment`, `load_effective_config`, `load_provider_local_config`, `main_checkout`; follow the `usage_cli.py` CLI pattern.
- Non-goals: see the spec's Out of scope.

## Approach Options
### Option 1: CLI helper called by the skill
- Summary: a pure routing module plus a thin CLI; the skill runs one command.
- Pros: deterministic, testable, about ten lines of output per review.
- Cons: one more command to document.

### Option 2: Skill prose only
- Summary: describe the rules in the `review` skill; the agent reads the manifest and provider files itself.
- Pros: no code.
- Cons: more tokens per review, inconsistent application, untestable.

### Recommended Approach
- Selected option: Option 1 (confirmed in discuss).
- Reasoning: deterministic rules belong in code; the skill stays short.

## Scope
- In scope: `workflow_core/reviewer.py`, `workflow_core/reviewer_cli.py`, the `reviewer` entry in `workflow_core/cli.py`, tests, the `review` skill, `docs/reference/cli.md`, `docs/concepts/providers.md`.
- Out of scope: the spec's Out of scope list.

## Execution Strategy

```yaml
execution_strategy:
  mode: direct
  workers:
    mode: sequential
  rationale: Two small sequential tracks; Track 2 documents the command Track 1 adds.
```

## Tasks

### Track 1: `gin-workflow reviewer` command

**Metadata:**
- Dependencies: none
- Provider role: `backend`
- Reasoning: `medium`
- Model class: `standard_impl`
- Estimated complexity: low

**Files:**
- Create: `plugins/gin-workflow/src/scripts/workflow_core/reviewer.py`
- Create: `plugins/gin-workflow/src/scripts/workflow_core/reviewer_cli.py`
- Modify: `plugins/gin-workflow/src/scripts/workflow_core/cli.py` (command tuple and usage string, lines 69-70; dispatch after the `usage` branch, lines 82-84)
- Modify: `docs/reference/cli.md` (new section `## \`gin-workflow reviewer\`` before `## \`gin-workflow usage\``; `test_docs_coverage.test_every_cli_subcommand_has_a_heading` requires it)
- Test: `tests/workflow_core/test_reviewer.py`

**Interfaces:**
- `reviewer.is_docs(path: str) -> bool`
- `reviewer.review_tier(base: str, changed: Sequence[str]) -> tuple[str, list[str]]` (tier, reasons)
- `reviewer.ReviewerError(Exception)`
- `reviewer.route(root: Path, bead: str, base: str, *, workflow_id: str, config: EffectiveConfig, local: Mapping[str, ProviderModelConfig]) -> dict[str, Any]` with keys `bead`, `tier`, `base_tier`, `reasons`, `implementer`, `independence`, `routes` (list of `{"provider", "model", "effort"}`)
- `reviewer_cli.main(arguments: Sequence[str]) -> int`

**Steps:**

1. Write `tests/workflow_core/test_reviewer.py`:

```python
"""`gin-workflow reviewer`: review tier and ordered reviewer routes for a bead (agent-facing, read-only)."""

from __future__ import annotations

import io
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))

from team_fixtures import fake_cli, git, path_with, write  # noqa: E402
from workflow_core import reviewer_cli  # noqa: E402
from workflow_core.models import EffectiveConfig  # noqa: E402
from workflow_core.provider_config import ProviderModelConfig  # noqa: E402
from workflow_core.reviewer import ReviewerError, is_docs, review_tier, route  # noqa: E402

LOCAL = {
    "antigravity": ProviderModelConfig("antigravity", "agy", {"low": "g-low", "medium": "g-mid", "high": "g-high"}),
    "claude": ProviderModelConfig("claude", "claude", {"low": "haiku", "medium": "sonnet", "high": "opus"}),
    "codex": ProviderModelConfig("codex", "codex", {"low": "luna", "medium": "sol", "high": "astra"}),
}


def config(root: Path, **review) -> EffectiveConfig:
    return EffectiveConfig({
        "schema_version": "2.3", "harness": "claude",
        "routing": {"roles": {"review": {"preferred": ["antigravity"], "fallback": ["codex", "claude"]}},
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
        tier, reasons = review_tier("low", ["README.md", "src/app.py"])
        self.assertEqual("medium", tier)
        self.assertEqual(["low track changes non-docs files: src/app.py"], reasons)
        self.assertEqual("medium", review_tier("low", ["plugins/x/skills/y/SKILL.md"])[0])

    def test_medium_and_high_never_change_and_empty_diff_keeps_base(self):
        self.assertEqual(("medium", []), review_tier("medium", ["src/app.py"]))
        self.assertEqual(("high", []), review_tier("high", ["README.md"]))
        self.assertEqual(("low", []), review_tier("low", []))


class RepoCase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name) / "repo"
        self.root.mkdir()
        git(self.root, "init", "-q", "-b", "main")
        git(self.root, "commit", "-q", "--allow-empty", "-m", "base")
        self.base = git(self.root, "rev-parse", "HEAD").strip()

    def manifest(self, reasoning: str, provider: str = "claude") -> None:
        write(self.root, ".agent-workflow/runtime/assignments/wf.yaml", json.dumps({
            "workflow_id": "wf", "assignments": [{
                "task_id": "t1", "requested": {"provider_role": "docs", "reasoning": reasoning},
                "resolved": {"provider": provider, "selection_mode": "explicit", "model": "x"}, "fallback": []}]}))

    def change(self, path: str) -> None:
        write(self.root, path, "x\n")
        git(self.root, "add", path)
        git(self.root, "commit", "-q", "-m", path)


class RouteTests(RepoCase):
    def route(self, **review):
        return route(self.root, "t1", self.base, workflow_id="wf", config=config(self.root, **review), local=LOCAL)

    def test_low_docs_review_keeps_the_implementer_provider(self):
        self.manifest("low")
        self.change("docs/a.md")
        out = self.route()
        self.assertEqual(("low", "low", "session"), (out["tier"], out["base_tier"], out["independence"]))
        self.assertEqual([("antigravity", "g-low"), ("codex", "luna"), ("claude", "haiku")],
                         [(r["provider"], r["model"]) for r in out["routes"]])

    def test_low_track_changing_code_reviews_at_medium_without_the_implementer(self):
        self.manifest("low")
        self.change("src/app.py")
        out = self.route()
        self.assertEqual(("medium", "provider"), (out["tier"], out["independence"]))
        self.assertEqual(["low track changes non-docs files: src/app.py"], out["reasons"])
        self.assertEqual([("antigravity", "g-mid"), ("codex", "sol")],
                         [(r["provider"], r["model"]) for r in out["routes"]])

    def test_without_a_manifest_the_tier_is_medium_and_the_main_harness_is_excluded(self):
        self.change("src/app.py")
        out = self.route()
        self.assertEqual(("medium", "claude"), (out["tier"], out["implementer"]))
        self.assertEqual(["no assignment manifest"], out["reasons"])
        self.assertNotIn("claude", [r["provider"] for r in out["routes"]])

    def test_require_independent_false_keeps_the_implementer(self):
        self.manifest("medium")
        self.assertIn("claude", [r["provider"] for r in self.route(require_independent=False)["routes"]])

    def test_empty_list_after_the_filter_is_an_error_unless_self_review_is_allowed(self):
        self.manifest("high", provider="codex")
        cfg = {"routing": {"roles": {"review": {"preferred": ["codex"]}}}}
        only_codex = EffectiveConfig({**config(self.root).to_dict(), **cfg}, self.root)
        with self.assertRaisesRegex(ReviewerError, "no reviewer route independent of codex at tier high"):
            route(self.root, "t1", self.base, workflow_id="wf", config=only_codex, local=LOCAL)
        cfg["routing"]["review"] = {"allow_self_review_fallback": True}
        allowed = EffectiveConfig({**config(self.root).to_dict(), **cfg}, self.root)
        self.assertEqual(["codex"], [r["provider"] for r in route(
            self.root, "t1", self.base, workflow_id="wf", config=allowed, local=LOCAL)["routes"]])

    def test_bad_base_is_an_error(self):
        with self.assertRaisesRegex(ReviewerError, "not a commit: nope"):
            route(self.root, "t1", "nope", workflow_id="wf", config=config(self.root), local=LOCAL)


class ReviewerCliTests(RepoCase):
    def run_cli(self, *args: str, bead_found: bool = True) -> tuple[int, str, str]:
        bin_dir = Path(self.tmp.name) / "bin"
        fake_cli(bin_dir, "bd", [{"argv": ["show", "t1"], "stdout": [{"id": "t1"}]}] if bead_found else [])
        out, err = io.StringIO(), io.StringIO()
        with mock.patch.dict(os.environ, path_with(bin_dir)), \
                mock.patch.object(reviewer_cli, "load_effective_config", return_value=config(self.root)), \
                mock.patch.object(reviewer_cli, "load_provider_local_config", return_value=LOCAL), \
                mock.patch("sys.stdout", out), mock.patch("sys.stderr", err):
            code = reviewer_cli.main(["--bead", "t1", "--base", self.base, "--workflow-id", "wf",
                                      "--repository", str(self.root), *args])
        return code, out.getvalue(), err.getvalue()

    def test_text_and_json_output(self):
        self.manifest("low")
        self.change("docs/a.md")
        code, out, _ = self.run_cli()
        self.assertEqual(0, code)
        self.assertIn("tier low (base low); independence session; implementer claude", out)
        self.assertIn("antigravity g-low", out)
        code, out, _ = self.run_cli("--format", "json")
        self.assertEqual("low", json.loads(out)["tier"])

    def test_unknown_bead_exits_2(self):
        code, _, err = self.run_cli(bead_found=False)
        self.assertEqual(2, code)
        self.assertIn("bead t1 not found", err)

    def test_route_error_exits_2(self):
        self.base = "nope"
        code, _, err = self.run_cli()
        self.assertEqual(2, code)
        self.assertIn("not a commit: nope", err)
```

2. Run: `PYTHONPATH=plugins/gin-workflow/src/scripts:tests python3 -m unittest tests.workflow_core.test_reviewer </dev/null` → fails with `ModuleNotFoundError: No module named 'workflow_core.reviewer'`.

3. Create `plugins/gin-workflow/src/scripts/workflow_core/reviewer.py`:

```python
"""Reviewer routing: the review tier and ordered reviewer routes for a bead (agent-facing, read-only)."""

from __future__ import annotations

from pathlib import Path, PurePosixPath
import subprocess
from typing import Any, Mapping, Sequence

from .assignments import AssignmentRequest, AssignmentResolutionError, resolve_assignment
from .checkout import main_checkout
from .models import EffectiveConfig
from .configuration import require_yaml
from .provider_config import ProviderModelConfig


class ReviewerError(Exception):
    """The reviewer routes cannot be determined (exit 2)."""


def is_docs(path: str) -> bool:
    parts = PurePosixPath(path).parts
    return "skills" not in parts and (path.endswith(".md") or parts[:1] == ("docs",))


def review_tier(base: str, changed: Sequence[str]) -> tuple[str, list[str]]:
    """Raise a low base tier to medium when the diff changes anything but documentation; never lower."""
    code = [path for path in changed if not is_docs(path)]
    if base != "low" or not code:
        return base, []
    return "medium", [f"low track changes non-docs files: {', '.join(code[:3])}"]


def _assignment(root: Path, workflow_id: str, bead: str) -> Mapping[str, Any] | None:
    path = main_checkout(root) / ".agent-workflow/runtime/assignments" / f"{workflow_id}.yaml"
    if not path.is_file():
        return None
    loaded = require_yaml().safe_load(path.read_text(encoding="utf-8")) or {}
    return next((row for row in loaded.get("assignments") or () if row.get("task_id") == bead), None)


def _changed(root: Path, base: str) -> list[str]:
    def git(*argv: str) -> subprocess.CompletedProcess:
        return subprocess.run(["git", *argv], cwd=root, capture_output=True, text=True, check=False)

    if git("rev-parse", "--verify", "--quiet", f"{base}^{{commit}}").returncode != 0:
        raise ReviewerError(f"not a commit: {base}")
    diff = git("diff", "--name-only", f"{base}..HEAD")
    if diff.returncode != 0:
        raise ReviewerError(f"git diff failed: {diff.stderr.strip()}")
    return [line for line in diff.stdout.splitlines() if line]


def route(root: Path, bead: str, base: str, *, workflow_id: str, config: EffectiveConfig,
          local: Mapping[str, ProviderModelConfig]) -> dict[str, Any]:
    entry = _assignment(root, workflow_id, bead)
    if entry:
        base_tier, implementer, reasons = entry["requested"]["reasoning"], entry["resolved"]["provider"], []
    else:
        base_tier, implementer, reasons = "medium", config.harness, ["no assignment manifest"]
    tier, raised = review_tier(base_tier, _changed(root, base))
    try:
        candidates = resolve_assignment(
            AssignmentRequest(bead, "review", tier, config.harness or implementer, workflow_id), config, local)
    except AssignmentResolutionError as error:
        raise ReviewerError(str(error)) from error
    review = (config.get("routing") or {}).get("review") or {}
    independent = bool(review.get("require_independent", True)) and tier != "low"
    routes = [c for c in candidates if not independent or c.provider != implementer]
    if not routes and review.get("allow_self_review_fallback"):
        routes = list(candidates)
    if not routes:
        raise ReviewerError(f"no reviewer route independent of {implementer} at tier {tier}")
    return {
        "bead": bead, "tier": tier, "base_tier": base_tier, "reasons": reasons + raised,
        "implementer": implementer, "independence": "provider" if independent else "session",
        "routes": [{"provider": c.provider, "model": c.model, "effort": c.effort} for c in routes],
    }
```

4. Create `plugins/gin-workflow/src/scripts/workflow_core/reviewer_cli.py`:

```python
"""`gin-workflow reviewer` (agent-facing): exit 0 routes printed, 2 the routes cannot be determined."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import shutil
import subprocess
import sys
from typing import Sequence

from .configuration import ConfigValidationError, load_effective_config
from .provider_config import ProviderLocalConfigError, load_provider_local_config
from .reviewer import ReviewerError, route


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="gin-workflow reviewer")
    parser.add_argument("--bead", required=True)
    parser.add_argument("--base", required=True)
    parser.add_argument("--workflow-id", default="default-workflow")
    parser.add_argument("--repository", type=Path, default=Path.cwd())
    parser.add_argument("--format", choices=("text", "json"), default="text")
    return parser


def _bead_exists(root: Path, bead: str) -> bool:
    executable = shutil.which("bd")
    return executable is not None and subprocess.run(
        [executable, "show", bead, "--json"], cwd=root, capture_output=True, text=True, check=False,
        timeout=120).returncode == 0


def main(arguments: Sequence[str]) -> int:
    args = _parser().parse_args(list(arguments))
    root = args.repository.resolve()
    try:
        if not _bead_exists(root, args.bead):
            raise ReviewerError(f"bead {args.bead} not found")
        out = route(root, args.bead, args.base, workflow_id=args.workflow_id,
                    config=load_effective_config(root), local=load_provider_local_config(root))
    except (ReviewerError, ConfigValidationError, ProviderLocalConfigError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 2
    if args.format == "json":
        print(json.dumps(out, indent=2, sort_keys=True))
        return 0
    lines = [f"tier {out['tier']} (base {out['base_tier']}); independence {out['independence']}; "
             f"implementer {out['implementer']}"]
    lines += [f"reason: {reason}" for reason in out["reasons"]]
    lines += [" ".join(filter(None, (r["provider"], r["model"], r["effort"]))) for r in out["routes"]]
    print("\n".join(lines))
    return 0
```

5. In `workflow_core/cli.py`, add `"reviewer"` to the command tuple and the usage string at lines 69-70, and after the `usage` branch:

```python
    if argv[0] == "reviewer":
        from .reviewer_cli import main as reviewer_main
        return reviewer_main(argv[1:])
```

6. In `docs/reference/cli.md`, before `## \`gin-workflow usage\``:

~~~markdown
## `gin-workflow reviewer`

```
gin-workflow reviewer --bead ID --base SHA [--workflow-id ID] [--format text|json]
```

Called by the `review` skill to pick the reviewer; you do not need to run it. Prints the review tier and the reviewer routes in order. The tier is the track's reasoning from the assignment manifest (`medium` without one); a `low` track whose diff since `--base` changes anything but documentation (`*.md` or `docs/`, excluding `skills/`) is reviewed at `medium`. At `low` the implementer's provider may review in a fresh session; at `medium` and `high` it is excluded unless `routing.review.require_independent` is false.

Exit codes: 0 routes printed; 2 unknown bead, bad `--base`, no route for the tier, or no independent route.
~~~

7. Run: `PYTHONPATH=plugins/gin-workflow/src/scripts:tests python3 -m unittest tests.workflow_core.test_reviewer tests.workflow_core.test_docs_coverage </dev/null` → `OK`. Then the full suite `PYTHONPATH=plugins/gin-workflow/src/scripts timeout 600 python3 -m unittest tests/test_all.py </dev/null` → `OK (skipped=3)`.

8. Commit on the feature branch: `feat(review): add gin-workflow reviewer to size reviewers by track tier`.

**Acceptance criteria:**
- Every test in `test_reviewer.py` passes; the docs coverage test passes; the full suite passes.
- Independent review approves.

### Track 2: `review` skill and provider docs

**Metadata:**
- Dependencies: Track 1
- Provider role: `docs`
- Reasoning: `low`
- Model class: `cheap_simple`
- Estimated complexity: low

**Files:**
- Modify: `plugins/gin-workflow/src/skills/review/SKILL.md` (Requesting step 2, line 16)
- Modify: `docs/concepts/providers.md` (section `## Independent review`, line 56)

**Interfaces:** consumes `gin-workflow reviewer` from Track 1.

**Steps:**

1. In `review/SKILL.md` Requesting step 2, after "Dispatch an independent reviewer with a fresh context:" insert: "pick it with `gin-workflow reviewer --bead <id> --base <ledger base>` and use the first route whose provider is available, with its model, trying the next on a quota, rate-limit, or timeout failure; an exit 2 means `human_decision_required`. Use actor id `reviewer:<provider>`, or `reviewer:<provider>:session-<id>` when the provider is the implementer's. Give it". Keep the rest of the sentence (the context list) unchanged.

2. In `docs/concepts/providers.md` `## Independent review`, append to the paragraph at line 56: "The reviewer's tier follows the track's reasoning; a `low` track whose diff changes more than documentation is reviewed at `medium`. A `low`-tier review accepts a fresh session of the implementer's provider. `gin-workflow reviewer` computes the tier and the route order for the `review` skill."

3. Run: `PYTHONPATH=plugins/gin-workflow/src/scripts:tests python3 -m unittest tests.workflow_providers.test_harness_packaging tests.workflow_core.test_docs_coverage </dev/null` → `OK`; full suite → `OK (skipped=3)`; `bash tests/install_smoke_test.sh </dev/null` → exit 0; then `./install.sh --platform all` so the installed snapshot has the new skill text.

4. Commit: `docs(review): dispatch reviewers from gin-workflow reviewer`.

**Acceptance criteria:**
- The skill stays within its instruction budget; packaging and docs checks pass.
- Independent review approves.

## Integration
- **Branch**: `feat/review-tier-routing`
- **Merge strategy**: sequential

## Validation
- [ ] `PYTHONPATH=plugins/gin-workflow/src/scripts timeout 600 python3 -m unittest tests/test_all.py </dev/null` → `OK (skipped=3)`
- [ ] `bash tests/install_smoke_test.sh </dev/null` → exit 0
- [ ] Manual: in this repository, `gin-workflow reviewer --bead gin-workflow-t68.4 --base 4c708ac --workflow-id teamwork-hardening` prints `tier medium (base low); independence provider; implementer antigravity`, a `reason: low track changes non-docs files: ...` line (Track 4 changed `skills/gin-team/SKILL.md`), and no `antigravity` route

## Notes
- Track 2 is itself the first user of the rule: its base tier is `low`, but it changes `skills/review/SKILL.md`, so its review runs at `medium`.
- Model guidance is planning metadata, not Beads state. Concrete providers and models are resolved at orchestration.
- The parent bead stays open until the human-confirmed merge; track beads close after tests and review pass.
