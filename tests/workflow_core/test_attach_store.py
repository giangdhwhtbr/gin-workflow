from pathlib import Path
import sys
import tempfile
import unittest

SCRIPTS = Path(__file__).resolve().parents[2] / "plugins/gin-workflow/src/scripts"
sys.path.insert(0, str(SCRIPTS))

from workflow_core.attach_store import LocalStore, StoreError, blob_path, check_path  # noqa: E402

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

    def test_unsafe_paths_are_refused_and_outside_files_survive(self):
        outside = self.root.parent / f"{self.root.name}-outside"
        outside.write_bytes(b"keep")
        self.addCleanup(outside.unlink)
        store = LocalStore(self.root / "store")
        for bad in ("../x", "/etc/passwd", "ab\\cd", f"../{outside.name}"):
            with self.assertRaises(StoreError):
                store.get(bad)
            with self.assertRaises(StoreError):
                store.remove([bad])
        self.assertEqual(outside.read_bytes(), b"keep")

    def test_remove_checks_every_path_before_deleting(self):
        self.store.put(SHA, b"x")
        with self.assertRaises(StoreError):
            self.store.remove([blob_path(SHA), "../x"])
        self.assertEqual(self.store.paths(), {blob_path(SHA)})

    def test_bad_sha_is_refused(self):
        with self.assertRaises(StoreError):
            self.store.put("not-a-sha", b"x")
        with self.assertRaises(StoreError):
            self.store.put(SHA.upper(), b"x")

    def test_check_path(self):
        self.assertEqual(check_path(blob_path(SHA)), blob_path(SHA))
        with self.assertRaises(StoreError):
            check_path("cd/" + SHA)

    def test_paths_skips_stray_temporary_files(self):
        self.store.put(SHA, b"x")
        (self.root / "ab" / ".tmp-leftover").write_bytes(b"y")
        self.assertEqual(self.store.paths(), {blob_path(SHA)})


if __name__ == "__main__":
    unittest.main()
