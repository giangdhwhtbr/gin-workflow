"""xdist grouping for tests that rebuild shared build output.

HarnessPackagingTests.setUpClass rebuilds plugins/*/dist, so two xdist workers
building at once race. Keep the class on one worker. Everything is guarded on
the xdist plugin, so plain pytest (and -p no:xdist) still works.

xdist workers re-parse the command line and never see a --dist chosen here, so
the controller switches to loadgroup in pytest_configure and each worker folds
the group into the node id itself (the suffix loadgroup scheduling reads).
"""
GROUP = "harness-packaging-dist"


def pytest_configure(config):
    # An explicit --dist stays as given; -n turns the default into "load".
    if config.pluginmanager.hasplugin("xdist") and config.option.numprocesses \
            and config.option.dist in ("no", "load"):
        config.option.dist = "loadgroup"


def pytest_collection_modifyitems(config, items):
    if not hasattr(config, "workerinput"):  # only xdist workers
        return
    for item in items:
        cls = getattr(item, "cls", None)
        if cls is not None and cls.__name__ == "HarnessPackagingTests" \
                and item.path.name == "test_harness_packaging.py":
            item._nodeid = f"{item.nodeid}@{GROUP}"
