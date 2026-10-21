"""safety-check.sh blocks `--no-verify` so the gin-workflow git hooks cannot be skipped."""

import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

SCRIPT = Path(__file__).resolve().parents[1] / "plugins/gin-workflow/src/scripts/safety-check.sh"
POST_EDIT_SCRIPT = Path(__file__).resolve().parents[1] / "plugins/gin-workflow/src/scripts/post-edit.sh"


def exit_code(command):
    return subprocess.run(["bash", str(SCRIPT), command], stdin=subprocess.DEVNULL, capture_output=True).returncode


class TestNoVerifyBlocked(unittest.TestCase):
    def test_blocks_no_verify_on_commit_push_merge(self):
        for command in ("git commit --no-verify -m x", "git push --no-verify", "git push origin main --no-verify",
                        "git merge --no-verify topic", "git -C /tmp/r commit -am x --no-verify"):
            self.assertEqual(2, exit_code(command), command)

    def test_allows_normal_commands(self):
        for command in ("git commit -m 'fix -n flag'", "git push -n", "git push origin main", "git status"):
            self.assertEqual(0, exit_code(command), command)


class TestRecursiveRemoval(unittest.TestCase):
    def test_blocks_dangerous_targets(self):
        for command in ("rm -rf /", "rm -rf ~", "rm -rf ~/", "rm -r .", "rm -fr ..", 'rm -rf "$HOME"', "rm --recursive $HOME",
                        "cd /tmp && rm -rf ~/*", "ls; sudo rm -rf /", "git rm -r .", "find . -exec rm -rf ./ \\;",
                        'rm -rf "a;b" ~', "echo x ; rm -rf 'a|b' /", "rm -rf a\\;b ~", "echo ok\nrm -rf ~"):
            self.assertEqual(2, exit_code(command), command)

    def test_checks_each_command_of_a_compound_command_on_its_own(self):
        for command in ("cd ~/gin-console && git rm -r --cached .beads", "cd ~/x && rm -r build",
                        "cd /tmp/a && rm .beads && ls -R ~/", "unlink /home/u/gin-workflow/.beads && ls ~/",
                        "rm /tmp/gin-workflow/x.txt", 'bd create --description "cd ~/x && git rm -r --cached .beads"'):
            self.assertEqual(0, exit_code(command), command)


class TestPayloadWithoutJq(unittest.TestCase):
    def test_python3_parses_the_payload_when_jq_is_missing(self):
        with tempfile.TemporaryDirectory() as directory:
            for tool in ("bash", "cat", "git", "realpath", "python3"):
                Path(directory, tool).symlink_to(shutil.which(tool))
            for command, expected in (("git commit --no-verify -m x", 2), ("git status", 0)):
                payload = json.dumps({"tool_input": {"command": command}, "cwd": directory})
                done = subprocess.run([str(Path(directory, "bash")), str(SCRIPT)], input=payload.encode(),
                                      env={"PATH": directory}, capture_output=True)
                self.assertEqual(expected, done.returncode, (command, done.stderr))


class TestCopilotPayloads(unittest.TestCase):
    def test_safety_check_blocks_dangerous_command_from_copilot_payload(self):
        payload = json.dumps({"tool_name": "bash", "tool_input": {"command": "rm -rf /"}, "cwd": "/tmp"})
        done = subprocess.run(["bash", str(SCRIPT)], input=payload.encode(), capture_output=True)
        self.assertEqual(2, done.returncode)

    def test_safety_check_allows_safe_command_from_copilot_payload(self):
        payload = json.dumps({"tool_name": "bash", "tool_input": {"command": "ls"}, "cwd": "/tmp"})
        done = subprocess.run(["bash", str(SCRIPT)], input=payload.encode(), capture_output=True)
        self.assertEqual(0, done.returncode)

    def test_post_edit_runs_on_path_from_copilot_payload(self):
        payload = json.dumps({"tool_name": "edit", "tool_input": {"path": "a.txt"}})
        done = subprocess.run(["bash", str(POST_EDIT_SCRIPT)], input=payload, capture_output=True, text=True)
        self.assertEqual(0, done.returncode)
        self.assertIn("Post-edit hook run on: a.txt", done.stdout)


if __name__ == "__main__":
    unittest.main()
