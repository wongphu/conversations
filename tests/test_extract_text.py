"""Tests for scripts/extract_text.py (the Word-file side; OCR needs the models).

Run from the project root:
    .venv/bin/python -m unittest discover tests
"""

import sys
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest import mock

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))

import extract_text  # noqa: E402
from extract_text import conversation_number, extract_docx, find_input  # noqa: E402

NAMESPACES = ('xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main" '
              'xmlns:mc="http://schemas.openxmlformats.org/markup-compatibility/2006"')


def para(*runs: str) -> str:
    return "<w:p><w:pPr><w:rPr><w:b/></w:rPr></w:pPr>" + "".join(runs) + "</w:p>"


def run(text: str) -> str:
    return f'<w:r><w:rPr><w:b/></w:rPr><w:t xml:space="preserve">{text}</w:t></w:r>'


def row(*cells: str) -> str:
    return "<w:tr><w:trPr/>" + "".join(f"<w:tc><w:tcPr/>{c}</w:tc>" for c in cells) + "</w:tr>"


def write_docx(path: Path, body: str) -> None:
    document = f'<?xml version="1.0" encoding="UTF-8"?><w:document {NAMESPACES}><w:body>{body}</w:body></w:document>'
    with zipfile.ZipFile(path, "w") as docx:
        docx.writestr("word/document.xml", document)
        docx.writestr("word/footer1.xml", f'<w:ftr {NAMESPACES}>{para(run("#1"))}</w:ftr>')


class ExtractDocx(unittest.TestCase):
    def extract(self, body: str) -> str:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "page.docx"
            write_docx(path, body)
            return extract_docx(str(path))

    def test_table_rows_become_markdown_rows(self):
        body = (para(run("Conversation 1"))
                + "<w:tbl><w:tblPr/>"
                + row(para(run("Introductions")), para(run("Introduciones")))
                + row(para(run("Hello my "), run("name is ___.")), para(run("Hola, mi nombre es ____.")))
                + row(para(), para())                                           # empty: skipped
                + row(para(run("I like it.")), para(run("Me gusta.")) + para()  # trailing empty paragraph
                      + para(run("Mucho.")))                                    # second paragraph
                + "</w:tbl>"
                + "<w:sectPr/>")
        self.assertEqual(self.extract(body), "\n".join([
            "Conversation 1",
            "| Introductions | Introduciones |",
            "| Hello my name is ___. | Hola, mi nombre es ____. |",
            "| I like it. | Me gusta. Mucho. |",
        ]))

    def test_cleans_whitespace_and_invisible_characters(self):
        body = "<w:tbl>" + row(
            para(run("They are ____ and  "), run("____ years old.")),
            para(run("Tienen ____ y ​​____ años."), "<w:r><w:tab/><w:t>Sí</w:t><w:br/></w:r>"),
        ) + "</w:tbl>"
        self.assertEqual(self.extract(body),
                         "| They are ____ and ____ years old. | Tienen ____ y ____ años. Sí |")

    def test_skips_deleted_text_and_escapes_pipes(self):
        body = "<w:tbl>" + row(
            para(run("Yes"), "<w:del><w:r><w:delText>No</w:delText></w:r></w:del>",
                 "<w:ins>" + run(" | maybe") + "</w:ins>"),
            para(run("Sí")),
        ) + "</w:tbl>"
        self.assertEqual(self.extract(body), r"| Yes \| maybe | Sí |")

    def test_reads_through_content_controls_and_alternate_content(self):
        body = ("<w:sdt><w:sdtPr/><w:sdtContent><w:tbl>" + row(
            para("<w:r><mc:AlternateContent><mc:Choice>" + para(run("Box")) + "</mc:Choice>"
                 "<mc:Fallback>" + para(run("Box")) + "</mc:Fallback></mc:AlternateContent></w:r>"),
            para(run("Caja")),
        ) + "</w:tbl></w:sdtContent></w:sdt>")
        self.assertEqual(self.extract(body), "| Box | Caja |")


class FindInput(unittest.TestCase):
    def test_conversation_number(self):
        self.assertEqual(conversation_number(Path("inputs/41.jpeg")), 41)
        self.assertEqual(conversation_number(Path("inputs/1 - Greetings, introductions.docx")), 1)
        self.assertIsNone(conversation_number(Path("inputs/cover.jpeg")))

    def test_finds_the_input_by_number(self):
        with tempfile.TemporaryDirectory() as tmp:
            inputs = Path(tmp)
            for name in ("1 - Greetings.docx", "10.jpeg", "12.jpeg", "12 - Shopping.docx", "3 - Notes.txt"):
                (inputs / name).write_bytes(b"")
            with mock.patch.object(extract_text, "INPUTS_DIR", inputs):
                self.assertEqual(find_input(1).name, "1 - Greetings.docx")
                self.assertEqual(find_input(10).name, "10.jpeg")
                with self.assertRaises(SystemExit):
                    find_input(12)  # ambiguous
                with self.assertRaises(SystemExit):
                    find_input(3)   # not a page image or .docx


class CommittedOcrs(unittest.TestCase):
    def test_docx_inputs_match_their_ocrs(self):
        """Word extraction is deterministic, so ocrs/NN.md must match it once extracted."""
        for docx in sorted((PROJECT_ROOT / "inputs").glob("*.docx")):
            ocr = PROJECT_ROOT / "ocrs" / f"{conversation_number(docx)}.md"
            if not ocr.exists():
                continue  # not extracted yet; check.py notes it
            with self.subTest(docx=docx.name):
                self.assertEqual(ocr.read_text(), extract_docx(str(docx)) + "\n",
                                 f"re-run scripts/extract_text.py {conversation_number(docx)}")


if __name__ == "__main__":
    unittest.main()
