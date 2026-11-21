"""Tests for gin attach prune over a real bd and a LocalStore."""

from __future__ import annotations

from contextlib import redirect_stdout
from datetime import datetime, timezone
import hashlib
import io
import json
from pathlib import Path
import shutil
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "plugins/gin-workflow/src/scripts"))

from team_fixtures import git, init_beads  # noqa: E402
from test_attachments import bd  # noqa: E402
from workflow_core import attach_cli, attachments  # noqa: E402
from workflow_core.attach_store import LocalStore, StoreError  # noqa: E402
from workflow_core.attachments import AttachmentError, Settings  # noqa: E402
from workflow_core.configuration import resolve_effective_config  # noqa: E402

NOW = datetime(2026, 11, 21, 9, 30, tzinfo=timezone.utc)
NOTE = "run bd dolt pull first: a blob whose entry has not reached this machine counts as an orphan"


@unittest.skipUnless(shutil.which("bd"), "bd is not installed")
class PruneTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.tmp = Path(tmp.name)
        self.repo = self.tmp / "repo"
        self.repo.mkdir()
        git(self.repo, "init", "-q", "-b", "main")
        git(self.repo, "config", "user.email", "t@corp.com")
        git(self.repo, "config", "user.name", "T")
        init_beads(self.repo)
        (self.repo / ".agent-workflow").mkdir()
        (self.repo / ".agent-workflow/config.yaml").write_text(
            "schema_version: '2.11'\nproviders:\n  task_tracking: beads\n", encoding="utf-8")
        resolve_effective_config(self.repo)
        self.store = LocalStore(self.tmp / "store")
        self.closed_at = {}
        self.retention = None
        for patcher in (mock.patch.object(attachments, "_rows", self.rows),
                        mock.patch.object(attachments, "load_settings", self.settings),
                        mock.patch.object(attachments, "open_store", lambda repo, settings: self.store)):
            patcher.start()
            self.addCleanup(patcher.stop)

    def settings(self, repo):
        return Settings(store="local", retention_days=self.retention)

    def rows(self, repo):
        data = json.loads(bd(self.repo, "list", "--all", "-n", "0", "--json"))
        for row in data:
            if row["id"] in self.closed_at:
                row["closed_at"] = self.closed_at[row["id"]]
        return data

    def blob(self, text):
        data = text.encode()
        sha = hashlib.sha256(data).hexdigest()
        return sha, self.store.put(sha, data)

    def bead(self, *blobs, closed=None, raw=None, extra=None):
        bid = json.loads(bd(self.repo, "create", "B", "-t", "task", "--json"))["id"]
        held = [{"sha256": sha, "name": "f.png", "path": path, "extra": 1, **(extra or {})} for sha, path in blobs]
        bd(self.repo, "update", bid, "--set-metadata", f"attachments={raw if raw is not None else json.dumps(held)}")
        if closed:
            bd(self.repo, "close", bid)
            self.closed_at[bid] = closed
        return bid

    def stored(self, bid):
        data = json.loads(bd(self.repo, "show", bid, "--json"))
        return attachments.entries(data[0] if isinstance(data, list) else data)

    def prune(self, **kw):
        return attachments.prune(self.repo, now=NOW, **kw)

    def test_orphan_listed_and_dry_run_changes_nothing(self):
        sha, path = self.blob("orphan")
        found = self.prune()
        self.assertEqual(found, {"candidates": [{"path": path, "sha256": sha, "reason": "orphan", "beads": []}],
                                 "applied": False})
        self.assertEqual(self.store.paths(), {path})

    def test_retention_rules(self):
        self.retention = 30
        old, new, shared, kept = (self.blob(t) for t in ("old", "new", "shared", "open"))
        a = self.bead(old, closed="2026-10-12T00:00:00Z")
        self.bead(new, closed="2026-11-11T00:00:00Z")
        self.bead(shared, closed="2026-10-01T00:00:00Z")
        self.bead(shared)
        self.bead(kept)
        found = self.prune()["candidates"]
        self.assertEqual([(c["path"], c["reason"], c["beads"]) for c in found],
                         [(old[1], "closed 2026-10-12", [a])])

    def test_without_retention_only_orphans(self):
        self.bead(self.blob("old"), closed="2020-01-01T00:00:00Z")
        self.assertEqual(self.prune()["candidates"], [])

    def test_apply_removes_listed_paths_and_stamps_entries(self):
        self.retention = 30
        old, orphan, other = self.blob("old"), self.blob("orphan"), self.blob("other")
        bid = self.bead(old, other, closed="2026-01-01T00:00:00Z")
        self.bead(other)
        result = self.prune(apply=True)
        self.assertTrue(result["applied"])
        self.assertEqual({c["path"] for c in result["candidates"]}, {old[1], orphan[1]})
        self.assertEqual(self.store.paths(), {other[1]})
        first, second = self.stored(bid)
        self.assertEqual(first["pruned_at"], "2026-11-21T09:30:00Z")
        self.assertEqual(first["extra"], 1)
        self.assertNotIn("pruned_at", second)

    def test_pruned_entries_are_not_references(self):
        sha, path = self.blob("gone")
        self.bead((sha, path), extra={"pruned_at": "2026-01-01T00:00:00Z"})
        found = self.prune()["candidates"]
        self.assertEqual([c["reason"] for c in found], ["orphan"])

    def test_unreadable_metadata_stops_prune(self):
        _, path = self.blob("x")
        bad = self.bead(raw="not json")
        for apply in (False, True):
            with self.assertRaises(AttachmentError) as ctx:
                self.prune(apply=apply)
            self.assertIn(bad, str(ctx.exception))
        self.assertEqual(self.store.paths(), {path})

    def test_remove_error_stamps_nothing(self):
        self.retention = 30
        bid = self.bead(self.blob("old"), closed="2026-01-01T00:00:00Z")
        with mock.patch.object(self.store, "remove", side_effect=StoreError("moved")):
            with self.assertRaises(StoreError):
                self.prune(apply=True)
        self.assertNotIn("pruned_at", self.stored(bid)[0])

    def run_cli(self, *argv):
        out = io.StringIO()
        with redirect_stdout(out):
            code = attach_cli.main(["prune", "--repository", str(self.repo), *argv])
        return code, out.getvalue()

    def test_cli_text_and_json(self):
        _, path = self.blob("orphan")
        code, text = self.run_cli()
        self.assertEqual((code, text.splitlines()), (0, [f"{path} orphan", NOTE]))
        code, text = self.run_cli("--format", "json")
        self.assertEqual(json.loads(text)["applied"], False)
        self.assertEqual(json.loads(text)["candidates"][0]["path"], path)
        code, text = self.run_cli("--apply")
        self.assertEqual(text.splitlines(), [f"{path} orphan"])
        self.assertEqual(self.store.paths(), set())


if __name__ == "__main__":
    unittest.main()
