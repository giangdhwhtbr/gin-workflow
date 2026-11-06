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
        embed = Embed(Path("/nonexistent"))
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
            embed = Embed(base.resolve())
            html = markdown_html("![A](img/a.png) ![B](img/b.png) ![C](https://x.test/c.png)", base, "doc.md", embed)
        self.assertIn(f'<img src="{PNG_URI}" alt="A">', html)
        self.assertIn('<span class="missing-image">B</span>', html)
        self.assertIn('<img src="https://x.test/c.png" alt="C">', html)
        self.assertEqual(["doc.md: img/b.png"], embed.missing)

    def test_pipe_line_without_rule_row_stays_a_paragraph(self):
        html, _ = self.convert("| a | b |\nplain")
        self.assertRegex(html, r"(?s)<p>.*a \| b.*plain.*</p>")

    def test_unsafe_link_targets_render_only_the_label(self):
        html, _ = self.convert("[a](javascript:alert(1)) [b](data:text/html,x) [c](https://x.test) "
                               "[d](mailto:a@x.test) [e](#top) [f](docs/x.md?q=a:b)")
        self.assertNotIn("javascript", html)
        self.assertNotIn("data:", html)
        for needle in ('<a href="https://x.test">c</a>', '<a href="mailto:a@x.test">d</a>',
                       '<a href="#top">e</a>', '<a href="docs/x.md?q=a:b">f</a>'):
            self.assertIn(needle, html)
        self.assertTrue(html.startswith("<p>a"))

    def test_images_outside_the_root_or_not_images_are_missing(self):
        with tempfile.TemporaryDirectory() as directory:
            outer = Path(directory).resolve()
            root = outer / "repo"
            write_bytes(root, "docs/notes.txt", b"inside-secret")
            write_bytes(outer, "secret.txt", b"outside-secret")
            write_bytes(outer, "outside.png", PNG)
            embed = Embed(root)
            html = markdown_html(f"![a](../../secret.txt) ![b]({outer / 'outside.png'}) ![c](notes.txt)",
                                 root / "docs", "doc.md", embed)
        self.assertEqual(3, len(embed.missing))
        self.assertEqual(3, html.count('class="missing-image"'))
        for secret in (b"outside-secret", b"inside-secret", PNG):
            self.assertNotIn(base64.b64encode(secret).decode("ascii"), html)

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

    def test_out_that_is_a_directory_exits_2(self):
        (self.root / "outdir").mkdir()
        result = run_specs(self.root, "export", "auth", "--out", "outdir")
        self.assertEqual(2, result.returncode)
        self.assertIn("cannot write", result.stderr)
        self.assertNotIn("Traceback", result.stderr)

    def test_asset_symlink_to_an_outside_image_is_listed_not_embedded(self):
        with tempfile.TemporaryDirectory() as directory:
            outside = write_bytes(Path(directory), "outside.png", b"\x89PNG\r\nlinked-outside")
            link = self.root / "docs/specs/auth/assets/linked.png"
            try:
                link.symlink_to(outside)
            except (OSError, NotImplementedError):
                self.skipTest("symlinks unavailable")
            export(self.root, self.cfg, "auth", None)
        html = self.read("srs-auth.html")
        self.assertIn("<code>linked.png</code>", html)
        self.assertNotIn(base64.b64encode(b"\x89PNG\r\nlinked-outside").decode("ascii"), html)

    def test_template_single_quoted_src_is_embedded(self):
        write_bytes(self.root, "docs/brand/logo.png", PNG)
        document = specs.template_text(self.root, "srs.html").replace(
            '<section class="cover">', '<section class="cover"><img src=\'docs/brand/logo.png\' alt="A">')
        write(self.root, ".agent-workflow/templates/srs.html", document)
        self.assertEqual([], export(self.root, self.cfg, "auth", None)["missing"])
        self.assertIn(PNG_URI, self.read("srs-auth.html"))

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
