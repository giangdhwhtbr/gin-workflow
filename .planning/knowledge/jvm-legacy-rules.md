# JVM rule packs, build-file detection, and JVM and WebView scouting

**Context**
Epic `gin-workflow-jvm-legacy-rules` (2026-11-14, spec `.planning/specs/2026-11-14-jvm-legacy-rules-design.md`), split out of `gin-workflow-ws-entry-rules`. The brownfield legacy is Java 8 JSP, Struts, and Velocity, partly rendered inside Android and iOS WebViews; new services are Spring Boot.

**Decision/Solution**
- Detect kind `build_file_mentions` (`rules_checks._build_text`): case-insensitive substring match in `pom.xml`, `build.gradle`, `build.gradle.kts` at the root and one directory level down; unreadable or undecodable files are skipped. With per-entry proposals from `ws-entry-rules`, `gin setup doctor` proposes the packs per workspace child.
- Packs: `java` (language, Java 8 safe), `spring` (framework, requires `java`), `jvm-templates` (framework, `*.jsp`, `*.jspf`, `*.tag`, `*.vm`; escaping per context, `$esc` needs EscapeTool). Only Velocity among template engines; FreeMarker, Thymeleaf, Tiles deferred by the user.
- Tech-doc references `skills/tech-doc/references/jvm-routes.md` and `webview-shells.md`; step 3 gives each workspace entry, frozen ones included, its own scout.

**Consequences**
- Antigravity workers finished both backend tracks within the 900 s timeout, but returned results that failed the contract (`status` not in the enum, `commits` not strings), so dispatch reported `failed` after correct work; bead `gin-workflow-suk9`. One worker also edited `test_harness_packaging.py` out of scope; reverted.
- `test_harness_packaging.py` is flaky under `pytest -n auto` (shared `dist`), passes serially; bead `gin-workflow-0mw2`.
- The `/goal` condition from `gin goal` (process wording plus an uncountable turn clause) kept the Stop hook from accepting finished work; bead `gin-workflow-2zo4`; execute-skill wording for contract failures with commits: `gin-workflow-85og`.

**References**
- `plugins/gin-workflow/src/scripts/workflow_core/rules_checks.py`, `plugins/gin-workflow/src/rules/{java,spring,jvm-templates}.md`, `plugins/gin-workflow/src/skills/tech-doc/references/{jvm-routes,webview-shells}.md`, `docs/guides/rules.md`
- Beads: `gin-workflow-jvm-legacy-rules.1` to `.3`; follow-ups `gin-workflow-2zo4`, `suk9`, `85og`, `0mw2`, `87kq`
- Related: [workspace](workspace.md), [non-claude-dispatch](non-claude-dispatch.md)

**Scope**
Rule packs and detection, tech-doc scouting, antigravity dispatch.
