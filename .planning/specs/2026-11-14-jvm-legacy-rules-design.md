# Java, Spring, and JVM template rule packs and JVM and WebView route scouting in tech-doc

Epic: gin-workflow-jvm-legacy-rules
Status: draft for user review.

## Goal and scope

The `java`, `spring`, and `jvm-templates` rule packs exist and are proposed for repositories and workspace entries that use them, and `/gin:tech-doc` scouts Spring, JAX-RS, Struts, Servlet/JSP, and Velocity template routes, and the WebView shells of hybrid Android and iOS apps that render those pages, one scout per workspace entry.

In scope: a `build_file_mentions` detect kind (`workflow_core/rules_checks.py`); `plugins/gin-workflow/src/rules/java.md`, `spring.md`, and `jvm-templates.md`; `plugins/gin-workflow/src/skills/tech-doc/SKILL.md` and new `skills/tech-doc/references/jvm-routes.md` and `webview-shells.md`; `docs/guides/rules.md` and `rules.vi.md`; tests and packaging lists.

Out of scope: per-entry checks, pack selection, and shape (`gin-workflow-ws-entry-rules`, shipped); the legacy screen inventory, navigation graph, and coverage ledger for JSP applications (a separate epic, per `.planning/specs/2026-10-30-write-doc-design.md`); Java `tool_checks` (Checkstyle, SpotBugs); other server-side template engines (FreeMarker, Thymeleaf, Tiles), deferred by the user.

Confirmed understanding: the epic's only comment (`[gin ship]`, 2026-11-14) reports that `gin-workflow-ws-entry-rules` shipped (merge 3e78643c): workspace entries take `rules: {packs}`, `gin rules` in a child merges them and matches paths relative to the child, and `gin setup doctor` proposes packs per entry through `propose_packs`. So this epic only adds the packs and the detection they need; selection already works. Detection today supports `package_json_deps`, `pyproject_deps`, and `files_exist`; nothing reads dependencies in `pom.xml` or `build.gradle`. The brownfield starter's legacy is Java 8 JSP and Struts, and its new services are Spring Boot with Maven.

After the spec was first confirmed, the user added Velocity templates (only Velocity for now; other engines deferred: a JSP and Velocity app rendered inside Android and iOS WebViews), the WebView shells of such hybrid apps, and output-escaping rules for template files.

Comments considered: 1, latest 2026-11-14T10:43:21Z

## Requirements

1. Detect kind `build_file_mentions: [<token>...]`: a pack is proposed when any token appears, case-insensitively as a substring, in `pom.xml`, `build.gradle`, or `build.gradle.kts` at the root or in a first-level module directory (`*/pom.xml`, `*/build.gradle`, `*/build.gradle.kts`). A build file that cannot be read or decoded is skipped. `stack_intent` matching also uses these tokens. The pack test's allowed detect keys include it.
2. `rules/java.md`: tier `language`, `applies_to: ["**/*.java"]`, `detect: {files_exist: [pom.xml, build.gradle, build.gradle.kts]}`. Rules only tooling cannot enforce, valid for Java 8 (no rule requires `record`, `var`, or later APIs). It includes, at least: parameterized SQL (critical); try-with-resources for closeable resources; `equals` and `hashCode` overridden together; `BigDecimal` for money; no `null` returned from public collection-returning methods. Body within the 1,500-character limit; every critical rule has a `## Why` line.
3. `rules/spring.md`: tier `framework`, `requires: [java]`, `applies_to: ["**/*.java"]`, `detect: {build_file_mentions: [org.springframework, spring-boot]}`. It includes, at least: constructor injection; `@Transactional` on service methods, not controllers; `@Valid` on request bodies at the boundary; DTOs instead of entities in API responses; no secrets in `application.properties` or `application.yml` (critical). Same limits as requirement 2.
4. Tech-doc, JVM routes: a new `skills/tech-doc/references/jvm-routes.md` lists, per stack, what a scout searches for and what it records: Spring (`@RequestMapping` and the method variants, `@RestController`/`@Controller`, functional `RouterFunction`, view names returned to a view resolver); JAX-RS (`@Path`, `@GET`/`@POST`/..., `Application` subclasses); Struts (`struts-config.xml` action mappings and forwards, `struts.xml` results including `type="velocity"`, `@Action`); Servlet/JSP (`web.xml` `servlet-mapping`, `@WebServlet`, JSP pages, form `action` targets, `jsp:include`/`jsp:forward`, redirects); Velocity templates (`VelocityViewServlet` mappings such as `*.vm`, `VelocityViewResolver`, `#parse`/`#include`, form actions and links in `.vm` files). A route's row names the template that renders it.
5. Tech-doc, WebView shells: a new `skills/tech-doc/references/webview-shells.md` tells a scout of an Android or iOS entry to record the pages the app loads (`WebView.loadUrl`/`loadData`, `WKWebView.load`/`loadHTMLString`, configured base URLs) and the JavaScript bridges (`addJavascriptInterface` and `@JavascriptInterface` methods, `WKScriptMessageHandler`/`window.webkit.messageHandlers`, URL-scheme interception in `shouldOverrideUrlLoading`/`decidePolicyFor`). `02-FEATURES.md` rows link an app screen to the server route it loads; bridge calls are listed as app-side APIs in `05-API.md`.
6. `SKILL.md` step 3 links both references (JVM code; Android or iOS code), and says that in a workspace each entry, frozen ones included, gets its own scout. Phrases the tech-doc tests pin stay unchanged.
7. `rules/jvm-templates.md`: tier `framework`, no `requires`, `applies_to: ["**/*.jsp", "**/*.jspf", "**/*.tag", "**/*.vm"]`, `detect: {files_exist: [src/main/webapp/WEB-INF/web.xml, WebContent/WEB-INF/web.xml, WEB-INF/web.xml], build_file_mentions: [velocity, jstl]}`. It includes, at least: escape every value written into HTML, JavaScript, or a URL with the engine's escaping (`<c:out>`/`fn:escapeXml` in JSP, Velocity's escape tool), since Velocity and JSP expressions do not escape by default (critical); no scriptlets or business logic in templates; a CSRF token in every state-changing form; no secrets or internal data placed in pages a WebView shell or browser can read. Same limits as requirement 2.
8. Registration and docs: the pack id lists in `tests/workflow_core/test_token_budget.py` and `tests/gin_orchestrator/test_harness_packaging.py` include `java`, `spring`, and `jvm-templates`; `docs/guides/rules.md` and `rules.vi.md` list the three packs and name build files among what detection reads.

