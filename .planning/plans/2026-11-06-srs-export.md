# Plan: SRS export: printable HTML from living specs with a customizable template

Epic: gin-workflow-bel0
Spec: .planning/specs/2026-11-05-srs-export-design.md

## Objective
With the SDD layout, `gin-workflow specs export <capability>` writes `srs-<capability>.html` and `specs export --all` writes `srs.html`: one self-contained HTML file holding each capability's purpose, Mermaid diagrams, requirement blocks with scenarios, and assets (images embedded as `data:` URIs), with a table of contents, a cover, and print CSS. Two templates, `srs.html` and `srs-capability.html`, are overridable per project for the logo, customer, product brief, and section order. A missing local image still writes the file and exits 1. The CLI reference, the template guide, the SDD guide, and `gin-sdd` describe it.

Architecture: one new module `workflow_core/specs_export.py` (a stdlib Markdown-to-HTML converter for the subset the specs use, an `Embed` helper for `data:` URIs, chapter and document assembly, a one-pass placeholder fill); an `export` subcommand in `workflow_core/specs_cli.py`; two templates under `plugins/gin-workflow/src/templates/`. No config key, event, or dependency.

Tech stack: Python 3.12 standard library (`base64`, `html`, `re`, `pathlib`, `dataclasses`), `unittest` tests run by `python3 -m pytest -n auto`; Mermaid 11.4.1 loaded by the exported page from jsDelivr.

Global Constraints (from the spec):
- SDD layout only; `specs export` exits 2 with the legacy layout like the other `specs` commands that need `layout: sdd`.
- The SRS holds only the confirmed living requirements: no change folder, spec delta, user story, or traceability table.
- One self-contained HTML file: every local image is embedded as a `data:` URI; no `src` names a local path.
- Every piece of text is HTML-escaped; raw HTML in Markdown is shown as text; HTML comments are removed from Markdown and from both templates.
- Placeholders are filled in one pass, so text from a spec that contains `{{...}}` is never substituted.
- Mermaid loads from jsDelivr at an exact pinned version with `integrity` and `crossorigin`; without network the page shows the diagram sources.
- No new dependency: stdlib only. The export does not lint.
- Existing commands, templates, and config are unchanged.
- `skills/gin-*/SKILL.md` stay within 6,000 characters (`tests/workflow_core/test_token_budget.py`).

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
- Problem statement: a BA who must send a customer an SRS copies the living specs, diagrams, and assets into a document by hand.
- Success criteria: user stories US-1..US-4 of the spec; `specs export` exit codes 0, 1, 2 as in R1; the templates print their placeholders and pin Mermaid with `integrity`; full suite green.
- Constraints: see Global Constraints.
- Non-goals: exporting a change; user stories and traceability; producing PDF; `gin-workflow-explain`; a Markdown dependency or vendored JavaScript; the legacy layout.

## Approach Options
### Option 1: Stdlib converter and two overridable templates (chosen in discuss)
- Summary: Python converts the Markdown subset and assembles chapters; the project overrides `srs.html` and `srs-capability.html`.
- Pros: no dependency; the page renders without JavaScript except diagrams; one override mechanism the project already knows.
- Cons: about 230 lines of converter and assembly code to maintain; Markdown outside the subset renders as plain text.

### Option 2: Python `markdown` package
- Summary: convert with a third-party library.
- Pros: fuller Markdown.
- Cons: breaks the stdlib-plus-PyYAML runtime; every user installs a package.

### Option 3: Raw Markdown rendered by `marked.js` in the browser
- Summary: embed the Markdown and render client-side.
- Pros: least Python.
- Cons: without network the document is empty, and printing depends on JavaScript.

### Recommended Approach
- Selected option: Option 1.
- Rationale: chosen by the user in discuss on 2026-11-05, with capability and `--all` scope, Mermaid from a CDN with SRI, and customization through templates only. The code below was run against the tests below in a scratch copy: 11 passed, 39 subtests.

## Scope
- In scope: R1 to R5 of the spec.
- Out of scope: everything under the spec's "Out of scope".

## Execution Strategy

```yaml
execution_strategy:
  mode: direct
  workers:
    mode: sequential
  rationale: Two tracks; Track 2 documents the command and templates Track 1 ships and links to the template guide section Track 1 writes, so they run one after the other on the feature branch.
```

## Tasks
### Track 1: `specs export` command, converter, and SRS templates
- **Dependencies**: none
- **Files**:
  - Create `plugins/gin-workflow/src/scripts/workflow_core/specs_export.py`
  - Create `plugins/gin-workflow/src/templates/srs.html`
  - Create `plugins/gin-workflow/src/templates/srs-capability.html`
  - Modify `plugins/gin-workflow/src/scripts/workflow_core/specs_cli.py:39-40,108-109` (`export` subparser; `export` branch before `find_change`)
  - Test `tests/workflow_core/test_specs_export.py`
  - Modify `docs/reference/cli.md:139,142` (`export` row; exit code 1)
  - Modify `docs/guides/customizing-templates.md:27,41,99` (template list, table row, `### SRS export templates`)
  - Modify `docs/guides/customizing-templates.vi.md:27,41,99` (same, Vietnamese)
- **Provider role**: `backend`
- **Model:** `sonnet`
- **Effort:** `medium`
- **Why:** bounded new module with its full code, templates, and tests given below; the edge cases (escaping, one-pass fill, missing images, `--out` outside the repository, heading shift) are listed and tested.
- **Interfaces**:
  - Produces `workflow_core.specs_export.export(root: Path, cfg: Mapping[str, Any], cap: str | None, out: str | None, today: date | None = None) -> dict[str, Any]` returning `{"path": str, "capabilities": list[str], "missing": list[str]}`; `cap=None` exports every capability; raises `specs.SpecsError` (exit 2) for an unknown capability, no capability, or `--out` outside the repository.
  - Produces `workflow_core.specs_export.markdown_html(text: str, base: Path, origin: str, embed: Embed, top: int = 3) -> str`, `Embed` (`missing: list[str]`, `shown: set[Path]`, `src(target, base, origin) -> str | None`), `data_uri(path: Path) -> str`, `fill(template: str, values: Mapping[str, str]) -> str`. `gin-workflow-explain` may reuse them.
  - Produces CLI `gin-workflow specs export (CAP | --all) [--out FILE]`: text output is the path, then `missing image: <file>: <image>` lines; `--format json` prints the dict above; exit 0, 1 (missing images), 2.
  - Produces template names `srs.html` (placeholders `title`, `date`, `toc`, `chapters`) and `srs-capability.html` (`cap`, `capability`, `purpose`, `diagrams`, `requirements`, `assets`) for `gin-workflow specs template`.
  - Consumes `specs.living_files`, `specs.parse_blocks`, `specs.template_text`, `specs.SpecsError`, `specs._ISO_DATE` (`specs.py`), and `specs_fixtures` (`AUTH_SPEC`, `STATE`, `LAUNCHER`, `make_repo`, `write`, `write_activity`).
