"""Tests for workflow_core.attachments add, list, fetch and push over a real bd and a LocalStore."""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import shutil
import struct
import subprocess
import sys
import tempfile
import unittest
from unittest import mock
import zlib

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "plugins/gin-workflow/src/scripts"))

from team_fixtures import git, init_beads  # noqa: E402
from workflow_core import attachments  # noqa: E402
from workflow_core.configuration import resolve_effective_config  # noqa: E402
from workflow_core.attach_store import LocalStore, blob_path  # noqa: E402
from workflow_core.attachments import AttachmentError, Settings  # noqa: E402

NOW = datetime(2026, 11, 21, 9, 30, tzinfo=timezone.utc)


def _chunk(kind, data):
    return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data))


_MAGIC = b"\x89PNG\r\n\x1a\n"
PNG = _MAGIC + _chunk(b"IHDR", bytes(13)) + _chunk(b"tEXt", b"k\x00v") + _chunk(b"IDAT", b"px") + _chunk(b"IEND", b"")
CLEAN_PNG = _MAGIC + _chunk(b"IHDR", bytes(13)) + _chunk(b"IDAT", b"px") + _chunk(b"IEND", b"")


def bd(root, *args):
    return subprocess.run(["bd", *args], cwd=root, check=True, capture_output=True, text=True,
                          stdin=subprocess.DEVNULL, timeout=60).stdout


class EntriesTests(unittest.TestCase):
    def test_entries_reads_string_and_list(self):
        item = {"sha256": "a" * 64}
        self.assertEqual(attachments.entries({"metadata": {"attachments": json.dumps([item])}}), [item])
        self.assertEqual(attachments.entries({"metadata": {"attachments": [item]}}), [item])

    def test_entries_ignores_anything_else(self):
        for row in ({}, {"metadata": None}, {"metadata": {"attachments": "nope"}},
                    {"metadata": {"attachments": 3}}, {"metadata": {"attachments": ["x"]}}):
            self.assertEqual(attachments.entries(row), [])

    def test_reference(self):
        self.assertEqual(attachments.reference({"sha256": "ab", "name": "f.png", "caption": "Login"}),
                         "![Login](attachment:ab)")
        self.assertEqual(attachments.reference({"sha256": "ab", "name": "f.png", "caption": None}),
                         "![f.png](attachment:ab)")


