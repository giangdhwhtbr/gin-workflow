"""`gin-workflow reviewer`: review route and ordered reviewer routes (agent-facing, read-only)."""

from __future__ import annotations

import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))

from team_fixtures import git, write  # noqa: E402
from tests.workflow_core.orchestrator_fakes import fake_orchestrator, on_path  # noqa: E402
from workflow_core import reviewer  # noqa: E402
from workflow_core.catalog import DEFAULT_CATALOGS  # noqa: E402
from workflow_core.models import EffectiveConfig  # noqa: E402
from workflow_core.reviewer import ReviewerError, is_docs, review_route, route  # noqa: E402


def config(root: Path, harness: str = "claude", provider_mode: str = "single", **review) -> EffectiveConfig:
    return EffectiveConfig(
        {
            "schema_version": "2.9",
            "harness": harness,
            "provider_mode": provider_mode,
            "routing": {"review": review},
        },
        root,
    )


class ReviewRouteTests(unittest.TestCase):
    def test_docs_detection(self):
        self.assertTrue(is_docs("README.md"))
        self.assertTrue(is_docs("docs/guide/setup.txt"))
        self.assertFalse(is_docs("plugins/x/src/skills/review/SKILL.md"))
        self.assertFalse(is_docs("src/app.py"))

    def test_low_with_only_docs_stays_low(self):
        catalog = DEFAULT_CATALOGS["claude"]
        self.assertEqual(("haiku", "low", None), review_route(catalog, "haiku", "low", ["README.md", "docs/a.md"]))

    def test_low_with_code_or_skill_becomes_medium(self):
        catalog = DEFAULT_CATALOGS["claude"]
        self.assertEqual(
            ("sonnet", "low", "non-docs files changed"),
            review_route(catalog, "haiku", "low", ["README.md", "src/app.py"]),
        )
        self.assertEqual(
            ("sonnet", None, "non-docs files changed"),
            review_route(catalog, "haiku", None, ["plugins/x/skills/y/SKILL.md"]),
        )

    def test_medium_and_high_never_change_and_empty_diff_keeps_the_route(self):
        catalog = DEFAULT_CATALOGS["claude"]
        self.assertEqual(("sonnet", "medium", None), review_route(catalog, "sonnet", "medium", ["src/app.py"]))
        self.assertEqual(("opus", "high", None), review_route(catalog, "opus", "high", ["README.md"]))
        self.assertEqual(("haiku", "low", None), review_route(catalog, "haiku", "low", []))


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
        out = route(self.root, self.base, model="sonnet", effort="medium", implementer="claude", config=config(self.root, harness="claude"))
        self.assertEqual(out["model"], "sonnet")
        self.assertEqual(out["effort"], "medium")
        self.assertEqual(len(out["routes"]), 1)
        r = out["routes"][0]
        self.assertEqual(r["provider"], "claude")
        self.assertEqual(r["model"], "sonnet")
        self.assertEqual(r["effort"], "medium")
        self.assertRegex(r["actor_id"], r"^reviewer:claude:session-[0-9a-f]{8}$")

    def test_reviewer_haiku_with_changed_py_file_returns_sonnet_and_reason(self):
        self.change("src/app.py")
        out = route(self.root, self.base, model="haiku", effort="low", implementer="claude", config=config(self.root, harness="claude"))
        self.assertEqual(out["model"], "sonnet")
        self.assertEqual(out["effort"], "low")
        self.assertEqual(out["reason"], "non-docs files changed")
        self.assertEqual(out["routes"][0]["model"], "sonnet")

    def test_reviewer_haiku_with_only_md_changes_stays_haiku(self):
        self.change("docs/guide.md")
        out = route(self.root, self.base, model="haiku", effort="low", implementer="claude", config=config(self.root, harness="claude"))
        self.assertEqual(out["model"], "haiku")
        self.assertIsNone(out["reason"])
        self.assertEqual(out["routes"][0]["model"], "haiku")

    def test_tier_flag_is_rejected_by_argparse(self):
        stdout = io.StringIO()
        stderr = io.StringIO()
        with mock.patch("sys.stdout", stdout), mock.patch("sys.stderr", stderr):
            code = reviewer.main([
                "--base", self.base,
                "--implementer", "claude",
                "--tier", "medium",
                "--repository", str(self.root),
            ])
        self.assertEqual(2, code)

    def test_reviewer_of_another_implementer_is_provider_independent(self):
        out = route(self.root, self.base, model="sonnet", effort=None, implementer="codex", config=config(self.root, harness="claude"))
        self.assertEqual(len(out["routes"]), 1)
        r = out["routes"][0]
        self.assertEqual(r["provider"], "claude")
        self.assertEqual(r["actor_id"], "reviewer:claude")

    def test_provider_independence_without_orchestrator_warns(self):
        cfg = config(self.root, harness="claude", independence="provider")
        out = route(self.root, self.base, model="sonnet", effort=None, implementer="claude", config=cfg)
        self.assertEqual(len(out["warnings"]), 1)
        self.assertIn("gin-orchestrator", out["warnings"][0])

    def test_json_flag_prints_the_routes_document(self):
        stdout = io.StringIO()
        with mock.patch.object(reviewer, "load_effective_config", return_value=config(self.root, harness="claude")), \
                mock.patch("sys.stdout", stdout):
            code = reviewer.main([
                "--base", self.base,
                "--implementer", "claude",
                "--model", "sonnet",
                "--effort", "medium",
                "--repository", str(self.root),
                "--json",
            ])
        self.assertEqual(code, 0)
        doc = json.loads(stdout.getvalue())
        self.assertEqual(doc["model"], "sonnet")
        self.assertEqual(doc["effort"], "medium")
        self.assertEqual(len(doc["routes"]), 1)
        self.assertEqual(doc["routes"][0]["provider"], "claude")
        self.assertEqual(doc["routes"][0]["model"], "sonnet")
        self.assertEqual(doc["routes"][0]["effort"], "medium")
        self.assertRegex(doc["routes"][0]["actor_id"], r"^reviewer:claude:session-[0-9a-f]{8}$")

    def test_multi_mode_returns_orchestrator_routes(self):
        cfg = config(self.root, harness="claude", provider_mode="multi")
        orch_routes = [{"provider": "codex", "model": "opus", "effort": None, "actor_id": "reviewer:codex"}]
        with tempfile.TemporaryDirectory() as fake_dir:
            fake_orchestrator(fake_dir, contract=2, capabilities=["reviewer"], replies={"reviewer": orch_routes})
            with on_path(fake_dir):
                out = route(self.root, self.base, model="sonnet", effort="medium", implementer="claude", config=cfg)
                self.assertEqual(orch_routes, out["routes"])

    def test_empty_orchestrator_routes_exit_2(self):
        cfg = config(self.root, harness="claude", provider_mode="multi")
        with tempfile.TemporaryDirectory() as fake_dir:
            fake_orchestrator(fake_dir, contract=2, capabilities=["reviewer"], replies={"reviewer": []})
            with on_path(fake_dir):
                with self.assertRaises(ReviewerError):
                    route(self.root, self.base, model="sonnet", effort="medium", implementer="claude", config=cfg)

    def test_failing_orchestrator_reviews_on_the_main_harness_with_warning(self):
        cfg = config(self.root, harness="claude", provider_mode="multi")
        with tempfile.TemporaryDirectory() as fake_dir:
            fake_orchestrator(fake_dir, contract=2, capabilities=["reviewer"], fail=["reviewer"])
            with on_path(fake_dir):
                out = route(self.root, self.base, model="sonnet", effort="medium", implementer="claude", config=cfg)
                self.assertEqual("claude", out["routes"][0]["provider"])
                self.assertTrue(
                    any("gin-orchestrator failed" in w for w in out["warnings"]),
                    out["warnings"],
                )

    def test_malformed_orchestrator_reply_reviews_on_the_main_harness_with_warning(self):
        cfg = config(self.root, harness="claude", provider_mode="multi")
        for reply in ({"routes": []}, ["codex"]):
            with tempfile.TemporaryDirectory() as fake_dir:
                fake_orchestrator(fake_dir, contract=2, capabilities=["reviewer"], replies={"reviewer": reply})
                with on_path(fake_dir):
                    out = route(self.root, self.base, model="sonnet", effort="medium", implementer="claude", config=cfg)
                    self.assertEqual("claude", out["routes"][0]["provider"], reply)
                    self.assertIn("gin-orchestrator failed (orchestrator_failed); reviewing on the main harness",
                                  out["warnings"])


if __name__ == "__main__":
    unittest.main()
