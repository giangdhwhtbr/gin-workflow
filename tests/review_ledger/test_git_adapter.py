import unittest
import sys
import os
import tempfile
import shutil
import subprocess

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../plugins/gin-workflow/src/scripts')))

from review_ledger.git_adapter import (
    validate_working_tree_cleanliness,
    create_source_checkpoint,
    push_review_ref,
    fetch_review_ref,
    GitAdapterError,
    get_current_branch
)

class TestGitAdapter(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.remote_dir = tempfile.mkdtemp()
        
        # Init base remote
        subprocess.run(["git", "init", "--bare"], cwd=self.remote_dir, capture_output=True, check=True)
        
        # Init local repo
        subprocess.run(["git", "init"], cwd=self.test_dir, capture_output=True, check=True)
        subprocess.run(["git", "config", "user.name", "Test User"], cwd=self.test_dir, check=True)
        subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=self.test_dir, check=True)
        subprocess.run(["git", "remote", "add", "origin", self.remote_dir], cwd=self.test_dir, check=True)

        # Write initial file and commit so HEAD exists
        os.makedirs(os.path.join(self.test_dir, "src"))
        self.initial_file = os.path.join(self.test_dir, "src/init.txt")
        with open(self.initial_file, "w") as f:
            f.write("init")
        subprocess.run(["git", "add", "src/init.txt"], cwd=self.test_dir, check=True)
        subprocess.run(["git", "commit", "-m", "initial commit"], cwd=self.test_dir, check=True)
        # Push to remote master/main so remote has a default head
        subprocess.run(["git", "push", "origin", "master"], cwd=self.test_dir, check=True)

    def tearDown(self):
        shutil.rmtree(self.test_dir)
        shutil.rmtree(self.remote_dir)

    def test_working_tree_cleanliness(self):
        scope = {
            "included_paths": ["src/"],
            "excluded_artifact_paths": []
        }
        # Initially clean
        validate_working_tree_cleanliness(self.test_dir, scope)
        
        # Modify file in-scope
        with open(self.initial_file, "w") as f:
            f.write("modified")
        validate_working_tree_cleanliness(self.test_dir, scope) # Should pass
        
        # Add file out-of-scope
        out_file = os.path.join(self.test_dir, "out_of_scope.txt")
        with open(out_file, "w") as f:
            f.write("out")
            
        with self.assertRaises(GitAdapterError):
            validate_working_tree_cleanliness(self.test_dir, scope)

    def test_create_source_checkpoint_and_push_fetch(self):
        scope = {
            "included_paths": ["src/"],
            "excluded_artifact_paths": []
        }
        
        # Modify file in-scope
        with open(self.initial_file, "w") as f:
            f.write("modified-checkpoint")
            
        sha = create_source_checkpoint(
            self.test_dir,
            scope,
            "task-123",
            "feat: checkpoint test"
        )
        self.assertIsNotNone(sha)
        self.assertEqual(get_current_branch(self.test_dir), "bead/task-123")
        
        # Push to remote
        push_review_ref(self.test_dir, "origin", "task-123")
        
        # Clone another clean repo from remote to verify fetch
        cloned_dir = tempfile.mkdtemp()
        try:
            subprocess.run(["git", "clone", self.remote_dir, cloned_dir], check=True)
            subprocess.run(["git", "config", "user.name", "Test User"], cwd=cloned_dir, check=True)
            subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=cloned_dir, check=True)
            
            fetched_sha = fetch_review_ref(cloned_dir, "origin", "task-123")
            self.assertEqual(sha, fetched_sha)
        finally:
            shutil.rmtree(cloned_dir)

if __name__ == "__main__":
    unittest.main()
