"""scripts/upstream_watch.py: one bead per run for upstream lines that touch gin, and one for a source it cannot read."""

from __future__ import annotations

import importlib.util
import io
import json
from pathlib import Path
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("upstream_watch", ROOT / "scripts/upstream_watch.py")
upstream_watch = importlib.util.module_from_spec(spec)
spec.loader.exec_module(upstream_watch)

CHANGELOG = """# Changelog

## 2.1.12

- Added a `PreCompact` hook matcher
- Faster startup

## 2.1.11

- Reserved the /ship command name
- Fixed a typo

## 2.1.10

- Changed how plugin skills load
"""
RELEASES = [
    {"tag_name": "v1.4.0-rc.2", "published_at": "2026-11-20T00:00:00Z", "prerelease": True,
     "body": "- Schema v74 migration is one-way\n- New colors"},
    {"tag_name": "v1.3.4", "published_at": "2026-11-04T00:00:00Z", "prerelease": False,
     "body": "- bd update needs --force to take a claim"},
]
SURFACES = {"claude-code": {"hooks": ["hook"], "commands": ["/ship"], "plugins": ["plugin"]},
            "beads": {"data": ["schema"], "commands": ["bd update"]}}


class UpstreamWatchTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.state = Path(directory.name) / "runtime/upstream-watch.json"
        self.filed: list[tuple[str, str]] = []

    def fetch(self, url):
        return CHANGELOG if url == upstream_watch.CHANGELOG_URL else json.dumps(RELEASES)

    def run_watch(self, *, fetch=None, dry_run=False):
        out = io.StringIO()
        code = upstream_watch.run(self.state, fetch=fetch or self.fetch,
                                  file_bead=lambda title, text: self.filed.append((title, text)),
                                  surfaces=SURFACES, dry_run=dry_run, out=out)
        return code, out.getvalue()

    def save(self, claude, beads):
        self.state.parent.mkdir(parents=True, exist_ok=True)
        self.state.write_text(json.dumps({"claude-code": claude, "beads": beads}), encoding="utf-8")

    def test_the_first_run_records_the_baseline_and_files_nothing(self):
        self.assertEqual(0, self.run_watch()[0])
        self.assertEqual([], self.filed)
        self.assertEqual({"claude-code": "2.1.12", "beads": "2026-11-20T00:00:00Z"},
                         json.loads(self.state.read_text(encoding="utf-8")))

    def test_a_later_run_files_one_bead_with_the_new_matching_lines(self):
        self.save("2.1.10", "2026-11-04T00:00:00Z")
        self.assertEqual(0, self.run_watch()[0])
        [(title, text)] = self.filed
        self.assertEqual("Upstream changes: Claude Code 2.1.11 to 2.1.12; Beads v1.4.0-rc.2", title)
        self.assertIn("Added a `PreCompact` hook matcher (hooks)", text)
        self.assertIn("Reserved the /ship command name (commands)", text)
        self.assertIn("v1.4.0-rc.2 (release candidate)", text)
        self.assertIn("Schema v74 migration is one-way (data)", text)
        for absent in ("Faster startup", "plugin skills", "--force", "New colors"):
            self.assertNotIn(absent, text)
        self.assertEqual({"claude-code": "2.1.12", "beads": "2026-11-20T00:00:00Z"},
                         json.loads(self.state.read_text(encoding="utf-8")))

    def test_no_matching_line_files_nothing_and_advances_the_state(self):
        self.save("2.1.12", "2026-11-04T00:00:00Z")
        quiet = [dict(RELEASES[0], body="- New colors"), RELEASES[1]]
        self.assertEqual(0, self.run_watch(fetch=lambda url: CHANGELOG if "CHANGELOG" in url
                                           else json.dumps(quiet))[0])
        self.assertEqual([], self.filed)
        self.assertEqual("2026-11-20T00:00:00Z", json.loads(self.state.read_text(encoding="utf-8"))["beads"])

    def test_a_source_that_fails_files_a_bead_and_keeps_its_state(self):
        self.save("2.1.10", "2026-11-04T00:00:00Z")

        def fetch(url):
            if url == upstream_watch.RELEASES_URL:
                raise OSError("HTTP Error 403: rate limit exceeded")
            return CHANGELOG

        code, _ = self.run_watch(fetch=fetch)
        self.assertEqual(1, code)
        titles = [title for title, _ in self.filed]
        self.assertIn("Upstream check could not read Beads releases", titles)
        self.assertIn("Upstream changes: Claude Code 2.1.11 to 2.1.12", titles)
        saved = json.loads(self.state.read_text(encoding="utf-8"))
        self.assertEqual(("2.1.12", "2026-11-04T00:00:00Z"), (saved["claude-code"], saved["beads"]))

    def test_a_bead_that_cannot_be_filed_keeps_the_state(self):
        self.save("2.1.10", "2026-11-04T00:00:00Z")

        def refuse(title, text):
            raise RuntimeError("gin task create failed")

        out = io.StringIO()
        code = upstream_watch.run(self.state, fetch=self.fetch, file_bead=refuse, surfaces=SURFACES, out=out)
        self.assertEqual(2, code)
        self.assertEqual("2.1.10", json.loads(self.state.read_text(encoding="utf-8"))["claude-code"])

    def test_dry_run_files_and_writes_nothing(self):
        self.save("2.1.10", "2026-11-04T00:00:00Z")
        code, out = self.run_watch(dry_run=True)
        self.assertEqual(0, code)
        self.assertEqual([], self.filed)
        self.assertIn("Upstream changes: Claude Code 2.1.11 to 2.1.12", out)
        self.assertEqual("2.1.10", json.loads(self.state.read_text(encoding="utf-8"))["claude-code"])

    def test_a_source_that_failed_the_first_time_records_only_its_baseline_later(self):
        def fetch(url):
            if url == upstream_watch.RELEASES_URL:
                raise OSError("HTTP Error 403: rate limit exceeded")
            return CHANGELOG

        self.assertEqual(1, self.run_watch(fetch=fetch)[0])
        self.assertEqual({"claude-code": "2.1.12"}, json.loads(self.state.read_text(encoding="utf-8")))
        self.filed.clear()
        code, out = self.run_watch()
        self.assertEqual(0, code)
        self.assertEqual([], self.filed)
        self.assertEqual("2026-11-20T00:00:00Z", json.loads(self.state.read_text(encoding="utf-8"))["beads"])
        self.assertEqual(1, out.count("baseline recorded"))

    def test_releases_without_a_date_are_a_failed_read_not_an_empty_baseline(self):
        undated = [{"tag_name": "v1.0.0", "body": "- schema change"}]
        code, _ = self.run_watch(fetch=lambda url: CHANGELOG if "CHANGELOG" in url else json.dumps(undated))
        self.assertEqual(1, code)
        self.assertEqual(["Upstream check could not read Beads releases"], [title for title, _ in self.filed])
        self.assertEqual({"claude-code": "2.1.12"}, json.loads(self.state.read_text(encoding="utf-8")))

    def test_an_invalid_state_file_files_a_bead_and_is_replaced_by_a_baseline(self):
        for broken in ('{"claude-code": "2.1.1', '["2.1.10"]', '{"claude-code": 5}', '{"claude-code": "latest"}'):
            with self.subTest(broken=broken):
                self.filed.clear()
                self.state.parent.mkdir(parents=True, exist_ok=True)
                self.state.write_text(broken, encoding="utf-8")
                self.assertEqual(1, self.run_watch()[0])
                [(title, text)] = self.filed
                self.assertEqual("Upstream check could not read its state file", title)
                self.assertIn(str(self.state), text)
                self.assertEqual({"claude-code": "2.1.12", "beads": "2026-11-20T00:00:00Z"},
                                 json.loads(self.state.read_text(encoding="utf-8")))

    def test_the_surface_list_names_every_bd_subcommand_gin_calls(self):
        surfaces = json.loads((ROOT / "scripts/upstream_surfaces.json").read_text(encoding="utf-8"))
        keywords = {keyword for words in surfaces["beads"].values() for keyword in words}
        called = upstream_watch.bd_subcommands(ROOT / "plugins/gin-workflow/src/scripts")
        self.assertTrue({"show", "list", "update", "ready", "config", "dolt"} <= called, called)
        self.assertEqual([], sorted(name for name in called if f"bd {name}" not in keywords))


if __name__ == "__main__":
    unittest.main()
