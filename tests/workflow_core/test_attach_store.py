from pathlib import Path
import sys
import tempfile
import unittest

SCRIPTS = Path(__file__).resolve().parents[2] / "plugins/gin-workflow/src/scripts"
sys.path.insert(0, str(SCRIPTS))

from workflow_core.attach_store import LocalStore, StoreError, blob_path  # noqa: E402

SHA = "ab" + "0" * 62


class LocalStoreTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name)
        self.store = LocalStore(self.root)

    def test_blob_path(self):
        self.assertEqual(blob_path(SHA), "ab/" + SHA)

    def test_put_get_and_idempotence(self):
        self.assertEqual(self.store.name, "local")
        self.assertEqual(self.store.put(SHA, b"one"), blob_path(SHA))
        self.assertEqual((self.root / "ab" / SHA).read_bytes(), b"one")
        self.store.put(SHA, b"two")
        self.assertEqual(self.store.get(blob_path(SHA)), b"one")
        self.assertEqual([p.name for p in (self.root / "ab").iterdir()], [SHA])

    def test_get_missing_raises(self):
        with self.assertRaises(StoreError):
            self.store.get(blob_path(SHA))

    def test_paths_and_remove(self):
        self.assertEqual(self.store.paths(), set())
        self.store.put(SHA, b"x")
        self.assertEqual(self.store.paths(), {blob_path(SHA)})
        self.store.remove([blob_path(SHA)])
        self.assertEqual(self.store.paths(), set())
        self.assertFalse((self.root / "ab").exists())

    def test_push_and_fetch_are_noops(self):
        self.assertIsNone(self.store.push())
        self.assertIsNone(self.store.fetch())


if __name__ == "__main__":
    unittest.main()
