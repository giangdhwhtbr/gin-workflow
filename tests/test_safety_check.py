"""safety-check.sh blocks `--no-verify` so the gin-workflow git hooks cannot be skipped."""

import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

SCRIPT = Path(__file__).resolve().parents[1] / "plugins/gin-workflow/src/scripts/safety-check.sh"


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


if __name__ == "__main__":
    unittest.main()
