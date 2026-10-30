from pathlib import Path
import stat
import tempfile
import unittest

from tests.gin_orchestrator import paths  # noqa: F401

from gin_orchestrator.doctor import doctor_report  # noqa: E402
from gin_orchestrator.local_config import LOCAL_FILE  # noqa: E402


class DoctorReportTests(unittest.TestCase):
    def test_doctor_report_missing_file_reports_missing_mapping(self):
        with tempfile.TemporaryDirectory() as directory:
            repository = Path(directory)
            config = {
                "harness": "claude",
                "orchestrator": {
                    "roles": {
                        "backend": {"preferred": ["claude"]},
                    }
                },
            }
            report = doctor_report(repository, config, probe=False)
            self.assertIn("providers", report)
            self.assertIn("claude.mapping", report["providers"])
            self.assertFalse(report["providers"]["claude.mapping"]["available"])
            self.assertEqual(
                "missing_local_provider_mapping",
                report["providers"]["claude.mapping"]["reason"],
            )

    def test_doctor_report_offline_executable_check(self):
        with tempfile.TemporaryDirectory() as directory:
            repository = Path(directory)
            workflow = repository / ".agent-workflow"
            workflow.mkdir()
            (repository / LOCAL_FILE).write_text(
                "schema_version: '2.9'\n"
                "providers:\n"
                "  codex:\n"
                "    executable: /nonexistent/binary/codex-missing\n",
                encoding="utf-8",
            )
            config = {
                "harness": "codex",
                "orchestrator": {
                    "concurrency": {"codex": 1},
                    "roles": {"backend": {"preferred": ["codex"]}},
                },
            }
            report = doctor_report(repository, config, probe=False)
            self.assertIn("providers", report)
            self.assertFalse(report["providers"]["codex.executable"]["available"])
            self.assertEqual(
                "executable_not_found",
                report["providers"]["codex.executable"]["reason"],
            )

    def test_doctor_report_malformed_local_schema(self):
        with tempfile.TemporaryDirectory() as directory:
            repository = Path(directory)
            workflow = repository / ".agent-workflow"
            workflow.mkdir()
            (repository / LOCAL_FILE).write_text(
                "schema_version: '2.8'\n"
                "providers:\n"
                "  codex:\n"
                "    executable: codex\n"
                "    models:\n"
                "      low:\n"
                "        model: gpt-6\n"
                "        effort: extreme\n",
                encoding="utf-8",
            )
            config = {"harness": "codex"}
            report = doctor_report(repository, config, probe=False)
            self.assertIn("providers_config", report)
            self.assertFalse(report["providers_config"]["valid"])

    def test_doctor_report_probe_with_valid_executable(self):
        with tempfile.TemporaryDirectory() as directory:
            repository = Path(directory)
            workflow = repository / ".agent-workflow"
            workflow.mkdir()
            stub_codex = repository / "fake-codex"
            stub_codex.write_text(
                "#!/bin/sh\n"
                "if [ \"$1\" = \"exec\" ] && [ \"$2\" = \"--help\" ]; then\n"
                "  echo 'usage: codex exec --model MODEL --json --ephemeral --dangerously-bypass-approvals-and-sandbox --cd DIR'\n"
                "  exit 0\n"
                "fi\n"
                "exit 0\n",
                encoding="utf-8",
            )
            stub_codex.chmod(stub_codex.stat().st_mode | stat.S_IEXEC)

            (repository / LOCAL_FILE).write_text(
                f"schema_version: '2.9'\n"
                f"providers:\n"
                f"  codex:\n"
                f"    executable: '{stub_codex.resolve()}'\n",
                encoding="utf-8",
            )
            config = {
                "harness": "codex",
                "orchestrator": {
                    "concurrency": {"codex": 1},
                    "roles": {"backend": {"preferred": ["codex"]}},
                },
            }
            config["models"] = {"codex": {"models": ["gpt-6-mini", "gpt-6"]}}
            report = doctor_report(repository, config, probe=True)
            self.assertIn("providers", report)
            self.assertTrue(report["providers"]["codex.gpt-6-mini"]["available"])
            self.assertTrue(report["providers"]["codex.gpt-6"]["available"])
            self.assertTrue(
                (repository / ".agent-workflow/runtime/health-probe/codex").is_dir()
            )

    def test_doctor_report_probe_reports_failure(self):
        with tempfile.TemporaryDirectory() as directory:
            repository = Path(directory)
            workflow = repository / ".agent-workflow"
            workflow.mkdir()
            stub_codex = repository / "fake-codex"
            stub_codex.write_text(
                "#!/bin/sh\n"
                "exit 1\n",
                encoding="utf-8",
            )
            stub_codex.chmod(stub_codex.stat().st_mode | stat.S_IEXEC)

            (repository / LOCAL_FILE).write_text(
                f"schema_version: '2.9'\n"
                f"providers:\n"
                f"  codex:\n"
                f"    executable: '{stub_codex.resolve()}'\n",
                encoding="utf-8",
            )
            config = {
                "harness": "codex",
                "orchestrator": {
                    "concurrency": {"codex": 1},
                    "roles": {"backend": {"preferred": ["codex"]}},
                },
            }
            report = doctor_report(repository, config, probe=True)
            self.assertIn("providers", report)
            self.assertFalse(report["providers"]["codex.gpt-6-astra"]["available"])


if __name__ == "__main__":
    unittest.main()