## User Stories

### US-1: Java and Spring rules for a JVM repository
As a developer on a Spring Boot service, I want `gin rules` to give me Java and Spring rules, so that agents follow the practices tooling does not catch.

Acceptance criteria:
- `gin rules --files src/main/java/App.java` with `rules.packs: [java, spring]` selects `spring`, `java`, and `core`.
- `propose_packs` on a repository with a `pom.xml` naming `spring-boot-starter-web` proposes `java` and `spring`; with a plain `pom.xml` it proposes `java` only.
- A Gradle multi-module repository whose `app/build.gradle` names `org.springframework` gets `spring` proposed.
- An undecodable `pom.xml` does not break `propose_packs`.
- `gin rules --files src/main/webapp/views/order.vm` with `jvm-templates` enabled selects it; a repository with `WebContent/WEB-INF/web.xml` or a build file naming `velocity` gets `jvm-templates` proposed.

### US-2: Routes of a JVM legacy in the technical docs
As a BA documenting a JSP, Struts, and Velocity legacy, I want `/gin:tech-doc` to scout its routes and templates, so that `05-API.md` and `02-FEATURES.md` list the legacy endpoints and the pages that render them.

Acceptance criteria:
- `skills/tech-doc/references/jvm-routes.md` exists and covers Spring, JAX-RS, Struts, Servlet/JSP, and Velocity.
- The tech-doc skill links it and says each workspace entry, frozen ones included, gets its own scout.
- The existing tech-doc skill tests pass unchanged.

### US-3: Screens of a hybrid app traced to server pages
As a BA documenting a hybrid Android and iOS app whose screens are server-rendered pages in a WebView, I want the scout of each app entry to record the pages it loads and its JavaScript bridges, so that each app screen links to the server route behind it.

Acceptance criteria:
- `skills/tech-doc/references/webview-shells.md` exists and covers Android `WebView` and iOS `WKWebView`: loaded URLs and JavaScript bridges.
- The tech-doc skill links it for Android or iOS code.

## Errors and compatibility

- The new detect kind only adds proposals; existing packs and detection are unchanged.
- Rule packs are discovered by glob; no code registry changes.
- Java 8 code bases receive no rule they cannot follow.

## Testing

- `tests/workflow_core/test_rules_checks.py`: `build_file_mentions` at the root and in a first-level module, Maven and Gradle (Groovy and Kotlin DSL), case-insensitive, an undecodable build file, no match.
- `tests/workflow_core/test_rule_packs.py`: the new packs pass the structure checks (allowed detect keys include the new kind).
- `tests/workflow_core/test_rules.py`: a `.java` file selects `spring`, `java`, `core` when both packs are enabled; a `.vm` and a `.jsp` file select `jvm-templates` when it is enabled.
- `tests/workflow_core/test_token_budget.py`, `tests/gin_orchestrator/test_harness_packaging.py`, `tests/workflow_core/test_tech_doc_skill.py`: updated lists and a check that the skill links `references/jvm-routes.md` and `references/webview-shells.md`.
- `gin docs check` on the changed docs; full suite `python3 -m pytest -n auto` passes.

## Open Technical Questions
