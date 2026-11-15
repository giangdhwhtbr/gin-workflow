# Plan: Java, Spring, and JVM template rule packs and JVM and WebView route scouting in tech-doc

Spec: .planning/specs/2026-11-14-jvm-legacy-rules-design.md
Epic: gin-workflow-jvm-legacy-rules
Workflow: gin-workflow-jvm-legacy-rules

## Objective

A `build_file_mentions` detect kind; `java`, `spring`, and `jvm-templates` packs proposed for the repositories and workspace entries that use them; tech-doc references for JVM routes (Spring, JAX-RS, Struts, Servlet/JSP, Velocity) and for Android and iOS WebView shells, linked from the skill with one scout per workspace entry.

**Goal** (spec): the `java`, `spring`, and `jvm-templates` rule packs exist and are proposed for repositories and workspace entries that use them, and `/gin:tech-doc` scouts Spring, JAX-RS, Struts, Servlet/JSP, and Velocity template routes, and the WebView shells of hybrid Android and iOS apps that render those pages, one scout per workspace entry.

**Architecture**: detection gains one kind in `rules_checks.propose_packs`, read from root and first-level module build files, tolerant of unreadable files. Packs are Markdown files discovered by glob; three tests and the packaging list name the pack set. Tech-doc gets two skill-local references (`skills/tech-doc/references/`) and one sentence each in step 3.

**Tech Stack**: Python 3 standard library; unittest/pytest (`tests/workflow_core/test_rules_checks.py`, `test_rule_packs.py`, `test_rules.py`, `test_token_budget.py`, `test_tech_doc_skill.py`, `tests/gin_orchestrator/test_harness_packaging.py`); Markdown rule packs (bullet format and limits in `plugins/gin-workflow/src/rules/README.md`).

**Global Constraints** (spec, verbatim):
- Out of scope: per-entry checks, pack selection, and shape (`gin-workflow-ws-entry-rules`, shipped); the legacy screen inventory, navigation graph, and coverage ledger for JSP applications (a separate epic, per `.planning/specs/2026-10-30-write-doc-design.md`); Java `tool_checks` (Checkstyle, SpotBugs); other server-side template engines (FreeMarker, Thymeleaf, Tiles), deferred by the user.
- The new detect kind only adds proposals; existing packs and detection are unchanged.
- Rule packs are discovered by glob; no code registry changes.
- Java 8 code bases receive no rule they cannot follow.

## Route Rubric
- Choose the weakest model that can do the work.
- Raise the model for broad context or design judgement.
- Raise the effort for intrinsic difficulty: intricate logic, many edge cases, or long chains of steps.

| Kind of work | Model | Effort |
|---|---|---|
| Mechanical edits, documentation, boilerplate | weakest | `low` |
| Bounded implementation with a clear spec | middle | `medium` |
| Cross-module change, security, migration, concurrency | strongest | `high` |

Unclear requirements never raise the model or effort.

## Requirement Analysis
- Problem statement: no rules or detection for Java, Spring, JSP, and Velocity code, and tech-doc scouts miss JVM legacy routes and hybrid app shells.
- Success criteria: spec requirements 1–8 and US-1 to US-3; `python3 -m pytest -n auto` passes.
- Constraints: Global Constraints above.
- Non-goals: other template engines; Java tool checks; the JSP screen inventory.

## Approach Options
### Option 1: new detect kind, three packs, two tech-doc references (selected in `/discuss`)
- Summary: as the spec.
- Pros: `doctor` proposes the packs per workspace entry with no other change; references keep `SKILL.md` short.
- Cons: one more detect kind to maintain.

### Option 2: packs enabled only by hand
- Summary: no detection change.
- Pros: no code.
- Cons: no proposals for Spring or Velocity; rejected in `/discuss`.

### Recommended Approach
- Selected option: Option 1 (confirmed in `/discuss` on 2026-11-14).
- Rationale: reuses the per-entry proposal path that shipped with `ws-entry-rules`.

## Scope
- In scope: spec requirements 1–8.
- Out of scope: see Global Constraints.

## Execution Strategy

```yaml
execution_strategy:
  mode: direct
  workers:
    mode: sequential
  rationale: Track 2 uses the detect kind of Track 1, and Tracks 2 and 3 both edit the packaging test list; one lane.
```

## Tasks

