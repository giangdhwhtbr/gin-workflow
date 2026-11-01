# Beads metadata values and package detection limits

**Context**
Two limits surfaced while building the team workflow guide (epic `gin-workflow-k8uf`, 2026-11-01): one in how `bd` returns metadata, one in what `gin-workflow setup` detects.

**Decision/Solution**
- `bd update <id> --set-metadata key=<json>` accepts a JSON list or object, but `bd list --json` and `bd show --json` return the value as a JSON string, not a parsed value. Every reader must accept both shapes: parse when the value is a `str`, use it as is otherwise. `milestone_cli._trace_move` and `team_beads.metadata_json` do this; new readers copy the pattern.
- `workflow_core/project_detect.py` fills `project.packages` only from JavaScript workspaces (`package.json` `workspaces`, `pnpm-workspace.yaml`, `turbo.json`, `nx.json`, directories with a `package.json`). Maven, Gradle, Python and mixed repositories list their packages by hand in `.agent-workflow/config.yaml` (`path`, `shape`, `verify.checks`). `project.monorepo` is stored but nothing branches on it; the hooks run a package's checks in its directory whenever the package is listed.

**Consequences**
- A docs claim such as "setup detects packages from their manifests" is wrong outside JS workspaces; the walkthrough states the hand-written form.
- Code that reads bead metadata without the string branch fails on a real Beads database even when a unit test with a dict passes.

**References**
- `plugins/gin-workflow/src/scripts/workflow_core/milestone_cli.py` (`_trace_move`), `team_beads.py` (`metadata_json`)
- `plugins/gin-workflow/src/scripts/workflow_core/project_detect.py`, `hooks.py`
- `docs/starters/brownfield-walkthrough.md`, `docs/starters/brownfield-modernize.md`
- Beads: `gin-workflow-k8uf.3`, `gin-workflow-k8uf.5`

**Scope**
gin-workflow repository; applies to any command that stores structured metadata on beads and to any guide that describes monorepo setup.
