import unittest

from workflow_core import ext

EXPECTED = [
    "AcceptanceIdentity",
    "ApprovalAction",
    "AssignmentManifest",
    "AssignmentRequest",
    "AssignmentResolutionError",
    "Catalog",
    "ContextManifest",
    "ContextRequest",
    "DEFAULT_CATALOGS",
    "DEFAULT_EXECUTABLES",
    "EffectiveConfig",
    "PROVIDER_DEFAULT",
    "PROVIDER_DEFAULT_PROVIDERS",
    "PROVIDER_EXE_ALIASES",
    "ProviderLocalConfigError",
    "ProviderModelConfig",
    "RepositorySnapshot",
    "RouteCandidate",
    "SUPPORTED_CONFIG_VERSIONS",
    "WorkflowEvent",
    "WorkflowEventStore",
    "atomic_write_text",
    "authorize_protected_action",
    "catalog_for",
    "cleanup_worktree",
    "create_context_manifest",
    "create_worktree",
    "default_provider_model_config",
    "escalate",
    "file_lock",
    "freeze",
    "load_effective_config",
    "main_checkout",
    "map_route",
    "notify",
    "require_yaml",
    "resolve_harness_executable",
    "route_diagnostics",
    "thaw",
    "tier_of",
    "validate_instance",
    "validate_plan_assignments",
]


class TestExt(unittest.TestCase):
    def test_ext_version_and_exports(self):
        self.assertEqual(ext.EXT_VERSION, 2)
        self.assertEqual(sorted(ext.__all__), sorted(EXPECTED))
        for name in ext.__all__:
            self.assertTrue(hasattr(ext, name), f"ext is missing attribute {name}")


if __name__ == "__main__":
    unittest.main()