@unittest.skipUnless(shutil.which("bd"), "bd is not installed")
class AttachmentsTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.tmp = Path(tmp.name)
        self.repo = self.tmp / "repo"
        self.repo.mkdir()
        git(self.repo, "init", "-q", "-b", "main")
        git(self.repo, "config", "user.email", "Binh@Corp.com")
        git(self.repo, "config", "user.name", "T")
        init_beads(self.repo)
        self.configure("beads")
        self.bead = json.loads(bd(self.repo, "create", "Login", "-t", "task", "--json"))["id"]
        self.store = LocalStore(self.tmp / "store")
        self.png = self.tmp / "f.png"
        self.png.write_bytes(PNG)
        self.sha = hashlib.sha256(CLEAN_PNG).hexdigest()

    def configure(self, tracker):
        (self.repo / ".agent-workflow").mkdir(exist_ok=True)
        (self.repo / ".agent-workflow/config.yaml").write_text(
            f"schema_version: '2.11'\nproviders:\n  task_tracking: {tracker}\n", encoding="utf-8")
        resolve_effective_config(self.repo)

    def add(self, files, **kwargs):
        return attachments.add(self.repo, self.bead, files, now=NOW, store=self.store, **kwargs)

    def stored(self):
        data = json.loads(bd(self.repo, "show", self.bead, "--json"))
        row = data[0] if isinstance(data, list) else data
        return attachments.entries(row)

    def test_add_stores_cleaned_bytes_and_records_entry(self):
        added = self.add([self.png])
        self.assertEqual(added.refused, [])
        self.assertEqual(len(added.entries), 1)
        entry = added.entries[0]
        self.assertEqual(entry, {"sha256": self.sha, "name": "f.png", "mime": "image/png", "bytes": len(CLEAN_PNG),
                                 "caption": None, "case": None, "step": None, "added_by": "binh@corp.com",
                                 "added_at": "2026-11-21T09:30:00Z", "store": "local", "path": blob_path(self.sha)})
        self.assertEqual(self.store.get(entry["path"]), CLEAN_PNG)
        self.assertEqual(self.stored(), [entry])

    def test_add_twice_keeps_one_entry(self):
        first = self.add([self.png])
        second = self.add([self.png])
        self.assertEqual(second.entries, first.entries)
        self.assertEqual(len(self.stored()), 1)

    def test_readd_after_prune_appends_new_entry(self):
        self.add([self.png])
        pruned = [{**self.stored()[0], "pruned_at": "2026-11-20T00:00:00Z"}]
        bd(self.repo, "update", self.bead, "--set-metadata", f"attachments={json.dumps(pruned)}")
        self.store.remove([blob_path(self.sha)])
        added = self.add([self.png])
        self.assertEqual(len(added.entries), 1)
        stored = self.stored()
        self.assertEqual(len(stored), 2)
        self.assertIn("pruned_at", stored[0])
        self.assertNotIn("pruned_at", stored[1])
        self.assertEqual(self.store.get(blob_path(self.sha)), CLEAN_PNG)

    def test_refuses_wrong_type_and_oversize_but_adds_the_rest(self):
        pdf = self.tmp / "x.png"
        pdf.write_bytes(b"%PDF-1.4 not an image")
        added = self.add([pdf, self.png])
        self.assertEqual([e["name"] for e in added.entries], ["f.png"])
        self.assertEqual(len(added.refused), 1)
        self.assertEqual(added.refused[0]["name"], "x.png")
        self.assertIn("not a PNG, JPEG, WebP or GIF", added.refused[0]["reason"])
        with mock.patch.object(attachments, "load_settings", return_value=Settings(store="local", max_bytes=10)):
            added = attachments.add(self.repo, self.bead, [self.png], now=NOW, store=self.store)
        self.assertEqual(added.entries, [])
        self.assertIn("exceeds", added.refused[0]["reason"])

    def test_refuses_unreadable_and_malformed(self):
        broken = self.tmp / "b.png"
        broken.write_bytes(_MAGIC + b"junk")
        added = self.add([self.tmp / "missing.png", broken])
        self.assertEqual(added.entries, [])
        self.assertIn("cannot read", added.refused[0]["reason"])
        self.assertIn("malformed image/png", added.refused[1]["reason"])

    def test_caption_case_and_step_reach_the_entry(self):
        entry = self.add([self.png], caption="Login", case="TC-1", step=3).entries[0]
        self.assertEqual((entry["caption"], entry["case"], entry["step"]), ("Login", "TC-1", 3))

    def test_missing_bead_raises(self):
        with self.assertRaises(AttachmentError) as caught:
            attachments.add(self.repo, "t-nope", [self.png], now=NOW, store=self.store)
        self.assertEqual(caught.exception.code, 2)

    def test_markdown_backend_raises_naming_beads(self):
        self.configure("markdown")
        with self.assertRaises(AttachmentError) as caught:
            self.add([self.png])
        self.assertIn("Beads", str(caught.exception))

    def test_fetch_writes_blobs_and_verifies_sha(self):
        self.add([self.png])
        out = self.tmp / "out"
        written = attachments.fetch(self.repo, bead=self.bead, out=out, store=self.store)
        self.assertEqual(written, [out / f"{self.sha}.png"])
        self.assertEqual(written[0].read_bytes(), CLEAN_PNG)
        (self.tmp / "store" / blob_path(self.sha)).write_bytes(b"tampered")
        with self.assertRaises(AttachmentError):
            attachments.fetch(self.repo, bead=self.bead, out=out, store=self.store)

    def test_push_warning_is_returned_and_entry_kept(self):
        store = mock.Mock(wraps=self.store)
        store.name = "local"
        store.push.return_value = "origin unreachable"
        added = attachments.add(self.repo, self.bead, [self.png], now=NOW, store=store)
        self.assertEqual(added.warning, "origin unreachable")
        self.assertEqual(len(self.stored()), 1)
        self.assertEqual(attachments.push(self.repo, store=store), "origin unreachable")

    def test_list_entries(self):
        entry = self.add([self.png]).entries[0]
        self.assertEqual(attachments.list_entries(self.repo, self.bead), [entry])


if __name__ == "__main__":
    unittest.main()
