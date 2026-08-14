"""Make the documented top-level unittest command execute every test suite."""

from pathlib import Path
import importlib.util
import sys
import unittest


TEST_ROOT = Path(__file__).resolve().parent


def load_tests(_loader, _tests, pattern):
    suite = unittest.TestSuite()
    for name in ("workflow_core", "workflow_providers", "review_ledger"):
        for path in sorted((TEST_ROOT / name).glob(pattern or "test_*.py")):
            module_name = f"gin_workflow_tests.{name}.{path.stem}"
            spec = importlib.util.spec_from_file_location(module_name, path)
            if spec is None or spec.loader is None:
                raise ImportError(f"cannot load test module: {path}")
            module = importlib.util.module_from_spec(spec)
            sys.modules[module_name] = module
            spec.loader.exec_module(module)
            suite.addTests(unittest.TestLoader().loadTestsFromModule(module))
    return suite
