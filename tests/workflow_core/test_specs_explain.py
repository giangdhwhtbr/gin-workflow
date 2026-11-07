"""`gin specs explain`: one interactive HTML page for a capability or a change (gin-workflow-explain)."""

from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent))

from specs_fixtures import ADDED_BLOCK, AUTH_SPEC, LAUNCHER, delta, make_change, make_repo, write, write_activity  # noqa: E402

PNG = b"\x89PNG\r\n\x1a\nfake-image"
OUT = ".agent-workflow/runtime/explain"
MOCKUP = """<!doctype html>
<html><body>
<section class="screen" id="sign-in" data-title="Sign in"><button>Go</button></section>
<section class="screen" id="locked" data-title="Locked"></section>
<script>function route(){}</script>
</body></html>
"""
DESCRIPTION = "# auth: 2026-05-11\n\nKind: new\nConfirmed: 2026-05-12\n\n## Summary\n\nThe sign-in screens.\n"
SOURCE = "Source: `assets/2026-05-11/mockup/index.html#locked`\n"
SOURCED_BLOCK = ADDED_BLOCK.replace("after 5 failed logins.\n", "after 5 failed logins.\n" + SOURCE)
MODIFIED_BLOCK = ("### REQ-AUTH-002: Reject wrong password\n<!-- base: abc -->\n"
                  "The system SHALL reject a wrong password with a message.\n")
REMOVED_BLOCK = "### REQ-AUTH-001: Sign in with password\nReason: replaced by single sign-on.\n"
ADMIN_SECTION = "\n## Admin\n\n### REQ-AUTH-004: Unlock an account\nThe system SHALL let an admin unlock an account.\n"


def proposal(req: str, title: str = "Lockout") -> str:
    return (f"# {title}\n\nEpic: ep-1\n\n## Why\n\nStop password guessing.\n\n"
            "## What Changes\n\nLock after five failures.\n\n## User Stories\n\n"
            f"### US-1: Lock a guessed account\nAs a user, I want my account locked, so that nobody guesses it.\n"
            f"REQ: {req}\n\nAcceptance criteria:\n- the account locks\n")


