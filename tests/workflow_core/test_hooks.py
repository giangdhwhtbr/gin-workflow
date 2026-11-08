"""`gin hooks install|run`: shims, idempotence, first-failure stop, push filtering."""

from __future__ import annotations

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

from workflow_core import hooks, setup_service, verification  # noqa: E402
from workflow_core.events import WorkflowEventStore  # noqa: E402
from tests.workflow_core.test_workspace import make_workspace  # noqa: E402

CONFIG = """schema_version: "2.7"
project:
  rigor: {rigor}
verify:
  checks:
    lint: '{lint}'
    typecheck: ""
    test: '{test}'
    build: ""
    e2e: ""
"""
ZERO = "0" * 40


def git(root, *args):
    return subprocess.run(["git", *args], cwd=root, text=True, capture_output=True, check=True).stdout.strip()


def make_repo(base, *, lint="true", test="true", rigor="standard", extra=""):
    root = Path(base)
    git(root, "init", "-q")
    git(root, "config", "user.email", "t@example.com")
    git(root, "config", "user.name", "t")
    (root / ".agent-workflow").mkdir()
    (root / ".agent-workflow/config.yaml").write_text(CONFIG.format(rigor=rigor, lint=lint, test=test) + extra)
    (root / "f.txt").write_text("x")
    git(root, "add", "-A")
    git(root, "commit", "-qm", "init", "--no-verify")
    return root


def push_ref(root):
    return f"refs/heads/main {git(root, 'rev-parse', 'HEAD')} refs/heads/main {ZERO}"


class TestHooksStatus(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)

    def status(self, root):
        with contextlib.redirect_stdout(io.StringIO()) as out:
            code = hooks.main(["status", "--repository", str(root)])
        return code, json.loads(out.getvalue())

    def test_us8_missing_hook_is_not_ok(self):
        code, report = self.status(make_repo(self.tmp.name))
        self.assertEqual(1, code)
        self.assertEqual((False, "missing"), (report["ok"], report["hooks"]["pre-commit"]))
        self.assertEqual(["lint", "test"], report["verify_commands"])

    def test_us8_hooks_and_commands_in_place_are_ok(self):
        root = make_repo(self.tmp.name)
        hooks.install(root)
        code, report = self.status(root)
        self.assertEqual((0, True), (code, report["ok"]))

    def test_us8_no_verify_commands_is_not_ok(self):
        root = make_repo(self.tmp.name, lint="", test="")
        hooks.install(root)
        code, report = self.status(root)
        self.assertEqual((1, False, []), (code, report["ok"], report["verify_commands"]))


