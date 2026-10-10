"""The verify stage and verification_passed gate are gone: no tracked source or doc may still name them."""

from pathlib import Path
import re
import subprocess
import unittest

ROOT = Path(__file__).resolve().parents[2]
REMOVED = re.compile(
    r"verification_passed|verification-passed|verification\.passed|skills/verify|/gin-workflow:verify|model_tiers\.verify"
    r"|`verify` (stage|skill)|verify stage",
    re.IGNORECASE,
)
LEGACY_NOTE = re.compile(r"deprecated|removed", re.IGNORECASE)
# Intentional leftovers: removal messages, the deprecated-key mapping, historical-event readers, the review
# ledger's own state machine (its verification-* actions are kept on purpose).
ALLOWED = (
    "plugins/gin-workflow/src/scripts/workflow_core/lifecycle_cli.py",
    "plugins/gin-workflow/src/scripts/workflow_core/team.py",
    "plugins/gin-workflow/src/scripts/workflow_core/schemas.py",
    "plugins/gin-workflow/src/scripts/workflow_core/usage_attribution.py",
    "plugins/gin-workflow/src/scripts/review_ledger/",
    "plugins/gin-workflow/src/scripts/review-ledger.py",
    "tests/",
    ".planning/",
    ".beads/",
)


class TestNoVerifyStage(unittest.TestCase):
    def test_skill_directory_is_deleted(self):
        self.assertFalse((ROOT / "plugins/gin-workflow/src/skills/verify").exists())

    def test_no_tracked_file_names_the_removed_stage_or_gate(self):
        tracked = subprocess.run(["git", "ls-files"], cwd=ROOT, text=True, capture_output=True, check=True).stdout.split()
        offenders = []
        for relative in tracked:
            if relative.startswith(ALLOWED) or not (ROOT / relative).is_file():
                continue
            try:
                text = (ROOT / relative).read_text(encoding="utf-8")
            except UnicodeDecodeError:
                continue
            offenders += [f"{relative}:{n}" for n, line in enumerate(text.splitlines(), 1) if REMOVED.search(line) and not LEGACY_NOTE.search(line)]
        self.assertEqual([], offenders)


if __name__ == "__main__":
    unittest.main()
