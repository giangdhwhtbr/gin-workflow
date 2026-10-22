"""`gin-workflow reviewer`: review tier and ordered reviewer routes (agent-facing, read-only)."""

from __future__ import annotations

import io
import json
from pathlib import Path
import re
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))

from team_fixtures import git, write  # noqa: E402
from workflow_core import reviewer  # noqa: E402
from workflow_core.models import EffectiveConfig  # noqa: E402
from workflow_core.reviewer import ReviewerError, is_docs, review_tier, route  # noqa: E402


def config(root: Path, harness: str = "claude", **review) -> EffectiveConfig:
    return EffectiveConfig(
        {
            "schema_version": "2.7",
            "harness": harness,
            "routing": {"review": review},
        },
        root,
    )


class ReviewTierTests(unittest.TestCase):
    def test_docs_detection(self):
        self.assertTrue(is_docs("README.md"))
        self.assertTrue(is_docs("docs/guide/setup.txt"))
        self.assertFalse(is_docs("plugins/x/src/skills/review/SKILL.md"))
        self.assertFalse(is_docs("src/app.py"))

    def test_low_with_only_docs_stays_low(self):
        self.assertEqual(("low", None), review_tier("low", ["README.md", "docs/a.md"]))

    def test_low_with_code_or_skill_becomes_medium(self):
        self.assertEqual(
            ("medium", "low track changes non-docs files: src/app.py"),
            review_tier("low", ["README.md", "src/app.py"]),
        )
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

    def test_reviewer_runs_on_the_main_harness_in_a_fresh_session(self):
        out = route(self.root, self.base, tier="medium", implementer="claude", config=config(self.root, harness="claude"))
        self.assertEqual(out["tier"], "medium")
        self.assertEqual(len(out["routes"]), 1)
        r = out["routes"][0]
        self.assertEqual(r["provider"], "claude")
        self.assertEqual(r["model"], "sonnet")
        self.assertIsNone(r["effort"])
        self.assertRegex(r["actor_id"], r"^reviewer:claude:session-[0-9a-f]{8}$")

    def test_reviewer_of_another_implementer_is_provider_independent(self):
        out = route(self.root, self.base, tier="medium", implementer="codex", config=config(self.root, harness="claude"))
        self.assertEqual(len(out["routes"]), 1)
        r = out["routes"][0]
        self.assertEqual(r["provider"], "claude")
        self.assertEqual(r["actor_id"], "reviewer:claude")

    def test_provider_independence_without_orchestrator_warns(self):
        cfg = config(self.root, harness="claude", independence="provider")
        out = route(self.root, self.base, tier="medium", implementer="claude", config=cfg)
        self.assertEqual(len(out["warnings"]), 1)
        self.assertIn("gin-orchestrator", out["warnings"][0])

    def test_json_flag_prints_the_routes_document(self):
        stdout = io.StringIO()
        with mock.patch.object(reviewer, "load_effective_config", return_value=config(self.root, harness="claude")), \
                mock.patch("sys.stdout", stdout):
            code = reviewer.main([
                "--base", self.base,
                "--implementer", "claude",
                "--tier", "medium",
                "--repository", str(self.root),
                "--json",
            ])
        self.assertEqual(code, 0)
        doc = json.loads(stdout.getvalue())
        self.assertEqual(doc["tier"], "medium")
        self.assertEqual(len(doc["routes"]), 1)
        self.assertEqual(doc["routes"][0]["provider"], "claude")
        self.assertRegex(doc["routes"][0]["actor_id"], r"^reviewer:claude:session-[0-9a-f]{8}$")


if __name__ == "__main__":
    unittest.main()
