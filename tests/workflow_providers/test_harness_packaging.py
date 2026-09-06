import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[2]

CANONICAL_REFERENCE_PAIRS = (
    "agent-task-lifecycle.md",
    "orchestration-state-model.md",
    "setup-system.md",
    "capability-provider-contracts.md",
    "context-and-evidence-policy.md",
    "verification-and-handoff-workflow.md",
    "provider-routing.md",
)

USE_CASE_PAGES = (
    "README.md",
    "large-task.md",
    "resume-in-progress.md",
    "quick-debug.md",
)

REQUIRED_USE_CASE_SECTIONS = (
    "Prerequisites",
    "Flow",
    "State and evidence gates",
    "Realistic example",
    "Common failures",
    "Safe recovery",
)

REQUIRED_ARTIFACTS = (
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
    "references/provider-routing.md",
    "scripts/gin-workflow",
    "scripts/workflow_core/__init__.py",
    "scripts/workflow_core/configuration.py",
    "scripts/workflow_core/setup_service.py",
    "scripts/workflow_core/router.py",
    "scripts/workflow_core/worker_scheduler.py",
    "scripts/workflow_core/provider_config.py",
    "scripts/workflow_core/assignments.py",
    "scripts/workflow_core/review_coordinator.py",
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
    "scripts/workflow_providers/circuit_breaker.py",
    "scripts/workflow_providers/native_cli.py",
    "scripts/workflow_providers/routed_worker.py",
    "examples/config.full.yaml",
    "examples/providers.local.example.yaml",
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
                missing = [relative for relative in REQUIRED_ARTIFACTS if not (root / relative).is_file()]
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

    def test_plugin_metadata_and_harness_manifests_publish_version_1_1_0(self):
        manifests = (
            ROOT / "plugins/gin-workflow/plugin.meta.json",
            ROOT / "plugins/gin-workflow/src/.claude-plugin/plugin.json",
            ROOT / "plugins/gin-workflow/src/.codex-plugin/plugin.json",
            self.dist / "claude-code/.claude-plugin/plugin.json",
            self.dist / "codex/.codex-plugin/plugin.json",
            self.dist / "antigravity/plugin.json",
        )
        for manifest in manifests:
            with self.subTest(manifest=manifest.relative_to(ROOT)):
                with manifest.open(encoding="utf-8") as file:
                    self.assertEqual("1.1.2", json.load(file)["version"])

    def test_repository_ignores_installations_and_generated_workflow_output(self):
        ignored = (
            ".codex/plugin.json",
            ".claude/plugin.json",
            ".agents/plugin.json",
            ".agent-workflow/generated/plan.json",
            ".agent-workflow/runtime/evidence.json",
            ".agent-workflow/backups/config.yaml",
            ".agent-workflow/providers.local.yaml",
            "plugins/gin-workflow/dist/codex/plugin.json",
        )
        tracked = (
            "plugins/gin-workflow/src/commands/setup.md",
            ".claude-plugin/marketplace.json",
            ".agent-workflow/config.yaml",
            "docs/setup-system.md",
            "install.sh",
            "install.ps1",
        )

        for relative in ignored:
            with self.subTest(relative=relative):
                result = subprocess.run(
                    ["git", "check-ignore", "--no-index", "-q", relative],
                    cwd=ROOT,
                    check=False,
                )
                self.assertEqual(0, result.returncode)

        for relative in tracked:
            with self.subTest(relative=relative):
                result = subprocess.run(
                    ["git", "check-ignore", "--no-index", "-q", relative],
                    cwd=ROOT,
                    check=False,
                )
                self.assertEqual(1, result.returncode)
                tracked_result = subprocess.run(
                    ["git", "ls-files", "--error-unmatch", relative],
                    cwd=ROOT,
                    check=False,
                    capture_output=True,
                )
                self.assertEqual(0, tracked_result.returncode)

        untracked_roots = (
            ".codex",
            ".claude",
            ".agents",
            ".agent-workflow/generated",
            ".agent-workflow/runtime",
            ".agent-workflow/backups",
        )
        for root in untracked_roots:
            with self.subTest(root=root):
                result = subprocess.run(
                    ["git", "ls-files", "--", root],
                    cwd=ROOT,
                    check=False,
                    capture_output=True,
                    text=True,
                )
                self.assertEqual("", result.stdout)

    def test_canonical_references_are_packaged_without_drift(self):
        references = ROOT / "plugins/gin-workflow/src/references"
        for relative in CANONICAL_REFERENCE_PAIRS:
            canonical = ROOT / "docs" / relative
            packaged = references / relative
            with self.subTest(relative=relative):
                self.assertTrue(canonical.is_file())
                self.assertTrue(packaged.is_file())
                self.assertEqual(canonical.read_bytes(), packaged.read_bytes())

    def test_use_case_pages_have_required_sections_and_readme_links(self):
        use_cases = ROOT / "docs/use-cases"
        for relative in USE_CASE_PAGES:
            content = (use_cases / relative).read_text(encoding="utf-8")
            with self.subTest(relative=relative):
                for section in REQUIRED_USE_CASE_SECTIONS:
                    self.assertRegex(content, re.compile(rf"^## {re.escape(section)}\s*$", re.MULTILINE))

        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        for relative in ("large-task.md", "resume-in-progress.md", "quick-debug.md"):
            self.assertIn(f"docs/use-cases/{relative}", readme)

    def test_t8_lifecycle_review_is_separate_from_router_stages(self):
        lifecycle = (ROOT / "docs/agent-task-lifecycle.md").read_text(encoding="utf-8")
        resume = (ROOT / "docs/use-cases/resume-in-progress.md").read_text(encoding="utf-8")
        self.assertIn("separately coordinated provider-backed activity", lifecycle)
        self.assertIn("not a router lifecycle stage", lifecycle)
        self.assertIn("review_approved", lifecycle)
        self.assertNotIn("`workflow` routes review", resume)
        self.assertIn("review capability before workflow", resume)
        self.assertIn("router mechanically selects `verify` after", resume)
        self.assertIn("regardless of review state", resume)
        self.assertIn("The verify wrapper and evidence checks", resume)
        self.assertIn("fail closed without terminal review approval", resume)
        flow = resume[resume.index("## Flow") : resume.index("## State and evidence gates")]
        self.assertLess(flow.index("$gin-workflow:progress"), flow.index("Inspect that durable state"))
        self.assertLess(flow.index("Inspect that durable state"), flow.index("review capability and"))
        self.assertLess(flow.index("review capability and"), flow.index("$gin-workflow:workflow"))
        self.assertLess(flow.index("$gin-workflow:workflow"), flow.index("$gin-workflow:verify"))
        self.assertNotIn("Only then can `workflow` route `verify`", resume)

    def test_t8_quick_debug_orchestrates_before_execute(self):
        content = (ROOT / "docs/use-cases/quick-debug.md").read_text(encoding="utf-8")
        self.assertIn("$gin-workflow:orchestrate", content)
        self.assertIn("orchestration_ready", content)
        self.assertLess(content.index("$gin-workflow:orchestrate"), content.index("$gin-workflow:execute"))
        self.assertIn("creates the Bead", content)

    def test_t8_provider_routing_documents_portable_and_local_boundaries(self):
        content = (ROOT / "docs/provider-routing.md").read_text(encoding="utf-8")
        self.assertIn("provider aliases plus routing/concurrency policy", content)
        self.assertIn("machine-local provider/authentication", content)
        self.assertIn("concrete model aliases", content)
        self.assertIn("secret values", content)
        self.assertIn("provider_default", content)

    def test_scoped_markdown_links_are_repo_relative_and_resolve(self):
        roots = [ROOT / "README.md", ROOT / "docs", ROOT / "plugins/gin-workflow/src/references"]
        link_pattern = re.compile(r"\[[^\]]+\]\(([^)]+)\)")
        for root in roots:
            paths = [root] if root.is_file() else sorted(root.rglob("*.md"))
            for path in paths:
                for target in link_pattern.findall(path.read_text(encoding="utf-8")):
                    if target.startswith(("http://", "https://", "mailto:", "#")):
                        continue
                    target_path = target.split("#", 1)[0]
                    if not target_path:
                        continue
                    with self.subTest(path=path.relative_to(ROOT), target=target):
                        self.assertFalse(Path(target_path).is_absolute(), f"absolute Markdown link is not allowed: {target}")
                        resolved = (path.parent / target_path).resolve()
                        self.assertTrue(
                            resolved == ROOT or ROOT in resolved.parents,
                            f"Markdown link escapes repository root: {target}",
                        )
                        self.assertTrue(resolved.is_file(), f"missing Markdown link target: {target}")


if __name__ == "__main__":
    unittest.main()
