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
        self.assertEqual(("low", None), review_tier("low", ["README.md", "docs/a.md"]))

    def test_low_with_code_or_skill_becomes_medium(self):
        self.assertEqual(("medium", "low track changes non-docs files: src/app.py"),
                         review_tier("low", ["README.md", "src/app.py"]))
        self.assertEqual("medium", review_tier("low", ["plugins/x/skills/y/SKILL.md"])[0])

    def test_medium_and_high_never_change_and_empty_diff_keeps_the_tier(self):
        self.assertEqual(("medium", None), review_tier("medium", ["src/app.py"]))
        self.assertEqual(("high", None), review_tier("high", ["README.md"]))
        self.assertEqual(("low", None), review_tier("low", []))


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
        self.assertEqual(("medium", "low track changes non-docs files: src/app.py"), (out["tier"], out["reason"]))
        self.assertEqual([("antigravity", "g-mid"), ("codex", "sol")], [r[:2] for r in out["routes"]])

    def test_commits_added_to_the_base_branch_later_are_not_counted(self):
        git(self.root, "checkout", "-q", "-b", "track")
        self.change("docs/a.md")
        git(self.root, "checkout", "-q", "main")
        self.change("src/app.py")
        git(self.root, "checkout", "-q", "track")
        self.base = "main"
        self.assertEqual("antigravity g-low", self.providers("low")[0])

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
        with self.assertRaisesRegex(ReviewerError, r"git diff nope\.\.\.HEAD failed"):
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

        self.assertEqual((0, "tier low\nantigravity g-low\ncodex luna\nclaude haiku\n"),
                         run(self.base))
        code, text = run("nope")
        self.assertEqual(2, code)
        self.assertIn("git diff nope...HEAD failed", text)
