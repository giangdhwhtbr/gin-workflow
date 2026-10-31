import contextlib
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

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

    def test_us6_claim_sets_in_progress_and_assignee_and_list_filters_by_it(self):
        task = self.q("create", "T")["id"]
        with mock.patch.dict(os.environ, {"BD_ACTOR": "me@x"}):
            self.q("update", task, "--claim")
        shown = self.q("show", task)[0]
        self.assertEqual(("in_progress", "me@x"), (shown["status"], shown["assignee"]))
        self.assertEqual([task], [r["id"] for r in self.q("list", "--status", "in_progress", "--assignee", "me@x")])
        self.assertEqual([], self.q("list", "--status", "in_progress", "--assignee", "other@x"))
        with mock.patch.dict(os.environ, {"BD_ACTOR": "other@x"}):
            code, _, err = self.run_task("update", task, "--claim")
        self.assertEqual(1, code)
        self.assertIn("already claimed by me@x", err)

    def test_us6_claim_refuses_other_actors_bead_in_any_status_and_closed_beads(self):
        task = self.q("create", "T", "--assignee", "me@x")["id"]
        with mock.patch.dict(os.environ, {"BD_ACTOR": "other@x"}):
            code, _, err = self.run_task("update", task, "--claim")
            self.assertEqual(1, code)
            self.assertIn("already claimed by me@x", err)
        with mock.patch.dict(os.environ, {"BD_ACTOR": "me@x"}):
            self.q("update", task, "--claim")
            self.q("update", task, "--claim")
            self.q("close", task)
            code, _, err = self.run_task("update", task, "--claim")
        self.assertEqual(1, code)
        self.assertIn(f"{task} is closed", err)
        self.assertEqual("closed", self.q("show", task)[0]["status"])

    def test_us6_claim_falls_back_to_git_user_email(self):
        subprocess.run(["git", "config", "user.email", "git@x"], cwd=self.root, check=True)
        task = self.q("create", "T")["id"]
        with mock.patch.dict(os.environ, {}):
            os.environ.pop("BD_ACTOR", None)
            self.q("update", task, "--claim")
        self.assertEqual("git@x", self.q("show", task)[0]["assignee"])

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


    def test_unsafe_explicit_ids_are_rejected(self):
        for bad in ("../../escape", "x/y", "..", ".hidden", "a..b"):
            code, _, err = self.run_task("create", "--id", bad, "T")
            self.assertEqual(1, code, bad)
            self.assertIn("invalid task id", err)
        self.assertFalse((Path(self._directory.name) / "escape.md").exists())
        self.assertEqual("repo:a.b-1", self.q("create", "--id", "repo:a.b-1", "T")["id"])

    def test_concurrent_remembers_keep_every_fact(self):
        code = f"import sys; sys.path.insert(0, {str(SCRIPTS)!r}); from pathlib import Path; " \
               f"from workflow_core.task_markdown import main; sys.exit(main(Path('.'), sys.argv[1:]))"
        workers = [subprocess.Popen([sys.executable, "-c", code, "remember", f"fact {n}"],
                                    cwd=self.root, stdout=subprocess.DEVNULL) for n in range(16)]
        self.assertEqual([0] * 16, [worker.wait() for worker in workers])
        self.assertEqual(16, len(self.q("memories")))

    def test_misshapen_frontmatter_fails_closed_naming_the_file(self):
        self.q("create", "--type", "epic", "E")
        bad = self.root / ".planning/tasks/repo-1/bad.md"
        for head in ("deps: [repo-1]", "labels: foo", "acceptance_criteria: [1, {a: b}]", "title: [x]"):
            text = "---\nid: repo-9\ntitle: x\n" + head + "\n---\n"
            bad.write_text(text.replace("title: x\ntitle:", "title:"), encoding="utf-8")
            code, _, err = self.run_task("list")
            self.assertEqual(1, code, head)
            self.assertIn(str(bad), err, head)
        bad.write_bytes(b"---\nid: repo-9\ntitle: \xff\n---\n")
        code, _, err = self.run_task("list")
        self.assertEqual((1, True), (code, str(bad) in err))
        bad.write_text("---\nid: repo-1\ntitle: dup\n---\n", encoding="utf-8")
        code, _, err = self.run_task("list")
        self.assertEqual(1, code)
        self.assertIn("duplicate task id repo-1", err)
        self.assertIn(str(bad), err)
        self.assertIn("repo-1.md", err)

    def test_unquoted_timestamps_stay_strings(self):
        task = self.q("create", "T")["id"]
        path = self.root / f".planning/tasks/{task}/{task}.md"
        path.write_text(path.read_text(encoding="utf-8").replace("created_at: '", "created_at: ").replace(
            "Z'\n", "Z\n", 1), encoding="utf-8")
        code, out, _ = self.run_task("show", task, "--json")
        self.assertEqual(0, code)
        self.assertIsInstance(json.loads(out)[0]["created_at"], str)

    def test_dep_remove_status_and_notes_heading_in_description(self):
        a = self.q("create", "A")["id"]
        b = self.q("create", "B", "-d", "intro\n### Notes about x\nmore", "--notes", "n1")["id"]
        self.assertEqual("added", self.q("dep", "add", b, a)["status"])
        self.assertEqual("removed", self.q("dep", "remove", b, a)["status"])
        shown = self.q("show", b)[0]
        self.assertEqual(("intro\n### Notes about x\nmore", "n1"), (shown["description"], shown["notes"]))

    def test_notes_heading_in_description_is_rejected(self):
        for description in ("a\n## Notes\nb", "a\r\n## Notes\r\nb", "a\r## Notes\rb"):
            code, _, err = self.run_task("create", "-d", description, "D")
            self.assertEqual(1, code, repr(description))
            self.assertIn("## Notes", err)
        task = self.q("create", "T")["id"]
        self.assertEqual(1, self.run_task("update", task, "-d", "x\n## Notes")[0])
        self.assertEqual("", self.q("show", task)[0]["description"])

    def test_undecodable_memory_and_tagged_scalars_fail_closed(self):
        self.q("remember", "a fact")
        memory = self.root / ".planning/tasks/memory.md"
        memory.write_bytes(memory.read_bytes() + b"\xff\n")
        code, _, err = self.run_task("remember", "hi")
        self.assertEqual((1, True), (code, str(memory) in err))
        self.q("create", "--type", "epic", "E")
        bad = self.root / ".planning/tasks/repo-1/bad.md"
        for head in ("priority: !!binary aGk=", "assignee: !!set {a: null}", "parent: [x]"):
            bad.write_text("---\nid: repo-9\ntitle: x\n" + head + "\n---\n", encoding="utf-8")
            code, _, err = self.run_task("show", "repo-9", "--json")
            self.assertEqual(1, code, head)
            self.assertIn(str(bad), err, head)

if __name__ == "__main__":
    unittest.main()
