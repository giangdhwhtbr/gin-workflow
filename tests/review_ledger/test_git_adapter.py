import os
import shutil
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(
    0,
    os.path.abspath(
        os.path.join(os.path.dirname(__file__), "../../plugins/gin-workflow/src/scripts")
    ),
)

from review_ledger.git_adapter import (
    GitAdapterError,
    SourceCheckpoint,
    create_source_checkpoint,
    get_current_branch,
    validate_working_tree_cleanliness,
)


class TestGitAdapter(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        subprocess.run(["git", "init"], cwd=self.test_dir, capture_output=True, check=True)
        subprocess.run(["git", "config", "user.name", "Test User"], cwd=self.test_dir, check=True)
        subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=self.test_dir, check=True)
        os.makedirs(os.path.join(self.test_dir, "src"))
        self.initial_file = os.path.join(self.test_dir, "src/init.txt")
        with open(self.initial_file, "w") as stream:
            stream.write("init")
        subprocess.run(["git", "add", "src/init.txt"], cwd=self.test_dir, check=True)
        subprocess.run(["git", "commit", "-m", "initial"], cwd=self.test_dir, capture_output=True, check=True)

    def tearDown(self):
        shutil.rmtree(self.test_dir)

    def test_working_tree_cleanliness_allows_source_and_declared_artifacts(self):
        scope = {
            "included_paths": ["src/"],
            "excluded_artifact_paths": ["src/build/"],
            "allowed_generated_paths": ["src/generated/"],
        }
        with open(self.initial_file, "w") as stream:
            stream.write("modified")
        os.makedirs(os.path.join(self.test_dir, "src/generated"))
        with open(os.path.join(self.test_dir, "src/generated/out.txt"), "w") as stream:
            stream.write("generated")
        validate_working_tree_cleanliness(self.test_dir, scope)

        with open(os.path.join(self.test_dir, "unrelated.txt"), "w") as stream:
            stream.write("outside")
        with self.assertRaises(GitAdapterError):
            validate_working_tree_cleanliness(self.test_dir, scope)

    def test_checkpoint_rejects_refs_outside_dedicated_namespace(self):
        scope = {"included_paths": ["src/"]}
        with open(self.initial_file, "w") as stream:
            stream.write("modified")
        current_ref = self._git_text("rev-parse", "refs/heads/master").strip()
        subprocess.run(["git", "branch", "other"], cwd=self.test_dir, check=True)
        other_ref = self._git_text("rev-parse", "refs/heads/other").strip()

        for protected_ref in ("refs/heads/master", "refs/heads/other", "refs/tags/review"):
            with self.subTest(review_ref=protected_ref):
                with self.assertRaisesRegex(GitAdapterError, "dedicated namespace"):
                    create_source_checkpoint(
                        self.test_dir,
                        scope,
                        "task-protected",
                        review_ref=protected_ref,
                    )

        self.assertEqual(current_ref, self._git_text("rev-parse", "refs/heads/master").strip())
        self.assertEqual(other_ref, self._git_text("rev-parse", "refs/heads/other").strip())

    def test_checkpoint_rejects_symbolic_ref_inside_dedicated_namespace(self):
        symbolic_ref = "refs/gin/review/symbolic"
        subprocess.run(
            ["git", "symbolic-ref", symbolic_ref, "refs/heads/master"],
            cwd=self.test_dir,
            check=True,
        )
        before = self._git_text("rev-parse", "refs/heads/master").strip()
        with self.assertRaisesRegex(GitAdapterError, "must not be symbolic"):
            create_source_checkpoint(
                self.test_dir,
                {"included_paths": ["src/"]},
                "task-symbolic",
                review_ref=symbolic_ref,
            )
        self.assertEqual(before, self._git_text("rev-parse", "refs/heads/master").strip())

    def test_checkpoint_uses_complete_head_snapshot_when_base_is_older(self):
        base_sha = self._git_text("rev-parse", "HEAD").strip()
        with open(self.initial_file, "w") as stream:
            stream.write("committed-after-base")
        with open(os.path.join(self.test_dir, "src/after.py"), "w") as stream:
            stream.write("after")
        subprocess.run(["git", "add", "src"], cwd=self.test_dir, check=True)
        subprocess.run(
            ["git", "commit", "-m", "after base"],
            cwd=self.test_dir,
            capture_output=True,
            check=True,
        )

        checkpoint = create_source_checkpoint(
            self.test_dir,
            {"included_paths": ["src/"]},
            "task-old-base",
            base_ref=base_sha,
        )

        content = self._git_text("show", f"{checkpoint.checkpoint_sha}:src/init.txt")
        self.assertEqual(content, "committed-after-base")
        self.assertIn("src/after.py", self._tree_paths(checkpoint.checkpoint_sha))
        parent = self._git_text("rev-parse", f"{checkpoint.checkpoint_sha}^").strip()
        self.assertEqual(parent, base_sha)

    def test_checkpoint_removes_tracked_excluded_generated_and_nested_content(self):
        for relative in (
            "src/generated/out.txt",
            "src/artifacts/report.json",
            "src/vendor/code.py",
        ):
            absolute = os.path.join(self.test_dir, relative)
            os.makedirs(os.path.dirname(absolute), exist_ok=True)
            with open(absolute, "w") as stream:
                stream.write(relative)
        subprocess.run(["git", "add", "src"], cwd=self.test_dir, check=True)
        subprocess.run(
            ["git", "commit", "-m", "tracked artifacts"],
            cwd=self.test_dir,
            capture_output=True,
            check=True,
        )

        checkpoint = create_source_checkpoint(
            self.test_dir,
            {
                "included_paths": ["src/"],
                "excluded_artifact_paths": ["src/artifacts/"],
                "allowed_generated_paths": ["src/generated/"],
                "nested_repository_paths": ["src/vendor/"],
            },
            "task-filtered-base",
        )

        paths = self._tree_paths(checkpoint.checkpoint_sha)
        self.assertIn("src/init.txt", paths)
        self.assertNotIn("src/generated/out.txt", paths)
        self.assertNotIn("src/artifacts/report.json", paths)
        self.assertNotIn("src/vendor/code.py", paths)

    def test_checkpoint_preserves_head_branch_index_and_status(self):
        scope = {"included_paths": ["src/"]}
        with open(self.initial_file, "w") as stream:
            stream.write("modified-checkpoint")
        with open(os.path.join(self.test_dir, "src/staged.txt"), "w") as stream:
            stream.write("staged")
        subprocess.run(["git", "add", "src/staged.txt"], cwd=self.test_dir, check=True)
        with open(os.path.join(self.test_dir, "src/new.py"), "w") as stream:
            stream.write("print('new')")

        before_head = self._git_bytes("rev-parse", "HEAD")
        before_branch = get_current_branch(self.test_dir)
        before_status = self._git_bytes("status", "--porcelain=v1", "-z", "--untracked-files=all")
        before_staged = self._git_bytes("diff", "--cached", "--binary")

        checkpoint = create_source_checkpoint(
            self.test_dir,
            scope,
            "task-123",
            base_ref="HEAD",
            review_ref="refs/gin/review/task-123",
        )

        self.assertIsInstance(checkpoint, SourceCheckpoint)
        self.assertEqual(before_head, self._git_bytes("rev-parse", "HEAD"))
        self.assertEqual(before_branch, get_current_branch(self.test_dir))
        self.assertEqual(
            before_status,
            self._git_bytes("status", "--porcelain=v1", "-z", "--untracked-files=all"),
        )
        self.assertEqual(before_staged, self._git_bytes("diff", "--cached", "--binary"))
        self.assertEqual(
            checkpoint.checkpoint_sha,
            self._git_text("rev-parse", checkpoint.checkpoint_ref).strip(),
        )
        paths = self._tree_paths(checkpoint.checkpoint_sha)
        self.assertIn("src/staged.txt", paths)
        self.assertIn("src/new.py", paths)

    def test_checkpoint_records_staged_rename_without_mutating_real_index(self):
        scope = {"included_paths": ["src/"]}
        subprocess.run(
            ["git", "mv", "src/init.txt", "src/renamed.txt"],
            cwd=self.test_dir,
            check=True,
        )
        before_staged = self._git_bytes("diff", "--cached", "--binary")

        checkpoint = create_source_checkpoint(self.test_dir, scope, "task-rename")

        paths = self._tree_paths(checkpoint.checkpoint_sha)
        self.assertIn("src/renamed.txt", paths)
        self.assertNotIn("src/init.txt", paths)
        self.assertEqual(before_staged, self._git_bytes("diff", "--cached", "--binary"))

    def test_generated_untracked_file_is_not_checkpointed(self):
        scope = {
            "included_paths": ["src/"],
            "allowed_generated_paths": ["src/generated/"],
        }
        os.makedirs(os.path.join(self.test_dir, "src/generated"))
        with open(os.path.join(self.test_dir, "src/generated/out.txt"), "w") as stream:
            stream.write("generated")
        with open(os.path.join(self.test_dir, "src/ordinary.py"), "w") as stream:
            stream.write("ordinary")

        checkpoint = create_source_checkpoint(self.test_dir, scope, "task-generated")
        paths = self._tree_paths(checkpoint.checkpoint_sha)
        self.assertIn("src/ordinary.py", paths)
        self.assertNotIn("src/generated/out.txt", paths)

    def test_undeclared_nested_repository_fails_closed(self):
        nested = os.path.join(self.test_dir, "src/vendor")
        os.makedirs(nested)
        subprocess.run(["git", "init"], cwd=nested, capture_output=True, check=True)
        with open(os.path.join(nested, "code.py"), "w") as stream:
            stream.write("nested")
        with self.assertRaisesRegex(GitAdapterError, "nested repository"):
            create_source_checkpoint(self.test_dir, {"included_paths": ["src/"]}, "task-nested")

    def test_declared_nested_repository_is_separate(self):
        nested = os.path.join(self.test_dir, "src/vendor")
        os.makedirs(nested)
        subprocess.run(["git", "init"], cwd=nested, capture_output=True, check=True)
        subprocess.run(["git", "config", "user.name", "Test User"], cwd=nested, check=True)
        subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=nested, check=True)
        with open(os.path.join(nested, "code.py"), "w") as stream:
            stream.write("nested")
        subprocess.run(["git", "add", "code.py"], cwd=nested, check=True)
        subprocess.run(["git", "commit", "-m", "nested"], cwd=nested, capture_output=True, check=True)

        parent = create_source_checkpoint(
            self.test_dir,
            {"included_paths": ["src/"], "nested_repository_paths": ["src/vendor/"]},
            "task-parent",
        )
        child = create_source_checkpoint(
            nested,
            {"included_paths": ["code.py"]},
            "task-child",
            repository_id="vendor",
        )
        self.assertNotIn("src/vendor/code.py", self._tree_paths(parent.checkpoint_sha))
        self.assertIn("code.py", subprocess.check_output(["git", "ls-tree", "-r", "--name-only", child.checkpoint_sha], cwd=nested, text=True).splitlines())

    def test_submodule_is_encoded_as_gitlink(self):
        nested = tempfile.mkdtemp()
        try:
            subprocess.run(["git", "init"], cwd=nested, capture_output=True, check=True)
            subprocess.run(["git", "config", "user.name", "Test User"], cwd=nested, check=True)
            subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=nested, check=True)
            with open(os.path.join(nested, "code.py"), "w") as stream:
                stream.write("nested")
            subprocess.run(["git", "add", "code.py"], cwd=nested, check=True)
            subprocess.run(["git", "commit", "-m", "nested"], cwd=nested, capture_output=True, check=True)
            subprocess.run(
                ["git", "-c", "protocol.file.allow=always", "submodule", "add", nested, "src/sub"],
                cwd=self.test_dir,
                capture_output=True,
                check=True,
            )
            subprocess.run(["git", "commit", "-am", "submodule"], cwd=self.test_dir, capture_output=True, check=True)
            checkpoint = create_source_checkpoint(self.test_dir, {"included_paths": ["src/"]}, "task-sub")
            listing = self._git_text("ls-tree", checkpoint.checkpoint_sha, "src/sub")
            self.assertTrue(listing.startswith("160000 commit "))
        finally:
            shutil.rmtree(nested)

    def _git_bytes(self, *args):
        return subprocess.check_output(["git", *args], cwd=self.test_dir)

    def _git_text(self, *args):
        return subprocess.check_output(["git", *args], cwd=self.test_dir, text=True)

    def _tree_paths(self, treeish):
        return self._git_text("ls-tree", "-r", "--name-only", treeish).splitlines()


if __name__ == "__main__":
    unittest.main()
