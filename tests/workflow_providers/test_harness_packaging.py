import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[2]

REQUIRED_V21_ARTIFACTS = (
    "commands/setup.md",
    "commands/workflow.md",
    "skills/setup/SKILL.md",
    "skills/workflow/SKILL.md",
    "skills/context-manager/SKILL.md",
    "skills/approval-manager/SKILL.md",
    "skills/evidence-manager/SKILL.md",
    "skills/worker-dispatch/SKILL.md",
    "skills/worker-dispatch/references/worker-lifecycle.md",
    "skills/worker-dispatch/references/delegation-policy.md",
    "skills/worker-dispatch/references/result-contract.md",
    "references/setup-system.md",
    "references/capability-provider-contracts.md",
    "references/context-and-evidence-policy.md",
    "references/agent-task-lifecycle.md",
    "references/orchestration-state-model.md",
    "references/verification-and-handoff-workflow.md",
    "scripts/gin-workflow",
    "scripts/workflow_core/__init__.py",
    "scripts/workflow_core/configuration.py",
    "scripts/workflow_core/setup_service.py",
    "scripts/workflow_core/router.py",
    "scripts/workflow_core/worker_scheduler.py",
    "scripts/workflow_providers/__init__.py",
    "scripts/workflow_providers/contracts.py",
    "scripts/workflow_providers/registry.py",
    "scripts/workflow_providers/task_tracking.py",
    "scripts/workflow_providers/knowledge.py",
    "scripts/workflow_providers/workspace.py",
    "scripts/workflow_providers/review.py",
    "scripts/workflow_providers/evidence.py",
    "scripts/workflow_providers/notifications.py",
    "scripts/workflow_providers/fakes.py",
    "scripts/workflow_providers/worker_dispatch.py",
    "scripts/workflow_providers/claude_worker.py",
    "scripts/workflow_providers/codex_worker.py",
    "scripts/workflow_providers/antigravity_worker.py",
    "scripts/workflow_providers/sequential_worker.py",
)


class HarnessPackagingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temporary_home = tempfile.TemporaryDirectory()
        shutil.rmtree(ROOT / "plugins/gin-workflow/dist", ignore_errors=True)
        shutil.rmtree(ROOT / "plugins/gin-workflow-advanced/dist", ignore_errors=True)
        environment = os.environ.copy()
        environment["HOME"] = cls.temporary_home.name
        cls.install = subprocess.run(
            ["bash", "install.sh", "--platform", "all", "--dry-run"],
            cwd=ROOT,
            env=environment,
            text=True,
            capture_output=True,
            check=False,
        )
        cls.dist = ROOT / "plugins/gin-workflow/dist"

    @classmethod
    def tearDownClass(cls):
        cls.temporary_home.cleanup()

    def test_dry_run_builds_all_three_harness_layouts(self):
        self.assertEqual(0, self.install.returncode, self.install.stderr)
        for harness in ("claude-code", "codex", "antigravity"):
            with self.subTest(harness=harness):
                root = self.dist / harness
                missing = [relative for relative in REQUIRED_V21_ARTIFACTS if not (root / relative).is_file()]
                self.assertEqual([], missing)

    def test_each_harness_has_its_manifest_and_hooks_in_the_expected_location(self):
        expected = {
            "claude-code": (".claude-plugin/plugin.json", "hooks/hooks.json"),
            "codex": (".codex-plugin/plugin.json", "hooks/hooks.json"),
            "antigravity": ("plugin.json", "hooks/hooks.json"),
        }
        for harness, relatives in expected.items():
            with self.subTest(harness=harness):
                root = self.dist / harness
                self.assertTrue(all((root / relative).is_file() for relative in relatives))


if __name__ == "__main__":
    unittest.main()
