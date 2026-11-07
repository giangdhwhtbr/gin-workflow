"""workspace.py: manifest validation and workspace root resolution."""

from __future__ import annotations

from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "plugins/gin-workflow/src/scripts"))

from workflow_core import workspace  # noqa: E402
from workflow_core.schemas import validate_config_schema  # noqa: E402


def git(root, *argv):
    return subprocess.run(["git", *argv], cwd=root, capture_output=True, text=True, check=True).stdout.strip()


def init_repo(root: Path) -> Path:
    root.mkdir(parents=True, exist_ok=True)
    git(root, "init", "-q", "-b", "main")
    git(root, "config", "user.email", "t@example.com")
    git(root, "config", "user.name", "t")
    (root / "f.txt").write_text("x", encoding="utf-8")
    git(root, "add", "-A")
    git(root, "commit", "-qm", "init", "--no-verify")
    return root


MANIFEST = """schema_version: '2.9'
workspace:
  repos:
    - path: services/api
      url: git@example.com:acme/api.git
      shape: backend
      verify: {checks: {test: "echo api-test"}}
    - path: apps/web
      url: git@example.com:acme/web.git
      shape: frontend
      default_branch: master
    - path: legacy/portal
      url: git@example.com:acme/portal.git
      frozen: true
    - path: .beads
      url: git@example.com:acme/beads.git
      shape: beads
"""


def make_workspace(base: Path) -> Path:
    """A parent with the manifest above and `services/api` cloned (a plain repo at the path)."""
    root = init_repo(base / "ws")
    (root / ".agent-workflow").mkdir()
    (root / ".agent-workflow/config.yaml").write_text(MANIFEST, encoding="utf-8")
    init_repo(root / "services/api")
    return root


class ManifestTests(unittest.TestCase):
    def test_repos_from_parses_defaults(self):
        repos = workspace.repos_from({"workspace": {"repos": [
            {"path": "services/api", "url": "u", "shape": "backend"},
            {"path": "legacy/x", "url": "u2", "frozen": True},
            {"path": ".beads", "url": "u3", "shape": "beads"}]}})
        self.assertEqual(("services/api", "backend", False, "main", {}), (repos[0].path, repos[0].shape,
                                                                            repos[0].frozen, repos[0].default_branch,
                                                                            dict(repos[0].checks)))
        self.assertEqual([True, False, False], [r.workable for r in repos])

    def test_repos_from_rejects_bad_manifests(self):
        bad = [
            ([{"path": "a", "url": "u", "shape": "backend"}, {"path": "a", "url": "u", "shape": "backend"}], "duplicate"),
            ([{"path": "a", "url": "u", "shape": "backend"}, {"path": "a/b", "url": "u", "shape": "backend"}], "nests"),
            ([{"path": ".planning", "url": "u", "shape": "backend"}], "reserved"),
            ([{"path": "/abs", "url": "u", "shape": "backend"}], "relative"),
            ([{"path": "a", "url": "u"}], "shape"),
            ([{"path": "a", "url": "u", "shape": "beads"}], ".beads"),
        ]
        for repos, word in bad:
            with self.subTest(word=word), self.assertRaises(workspace.WorkspaceError) as caught:
                workspace.repos_from({"workspace": {"repos": repos}})
            self.assertIn(word, str(caught.exception))

    def test_schema_accepts_manifest_and_rejects_unknown_keys(self):
        import yaml
        validate_config_schema(yaml.safe_load(MANIFEST))
        with self.assertRaises(ValueError):
            validate_config_schema({"schema_version": "2.9", "workspace": {"repos": [
                {"path": "a", "url": "u", "shape": "backend", "branch": "x"}]}})
        with self.assertRaises(ValueError):
            validate_config_schema({"schema_version": "2.9", "workspace": {"repos": [
                {"path": "a", "url": "u", "shape": "fullstack"}]}})

    def test_repo_of_uses_the_longest_prefix(self):
        ws = workspace.Workspace(Path("/ws"), workspace.repos_from(
            {"workspace": {"repos": [{"path": "services/api", "url": "u", "shape": "backend"},
                                     {"path": "apps/web", "url": "u", "shape": "frontend"}]}}))
        self.assertEqual("services/api", ws.repo_of("services/api/src/Main.java").path)
        self.assertIsNone(ws.repo_of("docs/x.md"))
        self.assertIsNone(ws.repo_of("services/apix/a"))


class ResolutionTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.base = Path(directory.name).resolve()
        self.root = make_workspace(self.base)
        self.child = self.root / "services/api"

    def test_load_returns_none_without_manifest(self):
        plain = init_repo(self.base / "plain")
        (plain / ".agent-workflow").mkdir()
        (plain / ".agent-workflow/config.yaml").write_text("schema_version: '2.9'\n", encoding="utf-8")
        self.assertIsNone(workspace.load(plain))
        self.assertIsNone(workspace.load(self.base))

    def test_locate_from_parent_child_and_child_worktree(self):
        parent = workspace.locate(self.root)
        self.assertEqual((self.root, self.root, None), (parent.root, parent.repo, parent.entry))
        self.assertIsNotNone(parent.workspace)
        child = workspace.locate(self.child)
        self.assertEqual((self.root, self.child, "services/api"), (child.root, child.repo, child.entry.path))
        (self.child / "src").mkdir()
        nested = workspace.locate(self.child / "src")
        self.assertEqual(self.root, nested.root)
        wt = self.root / ".planning/worktrees/t1"
        wt.parent.mkdir(parents=True)
        git(self.child, "worktree", "add", "-b", "feat/x-t1", str(wt), "main")
        linked = workspace.locate(wt)
        self.assertEqual((self.root, self.child, "services/api"), (linked.root, linked.repo, linked.entry.path))

    def test_locate_outside_a_workspace_keeps_the_repository(self):
        plain = init_repo(self.base / "plain")
        located = workspace.locate(plain)
        self.assertEqual((plain, plain, None, None), (located.root, located.repo, located.workspace, located.entry))
        stray = init_repo(self.base / "elsewhere/api")  # a child cloned outside its manifest path
        self.assertEqual(stray, workspace.locate(stray).root)

    def test_repository_root_resolves_only_the_default(self):
        self.assertEqual(self.child, workspace.repository_root(self.child))
        self.assertEqual(self.root, workspace.project_root(self.child))

    def test_summary(self):
        child = workspace.summary(workspace.locate(self.child))
        self.assertEqual(str(self.root), child["root"])
        self.assertEqual("services/api", child["current_repo"])
        by_path = {r["path"]: r for r in child["repos"]}
        self.assertEqual({"path": "services/api", "shape": "backend", "frozen": False, "present": True,
                          "branch": "main"}, by_path["services/api"])
        self.assertEqual({"path": "apps/web", "shape": "frontend", "frozen": False, "present": False,
                          "branch": None}, by_path["apps/web"])
        self.assertIsNone(workspace.summary(workspace.locate(init_repo(self.base / "plain"))))
        self.assertIsNone(workspace.summary(workspace.locate(self.root))["current_repo"])


if __name__ == "__main__":
    unittest.main()
