"""safety-check.sh blocks `--no-verify` so the gin-workflow git hooks cannot be skipped."""

from pathlib import Path
import subprocess
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


if __name__ == "__main__":
    unittest.main()