`C` is `plugins/gin-workflow/src/scripts/workflow_core`; `R` is `plugins/gin-workflow/src/rules`. Run tests from the repository root.

### Track 1: `build_file_mentions` detect kind
- **Dependencies**: none
- **Files**:
  - Modify `plugins/gin-workflow/src/scripts/workflow_core/rules_checks.py:31-60` (`_build_text`, `propose_packs`)
  - Modify `tests/workflow_core/test_rule_packs.py:16` (`DETECT_KEYS`)
  - Test `tests/workflow_core/test_rules_checks.py` (`TestPropose`)
- **Provider role**: `backend`
- **Model:** `sonnet`
- **Effort:** `medium`
- **Why:** one bounded function beside `_py_text`, with file-reading edge cases listed.
- **Interfaces**:
  - `_BUILD_FILES = ("pom.xml", "build.gradle", "build.gradle.kts")`.
  - `_build_text(root: Path) -> str`: lower-cased concatenation of each build file at `root` and in each first-level subdirectory (`root/*/<name>`), skipping a file whose read raises `OSError` or `UnicodeDecodeError` (read with `encoding="utf-8"`; on decode error skip the file rather than `errors="replace"`, so binary junk never matches), and skipping hidden directories and `node_modules`.
  - `propose_packs`: `build_names = [str(n).lower() for n in detect.get("build_file_mentions", [])]`; a pack is chosen when `any(name in build_text for name in build_names)` (substring, case-insensitive); `stack_intent` matching adds `*build_names` to the names it checks. `_build_text(root)` is computed once per call.
  - `DETECT_KEYS` adds `"build_file_mentions"`.
- **Steps**:
  1. Failing tests in `TestPropose` with a fake plugin pack whose `detect` is `{"build_file_mentions": ["org.springframework", "spring-boot"]}` (follow how the class builds packs, or write a temp pack file and load it): root `pom.xml` naming `spring-boot-starter-web` → proposed; `app/build.gradle` naming `org.springframework.boot` → proposed; `build.gradle.kts` with upper-case `Org.SpringFramework` → proposed; `pom.xml` without the tokens → not proposed; a `pom.xml` with invalid UTF-8 bytes → no exception, not proposed; `stack_intent="spring-boot service"` → proposed. Run `python3 -m pytest tests/workflow_core/test_rules_checks.py -q` → fail.
  2. Implement per Interfaces.
  3. `python3 -m pytest tests/workflow_core/test_rules_checks.py tests/workflow_core/test_rule_packs.py tests/workflow_core/test_workspace_cli.py -q -n auto` → pass.
  4. Commit: `feat(rules): build_file_mentions detect kind for Maven and Gradle (gin-workflow-jvm-legacy-rules)`.
- **Acceptance criteria**: spec requirement 1; US-1 bullets 2–4.
- **Estimated complexity**: low

### Track 2: `java`, `spring`, and `jvm-templates` packs
- **Dependencies**: Track 1
- **Files**:
  - Create `plugins/gin-workflow/src/rules/java.md`, `plugins/gin-workflow/src/rules/spring.md`, `plugins/gin-workflow/src/rules/jvm-templates.md`
  - Modify `tests/workflow_core/test_token_budget.py:98` (pack id set), `tests/gin_orchestrator/test_harness_packaging.py:48-58` (`rules/<id>.md` list)
  - Modify `docs/guides/rules.md:7-20`, `docs/guides/rules.vi.md` (same table and sentence)
  - Test `tests/workflow_core/test_rules.py`, `tests/workflow_core/test_rules_checks.py`
