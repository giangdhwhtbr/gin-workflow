import json
import os
import shutil
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest import mock


ROOT = Path(__file__).resolve().parents[2]
LAUNCHER = ROOT / "plugins/gin-workflow/src/scripts/gin-workflow"
sys.path.insert(0, str(ROOT / "plugins/gin-workflow/src/scripts"))

from workflow_core import setup_service  # noqa: E402
from tests.workflow_core.orchestrator_fakes import fake_orchestrator, on_path  # noqa: E402


class SetupCliTests(unittest.TestCase):
    def test_reports_current_setup_cli_version(self):
        result = subprocess.run(
            [sys.executable, str(LAUNCHER), "--version"],
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=False,
        )

        self.assertEqual(0, result.returncode, result.stderr)
        self.assertEqual("gin-workflow 2.8", result.stdout.strip())

    def run_cli(self, repository: Path, *arguments: str,
                env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, str(LAUNCHER), "setup", *arguments, "--repository", str(repository), "--format", "json"],
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=False,
            env=env,
        )

    def test_preset_proposes_explicit_assignments(self):
        with tempfile.TemporaryDirectory() as directory:
            result = self.run_cli(Path(directory), "preset", "--project-stage", "brownfield", "--project-shape",
                                  "frontend", "--rigor", "easy", "--task-tracking", "markdown")
            self.assertEqual(0, result.returncode, result.stderr)
            payload = json.loads(result.stdout)
            self.assertEqual("proposed", payload["status"])
            self.assertIn('project.rigor="easy"', payload["assignments"])
            self.assertIn('provider_mode="single"', payload["assignments"])
            self.assertIn('providers.task_tracking="markdown"', payload["assignments"])
            self.assertIn('routing.review.independence="session"', payload["assignments"])
            self.assertEqual(["core"], payload["rule_packs"])
            self.assertIn('rules.packs=["core"]', payload["assignments"])
            self.assertEqual([], payload["rule_tool_checks"])

    def test_doctor_reports_rules_without_changing_health(self):
        with tempfile.TemporaryDirectory() as directory:
            repository = Path(directory)
            self.assertEqual(0, self.run_cli(repository, "init", "--approve", "--non-interactive").returncode)
            (repository / "CLAUDE.md").write_text("Use default export for pages.\n", encoding="utf-8")
            self.assertEqual(0, self.run_cli(repository, "configure", "--approve",
                                             "--set", 'rules.packs=["core", "react"]').returncode)
            payload = json.loads(self.run_cli(repository, "doctor", "--format", "json").stdout)
            rules = payload["checks_details"]["rules"]
            self.assertEqual(["core", "react", "typescript"], sorted(rules["packs"]))
            self.assertEqual("react", rules["conflicts"][0]["pack"])
            self.assertNotIn("rules", payload["checks"])

    def test_init_creates_documented_layout_and_is_idempotent(self):
        with tempfile.TemporaryDirectory() as directory:
            repository = Path(directory)

            first = self.run_cli(repository, "init", "--approve", "--non-interactive")
            self.assertEqual(0, first.returncode, first.stderr)
            self.assertEqual("initialized", json.loads(first.stdout)["status"])

            workflow = repository / ".agent-workflow"
            expected = (
                workflow / "config.yaml",
                workflow / "generated/effective-config.yaml",
                workflow / "generated/config-provenance.yaml",
                workflow / "backups",
                workflow / "references",
                workflow / "runtime/evidence",
            )
            for path in expected:
                self.assertTrue(path.exists(), path)

            config_before = (workflow / "config.yaml").read_bytes()
            generated_before = (workflow / "generated/effective-config.yaml").read_bytes()
            second = self.run_cli(repository, "init", "--non-interactive")

            self.assertEqual(0, second.returncode, second.stderr)
            self.assertEqual("already_initialized", json.loads(second.stdout)["status"])
            self.assertEqual(config_before, (workflow / "config.yaml").read_bytes())
            self.assertEqual(generated_before, (workflow / "generated/effective-config.yaml").read_bytes())

    def test_init_writes_no_local_provider_file(self):
        with tempfile.TemporaryDirectory() as directory:
            repository = Path(directory)
            result = self.run_cli(
                repository,
                "init",
                "--approve",
                "--non-interactive",
                "--harness",
                "claude",
            )
            self.assertEqual(0, result.returncode, result.stderr)
            workflow = repository / ".agent-workflow"
            self.assertTrue(workflow.is_dir())
            self.assertTrue((workflow / "config.yaml").is_file())
            self.assertFalse((workflow / "providers.local.yaml").exists())
            self.assertFalse((workflow / "orchestrator.local.yaml").exists())

    def test_init_applies_approved_configuration_atomically_in_one_call(self):
        with tempfile.TemporaryDirectory() as directory:
            repository = Path(directory)

            result = self.run_cli(
                repository,
                "init",
                "--harness",
                "codex",
                "--set",
                "policy.mode=guarded",
                "--approve",
                "--non-interactive",
            )

            self.assertEqual(0, result.returncode, result.stderr)
            self.assertEqual("initialized", json.loads(result.stdout)["status"])
            config = (repository / ".agent-workflow/config.yaml").read_text(encoding="utf-8")
            generated = (
                repository / ".agent-workflow/generated/effective-config.yaml"
            ).read_text(encoding="utf-8")
            self.assertIn("harness: codex", config)
            self.assertIn("mode: guarded", config)
            self.assertIn("mode: guarded", generated)

    def test_init_stages_all_configuration_files_before_mutating_repository(self):
        with tempfile.TemporaryDirectory() as directory:
            repository = Path(directory)
            with mock.patch.object(
                setup_service,
                "atomic_write_many",
                side_effect=OSError("staging failed"),
                create=True,
            ):
                with self.assertRaisesRegex(OSError, "staging failed"):
                    setup_service.initialize(repository, approve=True)

            self.assertFalse((repository / ".agent-workflow").exists())

    def test_init_repairs_interrupted_setup_with_config_but_no_generated_files(self):
        with tempfile.TemporaryDirectory() as directory:
            repository = Path(directory)
            workflow = repository / ".agent-workflow"
            workflow.mkdir()
            (workflow / "config.yaml").write_text(
                "schema_version: '2.3'\n"
                "workflow_version: '2.3'\n"
                "setup_cli_version: '2.3'\n",
                encoding="utf-8",
            )

            preview = self.run_cli(
                repository, "init", "--dry-run", "--non-interactive"
            )

            self.assertEqual(0, preview.returncode, preview.stderr)
            self.assertEqual("would_repair", json.loads(preview.stdout)["status"])
            self.assertFalse(
                (workflow / "generated/effective-config.yaml").exists()
            )

            denied = self.run_cli(repository, "init", "--non-interactive")

            self.assertNotEqual(0, denied.returncode)
            self.assertEqual("approval_required", json.loads(denied.stdout)["status"])
            self.assertFalse(
                (workflow / "generated/effective-config.yaml").exists()
            )

            result = self.run_cli(
                repository, "init", "--approve", "--non-interactive"
            )

            self.assertEqual(0, result.returncode, result.stderr)
            self.assertEqual("repaired", json.loads(result.stdout)["status"])
            self.assertTrue(
                (workflow / "generated/effective-config.yaml").is_file()
            )
            self.assertTrue(
                (workflow / "generated/config-provenance.yaml").is_file()
            )

    def test_init_requires_approval_before_any_first_time_write(self):
        with tempfile.TemporaryDirectory() as directory:
            repository = Path(directory)

            result = self.run_cli(repository, "init", "--non-interactive")

            self.assertNotEqual(0, result.returncode)
            self.assertEqual("approval_required", json.loads(result.stdout)["status"])
            self.assertFalse((repository / ".agent-workflow").exists())

    def test_init_rejects_unapproved_configuration_without_partial_setup(self):
        with tempfile.TemporaryDirectory() as directory:
            repository = Path(directory)

            result = self.run_cli(
                repository,
                "init",
                "--set",
                "policy.mode=guarded",
                "--non-interactive",
            )

            self.assertNotEqual(0, result.returncode)
            self.assertEqual("approval_required", json.loads(result.stdout)["status"])
            self.assertFalse((repository / ".agent-workflow").exists())

    def test_init_dry_run_reports_exact_actions_without_writing(self):
        with tempfile.TemporaryDirectory() as directory:
            repository = Path(directory)

            result = self.run_cli(repository, "init", "--dry-run", "--non-interactive")

            self.assertEqual(0, result.returncode, result.stderr)
            payload = json.loads(result.stdout)
            self.assertEqual("would_initialize", payload["status"])
            self.assertEqual(
                [
                    "create .agent-workflow/config.yaml",
                    "create .agent-workflow/backups/",
                    "create .agent-workflow/references/",
                    "create .agent-workflow/runtime/evidence/",
                    "generate .agent-workflow/generated/effective-config.yaml",
                    "generate .agent-workflow/generated/config-provenance.yaml",
                    "write AGENTS.md gin-workflow block",
                    "add @AGENTS.md to CLAUDE.md",
                ],
                payload["actions"],
            )
            self.assertFalse((repository / ".agent-workflow").exists())

    def test_init_dry_run_returns_complete_proposed_configuration(self):
        with tempfile.TemporaryDirectory() as directory:
            repository = Path(directory)

            result = self.run_cli(
                repository,
                "init",
                "--dry-run",
                "--harness",
                "codex",
                "--set",
                "policy.mode=guarded",
                "--non-interactive",
            )

            self.assertEqual(0, result.returncode, result.stderr)
            payload = json.loads(result.stdout)
            self.assertIn("configuration", payload)
            self.assertEqual(
                {
                    "harness": "codex",
                    "policy": {"mode": "guarded"},
                    "schema_version": "2.8",
                    "setup_cli_version": "2.8",
                    "workflow_version": "2.8",
                },
                payload["configuration"],
            )
            self.assertFalse((repository / ".agent-workflow").exists())

    def test_configure_requires_explicit_approval_before_user_authored_write(self):
        with tempfile.TemporaryDirectory() as directory:
            repository = Path(directory)
            initialized = self.run_cli(
                repository, "init", "--approve", "--non-interactive"
            )
            self.assertEqual(0, initialized.returncode, initialized.stderr)
            config = repository / ".agent-workflow/config.yaml"
            before = config.read_bytes()

            denied = self.run_cli(
                repository,
                "configure",
                "--set",
                "policy.mode=guarded",
                "--non-interactive",
            )

            self.assertNotEqual(0, denied.returncode)
            self.assertEqual("approval_required", json.loads(denied.stdout)["status"])
            self.assertEqual(before, config.read_bytes())

            approved = self.run_cli(
                repository,
                "configure",
                "--set",
                "policy.mode=guarded",
                "--approve",
                "--non-interactive",
            )
            self.assertEqual(0, approved.returncode, approved.stderr)
            self.assertEqual("configured", json.loads(approved.stdout)["status"])
            self.assertIn("mode: guarded", config.read_text(encoding="utf-8"))

    def test_update_previews_then_applies_v2_3_routing(self):
        arguments = (
            "--to-version", "2.7",
            "--set", "routing.concurrency.claude=1",
            "--set", "routing.roles.backend.preferred=[claude]",
        )
        with tempfile.TemporaryDirectory() as directory:
            repository = Path(directory)
            workflow = repository / ".agent-workflow"
            workflow.mkdir()
            (workflow / "config.yaml").write_text(
                "schema_version: '2.2'\nworkflow_version: '2.2'\nsetup_cli_version: '2.2'\nharness: codex\n",
                encoding="utf-8",
            )

            preview = self.run_cli(repository, "update", "--dry-run", *arguments)

            self.assertEqual(0, preview.returncode, preview.stderr)
            payload = json.loads(preview.stdout)
            self.assertEqual("migration_available", payload["status"])
            self.assertIn("configuration", payload)
            self.assertEqual("2.7", payload["configuration"]["schema_version"])

            applied = self.run_cli(repository, "update", "--approve", *arguments)

            self.assertEqual(0, applied.returncode, applied.stderr)
            self.assertEqual("migrated", json.loads(applied.stdout)["status"])
            self.assertIn("routing:", (workflow / "config.yaml").read_text(encoding="utf-8"))
            effective = (workflow / "generated/effective-config.yaml").read_text(encoding="utf-8")
            provenance = (workflow / "generated/config-provenance.yaml").read_text(encoding="utf-8")
            self.assertIn("schema_version: '2.7'", effective)
            self.assertIn("routing:", effective)
            self.assertIn("schema_version: '2.3'", provenance)

    def test_read_only_commands_do_not_change_repository(self):
        with tempfile.TemporaryDirectory() as directory:
            repository = Path(directory)
            initialized = self.run_cli(
                repository, "init", "--approve", "--non-interactive"
            )
            self.assertEqual(0, initialized.returncode, initialized.stderr)
            before = {
                path.relative_to(repository): path.read_bytes()
                for path in repository.rglob("*")
                if path.is_file()
            }

            for command in ("detect", "doctor", "status", "diff"):
                with self.subTest(command=command):
                    result = self.run_cli(repository, command, "--non-interactive")
                    self.assertEqual(0, result.returncode, result.stderr)
                    json.loads(result.stdout)

            after = {
                path.relative_to(repository): path.read_bytes()
                for path in repository.rglob("*")
                if path.is_file()
            }
            self.assertEqual(before, after)

    def test_harness_override_command_and_reset(self):
        with tempfile.TemporaryDirectory() as directory:
            repository = Path(directory)
            initialized = self.run_cli(repository, "init", "--approve", "--non-interactive")
            self.assertEqual(0, initialized.returncode, initialized.stderr)

            # Set override to claude
            set_res = self.run_cli(repository, "harness-override", "--harness", "claude")
            self.assertEqual(0, set_res.returncode, set_res.stderr)
            payload = json.loads(set_res.stdout)
            self.assertEqual("success", payload["status"])
            self.assertEqual("claude", payload["harness"])

            override_file = repository / ".agent-workflow" / "runtime" / "session-harness.override"
            self.assertTrue(override_file.is_file())
            self.assertEqual("claude", override_file.read_text().strip())

            # Query current override
            get_res = self.run_cli(repository, "harness-override")
            self.assertEqual(0, get_res.returncode, get_res.stderr)
            get_payload = json.loads(get_res.stdout)
            self.assertEqual("claude", get_payload["harness"])

            # Reset override
            reset_res = self.run_cli(repository, "harness-override", "--reset")
            self.assertEqual(0, reset_res.returncode, reset_res.stderr)
            reset_payload = json.loads(reset_res.stdout)
            self.assertEqual("success", reset_payload["status"])
            self.assertFalse(override_file.exists())

    def test_doctor_reports_the_main_harness_executable(self):
        with tempfile.TemporaryDirectory() as directory, tempfile.TemporaryDirectory() as bin_dir:
            repository = Path(directory)
            fake_claude = Path(bin_dir) / "claude"
            fake_claude.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
            fake_claude.chmod(0o755)

            initialized = self.run_cli(
                repository,
                "init",
                "--approve",
                "--non-interactive",
                "--harness",
                "claude",
            )
            self.assertEqual(0, initialized.returncode, initialized.stderr)

            # Doctor with fake claude on PATH
            doc = self.run_cli(
                repository,
                "doctor",
                "--format",
                "json",
                env={**os.environ, "PATH": f"{bin_dir}{os.pathsep}{os.environ['PATH']}"},
            )
            self.assertEqual(0, doc.returncode, doc.stderr)
            payload = json.loads(doc.stdout)
            self.assertTrue(payload["checks"]["harness"])
            self.assertEqual(payload["checks_details"]["harness"]["name"], "claude")
            self.assertEqual(
                payload["checks_details"]["harness"]["executable"],
                str(fake_claude.resolve()),
            )

    def test_doctor_explains_a_missing_main_harness_executable(self):
        with tempfile.TemporaryDirectory() as directory:
            repository = Path(directory)
            initialized = self.run_cli(repository, "init", "--approve", "--non-interactive", "--harness", "claude")
            self.assertEqual(0, initialized.returncode, initialized.stderr)
            with mock.patch.object(setup_service, "resolve_harness_executable", return_value=None):
                report = setup_service.doctor(repository)
            self.assertFalse(report["checks"]["harness"])
            self.assertIn("main harness claude: executable not found on PATH", report["actions"])

    def test_doctor_reports_verify_commands_project_stage_and_codegraph_read_only(self):
        with tempfile.TemporaryDirectory() as directory, tempfile.TemporaryDirectory() as bin_directory:
            repository = Path(directory)
            git = lambda *args: subprocess.run(["git", *args], cwd=repository, check=True, capture_output=True)  # noqa: E731
            git("init")
            git("config", "user.email", "t@example.com")
            git("config", "user.name", "Tester")
            initialized = self.run_cli(repository, "init", "--approve", "--non-interactive",
                                       "--set", "project.stage=greenfield", "--set", 'verify.checks.test=""',
                                       "--set", "verify.checks.lint=ruff")
            self.assertEqual(0, initialized.returncode, initialized.stderr)
            (repository / "package.json").write_text("{}", encoding="utf-8")
            index = repository / ".codegraph"
            index.mkdir()
            (index / "graph.db").write_text("x", encoding="utf-8")
            os.utime(index / "graph.db", (1_000_000, 1_000_000))
            git("add", "package.json")
            git("commit", "-m", "init")
            before = {path: path.read_bytes() for path in repository.rglob("*")
                      if path.is_file() and ".git" not in path.relative_to(repository).parts}

            stub = Path(bin_directory) / "codegraph"
            stub.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
            stub.chmod(0o755)

            result = self.run_cli(repository, "doctor",
                                  env={**os.environ, "PATH": f"{bin_directory}{os.pathsep}{os.environ['PATH']}"})

            self.assertEqual(0, result.returncode, result.stderr)
            details = json.loads(result.stdout)["checks_details"]
            self.assertIn("test", details["verify_commands"]["missing"])
            self.assertNotIn("lint", details["verify_commands"]["missing"])
            self.assertIn("suggestion", details["project_stage"])
            self.assertTrue(details["codegraph"]["indexed"])
            self.assertTrue(details["codegraph"]["stale"])
            self.assertIn("codegraph sync", details["codegraph"]["suggestion"])
            after = {path: path.read_bytes() for path in repository.rglob("*")
                     if path.is_file() and ".git" not in path.relative_to(repository).parts}
            self.assertEqual(before, after)

    def test_doctor_suggests_installing_codegraph_only_when_missing(self):
        with tempfile.TemporaryDirectory() as directory, tempfile.TemporaryDirectory() as bin_directory:
            repository = Path(directory)
            subprocess.run(["git", "init"], cwd=repository, check=True, capture_output=True)
            initialized = self.run_cli(repository, "init", "--approve", "--non-interactive")
            self.assertEqual(0, initialized.returncode, initialized.stderr)
            git_dir = str(Path(shutil.which("git")).parent)
            missing = self.run_cli(repository, "doctor", env={**os.environ, "PATH": git_dir})
            self.assertEqual(0, missing.returncode, missing.stderr)
            graph = json.loads(missing.stdout)["checks_details"]["codegraph"]
            self.assertFalse(graph["installed"])
            self.assertIn("recommended-tools", graph["suggestion"])
            stub = Path(bin_directory) / "codegraph"
            stub.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
            stub.chmod(0o755)
            present = self.run_cli(repository, "doctor", env={**os.environ, "PATH": f"{bin_directory}{os.pathsep}{git_dir}"})
            self.assertEqual(0, present.returncode, present.stderr)
            graph = json.loads(present.stdout)["checks_details"]["codegraph"]
            self.assertTrue(graph["installed"])
            self.assertNotIn("suggestion", graph)

    def test_doctor_flags_stale_review_ledgers(self):
        with tempfile.TemporaryDirectory() as directory:
            repository = Path(directory)
            subprocess.run(["git", "init"], cwd=repository, check=True, capture_output=True)
            subprocess.run(["git", "config", "user.email", "t@example.com"], cwd=repository, check=True, capture_output=True)
            subprocess.run(["git", "config", "user.name", "Tester"], cwd=repository, check=True, capture_output=True)
            (repository / "init.txt").write_text("init")
            subprocess.run(["git", "add", "."], cwd=repository, check=True, capture_output=True)
            subprocess.run(["git", "commit", "-m", "init"], cwd=repository, check=True, capture_output=True)

            self.run_cli(repository, "init", "--approve", "--non-interactive")

            head_sha = subprocess.run(
                ["git", "rev-parse", "HEAD"], cwd=repository, check=True, capture_output=True, text=True
            ).stdout.strip()

            review_dir = repository / ".planning" / "reviews" / "closed-bead"
            review_dir.mkdir(parents=True, exist_ok=True)
            (review_dir / "review.json").write_text(json.dumps({
                "review_state": "review-approved",
                "repositories": [{"checkpoint_sha": head_sha, "repository_path": "."}],
            }))

            doc_run = self.run_cli(repository, "doctor", "--format", "json")
            self.assertEqual(0, doc_run.returncode, doc_run.stderr)
            payload = json.loads(doc_run.stdout)
            self.assertEqual("issues_found", payload["status"])
            self.assertFalse(payload["checks"]["review_ledgers"])
            self.assertIn("review_ledgers", payload["checks_details"])
            self.assertEqual(payload["checks_details"]["review_ledgers"]["stale_count"], 1)
            self.assertIn("closed-bead", payload["checks_details"]["review_ledgers"]["stale_beads"])
            self.assertTrue(any("review-ledger.py cleanup --all-closed" in action for action in payload["actions"]))


    def test_init_writes_agents_block_and_claude_import(self):
        with tempfile.TemporaryDirectory() as directory:
            repository = Path(directory)
            result = self.run_cli(
                repository,
                "init",
                "--approve",
                "--harness",
                "claude",
                "--set",
                'verify.checks.test="pytest"',
            )
            self.assertEqual(0, result.returncode, result.stderr)
            payload = json.loads(result.stdout)
            self.assertIn("write AGENTS.md gin-workflow block", payload["actions"])
            self.assertIn("add @AGENTS.md to CLAUDE.md", payload["actions"])
            agents = repository / "AGENTS.md"
            claude = repository / "CLAUDE.md"
            self.assertTrue(agents.is_file())
            self.assertTrue(claude.is_file())
            self.assertIn("test `pytest`", agents.read_text(encoding="utf-8"))
            self.assertEqual("@AGENTS.md", claude.read_text(encoding="utf-8").splitlines()[0])

    def test_init_dry_run_lists_agents_actions_without_writing(self):
        with tempfile.TemporaryDirectory() as directory:
            repository = Path(directory)
            result = self.run_cli(
                repository,
                "init",
                "--dry-run",
                "--harness",
                "claude",
                "--set",
                'verify.checks.test="pytest"',
            )
            self.assertEqual(0, result.returncode, result.stderr)
            payload = json.loads(result.stdout)
            self.assertIn("write AGENTS.md gin-workflow block", payload["actions"])
            self.assertIn("add @AGENTS.md to CLAUDE.md", payload["actions"])
            self.assertFalse((repository / "AGENTS.md").exists())
            self.assertFalse((repository / "CLAUDE.md").exists())

    def test_init_on_initialized_repo_adds_missing_block(self):
        with tempfile.TemporaryDirectory() as directory:
            repository = Path(directory)
            self.assertEqual(
                0,
                self.run_cli(
                    repository,
                    "init",
                    "--approve",
                    "--harness",
                    "claude",
                    "--set",
                    'verify.checks.test="pytest"',
                ).returncode,
            )
            (repository / "AGENTS.md").unlink()

            dry = self.run_cli(repository, "init", "--dry-run")
            self.assertEqual(0, dry.returncode, dry.stderr)
            dry_payload = json.loads(dry.stdout)
            self.assertEqual("would_update", dry_payload["status"])
            self.assertIn("write AGENTS.md gin-workflow block", dry_payload["actions"])
            self.assertFalse((repository / "AGENTS.md").exists())

            unapproved = self.run_cli(repository, "init")
            self.assertNotEqual(0, unapproved.returncode)
            self.assertEqual("approval_required", json.loads(unapproved.stdout)["status"])
            self.assertFalse((repository / "AGENTS.md").exists())

            approved = self.run_cli(repository, "init", "--approve")
            self.assertEqual(0, approved.returncode, approved.stderr)
            approved_payload = json.loads(approved.stdout)
            self.assertEqual("updated", approved_payload["status"])
            self.assertIn("write AGENTS.md gin-workflow block", approved_payload["actions"])
            self.assertTrue((repository / "AGENTS.md").exists())

            further = self.run_cli(repository, "init", "--approve")
            self.assertEqual(0, further.returncode, further.stderr)
            further_payload = json.loads(further.stdout)
            self.assertEqual("already_initialized", further_payload["status"])

    def test_refresh_updates_existing_block_only(self):
        with tempfile.TemporaryDirectory() as directory:
            repository = Path(directory)
            self.assertEqual(
                0,
                self.run_cli(
                    repository,
                    "init",
                    "--approve",
                    "--harness",
                    "claude",
                    "--set",
                    'verify.checks.test="pytest"',
                ).returncode,
            )
            (repository / ".planning").mkdir(parents=True, exist_ok=True)
            (repository / ".planning/roadmap.md").write_text("roadmap", encoding="utf-8")

            refreshed = self.run_cli(repository, "refresh")
            self.assertEqual(0, refreshed.returncode, refreshed.stderr)
            payload = json.loads(refreshed.stdout)
            self.assertEqual("updated", payload.get("agents_block"))
            self.assertIn("Roadmap: `.planning/roadmap.md`", (repository / "AGENTS.md").read_text(encoding="utf-8"))

            (repository / "AGENTS.md").write_text("# Custom without block\n", encoding="utf-8")
            refreshed_absent = self.run_cli(repository, "refresh")
            self.assertEqual(0, refreshed_absent.returncode, refreshed_absent.stderr)
            absent_payload = json.loads(refreshed_absent.stdout)
            self.assertEqual("absent", absent_payload.get("agents_block"))
            self.assertEqual("# Custom without block\n", (repository / "AGENTS.md").read_text(encoding="utf-8"))

    def test_refresh_and_init_fail_on_broken_markers(self):
        with tempfile.TemporaryDirectory() as directory:
            repository = Path(directory)
            self.assertEqual(
                0,
                self.run_cli(
                    repository,
                    "init",
                    "--approve",
                    "--harness",
                    "claude",
                    "--set",
                    'verify.checks.test="pytest"',
                ).returncode,
            )
            from workflow_core import agents_block
            agents = repository / "AGENTS.md"
            with open(agents, "a", encoding="utf-8") as f:
                f.write(f"\n{agents_block.START}\n")
            broken_bytes = agents.read_bytes()
            effective = repository / ".agent-workflow/generated/effective-config.yaml"
            effective.unlink()

            refreshed = self.run_cli(repository, "refresh")
            self.assertNotEqual(0, refreshed.returncode)
            self.assertEqual(broken_bytes, agents.read_bytes())
            self.assertFalse(effective.exists())

            initialized = self.run_cli(repository, "init", "--approve")
            self.assertNotEqual(0, initialized.returncode)
            self.assertEqual(broken_bytes, agents.read_bytes())

    def test_doctor_reports_agents_block_state(self):
        with tempfile.TemporaryDirectory() as directory:
            repository = Path(directory)
            subprocess.run(["git", "init"], cwd=repository, check=True, capture_output=True)
            self.assertEqual(
                0,
                self.run_cli(
                    repository,
                    "init",
                    "--approve",
                    "--harness",
                    "claude",
                    "--set",
                    'verify.checks.test="pytest"',
                ).returncode,
            )
            doc_ok = self.run_cli(repository, "doctor")
            self.assertEqual(0, doc_ok.returncode, doc_ok.stderr)
            payload_ok = json.loads(doc_ok.stdout)
            self.assertEqual("ok", payload_ok["checks_details"]["agents_block"])

            (repository / ".planning").mkdir(parents=True, exist_ok=True)
            (repository / ".planning/roadmap.md").write_text("roadmap", encoding="utf-8")
            doc_stale = self.run_cli(repository, "doctor")
            self.assertEqual(0, doc_stale.returncode, doc_stale.stderr)
            payload_stale = json.loads(doc_stale.stdout)
            self.assertEqual("stale", payload_stale["checks_details"]["agents_block"])
            self.assertTrue(any("gin-workflow setup refresh" in action for action in payload_stale["actions"]))

            (repository / "AGENTS.md").write_text("# Custom without block\n", encoding="utf-8")
            doc_absent = self.run_cli(repository, "doctor")
            self.assertEqual(0, doc_absent.returncode, doc_absent.stderr)
            payload_absent = json.loads(doc_absent.stdout)
            self.assertEqual("absent", payload_absent["checks_details"]["agents_block"])
            self.assertNotIn("agents_block", payload_absent["checks"])
            self.assertTrue(payload_absent["checks"]["configuration"])

    def test_doctor_warns_when_beads_exists_and_backend_is_unset(self):
        with tempfile.TemporaryDirectory() as directory:
            repository = Path(directory)
            workflow = repository / ".agent-workflow"
            workflow.mkdir()
            (workflow / "config.yaml").write_text("schema_version: '2.8'\nharness: claude\n", encoding="utf-8")
            (repository / ".beads").mkdir()
            res = self.run_cli(repository, "doctor", "--format", "json")
            self.assertEqual(0, res.returncode, res.stderr)
            payload = json.loads(res.stdout)
            self.assertTrue(any("providers.task_tracking=beads" in action for action in payload.get("actions", [])))

    def test_doctor_does_not_warn_about_the_backend_in_team_mode(self):
        with tempfile.TemporaryDirectory() as directory:
            repository = Path(directory)
            subprocess.run(["git", "init", "-q"], cwd=repository, check=True)
            (repository / ".agent-workflow").mkdir()
            (repository / ".agent-workflow/config.yaml").write_text(
                "schema_version: '2.8'\nharness: claude\nteam:\n  host: github\n  members:\n"
                "    a@example.com: {roles: [be_dev], login: a}\n", encoding="utf-8")
            (repository / ".beads").mkdir()
            res = self.run_cli(repository, "doctor", "--format", "json")
            self.assertEqual(0, res.returncode, res.stderr)
            payload = json.loads(res.stdout)
            self.assertFalse(any("providers.task_tracking" in action for action in payload.get("actions", [])))

    def test_doctor_suggests_the_2_8_migration_for_legacy_worker_routing(self):
        with tempfile.TemporaryDirectory() as directory:
            repository = Path(directory)
            workflow = repository / ".agent-workflow"
            workflow.mkdir()
            (workflow / "config.yaml").write_text(
                "schema_version: '2.7'\nharness: claude\nrouting:\n  concurrency:\n    claude: 2\n",
                encoding="utf-8"
            )
            res = self.run_cli(repository, "doctor", "--format", "json")
            self.assertEqual(0, res.returncode, res.stderr)
            payload = json.loads(res.stdout)
            self.assertTrue(any("setup update --to-version 2.8" in action for action in payload.get("actions", [])))

    def test_doctor_probe_delegates_in_multi_mode(self):
        with tempfile.TemporaryDirectory() as directory, tempfile.TemporaryDirectory() as bin_dir:
            repository = Path(directory)
            self.assertEqual(0, self.run_cli(repository, "init", "--approve", "--non-interactive", "--harness", "claude").returncode)
            self.assertEqual(0, self.run_cli(repository, "configure", "--approve", "--set", "provider_mode=multi").returncode)
            prov_reply = {"codex.low": {"available": True, "reason": "ready"}}
            fake_orchestrator(bin_dir, contract=2, capabilities=["doctor"], replies={"doctor": {"providers": prov_reply}})
            env = {**os.environ, "PATH": f"{bin_dir}{os.pathsep}{os.environ.get('PATH', '')}"}
            res = self.run_cli(repository, "doctor", "--probe", env=env)
            self.assertEqual(0, res.returncode, res.stderr)
            payload = json.loads(res.stdout)
            self.assertEqual(prov_reply, payload["checks_details"]["providers"])
            self.assertTrue(payload["checks"]["providers"])
            self.assertTrue(payload["checks_details"]["orchestrator"]["available"])

    def test_doctor_reports_orchestrator_missing_with_the_install_command(self):
        with tempfile.TemporaryDirectory() as directory, tempfile.TemporaryDirectory() as empty_bin:
            repository = Path(directory)
            self.assertEqual(0, self.run_cli(repository, "init", "--approve", "--non-interactive", "--harness", "claude").returncode)
            self.assertEqual(0, self.run_cli(repository, "configure", "--approve", "--set", "provider_mode=multi").returncode)
            env = {**os.environ, "PATH": empty_bin}
            res = self.run_cli(repository, "doctor", env=env)
            self.assertEqual(0, res.returncode, res.stderr)
            payload = json.loads(res.stdout)
            self.assertFalse(payload["checks_details"]["orchestrator"]["available"])
            self.assertEqual("orchestrator_missing", payload["checks_details"]["orchestrator"]["reason"])
            self.assertTrue(any("orchestrator_missing" in a and "./install.sh --plugin gin-orchestrator" in a for a in payload.get("actions", [])))

    def test_doctor_probe_failure_reports_orchestrator_failed(self):
        with tempfile.TemporaryDirectory() as directory, tempfile.TemporaryDirectory() as bin_dir:
            repository = Path(directory)
            self.assertEqual(0, self.run_cli(repository, "init", "--approve", "--non-interactive", "--harness", "claude").returncode)
            self.assertEqual(0, self.run_cli(repository, "configure", "--approve", "--set", "provider_mode=multi").returncode)
            fake_orchestrator(bin_dir, contract=2, capabilities=["doctor"], fail=["doctor"])
            env = {**os.environ, "PATH": f"{bin_dir}{os.pathsep}{os.environ.get('PATH', '')}"}
            res = self.run_cli(repository, "doctor", "--probe", env=env)
            payload = json.loads(res.stdout)
            self.assertFalse(payload["checks"]["providers"])
            self.assertEqual("orchestrator_failed", payload["checks_details"]["providers"]["reason"])

    def test_models_delegates_or_returns_an_empty_list(self):
        with tempfile.TemporaryDirectory() as directory, tempfile.TemporaryDirectory() as bin_dir:
            repository = Path(directory)
            fake_orchestrator(bin_dir, contract=2, capabilities=["models"], replies={"models": [{"id": "m1"}]})
            env = {**os.environ, "PATH": f"{bin_dir}{os.pathsep}{os.environ.get('PATH', '')}"}
            res = self.run_cli(repository, "models", "--provider", "codex", env=env)
            self.assertEqual(0, res.returncode, res.stderr)
            payload = json.loads(res.stdout)
            self.assertEqual([{"id": "m1"}], payload["models"])

        with tempfile.TemporaryDirectory() as directory, tempfile.TemporaryDirectory() as empty_bin:
            repository = Path(directory)
            env = {**os.environ, "PATH": empty_bin}
            res = self.run_cli(repository, "models", "--provider", "codex", env=env)
            self.assertEqual(0, res.returncode, res.stderr)
            payload = json.loads(res.stdout)
            self.assertEqual([], payload["models"])



if __name__ == "__main__":
    unittest.main()


