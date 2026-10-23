"""The ADLC deck stays offline, navigable, linked and in step with the lifecycle doc."""

from __future__ import annotations

from pathlib import Path
import re
import unittest
import zipfile

ROOT = Path(__file__).resolve().parents[2]
LIFECYCLE = ROOT / "docs/concepts/lifecycle.md"
DECK_HTML = ROOT / "docs/presentations/adlc.html"
DECK_PPTX = ROOT / "docs/presentations/adlc.pptx"
DECK_LINKS = ("presentations/adlc.html", "presentations/adlc.pptx")
FORBIDDEN = ("codex", "antigravity", "opencode", "gemini", "sonnet", "opus", "haiku", "gpt")
SLIDES = 17


def pptx_slide_texts() -> list[str]:
    """The text runs of each slide, in slide order."""
    with zipfile.ZipFile(DECK_PPTX) as deck:
        slides = [name for name in deck.namelist() if re.fullmatch(r"ppt/slides/slide\d+\.xml", name)]
        slides.sort(key=lambda name: int(re.search(r"\d+", name).group()))
        return [" ".join(re.findall(r"<a:t>([^<]*)</a:t>", deck.read(name).decode("utf-8"))) for name in slides]


def lifecycle_names() -> set[str]:
    """Stage and gate names from the Stages and gates table of the lifecycle doc."""
    names: set[str] = set()
    for line in LIFECYCLE.read_text(encoding="utf-8").splitlines():
        cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
        if len(cells) == 4 and cells[0].startswith("`"):
            names.update((cells[0].strip("`"), cells[2].strip("`")))
    return names


def names_forbidden_word(text: str) -> list[str]:
    lowered = text.lower()
    return [word for word in FORBIDDEN if re.search(rf"\b{word}", lowered)]


class TestLifecycleNames(unittest.TestCase):
    def test_reads_five_stages_and_five_gates(self):
        self.assertEqual(
            {"discuss", "plan", "orchestrate", "execute", "ship", "requirement_confirmed", "plan_approved",
             "orchestration_ready", "implementation_complete", "shipped"},
            lifecycle_names(),
        )


class TestAdlcHtmlDeck(unittest.TestCase):
    def setUp(self):
        self.html = DECK_HTML.read_text(encoding="utf-8")

    def test_shows_every_stage_and_gate(self):
        for name in sorted(lifecycle_names()):
            with self.subTest(name=name):
                self.assertIn(name, self.html)

    def test_has_seventeen_slides(self):
        self.assertEqual(SLIDES, len(re.findall(r'<section class="slide[" ]', self.html)))

    def test_loads_nothing_from_the_network(self):
        self.assertEqual([], re.findall(r"""(?:src|href)\s*=\s*["']?https?:""", self.html, re.IGNORECASE))

    def test_navigates_by_keyboard(self):
        for key in ("ArrowLeft", "ArrowRight", "Home", "End"):
            with self.subTest(key=key):
                self.assertIn(f'"{key}"', self.html)

    def test_names_no_provider_or_model(self):
        self.assertEqual([], names_forbidden_word(self.html))


class TestAdlcPptxDeck(unittest.TestCase):
    def setUp(self):
        self.slides = pptx_slide_texts()
        self.text = " ".join(self.slides)

    def test_shows_every_stage_and_gate(self):
        for name in sorted(lifecycle_names()):
            with self.subTest(name=name):
                self.assertIn(name, self.text)

    def test_has_seventeen_slides(self):
        self.assertEqual(SLIDES, len(self.slides))

    def test_is_sixteen_by_nine(self):
        with zipfile.ZipFile(DECK_PPTX) as deck:
            presentation = deck.read("ppt/presentation.xml").decode("utf-8")
        size = re.search(r'<p:sldSz cx="(\d+)" cy="(\d+)"', presentation)
        self.assertEqual(16 * int(size.group(2)), 9 * int(size.group(1)))

    def test_has_no_pictures(self):
        with zipfile.ZipFile(DECK_PPTX) as deck:
            self.assertEqual([], [name for name in deck.namelist() if name.startswith("ppt/media/")])

    def test_names_no_provider_or_model(self):
        self.assertEqual([], names_forbidden_word(self.text))


class TestAdlcDeckLinks(unittest.TestCase):
    def test_readme_and_getting_started_link_the_deck(self):
        for doc in ("README.md", "docs/getting-started.md"):
            text = (ROOT / doc).read_text(encoding="utf-8")
            for target in DECK_LINKS:
                with self.subTest(doc=doc, target=target):
                    self.assertIn(target, text)


if __name__ == "__main__":
    unittest.main()