- **Acceptance criteria**: `python3 -m pytest tests/workflow_core/test_specs_export.py -q` passes (11 tests); `gin-workflow docs check docs/reference/cli.md docs/guides/customizing-templates.md docs/guides/customizing-templates.vi.md` prints no finding.
- **Estimated complexity**: medium
- **Steps**:
  1. Failing tests. Create `tests/workflow_core/test_specs_export.py`:
     ````python
     """`gin-workflow specs export`: living specs to one printable SRS HTML file (gin-workflow-bel0)."""

     from __future__ import annotations

     import base64
     from datetime import date
     import json
     from pathlib import Path
     import re
     import subprocess
     import sys
     import tempfile
     import unittest

     sys.path.insert(0, str(Path(__file__).resolve().parent))

     from specs_fixtures import AUTH_SPEC, LAUNCHER, STATE, make_repo, write, write_activity  # noqa: E402
     from workflow_core import specs  # noqa: E402
     from workflow_core.specs_export import Embed, export, fill, markdown_html  # noqa: E402

     PNG = b"\x89PNG\r\n\x1a\nfake-image"
     PNG_URI = "data:image/png;base64," + base64.b64encode(PNG).decode("ascii")
     DESCRIPTION = """# auth: 2026-05-11

     Kind: new
     Source: kickoff call

     ## Summary

     The login screen as the customer drew it: ![Login screen](mockup/login.png)
     """


     def run_specs(root: Path, *args: str) -> subprocess.CompletedProcess[str]:
         return subprocess.run([sys.executable, str(LAUNCHER), "specs", *args, "--repository", str(root)],
                               text=True, capture_output=True, check=False)


     def write_bytes(root: Path, relative: str, data: bytes) -> Path:
         path = Path(root) / relative
         path.parent.mkdir(parents=True, exist_ok=True)
         path.write_bytes(data)
         return path


     class TestMarkdown(unittest.TestCase):
         def convert(self, text: str, top: int = 3) -> tuple[str, Embed]:
             embed = Embed()
             return markdown_html(text, Path("/nonexistent"), "doc.md", embed, top), embed

         def test_blocks_and_inline(self):
             html, _ = self.convert(
                 "# Title\n\nSome **bold**, *italic*, `a<b`, and [a link](https://x.test/?a=1&b=2).\n"
                 "second line\n\n- one\n  - nested\n- two\n\n1. first\n2. second\n\n"
                 "| Field | Rule |\n|---|---|\n| email | **required** |\n\n```\nx < y\n```\n\n"
                 "```mermaid\nflowchart TD\n  a --> b\n```\n")
             for needle in ("<h3>Title</h3>", "<strong>bold</strong>", "<em>italic</em>", "<code>a&lt;b</code>",
                            '<a href="https://x.test/?a=1&amp;b=2">a link</a>', "second line</p>",
                            "<ul><li>one<ul><li>nested</li></ul></li><li>two</li></ul>",
                            "<ol><li>first</li><li>second</li></ol>",
                            "<thead><tr><th>Field</th><th>Rule</th></tr></thead>",
                            "<td><strong>required</strong></td>", "<pre><code>x &lt; y</code></pre>",
                            '<pre class="mermaid">flowchart TD\n  a --&gt; b</pre>'):
                 with self.subTest(needle=needle):
                     self.assertIn(needle, html)

         def test_comments_removed_raw_html_escaped_snake_case_kept(self):
             html, _ = self.convert("<!-- base: abc -->\nA <script>alert(1)</script> test_globs value.\n")
             self.assertNotIn("base: abc", html)
             self.assertIn("&lt;script&gt;alert(1)&lt;/script&gt;", html)
             self.assertIn("test_globs", html)
             self.assertNotIn("<em>", html)

         def test_headings_shift_to_top_and_cap_at_six(self):
             html, _ = self.convert("## A\n\n### B\n\n###### C\n", top=3)
             self.assertIn("<h3>A</h3>", html)
             self.assertIn("<h4>B</h4>", html)
             self.assertIn("<h6>C</h6>", html)

         def test_images_local_missing_remote(self):
             with tempfile.TemporaryDirectory() as directory:
                 base = Path(directory)
                 write_bytes(base, "img/a.png", PNG)
                 embed = Embed()
                 html = markdown_html("![A](img/a.png) ![B](img/b.png) ![C](https://x.test/c.png)", base, "doc.md", embed)
             self.assertIn(f'<img src="{PNG_URI}" alt="A">', html)
             self.assertIn('<span class="missing-image">B</span>', html)
             self.assertIn('<img src="https://x.test/c.png" alt="C">', html)
             self.assertEqual(["doc.md: img/b.png"], embed.missing)

         def test_fill_is_one_pass(self):
             self.assertEqual("<p>{{date}}</p> 2026", fill("{{body}} {{date}}", {"body": "<p>{{date}}</p>", "date": "2026"}))
             self.assertEqual("{{unknown}}", fill("{{unknown}}", {}))


     class TestExport(unittest.TestCase):
         def setUp(self):
             self.tmp = tempfile.TemporaryDirectory()
             self.root = make_repo(Path(self.tmp.name)).resolve()
             self.cfg = specs.sdd_config(specs.load_config(self.root))
             write(self.root, "docs/specs/auth/spec.md", AUTH_SPEC.replace("Sign-in.", "Sign-in. Literal {{date}} stays."))
             write_activity(self.root)
             write(self.root, "docs/specs/auth/diagrams/account-state.md", STATE)
             write(self.root, "docs/specs/auth/assets/2026-05-11/description.md", DESCRIPTION)
             write_bytes(self.root, "docs/specs/auth/assets/2026-05-11/mockup/login.png", PNG)
             write_bytes(self.root, "docs/specs/auth/assets/2026-05-11/legacy/old.png", PNG)
             write(self.root, "docs/specs/auth/assets/2026-05-11/notes.txt", "call notes")
             write(self.root, "docs/specs/auth/assets/2026-06-02/description.md", "# auth: 2026-06-02\n\nKind: change\n")
             write_bytes(self.root, "docs/specs/auth/assets/flat.png", PNG)
             write(self.root, "docs/specs/billing/spec.md", "# Billing\n\n## Purpose\n\nInvoices.\n\n## Requirements\n")

         def tearDown(self):
             self.tmp.cleanup()

         def read(self, relative: str) -> str:
             return (self.root / relative).read_text(encoding="utf-8")

         def test_one_capability_holds_purpose_diagrams_requirements_and_assets(self):
             result = run_specs(self.root, "export", "auth")
             self.assertEqual(0, result.returncode, result.stderr)
             self.assertEqual("srs-auth.html", result.stdout.strip())
             html = self.read("srs-auth.html")
             for needle in ("<title>Auth</title>", '<section class="chapter" id="auth">', "<h1>Auth</h1>",
                            "Sign-in. Literal {{date}} stays.", '<pre class="mermaid">flowchart TD',
                            '<pre class="mermaid">%% stored in invoices.status\nstateDiagram-v2',
                            '<section class="requirement" id="REQ-AUTH-001">',
                            "<h3>REQ-AUTH-001: Sign in with password</h3>", "<h4>Scenario: valid password</h4>",
                            "<li>GIVEN a registered user</li>", '<a href="#REQ-AUTH-002">REQ-AUTH-002: Reject wrong password</a>',
                            "<h3>auth: 2026-05-11</h3>", '<figcaption>legacy/old.png</figcaption>',
                            "<code>notes.txt</code>", "<h3>Files</h3>", "<figcaption>flat.png</figcaption>",
                            "mermaid@11.4.1/dist/mermaid.min.js", 'integrity="sha384-'):
                 with self.subTest(needle=needle):
                     self.assertIn(needle, html)
             self.assertEqual(1, html.count("<figcaption>mockup/login.png</figcaption>") + html.count('alt="Login screen"'))
             self.assertLess(html.index("auth: 2026-05-11"), html.index("auth: 2026-06-02"))
             self.assertLess(html.index("auth: 2026-06-02"), html.index("<h3>Files</h3>"))
             self.assertIsNone(re.search(r'\bsrc="(?!data:|https://)', html))
             self.assertNotIn("<!--", html)
             self.assertNotIn("Billing", html)

         def test_all_capabilities_sorted_with_toc_and_out(self):
             result = run_specs(self.root, "export", "--all", "--format", "json")
             self.assertEqual(0, result.returncode, result.stderr)
             payload = json.loads(result.stdout)
             self.assertEqual({"path": "srs.html", "capabilities": ["auth", "billing"], "missing": []}, payload)
             html = self.read("srs.html")
             self.assertIn(f"<title>{self.root.name}</title>", html)
             self.assertLess(html.index('id="auth"'), html.index('id="billing"'))
             self.assertIn('<li><a href="#billing">Billing</a></li>', html)
             write(self.root, "srs.html", "old")
             self.assertEqual(0, run_specs(self.root, "export", "--all").returncode)
             self.assertNotEqual("old", self.read("srs.html"))
             self.assertEqual(0, run_specs(self.root, "export", "billing", "--out", "docs/srs/v1.html").returncode)
             self.assertIn("<h1>Billing</h1>", self.read("docs/srs/v1.html"))

         def test_missing_image_writes_the_file_and_exits_1(self):
             (self.root / "docs/specs/auth/assets/2026-05-11/mockup/login.png").unlink()
             result = run_specs(self.root, "export", "auth")
             self.assertEqual(1, result.returncode)
             self.assertIn("missing image: docs/specs/auth/assets/2026-05-11/description.md: mockup/login.png", result.stdout)
             self.assertIn('<span class="missing-image">Login screen</span>', self.read("srs-auth.html"))

         def test_usage_errors_exit_2_and_write_nothing(self):
             for args in (("nope",), (), ("auth", "--all"), ("auth", "--out", "../outside.html")):
                 with self.subTest(args=args):
                     result = run_specs(self.root, "export", *args)
                     self.assertEqual(2, result.returncode)
                     self.assertIn("specs error:", result.stderr)
             self.assertFalse(list(self.root.glob("*.html")))
             with tempfile.TemporaryDirectory() as directory:
                 legacy = make_repo(Path(directory), layout="legacy")
                 self.assertEqual(2, run_specs(legacy, "export", "--all").returncode)
                 empty = make_repo(Path(directory) / "empty")
                 self.assertIn("no capability", run_specs(empty, "export", "--all").stderr)

         def test_template_overrides_embed_logo_and_reorder_sections(self):
             write_bytes(self.root, "docs/brand/logo.png", PNG)
             document = specs.template_text(self.root, "srs.html").replace(
                 '<section class="cover">', '<section class="cover">\n  <img class="logo" src="docs/brand/logo.png" alt="Acme">')
             write(self.root, ".agent-workflow/templates/srs.html", document)
             write(self.root, ".agent-workflow/templates/srs-capability.html",
                   '<section class="chapter" id="{{cap}}"><h1>{{capability}}</h1>{{requirements}}{{purpose}}</section>')
             result = export(self.root, self.cfg, "auth", None, today=date(2026, 11, 6))
             self.assertEqual([], result["missing"])
             html = self.read("srs-auth.html")
             self.assertIn(f'<img class="logo" src="{PNG_URI}" alt="Acme">', html)
             self.assertIn('<p class="date">2026-11-06</p>', html)
             self.assertLess(html.index('id="REQ-AUTH-001"'), html.index("Sign-in."))
             self.assertNotIn("auth: 2026-05-11", html)
             write(self.root, ".agent-workflow/templates/srs.html", document.replace("docs/brand/logo.png", "docs/brand/gone.png"))
             self.assertEqual(["srs.html: docs/brand/gone.png"], export(self.root, self.cfg, "auth", None)["missing"])


     class TestTemplates(unittest.TestCase):
         def test_srs_templates_print_their_placeholders(self):
             with tempfile.TemporaryDirectory() as directory:
                 root = make_repo(Path(directory), layout="legacy")
                 document = run_specs(root, "template", "srs.html").stdout
                 chapter = run_specs(root, "template", "srs-capability.html").stdout
             for needle in ("{{title}}", "{{date}}", "{{toc}}", "{{chapters}}", "@media print"):
                 with self.subTest(needle=needle):
                     self.assertIn(needle, document)
             self.assertRegex(document, r'mermaid@\d+\.\d+\.\d+/dist/mermaid\.min\.js"\s+integrity="sha384-[A-Za-z0-9+/=]{64}"')
             order = [chapter.index("{{" + key + "}}") for key in ("cap", "capability", "purpose", "diagrams",
                                                                      "requirements", "assets")]
             self.assertEqual(sorted(order), order)


     if __name__ == "__main__":
         unittest.main()
     ````
  2. Run `python3 -m pytest tests/workflow_core/test_specs_export.py -q`: expect a collection error, `ModuleNotFoundError: No module named 'workflow_core.specs_export'`.
  3. Create `plugins/gin-workflow/src/templates/srs-capability.html`:
     ````html
     <!-- One chapter of `gin-workflow specs export`, written once per capability. Override it in
          .agent-workflow/templates/srs-capability.html. Placeholders, each in double braces: cap (the capability
          folder, used as the anchor), capability (the title of its spec.md), purpose, diagrams, requirements, assets.
          Reorder the sections below, or delete a placeholder and its heading to drop a section.
          Comments are removed before the chapter is written. -->
     <section class="chapter" id="{{cap}}">
       <h1>{{capability}}</h1>
       <h2>Purpose</h2>
       {{purpose}}
       <h2>Diagrams</h2>
       {{diagrams}}
       <h2>Requirements</h2>
       {{requirements}}
       <h2>Assets</h2>
       {{assets}}
     </section>
     ````
  4. Create `plugins/gin-workflow/src/templates/srs.html` (the `integrity` value is the sha384 of `https://cdn.jsdelivr.net/npm/mermaid@11.4.1/dist/mermaid.min.js`, computed with `curl -sfL <url> | openssl dgst -sha384 -binary | openssl base64 -A`):
     ````html
     <!doctype html>
     <html lang="en">
     <head>
     <meta charset="utf-8">
     <meta name="viewport" content="width=device-width, initial-scale=1">
     <title>{{title}}</title>
     <!-- The document of `gin-workflow specs export`. Override it in .agent-workflow/templates/srs.html.
          Placeholders, each in double braces: title, date, toc, chapters (each chapter comes from srs-capability.html).
          Put your logo, the customer, and the product brief on the cover, for example:
            <img class="logo" src="docs/brand/logo.png" alt="Acme">
            <p class="customer">Prepared for Example Corp</p>
            <p class="brief">One paragraph on what the product does and for whom.</p>
          A relative src is read from the repository root and embedded in the file.
          Comments are removed before the document is written. -->
     <style>
       :root { --ink: #1f2328; --muted: #59636e; --line: #d1d9e0; --accent: #0b5cad; --code: #f6f8fa; }
       body { font: 15px/1.55 system-ui, -apple-system, "Segoe UI", Roboto, sans-serif; color: var(--ink);
              background: #fff; max-width: 60rem; margin: 0 auto; padding: 2rem 1rem; }
       h1, h2, h3, h4, h5, h6 { line-height: 1.25; }
       .cover { min-height: 60vh; display: flex; flex-direction: column; justify-content: center;
                border-bottom: 2px solid var(--accent); margin-bottom: 2rem; }
       .cover .subtitle { font-size: 1.25rem; color: var(--muted); }
       .logo { max-height: 4rem; align-self: flex-start; }
       .toc ul { list-style: none; padding-left: 1rem; }
       .chapter { border-top: 1px solid var(--line); margin-top: 2.5rem; padding-top: 1rem; }
       .requirement { border-left: 3px solid var(--accent); padding-left: 1rem; margin: 1.25rem 0; }
       pre { background: var(--code); padding: .75rem; overflow-x: auto; }
       pre.mermaid[data-processed] { background: none; text-align: center; }
       table { border-collapse: collapse; margin: 1rem 0; }
       th, td { border: 1px solid var(--line); padding: .3rem .6rem; text-align: left; vertical-align: top; }
       img { max-width: 100%; }
       figure { margin: 1rem 0; }
       figcaption { color: var(--muted); font-size: .85rem; }
       .missing-image { color: #b42318; font-style: italic; }
       @media print {
         body { max-width: none; padding: 0; font-size: 11pt; }
         .cover { min-height: 90vh; break-after: page; border-bottom: none; }
         .toc { break-after: page; }
         .chapter { break-before: page; border-top: none; margin-top: 0; }
         .requirement, figure, pre, table { break-inside: avoid; }
         a { color: inherit; text-decoration: none; }
       }
     </style>
     </head>
     <body>
     <section class="cover">
       <h1>{{title}}</h1>
       <p class="subtitle">Software Requirements Specification</p>
       <p class="date">{{date}}</p>
     </section>
     <nav class="toc">
       <h2>Contents</h2>
       {{toc}}
     </nav>
     {{chapters}}
     <script src="https://cdn.jsdelivr.net/npm/mermaid@11.4.1/dist/mermaid.min.js"
             integrity="sha384-rbtjAdnIQE/aQJGEgXrVUlMibdfTSa4PQju4HDhN3sR2PmaKFzhEafuePsl9H/9I"
             crossorigin="anonymous"></script>
     <script>if (window.mermaid) { window.mermaid.initialize({ startOnLoad: true }); }</script>
     </body>
     </html>
     ````
  5. Create `plugins/gin-workflow/src/scripts/workflow_core/specs_export.py`:
     ````python
     """`gin-workflow specs export`: living specs to one self-contained SRS HTML file."""

     from __future__ import annotations

     import base64
     from dataclasses import dataclass, field
     from datetime import date
     from html import escape
     from pathlib import Path
     import re
     from typing import Any, Callable, Mapping

     from . import specs

     MEDIA_TYPES = {".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".gif": "image/gif",
                    ".svg": "image/svg+xml", ".webp": "image/webp"}
     _COMMENT = re.compile(r"<!--.*?-->", re.DOTALL)
     _PLACEHOLDER = re.compile(r"\{\{(\w+)\}\}")
     _TEMPLATE_SRC = re.compile(r'\bsrc="([^"]+)"')
     _REMOTE = ("http://", "https://")
     _INLINE = re.compile(r"`([^`]+)`|!\[([^\]]*)\]\(([^)\s]+)\)|\[([^\]]+)\]\(([^)\s]+)\)"
                          r"|\*\*(.+?)\*\*|\*(.+?)\*|(?<!\w)_(.+?)_(?!\w)")
     _HEADING = re.compile(r"^(#{1,6})\s+(.*?)\s*#*\s*$")
     _LIST_ITEM = re.compile(r"^(\s*)([-*+]|\d+[.)])\s+(.*)$")
     _TABLE_RULE = re.compile(r"^\s*\|?\s*:?-{3,}:?\s*(\|\s*:?-{3,}:?\s*)*\|?\s*$")


     @dataclass
     class Embed:
         """Turns local image paths into data: URIs and records the ones not found."""

         missing: list[str] = field(default_factory=list)
         shown: set[Path] = field(default_factory=set)

         def src(self, target: str, base: Path, origin: str) -> str | None:
             if target.startswith(_REMOTE):
                 return target
             path = (base / target).resolve()
             if not path.is_file():
                 self.missing.append(f"{origin}: {target}")
                 return None
             self.shown.add(path)
             return data_uri(path)


     def data_uri(path: Path) -> str:
         media = MEDIA_TYPES.get(path.suffix.lower(), "application/octet-stream")
         return f"data:{media};base64,{base64.b64encode(path.read_bytes()).decode('ascii')}"


     def _inline(text: str, image: Callable[[str, str], str]) -> str:
         out, last = [], 0
         for found in _INLINE.finditer(text):
             out.append(escape(text[last:found.start()]))
             code, alt, target, label, href, strong, em, em2 = found.groups()
             if code is not None:
                 out.append(f"<code>{escape(code)}</code>")
             elif target is not None:
                 out.append(image(alt, target))
             elif href is not None:
                 out.append(f'<a href="{escape(href)}">{_inline(label, image)}</a>')
             elif strong is not None:
                 out.append(f"<strong>{_inline(strong, image)}</strong>")
             else:
                 out.append(f"<em>{_inline(em if em is not None else em2, image)}</em>")
             last = found.end()
         out.append(escape(text[last:]))
         return "".join(out)


     def _list(items: list[tuple[int, bool, str]], inline: Callable[[str], str]) -> str:
         tag = "ol" if items[0][1] else "ul"
         out, i = [f"<{tag}>"], 0
         while i < len(items):
             indent, _, text = items[i]
             j = i + 1
             while j < len(items) and items[j][0] > indent:
                 j += 1
             nested = _list(items[i + 1:j], inline) if j > i + 1 else ""
             out.append(f"<li>{inline(text)}{nested}</li>")
             i = j
         out.append(f"</{tag}>")
         return "".join(out)


     def _cells(line: str) -> list[str]:
         return [cell.strip() for cell in line.strip().strip("|").split("|")]


     def markdown_html(text: str, base: Path, origin: str, embed: Embed, top: int = 3) -> str:
         """Convert the Markdown subset the specs use; every piece of text is escaped."""
         lines = _COMMENT.sub("", text).splitlines()
         fenced = False
         levels = []
         for line in lines:
             if line.startswith("```"):
                 fenced = not fenced
             elif not fenced and _HEADING.match(line):
                 levels.append(len(_HEADING.match(line).group(1)))
         shift = top - min(levels) if levels else 0

         def image(alt: str, target: str) -> str:
             src = embed.src(target, base, origin)
             if src is None:
                 return f'<span class="missing-image">{escape(alt or target)}</span>'
             return f'<img src="{escape(src)}" alt="{escape(alt)}">'

         def inline(value: str) -> str:
             return _inline(value, image)

         out: list[str] = []
         i = 0
         while i < len(lines):
             line = lines[i]
             if not line.strip():
                 i += 1
             elif line.startswith("```"):
                 language = line[3:].strip()
                 body: list[str] = []
                 i += 1
                 while i < len(lines) and not lines[i].startswith("```"):
                     body.append(lines[i])
                     i += 1
                 i += 1
                 source = escape("\n".join(body))
                 out.append(f'<pre class="mermaid">{source}</pre>' if language == "mermaid"
                            else f"<pre><code>{source}</code></pre>")
             elif _HEADING.match(line):
                 marks, title = _HEADING.match(line).groups()
                 level = min(6, max(1, len(marks) + shift))
                 out.append(f"<h{level}>{inline(title)}</h{level}>")
                 i += 1
             elif line.lstrip().startswith("|") and i + 1 < len(lines) and _TABLE_RULE.match(lines[i + 1]):
                 head = "".join(f"<th>{inline(cell)}</th>" for cell in _cells(line))
                 rows = []
                 i += 2
                 while i < len(lines) and lines[i].lstrip().startswith("|"):
                     rows.append("<tr>" + "".join(f"<td>{inline(cell)}</td>" for cell in _cells(lines[i])) + "</tr>")
                     i += 1
                 out.append(f"<table><thead><tr>{head}</tr></thead><tbody>{''.join(rows)}</tbody></table>")
             elif _LIST_ITEM.match(line):
                 items = []
                 while i < len(lines) and _LIST_ITEM.match(lines[i]):
                     indent, marker, value = _LIST_ITEM.match(lines[i]).groups()
                     items.append((len(indent), marker[0].isdigit(), value))
                     i += 1
                 out.append(_list(items, inline))
             else:
                 paragraph = []
                 while i < len(lines) and lines[i].strip() and not (
                         lines[i].startswith("```") or _HEADING.match(lines[i]) or _LIST_ITEM.match(lines[i])
                         or lines[i].lstrip().startswith("|")):
                     paragraph.append(lines[i].strip())
                     i += 1
                 out.append(f"<p>{inline(chr(10).join(paragraph))}</p>")
         return "\n".join(out)


     def _title(text: str, fallback: str) -> str:
         found = re.search(r"^# (.+)$", text, re.MULTILINE)
         return found.group(1).strip() if found else fallback


     def _section(text: str, heading: str) -> str:
         found = re.search(rf"^## {re.escape(heading)}[ \t]*\n(.*?)(?=^## |\Z)", text, re.MULTILINE | re.DOTALL)
         return found.group(1).strip() if found else ""


     def _shown(path: Path, root: Path) -> str:
         return path.relative_to(root).as_posix()


     def _files(title: str | None, description: Path | None, files: list[Path], folder: Path, root: Path,
                embed: Embed) -> str:
         out = []
         embed.shown = set()
         if description is not None:
             out.append(markdown_html(description.read_text(encoding="utf-8"), description.parent,
                                      _shown(description, root), embed))
         if title is not None:
             out.append(f"<h3>{escape(title)}</h3>")
         others = []
         for path in files:
             if path == description or path.resolve() in embed.shown:
                 continue
             name = escape(path.relative_to(folder).as_posix())
             if path.suffix.lower() in MEDIA_TYPES:
                 out.append(f'<figure><img src="{data_uri(path)}" alt="{name}"><figcaption>{name}</figcaption></figure>')
             else:
                 others.append(f"<li><code>{name}</code></li>")
         if others:
             out.append(f'<ul class="asset-files">{"".join(others)}</ul>')
         return "\n".join(out)


     def _assets(folder: Path, root: Path, embed: Embed) -> str:
         if not folder.is_dir():
             return ""
         groups = []
         for dated in sorted(p for p in folder.iterdir() if p.is_dir() and specs._ISO_DATE.match(p.name)):
             description = dated / "description.md"
             found = description if description.is_file() else None
             files = sorted(p for p in dated.rglob("*") if p.is_file())
             groups.append(_files(None if found else dated.name, found, files, dated, root, embed))
         flat = sorted(p for p in folder.iterdir() if p.is_file())
         if flat:
             groups.append(_files("Files", None, flat, folder, root, embed))
         return "\n".join(f'<section class="asset-group">{group}</section>' for group in groups)


     def _chapter(cap: str, spec: Path, root: Path, embed: Embed, template: str) -> tuple[str, str]:
         text = spec.read_text(encoding="utf-8")
         folder = spec.parent
         title = _title(text, cap)
         purpose = markdown_html(_section(text, "Purpose"), folder, _shown(spec, root), embed)
         diagrams = "\n".join(
             f'<section class="diagram" id="{escape(cap)}-{escape(path.stem)}">'
             f'{markdown_html(path.read_text(encoding="utf-8"), path.parent, _shown(path, root), embed)}</section>'
             for path in sorted((folder / "diagrams").glob("*.md")))
         blocks = specs.parse_blocks(text)[0]
         requirements = "\n".join(
             f'<section class="requirement" id="{escape(block.id)}">'
             f'{markdown_html(block.text, folder, _shown(spec, root), embed)}</section>' for block in blocks)
         chapter = fill(template, {"cap": escape(cap), "capability": escape(title), "purpose": purpose,
                                   "diagrams": diagrams, "requirements": requirements,
                                   "assets": _assets(folder / "assets", root, embed)})
         links = "".join(f'<li><a href="#{escape(b.id)}">{escape(b.id)}: {escape(b.title)}</a></li>' for b in blocks)
         toc = f'<li><a href="#{escape(cap)}">{escape(title)}</a>' + (f"<ul>{links}</ul>" if links else "") + "</li>"
         return chapter, toc


     def fill(template: str, values: Mapping[str, str]) -> str:
         """One pass: text inside a value is never substituted again."""
         return _PLACEHOLDER.sub(lambda found: values.get(found.group(1), found.group(0)), template)


     def _template(root: Path, name: str, embed: Embed) -> str:
         def local(found: re.Match[str]) -> str:
             target = found.group(1)
             if target.startswith((*_REMOTE, "data:", "#")) or "{{" in target:
                 return found.group(0)
             src = embed.src(target, root, name)
             return f'src="{escape(src)}"' if src else found.group(0)

         return _TEMPLATE_SRC.sub(local, _COMMENT.sub("", specs.template_text(root, name)))


     def export(root: Path, cfg: Mapping[str, Any], cap: str | None, out: str | None,
                today: date | None = None) -> dict[str, Any]:
         living = specs.living_files(root, cfg)
         if cap is None:
             caps = sorted(living)
             if not caps:
                 raise specs.SpecsError(f"no capability with a spec.md under {cfg['specs']}")
         elif cap in living:
             caps = [cap]
         else:
             raise specs.SpecsError(f"unknown capability: {cap} (no {cfg['specs']}/{cap}/spec.md)")
         path = (root / (out or (f"srs-{cap}.html" if cap else "srs.html"))).resolve()
         if not path.is_relative_to(root):
             raise specs.SpecsError(f"--out must stay inside the repository: {out}")
         embed = Embed()
         chapter_template = _template(root, "srs-capability.html", embed)
         document = _template(root, "srs.html", embed)
         chapters, toc = [], []
         for name in caps:
             chapter, entry = _chapter(name, living[name], root, embed, chapter_template)
             chapters.append(chapter)
             toc.append(entry)
         title = _title(living[cap].read_text(encoding="utf-8"), cap) if cap else root.name
         html = fill(document, {"title": escape(title), "date": (today or date.today()).isoformat(),
                                "toc": f'<ul>{"".join(toc)}</ul>', "chapters": "\n".join(chapters)})
         path.parent.mkdir(parents=True, exist_ok=True)
         path.write_text(html, encoding="utf-8")
         return {"path": _shown(path, root), "capabilities": caps, "missing": embed.missing}
     ````
  6. In `plugins/gin-workflow/src/scripts/workflow_core/specs_cli.py`, after `sub.add_parser("reqs", parents=[common]).add_argument("--change")`, add:
     ```python
     item = sub.add_parser("export", parents=[common])
     item.add_argument("cap", nargs="?")
     item.add_argument("--all", action="store_true")
     item.add_argument("--out")
     ```
     and in `_run`, after the `if args.command == "hash":` branch and before `change = specs.find_change(root, cfg, args.change)`, add:
     ```python
     if args.command == "export":
         from .specs_export import export

         if bool(args.cap) == args.all:
             raise specs.SpecsError("give one capability or --all")
         result = export(root, cfg, None if args.all else args.cap, args.out)
         _emit(result, args.format, "\n".join([result["path"], *(f"missing image: {m}" for m in result["missing"])]))
         return 1 if result["missing"] else 0
     ```
  7. Run `python3 -m pytest tests/workflow_core/test_specs_export.py -q`: expect `11 passed`. Then `python3 -m pytest tests/workflow_core -q -n auto -k "specs or packag or template or docs"`: expect no failure.
  8. Docs. In `docs/reference/cli.md`, after the `reqs [--change C]` row of the `gin-workflow specs` table, add:
     ```markdown
     | `export (CAP \| --all) [--out FILE]` | Write the living specs of one capability, or of every capability, into one printable SRS HTML file (default `srs-CAP.html` or `srs.html` at the repository root, overwritten), from the templates `srs.html` and `srs-capability.html`; images are embedded, diagrams load Mermaid from jsDelivr; a local image not found is listed and exits 1 |
     ```
     and change the exit code line to `Exit codes: 0 ok; 1 findings (lint errors, untraced requirements, archive conflicts, refused migration, images an export could not find); 2 usage or configuration error.`

     In `docs/guides/customizing-templates.md`, after the `- Specs, stories, and roadmap: ...` bullet of "Available templates", add:
     ```markdown
     - SRS export (`specs export`): `srs.html`, `srs-capability.html`
     ```
     after the `Activity and state diagrams` table row, add:
     ```markdown
     | SRS document and chapter (SDD layout) | `specs export` | `.agent-workflow/templates/srs.html`, `srs-capability.html` |
     ```
     and after the paragraph that starts "The `{{...}}` placeholders in `spec.md`", add:
     ````markdown
     ### SRS export templates

     `gin-workflow specs export` fills `srs.html` once and `srs-capability.html` once per capability. `srs.html` takes `{{title}}`, `{{date}}`, `{{toc}}`, and `{{chapters}}`. `srs-capability.html` takes `{{cap}}` (the chapter's anchor), `{{capability}}`, `{{purpose}}`, `{{diagrams}}`, `{{requirements}}`, and `{{assets}}`: reorder them to reorder a chapter, or delete one and its heading to drop that section. Each placeholder is filled once, so `{{...}}` written in a spec stays as text, and comments are removed from both templates.

     Put the logo, the customer, and the product brief on the cover of `srs.html`:

     ```html
     <section class="cover">
       <img class="logo" src="docs/brand/logo.png" alt="Acme">
       <h1>{{title}}</h1>
       <p class="customer">Prepared for Example Corp</p>
       <p class="brief">One paragraph on what the product does and for whom.</p>
       <p class="date">{{date}}</p>
     </section>
     ```

     A relative `src` in either template is read from the repository root and embedded in the exported file; when the file is missing, `specs export` exits 1 and names it.
     ````
     In `docs/guides/customizing-templates.vi.md`, the same three edits. After the `- Spec, story, và roadmap: ...` bullet add:
     ```markdown
     - Xuất SRS (`specs export`): `srs.html`, `srs-capability.html`
     ```
     after the `Sơ đồ activity và state` row add:
     ```markdown
     | Tài liệu SRS và chương (layout SDD) | `specs export` | `.agent-workflow/templates/srs.html`, `srs-capability.html` |
     ```
     and after the paragraph that starts "Các placeholder `{{...}}` trong `spec.md`", add:
     ````markdown
     ### Template xuất SRS { #srs-export-templates }

     `gin-workflow specs export` điền `srs.html` một lần và `srs-capability.html` một lần cho mỗi capability. `srs.html` nhận `{{title}}`, `{{date}}`, `{{toc}}`, và `{{chapters}}`. `srs-capability.html` nhận `{{cap}}` (anchor của chương), `{{capability}}`, `{{purpose}}`, `{{diagrams}}`, `{{requirements}}`, và `{{assets}}`: đổi thứ tự chúng để đổi thứ tự trong chương, hoặc xóa một placeholder cùng heading của nó để bỏ phần đó. Mỗi placeholder được điền một lần, nên `{{...}}` viết trong spec giữ nguyên là văn bản, và comment được bỏ khỏi cả hai template.

     Đặt logo, tên khách hàng, và phần giới thiệu sản phẩm trên trang bìa của `srs.html`:

     ```html
     <section class="cover">
       <img class="logo" src="docs/brand/logo.png" alt="Acme">
       <h1>{{title}}</h1>
       <p class="customer">Prepared for Example Corp</p>
       <p class="brief">One paragraph on what the product does and for whom.</p>
       <p class="date">{{date}}</p>
     </section>
     ```

     Một `src` tương đối trong template được đọc từ gốc repository và nhúng vào file xuất ra; khi file không tồn tại, `specs export` thoát với mã 1 và nêu tên file đó.
     ````
  9. Run `gin-workflow docs check docs/reference/cli.md docs/guides/customizing-templates.md docs/guides/customizing-templates.vi.md`: expect no finding (exit 0).
  10. Commit: `git add` the eight files, `git commit -m "feat(specs): export living specs to a printable SRS HTML (gin-workflow-bel0)"` with the trailer.

### Track 2: SRS export in the SDD guide and gin-sdd
- **Dependencies**: Track 1
- **Files**:
  - Modify `docs/guides/sdd.md:90` (new `## Exporting an SRS` before `## How the stages change`)
  - Modify `docs/guides/sdd.vi.md:90` (new `## Xuất SRS { #exporting-an-srs }`, same place)
  - Modify `plugins/gin-workflow/src/skills/gin-sdd/SKILL.md:8` (one sentence)
  - Test `tests/workflow_core/test_skill_routing.py:80` (new test after `test_sdd_discuss_confirms_capabilities_before_ids`)
- **Provider role**: `docs`
- **Model:** `sonnet`
- **Effort:** `low`
- **Why:** documentation and one skill sentence whose exact text is given below; the facts come from Track 1's code and tests.
- **Interfaces**:
  - Consumes the CLI `gin-workflow specs export (CAP | --all) [--out FILE]`, its default paths, exit codes, chapter content, and the anchor `customizing-templates.md#srs-export-templates` written by Track 1.
  - Produces the `gin-sdd` sentence naming `` `specs export <cap>` ``.
- **Acceptance criteria**: `python3 -m pytest tests/workflow_core/test_skill_routing.py tests/workflow_core/test_token_budget.py -q` passes; `gin-workflow docs check docs/guides/sdd.md docs/guides/sdd.vi.md` prints no finding.
- **Estimated complexity**: low
- **Steps**:
  1. Failing test. In `tests/workflow_core/test_skill_routing.py`, after `test_sdd_discuss_confirms_capabilities_before_ids`, add:
     ```python
     def test_sdd_names_the_srs_export(self):
         text = (SRC / "skills/gin-sdd/SKILL.md").read_text(encoding="utf-8")
         self.assertIn("`specs export <cap>`", text)
         self.assertIn("`--all`", text)
         self.assertLessEqual(len(text), 6_000)
     ```
  2. Run `python3 -m pytest tests/workflow_core/test_skill_routing.py -q -k srs_export`: expect 1 failure (`` `specs export <cap>` `` not found).
  3. In `plugins/gin-workflow/src/skills/gin-sdd/SKILL.md`, at the end of the paragraph that starts `Applies only when` (line 8), append the sentence: `` `specs export <cap>` (or `--all`) writes the living specs into one printable SRS HTML file for the customer. ``
  4. Run `python3 -m pytest tests/workflow_core/test_skill_routing.py tests/workflow_core/test_token_budget.py -q`: expect all passed.
  5. In `docs/guides/sdd.md`, before `## How the stages change`, add:
     ````markdown
     ## Exporting an SRS

     `gin-workflow specs export <capability>` writes the capability's living spec into one HTML file, `srs-<capability>.html` at the repository root. `specs export --all` writes every capability into `srs.html`, one chapter each, sorted by name. `--out <file>` writes elsewhere in the repository. The file is generated, so each run overwrites it.

     Each chapter holds the capability's `## Purpose`, its diagrams, its requirement blocks with their scenarios, and its assets: each dated folder, oldest first (its `description.md`, then the images and file names it does not show), then the flat files. Images are embedded, so the file can be sent alone. Open it in a browser and print it to PDF; each chapter starts on a new page.

     The file loads Mermaid from jsDelivr at a pinned version to draw the diagrams; without network access it shows their source instead. The export does not lint, so run `specs lint` first. A local image it cannot find shows as its alt text, and the command exits 1 naming it. The cover, logo, customer, and section order come from the templates `srs.html` and `srs-capability.html`; see [SRS export templates](customizing-templates.md#srs-export-templates).
     ````
     In `docs/guides/sdd.vi.md`, before `## Các stage thay đổi thế nào { #how-the-stages-change }`, add:
     ````markdown
     ## Xuất SRS { #exporting-an-srs }

     `gin-workflow specs export <capability>` ghi living spec của capability vào một file HTML, `srs-<capability>.html` ở gốc repository. `specs export --all` ghi mọi capability vào `srs.html`, mỗi capability một chương, sắp theo tên. `--out <file>` ghi ra chỗ khác trong repository. File là file sinh ra, nên mỗi lần chạy sẽ ghi đè nó.

     Mỗi chương gồm `## Purpose` của capability, các sơ đồ, các requirement block cùng scenario, và các asset: từng thư mục theo ngày, cũ nhất trước (`description.md` của nó, rồi các ảnh và tên file nó chưa hiển thị), rồi các file phẳng. Ảnh được nhúng vào file, nên có thể gửi riêng file đó. Mở file trong trình duyệt và in ra PDF; mỗi chương bắt đầu ở một trang mới.

     File tải Mermaid từ jsDelivr ở một phiên bản cố định để vẽ sơ đồ; khi không có mạng, nó hiển thị mã nguồn của sơ đồ. Lệnh xuất không lint, nên hãy chạy `specs lint` trước. Một ảnh local không tìm thấy hiển thị bằng alt text, và lệnh thoát với mã 1 kèm tên ảnh đó. Trang bìa, logo, khách hàng, và thứ tự các phần lấy từ template `srs.html` và `srs-capability.html`; xem [Template xuất SRS](customizing-templates.md#srs-export-templates).
     ````
  6. Run `gin-workflow docs check docs/guides/sdd.md docs/guides/sdd.vi.md`: expect no finding.
  7. Commit: `git add` the four files, `git commit -m "docs(sdd): SRS export in gin-sdd and the guide (gin-workflow-bel0)"` with the trailer.

## Integration
- **Branch**: `feat/srs-export`
- **Merge strategy**: sequential

## Validation
- [ ] `python3 -m pytest tests/workflow_core/test_specs_export.py -q`: 11 passed
- [ ] Full suite `python3 -m pytest -n auto` through the pre-push hook
- [ ] `gin-workflow docs check` on the five changed pages: no finding
- [ ] Manual: `gin-workflow specs export --all` in a repository with SDD living specs, open the file in a browser, print preview shows one chapter per page and drawn diagrams

## Notes
- `Model:` and `Effort:` are chosen from the main harness catalog using the route rubric; the user may override them before plan approval.
- The parent bead `gin-workflow-bel0` stays open until the human-confirmed merge; each track closes after its tests and review pass.
- Spec R3 says one list nesting level; the converter nests any depth, which covers it.
