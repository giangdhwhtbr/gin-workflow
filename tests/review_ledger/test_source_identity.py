import unittest
import sys
import os
import tempfile
import shutil
import subprocess

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../plugins/gin-workflow/src/scripts')))

from review_ledger.source_identity import (
    is_path_in_scope,
    get_git_files,
    compute_source_tree_hash,
    compute_source_scope_hash,
    validate_untracked_files
)

class TestSourceIdentity(unittest.TestCase):
    def setUp(self):
        # Create a temp directory for git testing
        self.test_dir = tempfile.mkdtemp()
        
        # Init git repo
        subprocess.run(["git", "init"], cwd=self.test_dir, capture_output=True, check=True)
        # Configure basic dummy name/email
        subprocess.run(["git", "config", "user.name", "Test User"], cwd=self.test_dir, check=True)
        subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=self.test_dir, check=True)

    def tearDown(self):
        shutil.rmtree(self.test_dir)

    def test_is_path_in_scope(self):
        scope = {
            "included_paths": ["src/", "tests/"],
            "excluded_artifact_paths": ["src/artifacts/"]
        }
        self.assertTrue(is_path_in_scope("src/main.py", scope))
        self.assertTrue(is_path_in_scope("tests/test_main.py", scope))
        self.assertFalse(is_path_in_scope("docs/index.md", scope))
        self.assertFalse(is_path_in_scope("src/artifacts/data.json", scope))
        self.assertTrue(is_path_in_scope("src/artifacts_not_excluded/data.json", scope))

    def test_source_hashing_and_untracked_validation(self):
        # Create directories
        os.makedirs(os.path.join(self.test_dir, "src"))
        os.makedirs(os.path.join(self.test_dir, "docs"))
        
        # Write files
        f1_path = os.path.join(self.test_dir, "src/main.py")
        with open(f1_path, "w") as f:
            f.write("print('hello')")
            
        f2_path = os.path.join(self.test_dir, "docs/readme.md")
        with open(f2_path, "w") as f:
            f.write("# README")

        # Stage and commit f1 and f2
        subprocess.run(["git", "add", "src/main.py", "docs/readme.md"], cwd=self.test_dir, check=True)
        subprocess.run(["git", "commit", "-m", "initial commit"], cwd=self.test_dir, check=True)

        scope = {
            "included_paths": ["src/"],
            "excluded_artifact_paths": [],
            "allowed_generated_paths": ["src/temp_gen/"]
        }

        # 1. Hashing Check
        h1 = compute_source_tree_hash("primary", self.test_dir, scope)
        self.assertIsNotNone(h1)
        
        # Verify it only hashes src/main.py by changing docs/readme.md and checking hash is unchanged
        with open(f2_path, "a") as f:
            f.write("\nappend text")
        subprocess.run(["git", "add", "docs/readme.md"], cwd=self.test_dir, check=True)
        subprocess.run(["git", "commit", "-m", "update doc"], cwd=self.test_dir, check=True)
        
        h2 = compute_source_tree_hash("primary", self.test_dir, scope)
        self.assertEqual(h1, h2) # Should match because docs/ is outside scope

        # Changing src/main.py should change hash
        with open(f1_path, "a") as f:
            f.write("\n# comment")
        subprocess.run(["git", "add", "src/main.py"], cwd=self.test_dir, check=True)
        subprocess.run(["git", "commit", "-m", "update src"], cwd=self.test_dir, check=True)
        
        h3 = compute_source_tree_hash("primary", self.test_dir, scope)
        self.assertNotEqual(h1, h3)

        # 2. Untracked file validation
        # Create an allowed untracked file
        os.makedirs(os.path.join(self.test_dir, "src/temp_gen"))
        with open(os.path.join(self.test_dir, "src/temp_gen/gen.txt"), "w") as f:
            f.write("generated")
            
        # Create a prohibited untracked file
        with open(os.path.join(self.test_dir, "src/prohibited.py"), "w") as f:
            f.write("prohibited")
            
        prohibited = validate_untracked_files(self.test_dir, scope)
        self.assertEqual(prohibited, ["src/prohibited.py"])

    def test_scope_hash(self):
        scope = {"included_paths": ["src/"]}
        self.assertIsNotNone(compute_source_scope_hash(scope))

if __name__ == "__main__":
    unittest.main()
