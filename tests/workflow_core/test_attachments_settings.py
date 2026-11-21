from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

SCRIPTS = Path(__file__).resolve().parents[2] / "plugins/gin-workflow/src/scripts"
sys.path.insert(0, str(SCRIPTS))

from workflow_core import setup_service  # noqa: E402
from workflow_core.attach_store import LocalStore  # noqa: E402
from workflow_core.attachments import (  # noqa: E402
    DEFAULT_MAX_BYTES,
    AttachmentError,
    Settings,
    load_settings,
    open_store,
)

BASE = {"schema_version": "2.11", "workflow_version": "2.11", "setup_cli_version": "2.11", "harness": "claude"}


def _repository(directory, **extra):
    repository = Path(directory)
    subprocess.run(["git", "init", "-q", str(repository)], check=True)
    workflow = repository / ".agent-workflow"
    workflow.mkdir()
    yaml = setup_service.require_yaml()
    (workflow / "config.yaml").write_text(yaml.safe_dump({**BASE, **extra}), encoding="utf-8")
    return repository


class AttachmentSettingsTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.dir = self._tmp.name

    def test_no_section_gives_defaults(self):
        repo = _repository(self.dir)
        self.assertEqual(load_settings(repo), Settings())
        self.assertEqual(Settings().max_bytes, DEFAULT_MAX_BYTES)

    def test_section_is_read_back(self):
        repo = _repository(self.dir, attachments={"store": "local", "max_bytes": 5, "retention_days": 30})
        self.assertEqual(load_settings(repo), Settings(store="local", max_bytes=5, retention_days=30))

    def test_s3_without_bucket_is_refused(self):
        repo = _repository(self.dir, attachments={"store": "s3"})
        with self.assertRaises(AttachmentError) as caught:
            load_settings(repo)
        self.assertIn("attachments.s3.bucket", str(caught.exception))
        self.assertEqual(caught.exception.code, 2)

    def test_unknown_store_fails_schema_validation(self):
        repo = _repository(self.dir, attachments={"store": "ftp"})
        with self.assertRaises(AttachmentError) as caught:
            load_settings(repo)
        self.assertIn("invalid configuration", str(caught.exception))

    def test_local_store_lives_under_main_checkout(self):
        repo = _repository(self.dir)
        store = open_store(repo, Settings(store="local"))
        self.assertIsInstance(store, LocalStore)
        self.assertEqual(store.directory.resolve(), (repo / ".agent-workflow/attachments").resolve())

    def test_setup_gitignores_attachments(self):
        self.assertIn("attachments/", setup_service.LOCAL_GITIGNORE_ENTRIES)


if __name__ == "__main__":
    unittest.main()
