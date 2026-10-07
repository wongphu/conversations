"""Tests for scripts/generate_html.py.

Run from the project root:
    .venv/bin/python -m unittest discover tests
"""

import sys
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DOCS = PROJECT_ROOT / "docs"
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))

from generate_html import (  # noqa: E402
    generate_html, generate_index, parse_level, player_version, render_text)


class CommittedPages(unittest.TestCase):
    """The committed pages are exactly what the generator produces."""

    def test_pages_match(self):
        pages = sorted(p for p in DOCS.glob("*.html") if p.stem.isdigit())
        self.assertTrue(pages)
        for path in pages:
            with self.subTest(page=path.name):
                self.assertEqual(generate_html(int(path.stem)), path.read_text())

    def test_index_matches(self):
        self.assertEqual(generate_index(), (DOCS / "index.html").read_text())

    def test_page_references_resolve(self):
        for path in DOCS.glob("*.html"):
            html = path.read_text()
            for marker in ('data-audio="', 'src="', 'href="'):
                for chunk in html.split(marker)[1:]:
                    ref = chunk.split('"', 1)[0].split("?", 1)[0]
                    if ref.startswith(("http:", "https:", "#")):
                        continue
                    with self.subTest(page=path.name, ref=ref):
                        self.assertTrue((DOCS / ref).is_file())


class PlayerVersion(unittest.TestCase):
    def test_pages_load_the_current_player(self):
        # A stale hash would let browsers keep running a cached older player.
        src = f'src="player.js?v={player_version()}"'
        for path in DOCS.glob("*.html"):
            if path.stem.isdigit():
                with self.subTest(page=path.name):
                    self.assertIn(src, path.read_text())


class ParseLevel(unittest.TestCase):
    def test_level_line(self):
        self.assertEqual(parse_level("# 5. At the Market — En el mercado\n\nLevel: A1\n\n| a | b |\n"), "A1")

    def test_missing_or_invalid(self):
        self.assertIsNone(parse_level("# 5. At the Market\n\n| a | b |\n"))
        self.assertIsNone(parse_level("Level: D1\n"))
        self.assertIsNone(parse_level("| Level: B1 | Nivel: B1 |\n"))


class RenderText(unittest.TestCase):
    def test_escapes_and_italics(self):
        self.assertEqual(render_text("Tom & *Jerry* <3"), "Tom &amp; <em>Jerry</em> &lt;3")


if __name__ == "__main__":
    unittest.main()