def run_specs(root: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run([sys.executable, str(LAUNCHER), "specs", *args, "--repository", str(root)],
                          text=True, capture_output=True, check=False)


def write_bytes(root: Path, relative: str, data: bytes) -> Path:
    path = Path(root) / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    return path


def auth_repo(base: str, spec: str = AUTH_SPEC) -> Path:
    root = make_repo(Path(base) / "repo")
    write(root, "docs/specs/auth/spec.md", spec)
    write_activity(root)
    return root


def page(root: Path, name: str) -> str:
    return (root / OUT / f"{name}.html").read_text(encoding="utf-8")


class TestCapability(unittest.TestCase):
    def test_tabs_requirements_grouped_by_section_and_diagrams(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = auth_repo(tmp, AUTH_SPEC + ADMIN_SECTION)
            result = run_specs(root, "explain", "auth")
            self.assertEqual(0, result.returncode, result.stdout + result.stderr)
            self.assertEqual(f"{OUT}/auth.html", result.stdout.strip())
            html = page(root, "auth")
            for needle in ('href="#overview"', 'href="#requirements"', 'href="#diagrams"', 'id="req-search"',
                           '<article class="card" id="REQ-AUTH-001">', "Sign-in.",
                           '<pre class="mermaid">flowchart TD', "mermaid@11.4.1",
                           'integrity="sha384-rbtjAdnIQE/aQJGEgXrVUlMibdfTSa4PQju4HDhN3sR2PmaKFzhEafuePsl9H/9I"'):
                with self.subTest(needle=needle):
                    self.assertIn(needle, html)
            self.assertNotIn('href="#stories"', html)
            self.assertNotIn('href="#mockups"', html)
            self.assertNotIn("{{", html)
            self.assertLess(html.index("<h3>Requirements</h3>"), html.index('id="REQ-AUTH-002"'))
            self.assertLess(html.index('id="REQ-AUTH-002"'), html.index("<h3>Admin</h3>"))
            self.assertLess(html.index("<h3>Admin</h3>"), html.index('id="REQ-AUTH-004"'))

    def test_stories_from_active_and_archived_changes_that_name_its_requirements(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = auth_repo(tmp)
            write(root, "docs/changes/ep-1-lockout/01-proposal.md", proposal("REQ-AUTH-001"))
            write(root, "docs/changes/archive/2026-01-01-ep-0-signin/01-proposal.md", proposal("REQ-AUTH-002"))
            write(root, "docs/changes/ep-2-billing/01-proposal.md", proposal("REQ-BILL-001"))
            self.assertEqual(0, run_specs(root, "explain", "auth").returncode)
            html = page(root, "auth")
            self.assertIn('href="#stories"', html)
            self.assertIn('<p class="from">ep-1-lockout</p>', html)
            self.assertIn('<p class="from">2026-01-01-ep-0-signin</p>', html)
            self.assertNotIn("ep-2-billing", html)
            self.assertIn('<a href="#REQ-AUTH-001">REQ-AUTH-001</a>', html)

    def test_dated_folders_oldest_first_with_images_and_a_sandboxed_mockup(self):
        with tempfile.TemporaryDirectory() as tmp:
            spec = AUTH_SPEC.replace("with a valid password.\n", "with a valid password.\n" + SOURCE)
            root = auth_repo(tmp, spec)
            write(root, "docs/specs/auth/assets/2026-06-01/description.md", "# auth: 2026-06-01\n\nConfirmed: no\n")
            write(root, "docs/specs/auth/assets/2026-05-11/description.md", DESCRIPTION)
            write(root, "docs/specs/auth/assets/2026-05-11/mockup/index.html", MOCKUP)
            write_bytes(root, "docs/specs/auth/assets/2026-05-11/legacy/login.png", PNG)
            result = run_specs(root, "explain", "auth")
            self.assertEqual(0, result.returncode, result.stdout + result.stderr)
            html = page(root, "auth")
            self.assertLess(html.index('id="asset-auth-assets-2026-05-11"'),
                            html.index('id="asset-auth-assets-2026-06-01"'))
            for needle in ("Confirmed: 2026-05-12", "data:image/png;base64,", "legacy/login.png",
                           '<iframe sandbox="allow-scripts" srcdoc="',
                           "&lt;section class=&quot;screen&quot; id=&quot;locked&quot;",
                           "/^[a-z][a-z0-9-]*$/.test(s)",
                           '<option value="sign-in">', '<option value="locked">',
                           'id="asset-auth-assets-2026-05-11-mockup-index-html"',
                           '<a href="#asset-auth-assets-2026-05-11-mockup-index-html" data-screen="locked">'
                           "<code>assets/2026-05-11/mockup/index.html#locked</code></a>"):
                with self.subTest(needle=needle):
                    self.assertIn(needle, html)
            self.assertNotIn("allow-same-origin", html)

    @unittest.skipIf(sys.platform == "win32", "symlinks need privileges on Windows")
    def test_mockup_outside_the_repository_is_listed_and_exits_1(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = auth_repo(tmp)
            outside = Path(tmp) / "outside.html"
            outside.write_text(MOCKUP, encoding="utf-8")
            write(root, "docs/specs/auth/assets/2026-05-11/description.md", DESCRIPTION)
            link = root / "docs/specs/auth/assets/2026-05-11/mockup/index.html"
            link.parent.mkdir(parents=True)
            link.symlink_to(outside)
            result = run_specs(root, "explain", "auth")
            self.assertEqual(1, result.returncode, result.stdout + result.stderr)
            self.assertIn("missing image: docs/specs/auth/assets/2026-05-11/mockup/index.html: mockup not embedded",
                          result.stdout)
            self.assertNotIn("<iframe", page(root, "auth"))


class TestChange(unittest.TestCase):
    def test_delta_grouped_proposal_overview_and_only_cited_folders(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = auth_repo(tmp)
            make_change(root, "ep-1-lockout", spec_delta=delta(
                added=SOURCED_BLOCK, modified=MODIFIED_BLOCK, removed=REMOVED_BLOCK))
            write(root, "docs/changes/ep-1-lockout/01-proposal.md", proposal("REQ-AUTH-003"))
            write(root, "docs/changes/ep-1-lockout/03-design.md", "# Design\n\n## Data Flow\n\nSee login.\n")
            write(root, "docs/specs/auth/assets/2026-05-11/description.md", DESCRIPTION)
            write(root, "docs/specs/auth/assets/2026-05-11/mockup/index.html", MOCKUP)
            write(root, "docs/specs/auth/assets/2026-06-01/description.md", "# auth: 2026-06-01\n\nConfirmed: no\n")
            result = run_specs(root, "explain", "ep-1", "--format", "json")
            self.assertEqual(0, result.returncode, result.stdout + result.stderr)
            self.assertEqual({"path": f"{OUT}/ep-1-lockout.html", "kind": "change", "missing": []},
                             json.loads(result.stdout))
            html = page(root, "ep-1-lockout")
            self.assertLess(html.index("<h3>ADDED</h3>"), html.index("<h3>MODIFIED</h3>"))
            self.assertLess(html.index("<h3>MODIFIED</h3>"), html.index("<h3>REMOVED</h3>"))
            for needle in ("<h1>Lockout</h1>", 'id="REQ-AUTH-003"', "Stop password guessing.",
                           "Lock after five failures.", "Lock a guessed account",
                           '<a href="#REQ-AUTH-003">REQ-AUTH-003</a>', "<h3>Design</h3>",
                           '<pre class="mermaid">flowchart TD', 'id="asset-auth-assets-2026-05-11"',
                           '<iframe sandbox="allow-scripts" srcdoc="'):
                with self.subTest(needle=needle):
                    self.assertIn(needle, html)
            self.assertNotIn("2026-06-01", html)


class TestNarrativeAndPaths(unittest.TestCase):
    def test_narrative_comes_first_and_is_escaped(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = auth_repo(tmp)
            write(root, f"{OUT}/auth.narrative.md",
                  "Auth signs users in (REQ-AUTH-001).\n\n<script>alert(1)</script> [x](javascript:alert(1))\n")
            result = run_specs(root, "explain", "auth", "--narrative", f"{OUT}/auth.narrative.md")
            self.assertEqual(0, result.returncode, result.stdout + result.stderr)
            html = page(root, "auth")
            self.assertIn("&lt;script&gt;alert(1)&lt;/script&gt;", html)
            self.assertNotIn("javascript:", html)
            self.assertLess(html.index("Auth signs users in (REQ-AUTH-001)."), html.index("Sign-in."))

    def test_paths_outside_the_repository_exit_2_and_write_nothing(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = auth_repo(tmp)
            outside = Path(tmp) / "narrative.md"
            outside.write_text("Outside.\n", encoding="utf-8")
            for args in (("--narrative", str(outside)), ("--narrative", "missing.md"), ("--out", "../auth.html")):
                with self.subTest(args=args):
                    result = run_specs(root, "explain", "auth", *args)
                    self.assertEqual(2, result.returncode)
                    self.assertIn("specs error:", result.stdout + result.stderr)
            self.assertFalse((root / OUT).exists())
            self.assertFalse((Path(tmp) / "auth.html").exists())

    def test_out_writes_elsewhere_inside_the_repository(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = auth_repo(tmp)
            result = run_specs(root, "explain", "auth", "--out", "docs/auth.html", "--format", "json")
            self.assertEqual({"path": "docs/auth.html", "kind": "capability", "missing": []},
                             json.loads(result.stdout))
            self.assertTrue((root / "docs/auth.html").is_file())

    def test_unknown_ambiguous_bad_names_and_legacy_layout_exit_2(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = auth_repo(tmp)
            make_change(root, "ep-1-a")
            make_change(root, "ep-1-b")
            for name, needle in (("nope", "unknown capability or change"), ("ep-1", "ambiguous"),
                                 ("../docs", "not a capability or change name")):
                with self.subTest(name=name):
                    result = run_specs(root, "explain", name)
                    self.assertEqual(2, result.returncode)
                    self.assertIn(needle, result.stdout + result.stderr)
            self.assertFalse((root / OUT).exists())
            legacy = make_repo(Path(tmp) / "legacy", layout="legacy")
            self.assertEqual(2, run_specs(legacy, "explain", "auth").returncode)

    def test_project_template_override(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = auth_repo(tmp)
            write(root, ".agent-workflow/templates/explain.html", "<h1>{{title}}</h1><!-- note -->{{nav}}{{sections}}")
            self.assertEqual(0, run_specs(root, "explain", "auth").returncode)
            html = page(root, "auth")
            self.assertTrue(html.startswith("<h1>Auth</h1>"))
            self.assertNotIn("note", html)


if __name__ == "__main__":
    unittest.main()
