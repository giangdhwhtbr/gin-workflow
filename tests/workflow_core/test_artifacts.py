from pathlib import Path
import sys
import tempfile
import unittest


SCRIPTS = Path(__file__).resolve().parents[2] / "plugins/gin-workflow/src/scripts"
sys.path.insert(0, str(SCRIPTS))

from workflow_core.artifacts import ArtifactResolutionError, resolve_artifact  # noqa: E402
from workflow_core.models import EffectiveConfig  # noqa: E402


class ArtifactTests(unittest.TestCase):
    def test_returns_only_each_explicitly_configured_artifact_path(self):
        with tempfile.TemporaryDirectory() as directory:
            repository = Path(directory)
            configured = {
                "plans": "custom/plans",
                "beads": "state/beads",
                "worktrees": "isolated/trees",
                "knowledge": "/shared/knowledge",
                "evidence": "audit/evidence",
                "runtime": "runtime/state",
            }
            config = EffectiveConfig(
                data={"schema_version": "2.1", "artifacts": configured},
                repository_root=repository,
            )

            self.assertEqual(repository / "custom/plans", resolve_artifact(config, "plans"))
            self.assertEqual(Path("/shared/knowledge"), resolve_artifact(config, "knowledge"))
            for name, raw_path in configured.items():
                expected = Path(raw_path)
                if not expected.is_absolute():
                    expected = repository / expected
                self.assertEqual(expected, resolve_artifact(config, name))
                self.assertFalse(expected.exists())

    def test_missing_or_unknown_artifact_is_an_error_without_legacy_guessing(self):
        with tempfile.TemporaryDirectory() as directory:
            repository = Path(directory)
            legacy = repository / "docs/plans"
            legacy.mkdir(parents=True)
            config = EffectiveConfig(
                data={"schema_version": "2.1", "artifacts": {"runtime": "run"}},
                repository_root=repository,
            )

            with self.assertRaises(ArtifactResolutionError):
                resolve_artifact(config, "plans")
            with self.assertRaises(ArtifactResolutionError):
                resolve_artifact(config, "unknown")
            self.assertTrue(legacy.is_dir())
            self.assertFalse((repository / "run").exists())


if __name__ == "__main__":
    unittest.main()
