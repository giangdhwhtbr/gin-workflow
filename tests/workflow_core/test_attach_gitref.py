import hashlib
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
import unittest
from unittest.mock import patch

SCRIPTS = Path(__file__).resolve().parents[2] / "plugins/gin-workflow/src/scripts"
sys.path.insert(0, str(SCRIPTS))

from workflow_core.attach_gitref import REF, GitRefStore  # noqa: E402
from workflow_core.attach_store import StoreError, blob_path  # noqa: E402

# Variables a git hook may export; any of them would point the store's git at another repository.
HOOK_ENV = ("GIT_DIR", "GIT_WORK_TREE", "GIT_INDEX_FILE", "GIT_PREFIX", "GIT_OBJECT_DIRECTORY", "GIT_COMMON_DIR")
X, Y, Z = b"image x", b"image y", b"image z"


def sha(data):
    return hashlib.sha256(data).hexdigest()


def git(cwd, *args, env=None):
    done = subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True, check=False,
                          env={**os.environ, **(env or {})})
    if done.returncode:
        raise AssertionError(f"git {' '.join(args)}: {done.stderr}")
    return done.stdout.strip()


class GitRefStoreTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.root = Path(directory.name).resolve()
        # No global or system git config: the store must commit without the developer's identity.
        empty = self.root / "gitconfig"
        empty.write_text("", encoding="utf-8")
        environment = patch.dict(os.environ, {"GIT_CONFIG_GLOBAL": str(empty), "GIT_CONFIG_NOSYSTEM": "1"})
        environment.start()
        self.addCleanup(environment.stop)
        for name in HOOK_ENV:
            os.environ.pop(name, None)
        self.origin = self.root / "origin.git"
        git(self.root, "init", "-q", "--bare", str(self.origin))
        self.a, self.b = self.clone("a"), self.clone("b")

    def clone(self, name, remote=True):
        repo = self.root / name
        git(self.root, "init", "-q", str(repo))
        if remote:
            git(repo, "remote", "add", "origin", str(self.origin))
        return GitRefStore(repo)

    def tip(self, repo, ref=REF):
        return git(repo, "rev-parse", "-q", "--verify", ref) if git(repo, "for-each-ref", ref) else None

    def tree(self, repo):
        return set(git(repo, "ls-tree", "-r", "--name-only", REF).split())

    def push_from(self, store, data):
        path = store.put(sha(data), data)
        self.assertIsNone(store.push())
        return path

    def test_put_commits_locally_and_get_reads_it_back(self):
        git(self.a.repo, "remote", "set-url", "origin", str(self.root / "missing.git"))
        self.assertEqual("git-ref", self.a.name)
        path = self.a.put(sha(X), X)
        self.assertEqual(blob_path(sha(X)), path)
        self.assertEqual({path}, self.tree(self.a.repo))
        self.assertEqual(X, self.a.get(path))
        self.assertEqual({path}, self.a.paths())
        first = self.tip(self.a.repo)
        self.assertEqual("", git(self.a.repo, "log", "-1", "--format=%P", first))
        self.assertEqual({"gin@localhost"}, set(git(self.a.repo, "log", "-1", "--format=%ae%n%ce", first).split()))
        self.assertEqual(path, self.a.put(sha(X), X))
        self.assertEqual(first, self.tip(self.a.repo))
        git(self.a.repo, "config", "user.email", "dev@example.com")
        self.a.put(sha(Y), Y)
        self.assertEqual({"dev@example.com"}, set(git(self.a.repo, "log", "-1", "--format=%ae%n%ce", REF).split()))
        self.assertEqual(first, git(self.a.repo, "rev-parse", f"{REF}^"))

    def test_push_sends_the_local_tip(self):
        self.push_from(self.a, X)
        self.assertEqual(self.tip(self.a.repo), self.tip(self.origin))
        self.assertIsNone(self.a.push())

    def test_push_restores_the_ref_on_an_origin_that_lost_it(self):
        x = self.push_from(self.a, X)
        git(self.origin, "update-ref", "-d", REF)
        self.assertIsNone(self.a.push())
        self.assertEqual({x}, self.tree(self.origin))

    def test_fetch_brings_pushed_blobs_and_keeps_unpushed_ones(self):
        y = self.b.put(sha(Y), Y)
        x = self.push_from(self.a, X)
        self.b.fetch()
        self.assertEqual(X, self.b.get(x))
        self.assertEqual({x, y}, self.b.paths())
        self.assertIsNone(self.b.push())
        self.assertEqual({x, y}, self.tree(self.origin))

    def test_two_clones_that_put_before_either_pushed_both_land(self):
        x, y = self.a.put(sha(X), X), self.b.put(sha(Y), Y)
        self.assertIsNone(self.a.push())
        self.assertIsNone(self.b.push())
        self.a.fetch()
        self.assertEqual({x, y}, self.a.paths())
        self.assertEqual({x, y}, self.tree(self.origin))
        self.assertEqual(self.tip(self.a.repo), self.tip(self.origin))

    def test_push_rebuilds_on_origin_when_origin_moves_after_its_fetch(self):
        y = self.b.put(sha(Y), Y)
        fetch, moved = self.b.fetch, []

        def fetch_then_a_pushes():
            fetch()
            if not moved:
                moved.append(self.push_from(self.a, X))

        with patch.object(self.b, "fetch", side_effect=fetch_then_a_pushes) as fetches:
            self.assertIsNone(self.b.push())
        self.assertEqual(2, fetches.call_count)
        self.assertEqual({moved[0], y}, self.tree(self.origin))
        self.assertEqual(self.tip(self.a.repo), git(self.origin, "log", "-1", "--format=%P", REF))

    def test_two_clones_pushing_at_once_both_land(self):
        stores = [self.a, self.b]
        paths = {store.put(sha(data), data) for store, data in zip(stores, (X, Y))}
        start, results = threading.Barrier(len(stores)), {}

        def push(store):
            start.wait()
            try:
                results[store.repo.name] = store.push()
            except StoreError as error:
                results[store.repo.name] = error

        threads = [threading.Thread(target=push, args=(store,)) for store in stores]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()
        self.assertEqual({"a": None, "b": None}, results)
        self.assertEqual(paths, self.tree(self.origin))

    def test_rejected_push_keeps_the_blob_and_warns(self):
        hook = self.origin / "hooks" / "pre-receive"
        hook.write_text("#!/bin/sh\necho rejected >> attempts\necho rejected by test >&2\nexit 1\n",
                        encoding="utf-8", newline="\n")
        hook.chmod(0o755)
        path = self.a.put(sha(X), X)
        warning = self.a.push()
        self.assertIn("gin attach push", warning)
        self.assertIn("rejected by test", warning)
        self.assertEqual(3, len((self.origin / "attempts").read_text(encoding="utf-8").split()))
        self.assertEqual(X, self.a.get(path))
        self.assertIsNone(self.tip(self.origin))

    def test_unreachable_origin_fails_fetch_and_warns_on_push_until_it_is_back(self):
        git(self.a.repo, "remote", "set-url", "origin", str(self.root / "missing.git"))
        path = self.a.put(sha(X), X)
        with self.assertRaisesRegex(StoreError, "cannot reach origin"):
            self.a.fetch()
        self.assertIn("gin attach push", self.a.push())
        self.assertEqual(X, self.a.get(path))
        git(self.a.repo, "remote", "set-url", "origin", str(self.origin))
        self.assertIsNone(self.a.push())
        self.b.fetch()
        self.assertEqual(X, self.b.get(path))

    def test_without_origin_remote_everything_stays_local(self):
        store = self.clone("solo", remote=False)
        x, y = store.put(sha(X), X), store.put(sha(Y), Y)
        self.assertIn("stay on this machine", store.push())
        self.assertIsNone(store.fetch())
        store.remove([x])
        self.assertEqual({y}, store.paths())
        self.assertEqual("", git(store.repo, "log", "-1", "--format=%P", REF))

    def test_remove_rewrites_one_root_commit_under_the_lease(self):
        x, y = self.push_from(self.a, X), self.push_from(self.b, Y)
        self.b.fetch()
        self.a.remove([x])
        self.assertEqual("1", git(self.a.repo, "rev-list", "--count", REF))
        self.assertEqual({y}, self.a.paths())
        self.assertEqual(self.tip(self.a.repo), self.tip(self.origin))
        self.b.fetch()
        self.assertEqual({y}, self.b.paths())

    def test_remove_creates_the_ref_on_an_origin_that_has_none(self):
        x, y = self.a.put(sha(X), X), self.a.put(sha(Y), Y)
        self.a.remove([x])
        self.assertEqual({y}, self.tree(self.origin))
        self.assertEqual(self.tip(self.a.repo), self.tip(self.origin))

    def test_prune_is_not_undone_by_a_clone_that_fetched_before_it(self):
        x, y = self.push_from(self.a, X), self.push_from(self.b, Y)
        self.b.fetch()
        self.a.remove([x])
        z = self.push_from(self.b, Z)
        self.assertEqual({y, z}, self.tree(self.origin))
        self.assertNotIn(sha(X), git(self.origin, "rev-list", "--objects", REF))
        self.assertEqual("1", git(self.origin, "rev-list", "--count", f"{REF}^"))
        self.a.fetch()
        self.assertEqual({y, z}, self.a.paths())

    def lose_lease(self, store, data):
        """While store.remove runs, another clone pushes data right after store's own fetch."""
        fetch = store.fetch

        def fetch_then_b_pushes():
            fetch()
            self.push_from(self.b, data)

        return patch.object(store, "fetch", side_effect=fetch_then_b_pushes)

    def test_lost_lease_refuses_the_prune_and_keeps_origin(self):
        x, y = self.push_from(self.a, X), self.push_from(self.b, Y)
        self.a.fetch()
        before = self.tip(self.a.repo)
        with self.lose_lease(self.a, Z), self.assertRaisesRegex(StoreError, "gin attach prune --apply"):
            self.a.remove([x])
        self.assertEqual({x, y, blob_path(sha(Z))}, self.tree(self.origin))
        self.assertEqual(before, self.tip(self.a.repo))

    def test_lost_lease_when_origin_had_no_ref(self):
        x, y = self.a.put(sha(X), X), self.a.put(sha(Y), Y)
        with self.lose_lease(self.a, Z), self.assertRaisesRegex(StoreError, "gin attach prune --apply"):
            self.a.remove([x])
        self.assertEqual({blob_path(sha(Z))}, self.tree(self.origin))
        self.assertEqual({x, y}, self.a.paths())

    def test_missing_or_malformed_paths_are_refused_before_any_change(self):
        x = self.a.put(sha(X), X)
        with self.assertRaises(StoreError):
            self.a.get(blob_path(sha(Y)))
        with self.assertRaises(StoreError):
            self.b.get(x)
        for bad in ("../x", f"{REF}:{x}", x.upper(), f"cd/{sha(X)}"):
            with self.subTest(bad), self.assertRaises(StoreError):
                self.a.get(bad)
        before = self.tip(self.a.repo)
        with self.assertRaises(StoreError):
            self.a.remove([x, "zz/not-a-path"])
        self.assertEqual(before, self.tip(self.a.repo))
        with self.assertRaises(StoreError):
            self.a.put("not-a-sha", X)

    def test_paths_lists_only_store_blobs(self):
        x = self.a.put(sha(X), X)
        repo, index = self.a.repo, {"GIT_INDEX_FILE": str(self.root / "index")}
        (self.root / "README").write_text("not an attachment", encoding="utf-8")
        readme = git(repo, "hash-object", "-w", str(self.root / "README"))
        git(repo, "read-tree", REF, env=index)
        git(repo, "update-index", "--add", "--cacheinfo", f"100644,{readme},README", env=index)
        git(repo, "update-index", "--add", "--cacheinfo", f"100644,{readme},ab/short", env=index)
        tree = git(repo, "write-tree", env=index)
        commit = git(repo, "commit-tree", tree, "-p", REF, "-m", "foreign",
                     env={"GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@example.com",
                          "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@example.com"})
        git(repo, "update-ref", REF, commit)
        self.assertEqual({x}, self.a.paths())
        with self.assertRaises(StoreError):
            self.a.get("README")

    def test_temporary_index_files_are_removed(self):
        scratch = self.root / "tmp"
        scratch.mkdir()
        with patch.object(tempfile, "tempdir", str(scratch)):
            x = self.push_from(self.a, X)
            self.b.put(sha(Y), Y)
            self.assertIsNone(self.b.push())
            self.a.remove([x])
        self.assertEqual([], list(scratch.iterdir()))


if __name__ == "__main__":
    unittest.main()
