import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[2]

USE_CASE_SECTIONS = (
    "Small change",
    "Bounded defect",
    "Large multi-track change",
    "Resume in-progress work",
)

REQUIRED_ARTIFACTS = (
    "skills/setup/SKILL.md",
    "skills/workflow/SKILL.md",
    "skills/discuss/SKILL.md",
    "skills/plan/SKILL.md",
    "skills/plan/plan-schema.md",
    "skills/orchestrate/SKILL.md",
    "skills/execute/SKILL.md",
    "skills/execute/references/worker-lifecycle.md",
    "skills/execute/references/delegation-policy.md",
    "skills/execute/references/result-contract.md",
    "skills/verify/SKILL.md",
    "skills/ship/SKILL.md",
    "skills/review/SKILL.md",
    "references/stage-contract.md",
    "references/shape-frontend.md",
    "references/shape-backend.md",
    "agents/developer.md",
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
    "rules/README.md",
    "rules/core.md",
    "rules/lean.md",
    "rules/typescript.md",
    "rules/python.md",
    "rules/react.md",
    "rules/nextjs.md",
    "rules/fastapi.md",
    "rules/node-api.md",
    "templates/proposal.md",
    "templates/spec-delta.md",
    "templates/spec.md",
    "templates/specs-README.md",
    "templates/codebase/OVERVIEW.md",
    "scripts/workflow_core/specs.py",
    "scripts/workflow_core/specs_cli.py",
    "scripts/workflow_core/specs_archive.py",
    "scripts/workflow_core/specs_trace.py",
    "scripts/workflow_core/specs_migrate.py",
    "skills/migrate-specs/SKILL.md",
    "skills/gin-sdd/SKILL.md",
    "templates/team/pull_request_template.md",
    "templates/team/commit-msg",
    "templates/team/github-ci.yml",
    "templates/team/gitlab-ci.yml",
    "scripts/workflow_core/team.py",
    "scripts/workflow_core/team_host.py",
    "scripts/workflow_core/team_beads.py",
    "scripts/workflow_core/team_init.py",
    "scripts/workflow_core/team_cli.py",
    "skills/gin-team/SKILL.md",
    "skills/team-setup/SKILL.md",
    "skills/report/SKILL.md",
    "scripts/workflow_core/usage.py",
    "scripts/workflow_core/usage_logs.py",
    "scripts/workflow_core/usage_attribution.py",
    "scripts/workflow_core/usage_cli.py",
    "skills/describe/SKILL.md",
    "scripts/workflow_core/describe.py",
    "scripts/workflow_core/describe_cli.py",
    "templates/describe.html",
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

    def test_removed_agents_are_gone_and_unreferenced(self):
        src = ROOT / "plugins/gin-workflow/src"
        for name in ("full-stack-developer", "codebase-mapper"):
            with self.subTest(agent=name):
                self.assertFalse((src / "agents" / f"{name}.md").exists())
                mentions = [path.relative_to(src).as_posix() for path in src.rglob("*")
                            if path.is_file() and path.suffix in (".md", ".py", ".json", ".yaml")
                            and name in path.read_text(encoding="utf-8", errors="replace")]
                self.assertEqual([], mentions)

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
                    self.assertEqual("1.3.1", json.load(file)["version"])

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
            "plugins/gin-workflow/src/skills/setup/SKILL.md",
            ".claude-plugin/marketplace.json",
            ".agent-workflow/config.yaml",
            "docs/reference/config.md",
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

    def test_docs_have_a_single_copy_outside_the_bundle(self):
        references = ROOT / "plugins/gin-workflow/src/references"
        packaged = sorted(path.name for path in references.glob("*.md"))
        self.assertEqual(["shape-backend.md", "shape-frontend.md", "stage-contract.md"], packaged)

    def test_use_cases_guide_has_every_case_and_readme_links_it(self):
        content = (ROOT / "docs/guides/use-cases.md").read_text(encoding="utf-8")
        for section in USE_CASE_SECTIONS:
            with self.subTest(section=section):
                self.assertRegex(content, re.compile(rf"^## {re.escape(section)}\s*$", re.MULTILINE))
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        self.assertIn("docs/guides/use-cases.md", readme)

    def test_t8_lifecycle_review_is_separate_from_router_stages(self):
        lifecycle = (ROOT / "docs/concepts/lifecycle.md").read_text(encoding="utf-8")
        guide = (ROOT / "docs/guides/use-cases.md").read_text(encoding="utf-8")
        resume = guide[guide.index("## Resume in-progress work"):]
        self.assertIn("not a router lifecycle stage", lifecycle)
        self.assertIn("review_approved", lifecycle)
        self.assertIn("fails closed when a ledger lacks terminal approval", resume)
        self.assertLess(resume.index("/gin-workflow:progress"), resume.index("finish the review first"))
        self.assertLess(resume.index("finish the review first"), resume.index("/gin-workflow:workflow"))
        self.assertLess(resume.index("/gin-workflow:workflow"), resume.index("selects `verify`"))

    def test_t8_bounded_defect_orchestrates_before_execute(self):
        guide = (ROOT / "docs/guides/use-cases.md").read_text(encoding="utf-8")
        defect = guide[guide.index("## Bounded defect"):guide.index("## Large multi-track change")]
        self.assertIn("/gin-workflow:orchestrate", defect)
        self.assertLess(defect.index("/gin-workflow:orchestrate"), defect.index("/gin-workflow:execute"))
        self.assertLess(defect.index("gin-debugging"), defect.index("/gin-workflow:plan"))

    def test_t8_provider_routing_documents_portable_and_local_boundaries(self):
        content = (ROOT / "docs/concepts/providers.md").read_text(encoding="utf-8")
        self.assertIn("without ever writing a provider or model name into the plan or Beads", content)
        self.assertIn("Concrete models come only from `.agent-workflow/providers.local.yaml`", content)
        self.assertIn("secret values are never written", content)
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
