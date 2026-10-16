import contextlib
import io
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

SCRIPTS = Path(__file__).resolve().parents[2] / "plugins/gin-workflow/src/scripts"
sys.path.insert(0, str(SCRIPTS))

from workflow_core import task_markdown  # noqa: E402


class TaskMarkdownTests(unittest.TestCase):
    def setUp(self):
        self._directory = tempfile.TemporaryDirectory()
        self.root = Path(self._directory.name) / "repo"
        self.root.mkdir()
        subprocess.run(["git", "init", "-q"], cwd=self.root, check=True)

    def tearDown(self):
        self._directory.cleanup()

    def run_task(self, *argv):
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = task_markdown.main(self.root, argv)
        return code, out.getvalue(), err.getvalue()

    def q(self, *argv):
        return task_markdown.query(self.root, argv)

    def test_create_epic_and_children_with_bd_shaped_ids_and_files(self):
        epic = self.q("create", "--type", "epic", "Epic")
        child = self.q("create", "Track", "--parent", epic["id"], "-d", "desc", "--acceptance", "a\nb")
        self.assertEqual("repo-1", epic["id"])
        self.assertEqual("repo-1.1", child["id"])
        path = self.root / ".planning/tasks/repo-1/repo-1.1.md"
        text = path.read_text(encoding="utf-8")
        self.assertTrue(text.startswith("---\nid: repo-1.1\n"))
        self.assertIn("\ndesc\n", text)
        shown = self.q("show", "repo-1.1")[0]
        self.assertEqual(["a", "b"], shown["acceptance_criteria"])
        self.assertIn({"depends_on_id": "repo-1", "type": "parent-child"}, shown["dependencies"])

    def test_explicit_id_labels_and_label_filters(self):
        self.q("create", "--id", "repo-rm-auth", "--type", "epic", "--labels", "roadmap", "Auth")
        self.q("update", "repo-rm-auth", "--add-label", "sprint:s1")
        self.assertEqual(["repo-rm-auth"], [r["id"] for r in self.q("list", "--label", "sprint:s1", "--all")])
        self.q("update", "repo-rm-auth", "--remove-label", "sprint:s1")
        self.assertEqual([], self.q("list", "--label", "sprint:s1", "--all"))
        code, _, err = self.run_task("create", "--id", "repo-rm-auth", "Again")
        self.assertEqual(1, code)
        self.assertIn("already exists", err)

    def test_ready_blocked_close_reopen_and_list_all(self):
        epic = self.q("create", "--type", "epic", "E")["id"]
        a = self.q("create", "A", "--parent", epic)["id"]
        b = self.q("create", "B", "--parent", epic)["id"]
        self.q("dep", "add", b, a)
        self.assertEqual({epic, a}, {r["id"] for r in self.q("ready")})
        self.assertEqual([(b, [a])], [(r["id"], r["blocked_by"]) for r in self.q("blocked")])
        self.q("close", a, "--reason", "tests green")
        self.assertEqual({epic, b}, {r["id"] for r in self.q("ready")})
        self.assertEqual([b], [r["id"] for r in self.q("list", "--parent", epic)])
        self.assertEqual({a, b}, {r["id"] for r in self.q("list", "--parent", epic, "--all", "--limit", "0")})
        self.assertEqual("tests green", self.q("show", a)[0]["close_reason"])
        self.q("reopen", a)
        self.assertEqual("open", self.q("show", a)[0]["status"])
        self.assertEqual({a, b}, {r["id"] for r in self.q("list", "--status", "open,in_progress", "--parent", epic)})

    def test_update_fields_and_notes(self):
        task = self.q("create", "T", "--notes", "first")["id"]
        self.q("update", task, "--status", "in_progress", "--title", "T2", "--append-notes", "second")
        shown = self.q("show", task)[0]
        self.assertEqual(("in_progress", "T2", "first\nsecond"), (shown["status"], shown["title"], shown["notes"]))

    def test_dependency_cycle_self_and_dangling_are_rejected(self):
        a = self.q("create", "A")["id"]
        b = self.q("create", "B")["id"]
        self.q("dep", "add", b, a)
        code, _, err = self.run_task("dep", "add", a, b)
        self.assertEqual(1, code)
        self.assertIn(f"dependency cycle: {a} -> {b} -> {a}", err)
        self.assertEqual(1, self.run_task("dep", "add", a, a)[0])
        self.assertEqual(1, self.run_task("dep", "add", a, "repo-99")[0])
        self.assertEqual([a], [r["id"] for r in self.q("dep", "list", b)])
        self.q("dep", "remove", b, a)
        self.assertEqual([], self.q("dep", "list", b))

    def test_malformed_file_fails_closed_naming_the_file(self):
        self.q("create", "--type", "epic", "E")
        bad = self.root / ".planning/tasks/repo-1/broken.md"
        bad.write_text("no frontmatter\n", encoding="utf-8")
        code, _, err = self.run_task("list")
        self.assertEqual(1, code)
        self.assertIn(str(bad), err)
        self.assertIsNone(self.q("list", "--all"))
        bad.write_text("---\nid: repo-9\ntitle: x\nstatus: done\n---\n", encoding="utf-8")
        self.assertIn("unsupported status", self.run_task("list")[2])

    def test_hand_edit_is_picked_up(self):
        task = self.q("create", "T")["id"]
        path = self.root / f".planning/tasks/{task}/{task}.md"
        path.write_text(path.read_text(encoding="utf-8").replace("status: open", "status: closed"), encoding="utf-8")
        self.assertEqual("closed", self.q("show", task)[0]["status"])

    def test_worktree_reads_and_writes_the_main_checkout(self):
        subprocess.run(["git", "commit", "-q", "--allow-empty", "-m", "init"], cwd=self.root, check=True,
                       env={"GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t", "GIT_COMMITTER_NAME": "t",
                            "GIT_COMMITTER_EMAIL": "t@t", "PATH": "/usr/bin:/bin"})
        worktree = Path(self._directory.name) / "wt"
        subprocess.run(["git", "worktree", "add", "-q", str(worktree), "-b", "wt"], cwd=self.root, check=True)
        created = task_markdown.query(worktree, ["create", "From worktree"])
        self.assertTrue((self.root / f".planning/tasks/{created['id']}/{created['id']}.md").is_file())
        self.assertFalse((worktree / ".planning/tasks").exists())

    def test_concurrent_creates_get_distinct_ids(self):
        epic = self.q("create", "--type", "epic", "E")["id"]
        code = f"import sys; sys.path.insert(0, {str(SCRIPTS)!r}); from pathlib import Path; " \
               f"from workflow_core.task_markdown import main; sys.exit(main(Path('.'), sys.argv[1:]))"
        workers = [subprocess.Popen([sys.executable, "-c", code, "create", f"T{n}", "--parent", epic],
                                    cwd=self.root, stdout=subprocess.DEVNULL) for n in range(12)]
        self.assertEqual([0] * 12, [worker.wait() for worker in workers])
        self.assertEqual(12, len(self.q("list", "--parent", epic)))

    def test_task_files_are_git_ignored(self):
        self.q("create", "--type", "epic", "E")
        self.q("remember", "a fact")
        status = subprocess.run(["git", "status", "--porcelain"], cwd=self.root, text=True, capture_output=True)
        self.assertEqual("", status.stdout)
        self.assertEqual("*\n", (self.root / ".planning/tasks/.gitignore").read_text(encoding="utf-8"))

    def test_memory_and_prefix(self):
        self.q("remember", "use uv for python")
        self.q("remember", "never edit .beads")
        self.assertEqual(["use uv for python"], self.q("memories", "uv"))
        self.assertEqual("repo", self.q("config", "get", "issue_prefix")["value"])
        self.assertEqual((0, "repo\n", ""), self.run_task("config", "get", "issue_prefix"))

    def test_text_output_and_unknown_command(self):
        task = self.q("create", "T")["id"]
        self.assertEqual((0, f"{task} [open] T\n", ""), self.run_task("list"))
        self.assertNotEqual(0, self.run_task("frobnicate")[0])


if __name__ == "__main__":
    unittest.main()
