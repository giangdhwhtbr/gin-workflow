import dataclasses
import os
from pathlib import Path
import sys
import tempfile
import unittest


SCRIPTS = Path(__file__).resolve().parents[2] / "plugins/gin-workflow/src/scripts"
sys.path.insert(0, str(SCRIPTS))

from workflow_core.configuration import (  # noqa: E402
    ConfigValidationError,
    resolve_effective_config,
)
from workflow_core import configuration  # noqa: E402


class ConfigurationTests(unittest.TestCase):
    def test_lifecycle_loader_requires_one_time_setup_and_reads_generated_config(self):
        loader = getattr(configuration, "load_effective_config", None)
        self.assertIsNotNone(loader, "lifecycle generated-config loader is missing")

        with tempfile.TemporaryDirectory() as directory:
            repository = Path(directory)
            with self.assertRaisesRegex(
                ConfigValidationError,
                r"run .*gin-workflow setup init.*once",
            ):
                loader(repository)

            resolve_effective_config(
                repository,
                repository_config={
                    "schema_version": "2.1",
                    "policy": {"mode": "configured-once"},
                },
            )

            loaded = loader(repository)

            self.assertEqual("configured-once", loaded["policy"]["mode"])
            self.assertEqual(repository.resolve(), loaded.repository_root)

    def test_lifecycle_loader_rejects_generated_config_missing_version_channels(self):
        with tempfile.TemporaryDirectory() as directory:
            repository = Path(directory)
            resolve_effective_config(
                repository,
                built_in_defaults={"schema_version": "2.1"},
            )

            with self.assertRaisesRegex(
                ConfigValidationError,
                r"missing required lifecycle version channel: workflow_version",
            ):
                configuration.load_effective_config(repository)

    def test_provenance_escapes_dotted_key_components_without_collision(self):
        with tempfile.TemporaryDirectory() as directory:
            result = resolve_effective_config(
                Path(directory),
                built_in_defaults={"schema_version": "2.1"},
                repository_config={
                    "a.b": "top-level",
                    "a": {"b": "nested"},
                },
            )

            self.assertEqual("top-level", result.config["a.b"])
            self.assertEqual("nested", result.config["a"]["b"])
            self.assertIn(r"a\.b", result.provenance)
            self.assertEqual("repository config", result.provenance[r"a\.b"])
            self.assertEqual("repository config", result.provenance["a.b"])
            self.assertEqual(3, len(result.provenance))

    def test_resolves_all_layers_in_order_and_tracks_leaf_provenance(self):
        with tempfile.TemporaryDirectory() as directory:
            repository = Path(directory)
            result = resolve_effective_config(
                repository,
                built_in_defaults={
                    "schema_version": "2.1",
                    "policy": {"mode": "builtin", "keep": True},
                },
                user_profile={"policy": {"mode": "user", "user": True}},
                organization_profile={"policy": {"mode": "organization"}},
                repository_config={"policy": {"mode": "repository"}},
                harness_override={"policy": {"mode": "harness"}},
                local_override={"policy": {"mode": "local"}},
                command_override={"policy": {"mode": "command"}},
            )

            self.assertEqual("command", result.config["policy"]["mode"])
            self.assertTrue(result.config["policy"]["keep"])
            self.assertTrue(result.config["policy"]["user"])
            self.assertEqual("command override", result.provenance["policy.mode"])
            self.assertEqual("built-in defaults", result.provenance["policy.keep"])
            self.assertEqual("user profile", result.provenance["policy.user"])

            with self.assertRaises(TypeError):
                result.config["policy"]["mode"] = "changed"
            with self.assertRaises(dataclasses.FrozenInstanceError):
                result.config.repository_root = Path("elsewhere")

    def test_writes_generated_config_and_provenance_without_resolving_secret_ref(self):
        with tempfile.TemporaryDirectory() as directory:
            repository = Path(directory)
            os.environ["WORKFLOW_TEST_TOKEN"] = "literal-value-must-not-appear"
            self.addCleanup(os.environ.pop, "WORKFLOW_TEST_TOKEN", None)

            result = resolve_effective_config(
                repository,
                repository_config={
                    "schema_version": "2.1",
                    "notifications": {
                        "credential": {"secret_ref": "env:WORKFLOW_TEST_TOKEN"}
                    },
                },
            )

            effective = repository / ".agent-workflow/generated/effective-config.yaml"
            provenance = repository / ".agent-workflow/generated/config-provenance.yaml"
            self.assertEqual(effective, result.effective_config_path)
            self.assertTrue(effective.is_file())
            self.assertTrue(provenance.is_file())
            serialized = effective.read_text(encoding="utf-8")
            self.assertIn("secret_ref", serialized)
            self.assertIn("WORKFLOW_TEST_TOKEN", serialized)
            self.assertNotIn("literal-value-must-not-appear", serialized)

    def test_validation_failure_leaves_previous_generated_files_unchanged(self):
        with tempfile.TemporaryDirectory() as directory:
            repository = Path(directory)
            first = resolve_effective_config(
                repository,
                repository_config={"schema_version": "2.1", "policy": {"mode": "safe"}},
            )
            effective_before = first.effective_config_path.read_bytes()
            provenance_before = first.provenance_path.read_bytes()

            with self.assertRaises(ConfigValidationError):
                resolve_effective_config(
                    repository,
                    repository_config={
                        "schema_version": "2.1",
                        "policy": {"mode": "unsafe"},
                        "provider_command": "curl https://example.invalid",
                    },
                )

            self.assertEqual(effective_before, first.effective_config_path.read_bytes())
            self.assertEqual(provenance_before, first.provenance_path.read_bytes())

    def test_rejects_nonportable_values_and_unknown_schema_versions(self):
        invalid_configs = (
            {"schema_version": "99"},
            {"schema_version": "2.1", "workflow_version": "9.9"},
            {"schema_version": "2.1", "setup_cli_version": "9.9"},
            {"schema_version": "2.1", "worker": {"model": "gpt-5.6"}},
            {"schema_version": "2.1", "notifications": {"api_key": "sk-literal"}},
            {"schema_version": "2.1", "provider": {"command": ["bd", "ready"]}},
            {"schema_version": "2.1", "secret_ref": "not a valid reference"},
        )

        for config in invalid_configs:
            with self.subTest(config=config), tempfile.TemporaryDirectory() as directory:
                with self.assertRaises(ConfigValidationError):
                    resolve_effective_config(Path(directory), repository_config=config)


if __name__ == "__main__":
    unittest.main()