- **Provider role**: `backend`
- **Model:** `sonnet`
- **Effort:** `medium`
- **Why:** rule content needs Java, Spring, JSP, and Velocity judgement within strict format and budget limits.
- **Interfaces** (front matter exactly; bodies follow `rules/README.md`: ``- [impact] `anchor`: Imperative text.``, unique anchors, body ≤ 1,500 characters, every `[critical]` bullet has a `## Why` line, only rules tooling cannot enforce):
  - `java.md`: `id: java`, `tier: language`, `applies_to: ["**/*.java"]`, `detect: {files_exist: [pom.xml, build.gradle, build.gradle.kts]}`. Bullets cover at least: `[critical] parameterized-sql` (bind parameters with `PreparedStatement` or the framework; never concatenate input into SQL/JPQL/HQL); `close-resources` (try-with-resources for every `AutoCloseable`); `equals-hashcode` (override together); `money-bigdecimal` (`BigDecimal` with an explicit scale and rounding for money); `empty-not-null` (return empty collections, not `null`); Java 8 compatible wording (no `record`, `var`, or later APIs).
  - `spring.md`: `id: spring`, `tier: framework`, `requires: [java]`, `applies_to: ["**/*.java"]`, `detect: {build_file_mentions: [org.springframework, spring-boot]}`. Bullets cover at least: `constructor-injection`; `transactional-service` (`@Transactional` on service methods, not controllers or repositories called from outside); `validate-boundary` (`@Valid` on request bodies and path/query constraints); `dto-not-entity`; `[critical] no-secrets-in-properties` (secrets from the environment or a secret store, never in `application.properties`/`application.yml` committed to git).
  - `jvm-templates.md`: `id: jvm-templates`, `tier: framework`, `applies_to: ["**/*.jsp", "**/*.jspf", "**/*.tag", "**/*.vm"]`, `detect: {files_exist: [src/main/webapp/WEB-INF/web.xml, WebContent/WEB-INF/web.xml, WEB-INF/web.xml], build_file_mentions: [velocity, jstl]}`. Bullets cover at least: `[critical] escape-output` (escape every value written into HTML, JavaScript, or a URL: `<c:out>`/`fn:escapeXml` in JSP, Velocity's escape tool such as `$esc.html(...)`; JSP EL and Velocity references do not escape by default); `no-logic-in-views` (no scriptlets or business logic; prepare data in the controller or action); `csrf-token` (every state-changing form carries the CSRF token); `no-internal-data` (no secrets, internal identifiers, or stack traces in pages a browser or WebView shell can read).
- **Steps**:
  1. Failing tests: `test_rules.py` — with `rules.packs: [java, spring, jvm-templates]`, `--files src/main/java/App.java` selects `spring`, `java`, `core`, `lean` (check how existing cases assert the id list and order) and `--files src/main/webapp/views/order.vm` and `WEB-INF/jsp/list.jsp` select `jvm-templates`; `test_rules_checks.py` `TestPropose` with the real plugin packs: a `pom.xml` naming `spring-boot-starter-web` → `java` and `spring`; a plain `pom.xml` → `java` only; `WebContent/WEB-INF/web.xml` → `jvm-templates`; a `pom.xml` naming `velocity-tools` → `java` and `jvm-templates`. Update `test_token_budget.py:98` and the packaging list. Run → fail.
  2. Write the three packs per Interfaces.
  3. `docs/guides/rules.md` table rows: `java` | language | `*.java` | via `rules.packs`; `spring` | framework (needs `java`) | `*.java` | via `rules.packs`; `jvm-templates` | framework | `*.jsp`, `*.jspf`, `*.tag`, `*.vm` | via `rules.packs`. Detection sentence: "(dependencies, `tsconfig.json`, `pyproject.toml`, Maven and Gradle build files, `WEB-INF/web.xml`)". Mirror in `rules.vi.md` in Vietnamese, code verbatim.
  4. `python3 -m pytest tests/workflow_core/test_rules.py tests/workflow_core/test_rules_checks.py tests/workflow_core/test_rule_packs.py tests/workflow_core/test_token_budget.py tests/gin_orchestrator/test_harness_packaging.py -q -n auto` → pass; `gin docs check docs/guides/rules.md docs/guides/rules.vi.md` → ok.
  5. Commit: `feat(rules): java, spring, and jvm-templates packs (gin-workflow-jvm-legacy-rules)`.
- **Acceptance criteria**: spec requirements 2, 3, 7, 8; US-1 bullets 1, 2, 5.
- **Estimated complexity**: medium

### Track 3: tech-doc JVM routes and WebView shells
- **Dependencies**: Track 2
- **Files**:
  - Create `plugins/gin-workflow/src/skills/tech-doc/references/jvm-routes.md`, `plugins/gin-workflow/src/skills/tech-doc/references/webview-shells.md`
  - Modify `plugins/gin-workflow/src/skills/tech-doc/SKILL.md:28` (step 3)
  - Modify `tests/gin_orchestrator/test_harness_packaging.py:30-40` (skill reference list)
  - Test `tests/workflow_core/test_tech_doc_skill.py`
- **Provider role**: `docs`
- **Model:** `sonnet`
- **Effort:** `low`
- **Why:** reference text for agents with exact framework names; needs JVM and mobile knowledge but no code.
- **Steps**:
  1. Failing test in `test_tech_doc_skill.py`: `SKILL.md` contains `[jvm-routes.md](references/jvm-routes.md)`, `[webview-shells.md](references/webview-shells.md)`, and the phrase "each workspace entry, frozen ones included, gets its own scout"; both reference files exist and name, respectively, `@RequestMapping`, `@Path`, `struts-config.xml`, `servlet-mapping`, `VelocityViewServlet`, `#parse`, and `loadUrl`, `WKWebView`, `addJavascriptInterface`, `WKScriptMessageHandler`. Add both files to the packaging list. Run → fail.
  2. `jvm-routes.md` (headings per stack; for each: where routes are declared, what a `05-API.md` row records, what a `02-FEATURES.md` row records): Spring (`@RequestMapping` and `@GetMapping`/`@PostMapping`/`@PutMapping`/`@DeleteMapping`/`@PatchMapping`, class-level prefixes, `@RestController` vs `@Controller` returning view names, `RouterFunction`); JAX-RS (`@Path` on class and method, `@GET`/`@POST`/..., `@Produces`/`@Consumes`, `Application` subclasses and `@ApplicationPath`); Struts 1 (`struts-config.xml` `<action path>` and `<forward>`), Struts 2 (`struts.xml` `<action name>` and `<result>` including `type="velocity"`, `@Action`/`@Result`); Servlet/JSP (`web.xml` `<servlet-mapping>`, `@WebServlet`, JSP pages reachable by URL, form `action` targets, `jsp:include`/`jsp:forward`, `sendRedirect`); Velocity (`VelocityViewServlet` mapping such as `*.vm` in `web.xml`, Spring `VelocityViewResolver` prefix and suffix, Struts velocity results, `#parse`/`#include`, form actions and `href`s in `.vm` files). Each route row names the controller, action, or servlet and the template that renders it, with `file:line`.
  3. `webview-shells.md`: Android (`WebView.loadUrl`/`loadData`/`loadDataWithBaseURL`, base URLs from `BuildConfig` or resources, `addJavascriptInterface` and `@JavascriptInterface` methods, `shouldOverrideUrlLoading` URL schemes); iOS (`WKWebView.load(URLRequest)`/`loadHTMLString`, base URLs from `Info.plist` or configuration, `WKScriptMessageHandler` and `window.webkit.messageHandlers.<name>.postMessage`, `decidePolicyFor` URL schemes). Records: each app screen and the server URL it loads go to `02-FEATURES.md` (linked to the `05-API.md` route); each bridge method goes to `05-API.md` as an app-side API (name, direction, payload), with `file:line`.
  4. `SKILL.md` step 3, after the frameworks example: "For JVM code, follow [jvm-routes.md](references/jvm-routes.md); for Android or iOS code, follow [webview-shells.md](references/webview-shells.md). In a workspace, each workspace entry, frozen ones included, gets its own scout." Keep every phrase `test_tech_doc_skill.py` and `install_smoke_test.sh` pin.
  5. `python3 -m pytest tests/workflow_core/test_tech_doc_skill.py tests/workflow_core/test_token_budget.py tests/workflow_core/test_skill_routing.py tests/gin_orchestrator/test_harness_packaging.py -q -n auto` → pass; `python3 -m pytest -n auto` → pass.
  6. Commit: `docs(tech-doc): JVM route and WebView shell scouting references (gin-workflow-jvm-legacy-rules)`.
- **Acceptance criteria**: spec requirements 4, 5, 6; US-2; US-3.
- **Estimated complexity**: low

## Integration
- **Branch**: `feat/jvm-legacy-rules`
- **Merge strategy**: sequential

## Validation
- [ ] `python3 -m pytest -n auto` passes
- [ ] `gin docs check` passes on the changed docs
- [ ] Each new pack body is within 1,500 characters

## Notes
- The user may override `Model:` and `Effort:` before plan approval.
- Deliverable merge-holds apply only to the Parent Bead; track beads close once tests and review pass.
- Backend tracks route to antigravity; the worker timeout is 900 s, so a Claude fallback may finish them.