class TestHooksInstall(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = make_repo(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def test_install_is_idempotent(self):
        first = hooks.install(self.root)
        self.assertEqual("installed", first["status"])
        self.assertEqual({"pre-commit": "installed", "pre-push": "installed"}, first["hooks"])
        hook = self.root / ".git/hooks/pre-push"
        if os.name != "nt":  # POSIX permission bits
            self.assertEqual(0o755, hook.stat().st_mode & 0o777)
        self.assertIn("hooks run pre-push", hook.read_text())
        again = hooks.install(self.root)
        self.assertEqual({"pre-commit": "unchanged", "pre-push": "unchanged"}, again["hooks"])

    def test_install_keeps_the_push_connection_alive_during_pre_push(self):
        with mock.patch.dict(os.environ, {}, clear=False):
            for name in ("GIT_SSH", "GIT_SSH_COMMAND"):
                os.environ.pop(name, None)
            self.assertEqual("set", hooks.install(self.root)["ssh_keepalive"])
            self.assertEqual(hooks.SSH_KEEPALIVE, git(self.root, "config", "--local", "core.sshCommand"))
            git(self.root, "config", "core.sshCommand", "ssh -i key")
            self.assertEqual("kept", hooks.install(self.root)["ssh_keepalive"])
            self.assertEqual("ssh -i key", git(self.root, "config", "core.sshCommand"))

    def test_install_leaves_ssh_alone_when_the_environment_chooses_it(self):
        with mock.patch.dict(os.environ, {"GIT_SSH": "plink"}):
            self.assertEqual("kept", hooks.install(self.root)["ssh_keepalive"])
        self.assertEqual("", subprocess.run(["git", "config", "core.sshCommand"], cwd=self.root,
                                            text=True, capture_output=True).stdout)

    def test_install_reports_a_keepalive_it_cannot_write(self):
        failing = subprocess.CompletedProcess([], 1, b"", b"")
        real_run = subprocess.run
        def run(argv, **kwargs):
            return failing if argv[:3] == ["git", "config", "--local"] else real_run(argv, **kwargs)
        with mock.patch.dict(os.environ, {}, clear=False), mock.patch.object(hooks.subprocess, "run", run):
            for name in ("GIT_SSH", "GIT_SSH_COMMAND"):
                os.environ.pop(name, None)
            result = hooks.install(self.root)
        self.assertEqual(("installed", "failed"), (result["status"], result["ssh_keepalive"]))

    def test_foreign_hook_is_kept(self):
        foreign = self.root / ".git/hooks/pre-commit"
        foreign.write_text("#!/bin/sh\necho mine\n")
        result = hooks.install(self.root)
        self.assertEqual("occupied", result["status"])
        self.assertEqual("occupied", result["hooks"]["pre-commit"])
        self.assertEqual("installed", result["hooks"]["pre-push"])
        self.assertEqual("#!/bin/sh\necho mine\n", foreign.read_text())

    def test_missing_hooks_path_is_reported_not_created(self):
        git(self.root, "config", "core.hooksPath", str(self.root / "nope"))
        result = hooks.install(self.root)
        self.assertEqual("missing", result["status"])
        self.assertFalse((self.root / "nope").exists())

    def test_status(self):
        self.assertEqual({"pre-commit": "missing", "pre-push": "missing"}, hooks.status(self.root))
        hooks.install(self.root)
        self.assertEqual({"pre-commit": "ok", "pre-push": "ok"}, hooks.status(self.root))

    def test_chained_foreign_hook_counts_as_ok(self):
        (self.root / ".git/hooks/pre-push").write_text('#!/bin/sh\nmy-tool\nexec gin hooks run pre-push "$@"\n')
        self.assertEqual("ok", hooks.status(self.root)["pre-push"])
        (self.root / ".git/hooks/pre-commit").write_text("#!/bin/sh\necho mine\n")
        self.assertEqual("occupied", hooks.status(self.root)["pre-commit"])
        actions = setup_service.doctor(repository=self.root)["actions"]
        self.assertTrue(any("pre-commit" in a and "hooks run pre-commit" in a for a in actions), actions)

    def test_install_reports_a_chained_foreign_hook_as_chained(self):
        chained = '#!/bin/sh\nmy-tool\nexec gin hooks run pre-push\n'
        (self.root / ".git/hooks/pre-push").write_text(chained)
        result = hooks.install(self.root)
        self.assertEqual(("installed", "chained"), (result["status"], result["hooks"]["pre-push"]))
        self.assertEqual(chained, (self.root / ".git/hooks/pre-push").read_text())

    def test_doctor_reports_hooks_without_flipping_health(self):
        payload = setup_service.doctor(repository=self.root)
        self.assertEqual({"pre-commit": "missing", "pre-push": "missing"}, payload["checks_details"]["hooks"])
        self.assertTrue(any(action.startswith("hooks: pre-push is missing") for action in payload["actions"]))
        self.assertTrue(all(payload["checks"].get(name, True) for name in ("configuration",)))


    def test_install_rewrites_a_legacy_hook(self):
        hook = self.root / ".git/hooks/pre-commit"
        hook.write_text("#!/bin/sh\n# generated by gin-workflow hooks install: pre-commit\n"
                        'exec gin-workflow hooks run pre-commit "$@"\n', encoding="utf-8")
        self.assertEqual("stale", hooks.status(self.root)["pre-commit"])
        self.assertEqual("installed", hooks.install(self.root)["hooks"]["pre-commit"])
        text = hook.read_text(encoding="utf-8")
        self.assertIn('exec gin hooks run pre-commit "$@"', text)
        self.assertNotIn("gin-workflow", text)
        self.assertEqual("ok", hooks.status(self.root)["pre-commit"])

    def test_a_chained_legacy_call_is_stale(self):
        hook = self.root / ".git/hooks/pre-push"
        hook.write_text('#!/bin/sh\nmy-check && gin-workflow hooks run pre-push "$@"\n', encoding="utf-8")
        self.assertEqual("stale", hooks.status(self.root)["pre-push"])
        self.assertEqual("chained", hooks.install(self.root)["hooks"]["pre-push"])

    def test_doctor_tells_how_to_fix_a_stale_hook(self):
        hook = self.root / ".git/hooks/pre-push"
        hook.write_text('#!/bin/sh\nmy-check && gin-workflow hooks run pre-push "$@"\n', encoding="utf-8")
        actions = setup_service.doctor(repository=self.root)["actions"]
        self.assertIn("hooks: pre-push still calls gin-workflow; run gin hooks install, "
                      "or in a hook you wrote replace gin-workflow hooks run with gin hooks run", actions)


class TestHooksRun(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.base = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def repo(self, name, **kwargs):
        path = self.base / name
        path.mkdir()
        return make_repo(path, **kwargs)

    def test_pre_commit_runs_only_lint_and_typecheck(self):
        self.assertNotEqual(0, hooks.run(self.repo("a", lint="false", test="false"), "pre-commit"))
        self.assertEqual(0, hooks.run(self.repo("b", lint="true", test="false"), "pre-commit"))

    @unittest.skipIf(os.name == "nt", "the verify command is POSIX sh syntax")
    def test_pre_push_runs_test_and_stops_at_first_failure(self):
        root = self.repo("a", test="echo ran >> ran.txt; false")
        self.assertNotEqual(0, hooks.run(root, "pre-push", [push_ref(root)]))
        self.assertEqual("ran\n", (root / "ran.txt").read_text())

    def test_pre_push_skips_tags_deletes_and_other_shas(self):
        root = self.repo("a", test="false")
        head = git(root, "rev-parse", "HEAD")
        for ref in (f"refs/tags/v1 {head} refs/tags/v1 {ZERO}",
                    f"HEAD {head} refs/tags/v1 {ZERO}",
                    f"(delete) {ZERO} refs/heads/x {head}",
                    f"refs/heads/other {'a' * 40} refs/heads/other {ZERO}"):
            self.assertEqual(0, hooks.run(root, "pre-push", [ref]), ref)

    def test_empty_verify_commands_exit_zero(self):
        root = self.repo("a", lint="", test="")
        self.assertEqual(0, hooks.run(root, "pre-commit"))
        self.assertEqual(0, hooks.run(root, "pre-push", [push_ref(root)]))

    def test_us6_env_prefix_is_split_off_the_command(self):
        calls = []
        def fake_run(command, **kwargs):
            calls.append((command, kwargs["env"]))
            return subprocess.CompletedProcess(command, 0)
        with mock.patch.object(hooks.subprocess, "run", fake_run):
            hooks._run_commands("pre-commit", [("test", "PYTHONPATH=src A_B=x=y python -m unittest")], Path("."), {"PATH": "p"})
        self.assertEqual([("python -m unittest", {"PATH": "p", "PYTHONPATH": "src", "A_B": "x=y"})], calls)

    def test_us6_command_without_prefix_is_unchanged(self):
        calls = []
        with mock.patch.object(hooks.subprocess, "run", lambda command, **kwargs: calls.append(command) or subprocess.CompletedProcess(command, 0)):
            hooks._run_commands("pre-commit", [("test", "echo A=1; ls -l=x")], Path("."), {})
        self.assertEqual(["echo A=1; ls -l=x"], calls)

    def test_env_prefix_stops_at_shell_metacharacters(self):
        for command in ('A="x y" cmd', "A='x y' cmd", "A=$HOME cmd", "A=x;rm cmd"):
            with self.subTest(command=command):
                self.assertEqual((command, {}), hooks._split_env_prefix(command))

    @unittest.skipIf(os.name == "nt", "the verify command is POSIX sh syntax")
    def test_git_env_is_stripped(self):
        root = self.repo("a", lint='test -z "$GIT_INDEX_FILE"')
        os.environ["GIT_INDEX_FILE"] = "/nonexistent"
        try:
            self.assertEqual(0, hooks.run(root, "pre-commit"))
        finally:
            del os.environ["GIT_INDEX_FILE"]

    def test_package_checks_run_in_the_package_directory(self):
        extra = ("  packages:\n    - path: pkg\n      shape: library\n      verify:\n"
                 "        checks:\n          test: \"touch ../pkg-ran\"\n")
        root = self.repo("a", test="true", extra="")
        config = root / ".agent-workflow/config.yaml"
        config.write_text(config.read_text().replace("project:\n  rigor: standard\n",
                                                     "project:\n  rigor: standard\n" + extra))
        (root / "pkg").mkdir()
        self.assertEqual(0, hooks.run(root, "pre-push", [push_ref(root)]))
        self.assertTrue((root / "pkg-ran").exists())

    def test_real_git_commit_is_blocked_by_installed_hook(self):
        root = self.repo("a", lint="false")
        bin_dir = self.base / "bin"
        bin_dir.mkdir()
        wrapper = bin_dir / "gin"
        wrapper.write_text(f'#!/bin/sh\nexec python3 "{SCRIPTS / "gin"}" "$@"\n')
        wrapper.chmod(0o755)
        hooks.install(root)
        (root / "f.txt").write_text("y")
        git(root, "add", "-A")
        env = {**os.environ, "PATH": f"{bin_dir}:{os.environ['PATH']}"}
        blocked = subprocess.run(["git", "commit", "-qm", "x"], cwd=root, env=env, capture_output=True, text=True)
        self.assertNotEqual(0, blocked.returncode)
        self.assertIn("lint failed", blocked.stderr)

    def test_real_git_push_runs_the_installed_hook(self):
        bin_dir = self.base / "bin"
        bin_dir.mkdir()
        wrapper = bin_dir / "gin"
        wrapper.write_text(f'#!/bin/sh\nexec python3 "{SCRIPTS / "gin"}" "$@"\n')
        wrapper.chmod(0o755)
        env = {**os.environ, "PATH": f"{bin_dir}:{os.environ['PATH']}"}
        for name, test, expected in (("ok", "true", 0), ("bad", "false", 1)):
            root = self.repo(name, test=test)
            remote = self.base / f"{name}.git"
            git(self.base, "init", "-q", "--bare", str(remote))
            git(root, "remote", "add", "origin", str(remote))
            hooks.install(root)
            pushed = subprocess.run(["git", "push", "-q", "origin", "HEAD:refs/heads/main"], cwd=root, env=env,
                                    capture_output=True, text=True)
            self.assertNotIn("unrecognized arguments", pushed.stderr)
            self.assertEqual(expected, int(pushed.returncode != 0), pushed.stderr)


if __name__ == "__main__":
    unittest.main()


class TestPassingRunRecords(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.base = Path(os.path.realpath(self.tmp.name))
        self.root = make_repo(self.base)

    def other(self, name, **kwargs):
        path = self.base / name
        path.mkdir()
        return make_repo(path, **kwargs)

    def records(self, root):
        path = root / ".agent-workflow/runtime/events.jsonl"
        events = WorkflowEventStore(path).read_all() if path.is_file() else []
        return [event for event in events if event.event_type == verification.EVENT_TYPE]

    def test_us4_passing_pre_push_records_the_tested_tree(self):
        self.assertEqual(0, hooks.run(self.root, "pre-push", [push_ref(self.root)]))
        found, _ = verification.check(self.root, "HEAD")
        self.assertEqual(found["tree"], git(self.root, "rev-parse", "HEAD^{tree}"))
        self.assertEqual((found["hook"], found["commands"]), ("pre-push", ["test"]))

    def test_pre_push_skips_commands_already_proven_on_the_tree(self):
        root = self.other("b", test="echo run>> ran.txt")
        err = io.StringIO()
        with contextlib.redirect_stderr(err):
            self.assertEqual(0, hooks.run(root, "pre-push", [push_ref(root)]))
            self.assertEqual(0, hooks.run(root, "pre-push", [push_ref(root)]))
        self.assertEqual("run\n", (root / "ran.txt").read_text())
        self.assertEqual(1, len(self.records(root)))
        self.assertIn("test already passed on this tree", err.getvalue())
        self.assertEqual(0, verification.run(root))
        self.assertEqual("run\n", (root / "ran.txt").read_text())

    def test_pre_push_reruns_when_the_record_lacks_a_configured_command(self):
        root = self.other("b", test="echo run>> ran.txt")
        verification.record(root, "pre-push", git(root, "rev-parse", "HEAD^{tree}"), ["pkg:test"])
        with contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(0, hooks.run(root, "pre-push", [push_ref(root)]))
        self.assertEqual("run\n", (root / "ran.txt").read_text())
        self.assertEqual(2, len(self.records(root)))

    def test_pre_push_reruns_on_a_different_tree(self):
        root = self.other("b", test="echo run>> ran.txt")
        with contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(0, hooks.run(root, "pre-push", [push_ref(root)]))
            (root / "f.txt").write_text("z")
            git(root, "commit", "-qam", "change", "--no-verify")
            self.assertEqual(0, hooks.run(root, "pre-push", [push_ref(root)]))
        self.assertEqual("run\nrun\n", (root / "ran.txt").read_text())
        self.assertEqual(2, len(self.records(root)))

    def test_pre_push_runs_when_the_record_file_is_unreadable(self):
        root = self.other("b", test="echo run>> ran.txt")
        events = root / ".agent-workflow/runtime/events.jsonl"
        events.parent.mkdir(parents=True)
        events.write_text("not json\n")
        err = io.StringIO()
        with contextlib.redirect_stderr(err):
            self.assertEqual(0, hooks.run(root, "pre-push", [push_ref(root)]))
        self.assertEqual("run\n", (root / "ran.txt").read_text())
        self.assertIn("earlier runs not readable", err.getvalue())

    def test_us4_failing_run_records_nothing(self):
        root = self.other("b", test="false")
        self.assertNotEqual(0, hooks.run(root, "pre-push", [push_ref(root)]))
        self.assertEqual([], self.records(root))

    def test_us4_tracked_changes_record_nothing(self):
        (self.root / "f.txt").write_text("y")
        self.assertEqual(0, hooks.run(self.root, "pre-push", [push_ref(self.root)]))
        self.assertEqual([], self.records(self.root))

    def test_us4_pre_commit_records_nothing(self):
        self.assertEqual(0, hooks.run(self.root, "pre-commit"))
        self.assertEqual([], self.records(self.root))

    def test_us4_failed_record_warns_and_keeps_the_exit_code(self):
        err = io.StringIO()
        with mock.patch.object(verification, "record", side_effect=OSError("disk full")), \
                contextlib.redirect_stderr(err):
            self.assertEqual(0, hooks.run(self.root, "pre-push", [push_ref(self.root)]))
        self.assertIn("passing run not recorded: disk full", err.getvalue())

    def test_us4_check_needs_a_test_command(self):
        tree = git(self.root, "rev-parse", "HEAD^{tree}")
        self.assertEqual((None, f"no passing check recorded for tree {tree}"), verification.check(self.root, "HEAD"))
        verification.record(self.root, "pre-push", tree, ["lint"])
        found, reason = verification.check(self.root, "HEAD")
        self.assertIsNone(found)
        self.assertIn("ran no test command", reason)
        verification.record(self.root, "pre-push", tree, ["pkg:test"])
        self.assertIsNotNone(verification.check(self.root, "HEAD")[0])

    def test_us4_check_without_commit_needs_a_clean_tree(self):
        verification.record(self.root, "pre-push", git(self.root, "rev-parse", "HEAD^{tree}"), ["test"])
        self.assertIsNotNone(verification.check(self.root)[0])
        (self.root / "f.txt").write_text("y")
        found, reason = verification.check(self.root)
        self.assertIsNone(found)
        self.assertIn("commit them first", reason)

    def test_us4_evidence_cli_run_and_check(self):
        quiet = contextlib.redirect_stdout(io.StringIO())
        with quiet, contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(1, verification.main(["check", "--repository", str(self.root)]))
            self.assertEqual(0, verification.main(["run", "--repository", str(self.root)]))
            self.assertEqual(0, verification.main(["check", "--commit", "HEAD", "--repository", str(self.root)]))
            (self.root / "f.txt").write_text("y")
            self.assertEqual(2, verification.main(["run", "--repository", str(self.root)]))

    def test_us4_record_from_a_linked_worktree_lands_in_the_main_checkout(self):
        tree = self.base / "wt"
        git(self.root, "worktree", "add", "-q", "-b", "track", str(tree))
        with contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(0, verification.run(tree))
        self.assertEqual(1, len(self.records(self.root)))
        self.assertIsNotNone(verification.check(self.root, "HEAD")[0])


class WorkspaceHookTests(unittest.TestCase):
    """Hooks fired in a child repository run that entry's checks and record in the workspace."""

    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.root = make_workspace(Path(directory.name).resolve())
        self.child = self.root / "services/api"
        config = self.root / ".agent-workflow/config.yaml"
        text = config.read_text(encoding="utf-8").replace(
            'verify: {checks: {test: "echo api-test"}}', 'verify: {checks: {lint: "touch child-lint", test: "true"}}')
        config.write_text(text + "verify:\n  checks:\n    lint: touch parent-lint\n", encoding="utf-8")

    def hook(self, *argv):
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = hooks.main(list(argv))
        return code, out.getvalue(), err.getvalue()

    def events(self):
        path = self.root / ".agent-workflow/runtime/events.jsonl"
        return WorkflowEventStore(path).read_all() if path.is_file() else []

    def test_pre_commit_in_a_child_runs_only_the_entry_checks(self):
        code, _, _ = self.hook("run", "pre-commit", "--repository", str(self.child))
        self.assertEqual(0, code)
        self.assertTrue((self.child / "child-lint").is_file())
        self.assertFalse((self.child / "parent-lint").exists() or (self.root / "parent-lint").exists())

    def test_status_in_a_child_lists_the_entry_checks_only(self):
        _, out, _ = self.hook("status", "--repository", str(self.child))
        self.assertEqual(["services/api:lint", "services/api:test"], json.loads(out)["verify_commands"])

    def test_passing_pre_push_in_a_child_records_in_the_workspace(self):
        with mock.patch.object(sys, "stdin", io.StringIO(push_ref(self.child))):
            self.assertEqual(0, self.hook("run", "pre-push", "--repository", str(self.child))[0])
        self.assertEqual(1, len(self.events()))
        self.assertFalse((self.child / ".agent-workflow/runtime/events.jsonl").exists())
        with mock.patch.object(sys, "stdin", io.StringIO(push_ref(self.child))):
            code, _, err = self.hook("run", "pre-push", "--repository", str(self.child))
        self.assertEqual(0, code)
        self.assertIn("already passed on this tree", err)
        self.assertEqual(1, len(self.events()))

    def child_worktree(self):
        worktree = self.root / ".planning/worktrees/t1"
        git(self.child, "worktree", "add", "-q", str(worktree), "-b", "feat/t1", "main")
        return worktree

    def test_pre_commit_in_a_child_worktree_runs_the_checks_there(self):
        worktree = self.child_worktree()
        code, _, _ = self.hook("run", "pre-commit", "--repository", str(worktree))
        self.assertEqual(0, code)
        self.assertTrue((worktree / "child-lint").is_file())
        self.assertFalse((self.child / "child-lint").exists())

    def test_pre_push_in_a_child_worktree_records_the_worktree_tree(self):
        worktree = self.child_worktree()
        with mock.patch.object(sys, "stdin", io.StringIO(push_ref(worktree))):
            self.assertEqual(0, self.hook("run", "pre-push", "--repository", str(worktree))[0])
        self.assertFalse((self.child / "child-lint").exists())
        self.assertEqual([git(worktree, "rev-parse", "HEAD^{tree}")],
                         [event.payload["tree"] for event in self.events()])

    def test_install_all_repos_skips_frozen_beads_and_missing_clones(self):
        code, out, _ = self.hook("install", "--all-repos", "--repository", str(self.root))
        self.assertEqual(0, code)
        self.assertTrue((self.child / ".git/hooks/pre-commit").is_file())
        self.assertFalse((self.root / ".git/hooks/pre-commit").exists())
        for line in ("services/api: pre-commit: installed", "legacy/portal: skipped (frozen)",
                     ".beads: skipped (beads)", "apps/web: skipped (not cloned)"):
            self.assertIn(line, out)

    def test_install_all_repos_outside_a_workspace_fails(self):
        with tempfile.TemporaryDirectory() as plain:
            code, _, err = self.hook("install", "--all-repos", "--repository", str(make_repo(plain)))
        self.assertEqual((1, "error: not in a workspace\n"), (code, err))

    def test_a_child_without_checks_has_nothing_to_run(self):
        config = self.root / ".agent-workflow/config.yaml"
        config.write_text(config.read_text(encoding="utf-8").replace(
            'verify: {checks: {lint: "touch child-lint", test: "true"}}', "verify: {checks: {}}"), encoding="utf-8")
        code, _, err = self.hook("run", "pre-commit", "--repository", str(self.child))
        self.assertEqual(0, code)
        self.assertIn("no verify commands configured", err)
        self.assertFalse((self.root / "parent-lint").exists())
