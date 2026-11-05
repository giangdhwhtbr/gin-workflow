# gin-qa setup: the `## Types` rule and OpenCode skill ids

**Context**
Epic `gin-workflow-qa-setup` (2026-11-04) added `/gin-qa:setup`, which writes `qa/guidelines.md`, `qa/README.md`, and a project skill from one interview, and a `## Types` check in `gin-qa cases check`.

**Decision/Solution**
- The `## Types` rule runs only when the guidelines file has a `## Types` section. Projects without it (gin-console today) keep passing `cases check`, so adding a guidelines section never breaks an existing repository until the team opts in.
- An entry is `` - `<type>` `` optionally followed by `:` and text (`cases._TYPE_ENTRY`); a bare `` - `api` `` is valid. Docs must not say the description is required.
- The project skill copies no rule from the guidelines; it points to the guidelines, the README, and the gin-qa CLI, so editing the guidelines never makes it stale.
- OpenCode keys skills by directory name across plugins. A gin-qa skill whose name matches a gin-workflow skill must be renamed in the OpenCode bundle by both `install.sh` and `install.ps1` (`setup` becomes `gin-qa-setup`, as `report` already becomes `gin-workflow-report`).

**Consequences**
- gin-qa's `report` is still renamed `gin-workflow-report` in OpenCode and clashes with gin-workflow's `report`; not fixed by this epic.
- `External reference: required` in `## Bugs` is enforced by the `/gin-qa:run` skill, not by `gin-qa cases bug`; a direct CLI call can file a bug without a reference.
- The `install.ps1` rename was not executed on this host (no `pwsh`); it mirrors the `report` branch.

**References**
- `plugins/gin-qa/src/scripts/gin_qa/cases.py` (`declared_types`), `plugins/gin-qa/src/scripts/gin_qa/cli.py` (`_check`)
- `plugins/gin-qa/src/skills/setup/SKILL.md`, `plugins/gin-qa/src/templates/guidelines.md`, `plugins/gin-qa/src/templates/project-skill.md`
- `install.sh`, `install.ps1` (`install_opencode_bundle`, `Install-OpenCodeBundle`)
- Beads: `gin-workflow-qa-setup.1` to `gin-workflow-qa-setup.4`

**Scope**
gin-qa guidelines parsing, the setup skill, and OpenCode bundle naming.
