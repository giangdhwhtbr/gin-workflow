"""Tests for `gin attach` argument handling over patched attachments functions."""

from __future__ import annotations

import contextlib
import io
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "plugins/gin-workflow/src/scripts"))

from team_fixtures import git, init_beads  # noqa: E402
from workflow_core import attach_cli, attachments, cli  # noqa: E402
from workflow_core.attach_store import LocalStore  # noqa: E402
from workflow_core.configuration import resolve_effective_config  # noqa: E402
from workflow_core.attachments import AttachmentError, Added  # noqa: E402
from workflow_core.models import DependencyUnavailableError  # noqa: E402

ENTRY = {"sha256": "ab" * 32, "name": "f.png", "caption": "C"}


def run(argv):
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        code = attach_cli.main(argv)
    return code, out.getvalue(), err.getvalue()


class AttachCliTests(unittest.TestCase):
    def test_add_prints_reference(self):
        with mock.patch.object(attachments, "add", return_value=Added([ENTRY], [], None)) as add:
            code, out, _ = run(["add", "b", "f.png", "--caption", "C", "--repository", "/tmp"])
        self.assertEqual((code, out.strip()), (0, f"![C](attachment:{'ab' * 32})"))
        self.assertEqual(add.call_args.kwargs["caption"], "C")

    def test_add_refused_exits_1(self):
        added = Added([], [{"name": "f.pdf", "reason": "not a PNG, JPEG, WebP or GIF"}], None)
        with mock.patch.object(attachments, "add", return_value=added):
            code, _, err = run(["add", "b", "f.pdf", "--repository", "/tmp"])
        self.assertEqual(code, 1)
        self.assertIn("refused f.pdf: not a PNG, JPEG, WebP or GIF", err)

    def test_add_json(self):
        with mock.patch.object(attachments, "add", return_value=Added([ENTRY], [], "warn")):
            code, out, _ = run(["add", "b", "f.png", "--format", "json", "--repository", "/tmp"])
        self.assertEqual(code, 0)
        self.assertEqual(json.loads(out), {"bead": "b", "entries": [ENTRY], "refused": [], "warning": "warn"})

    def test_list_json(self):
        with mock.patch.object(attachments, "list_entries", return_value=[ENTRY]):
            code, out, _ = run(["list", "b", "--format", "json", "--repository", "/tmp"])
        self.assertEqual((code, json.loads(out)), (0, {"bead": "b", "entries": [ENTRY]}))

    def test_fetch_bead_without_out_exits_2(self):
        with mock.patch.object(attachments, "fetch") as fetch:
            code, _, err = run(["fetch", "--bead", "b", "--repository", "/tmp"])
        self.assertEqual(code, 2)
        self.assertTrue(err)
        fetch.assert_not_called()

    def test_push_warning_exits_2(self):
        with mock.patch.object(attachments, "push", return_value="origin unreachable"):
            code, _, err = run(["push", "--repository", "/tmp"])
        self.assertEqual(code, 2)
        self.assertIn("origin unreachable", err)

    def test_errors_exit_2(self):
        for error in (AttachmentError("no such bead"), DependencyUnavailableError("pip install boto3")):
            with mock.patch.object(attachments, "list_entries", side_effect=error):
                code, _, err = run(["list", "b", "--repository", "/tmp"])
            self.assertEqual(code, 2)
            self.assertEqual(err.strip(), f"error: {error}")

    def test_flag_like_bead_id_exits_2_without_calling_bd(self):
        with mock.patch.object(attachments, "_bd") as bd_call:
            code, _, err = run(["list", "--repository", "/tmp", "--", "--json"])
        self.assertEqual(code, 2)
        self.assertTrue(err.startswith("error: "))
        bd_call.assert_not_called()

    def test_fetch_out_that_is_a_file_exits_2(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "afile"
            out.write_text("x")
            with mock.patch.object(attachments, "load_settings"), \
                    mock.patch.object(attachments, "open_store", return_value=LocalStore(Path(tmp) / "s")), \
                    mock.patch.object(attachments, "list_entries", return_value=[]):
                code, _, err = run(["fetch", "--bead", "b", "--out", str(out), "--repository", "/tmp"])
        self.assertEqual(code, 2)
        self.assertTrue(err.startswith("error: "))
        self.assertIn("is not a directory", err)

    def test_top_level_dispatch(self):
        with mock.patch.object(attach_cli, "main", return_value=0) as main:
            self.assertEqual(cli.main(["attach", "list", "x"]), 0)
        main.assert_called_once_with(["list", "x"])


@unittest.skipUnless(shutil.which("bd"), "bd is not installed")
class AttachCliEndToEndTests(unittest.TestCase):
    def test_add_then_list_json(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        repo = Path(tmp.name) / "repo"
        repo.mkdir()
        git(repo, "init", "-q", "-b", "main")
        git(repo, "config", "user.email", "a@corp.com")
        init_beads(repo)
        (repo / ".agent-workflow").mkdir()
        (repo / ".agent-workflow/config.yaml").write_text(
            "schema_version: '2.11'\nproviders:\n  task_tracking: beads\nattachments:\n  store: local\n",
            encoding="utf-8")
        resolve_effective_config(repo)
        bead = json.loads(subprocess.run(["bd", "create", "Login", "-t", "task", "--json"], cwd=repo, check=True,
                                         capture_output=True, text=True, stdin=subprocess.DEVNULL).stdout)["id"]
        image = Path(tmp.name) / "f.gif"
        image.write_bytes(b"GIF89a" + bytes(7) + b";")
        code, out, _ = run(["add", bead, str(image), "--caption", "C", "--repository", str(repo)])
        self.assertEqual(code, 0)
        self.assertTrue(out.startswith("![C](attachment:"))
        code, out, _ = run(["list", bead, "--format", "json", "--repository", str(repo)])
        listed = json.loads(out)
        self.assertEqual(code, 0)
        self.assertEqual([e["name"] for e in listed["entries"]], ["f.gif"])
        self.assertEqual(listed["entries"][0]["store"], "local")


if __name__ == "__main__":
    unittest.main()
