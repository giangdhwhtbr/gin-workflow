import unittest

from workflow_core import ext

EXPECTED = [
    "AcceptanceIdentity",
    "ApprovalAction",
    "AssignmentManifest",
    "AssignmentRequest",
    "AssignmentResolutionError",
    "CODEX_EFFORT_VALUES",
    "ContextManifest",
    "ContextRequest",
    "DEFAULT_HARNESS_MODELS",
    "EffectiveConfig",
    "PROVIDER_DEFAULT",
    "PROVIDER_DEFAULT_PROVIDERS",
    "PROVIDER_EXE_ALIASES",
    "ProviderLocalConfigError",
    "ProviderModelConfig",
    "REASONING_TIERS",
    "RepositorySnapshot",
    "RouteCandidate",
    "SUPPORTED_CONFIG_VERSIONS",
    "TierModelTarget",
    "WorkflowEvent",
    "WorkflowEventStore",
    "atomic_write_text",
    "authorize_protected_action",
    "create_context_manifest",
    "default_provider_model_config",
    "file_lock",
    "freeze",
    "load_effective_config",
    "main_checkout",
    "notify",
    "require_yaml",
    "resolve_harness_executable",
    "thaw",
    "validate_instance",
    "validate_plan_assignments",
]


class TestExt(unittest.TestCase):
    def test_ext_version_and_exports(self):
        self.assertEqual(ext.EXT_VERSION, 1)
        self.assertEqual(sorted(ext.__all__), sorted(EXPECTED))
        for name in ext.__all__:
            self.assertTrue(hasattr(ext, name), f"ext is missing attribute {name}")


if __name__ == "__main__":
    unittest.main()
