"""Tests for scripts/make_clips.py.

Run from the project root:
    .venv/bin/python -m unittest discover tests
"""

import contextlib
import io
import json
import sys
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))

from make_clips import (  # noqa: E402
    assign_speakers,
    clips_from_markdown,
    detect_column_languages,
    has_table_header,
    parse_markdown_table,
    row_label,
)


def table(*rows: tuple[str, str]) -> str:
    return "\n".join(f"| {left} | {right} |" for left, right in rows)


def clips_for(md: str, conv: int = 99) -> list[dict]:
    return clips_from_markdown(md, conv)


def by_lang(clips: list[dict], lang: str) -> list[dict]:
    return [c for c in clips if c["lang"] == lang]


class CommittedConversations(unittest.TestCase):
    """Every texts/NN.md still produces its committed docs/NN/clips.json."""

    def test_clips_match(self):
        texts = sorted((PROJECT_ROOT / "texts").glob("*.md"))
        self.assertTrue(texts)
        for path in texts:
            conv = int(path.stem)
            with self.subTest(conversation=conv):
                expected = json.loads((PROJECT_ROOT / "docs" / str(conv) / "clips.json").read_text())
                self.assertEqual(clips_for(path.read_text(), conv), expected)


class ParseTable(unittest.TestCase):
    def test_skips_title_header_and_separator(self):
        md = "# 1. Title — Título\n\n| English | Spanish |\n|---|---|\n| A. Hi. | A. ¡Hola! |"
        self.assertEqual(parse_markdown_table(md), [{"left": "A. Hi.", "right": "A. ¡Hola!"}])


class TableHeader(unittest.TestCase):
    def test_header_and_separator(self):
        self.assertTrue(has_table_header("# T\n\n| English | Español |\n|---|:--|\n| A. Hi. | A. ¡Hola! |"))

    def test_missing_separator(self):
        self.assertFalse(has_table_header("# T\n\n| English | Español |\n| A. Hi. | A. ¡Hola! |"))

    def test_bare_rows(self):
        self.assertFalse(has_table_header("# T\n\n| A. Hi. | A. ¡Hola! |\n| B. Bye. | B. Adiós. |"))

    def test_committed_texts_have_header(self):
        for path in sorted((PROJECT_ROOT / "texts").glob("*.md")):
            with self.subTest(conversation=path.stem):
                self.assertTrue(has_table_header(path.read_text()))


class Labels(unittest.TestCase):
    def test_label_forms(self):
        self.assertEqual(row_label("A. Hello."), "A")
        self.assertEqual(row_label("R: Hello."), "R")
        self.assertEqual(row_label("Huésped: Hola."), "Huésped")
        self.assertEqual(row_label("Customer 2: Thank you."), "Customer 2")
        self.assertIsNone(row_label("Hello there."))

    def test_labels_are_stripped(self):
        clips = clips_for(table(
            ("Waiter: Good afternoon.", "Camarero: Buenas tardes."),
            ("Customer 2: Where is the bathroom?", "Cliente 2: ¿Dónde está el baño?"),
        ))
        self.assertEqual([c["text"] for c in by_lang(clips, "en")],
                         ["Good afternoon.", "Where is the bathroom?"])
        self.assertEqual([c["text"] for c in by_lang(clips, "es")],
                         ["Buenas tardes.", "¿Dónde está el baño?"])

    def test_one_off_leading_word_is_dialogue_in_unlabeled_table(self):
        # Without labels on every row, only recurring labels are stripped,
        # so a leading "No." stays part of the line.
        clips = clips_for(table(
            ("Is it far?", "¿Está lejos?"),
            ("No. It is close.", "No. Está cerca."),
        ))
        self.assertEqual(by_lang(clips, "en")[1]["text"], "No. It is close.")
        self.assertEqual(by_lang(clips, "es")[1]["text"], "No. Está cerca.")


class Speakers(unittest.TestCase):
    def test_three_speakers_by_first_appearance(self):
        rows = parse_markdown_table(table(
            ("Waiter: And for you?", "Camarero: ¿Y para usted?"),
            ("Customer: Water.", "Cliente: Agua."),
            ("Customer 2: Soup.", "Cliente 2: Sopa."),
            ("Waiter: Very good.", "Camarero: Muy bien."),
        ))
        self.assertEqual(assign_speakers(rows), ["a", "b", "c", "a"])

    def test_same_speaker_twice_in_a_row(self):
        rows = parse_markdown_table(table(
            ("A. Hello.", "A. Hola."),
            ("A. Are you there?", "A. ¿Está ahí?"),
            ("B. Yes.", "B. Sí."),
        ))
        self.assertEqual(assign_speakers(rows), ["a", "a", "b"])

    def test_speaker_ids_in_files_and_voices(self):
        clips = clips_for(table(
            ("Waiter: Hi.", "Camarero: Hola."),
            ("Customer: Hi.", "Cliente: Hola."),
            ("Customer 2: Thanks!", "Cliente 2: ¡Gracias!"),
        ), conv=10)
        self.assertEqual(clips[4]["file"], "10/audio/en/02-c.mp3")
        self.assertEqual(clips[4]["speaker"], "en_c")
        self.assertEqual(clips[5]["speaker"], "es_c")

    def test_unlabeled_row_falls_back_to_parity(self):
        rows = parse_markdown_table(table(
            ("A. Hello.", "A. Hola."),
            ("A. Hello again.", "A. Hola otra vez."),
            ("Goodbye.", "Adiós."),
        ))
        self.assertEqual(assign_speakers(rows), ["a", "b", "a"])

    def test_spanish_labels_do_not_pick_voices(self):
        # The Spanish column mislabels row 1; the English label wins.
        rows = parse_markdown_table(table(
            ("A. Hello.", "A. Hola."),
            ("B. Hi.", "A. Buenas."),
        ))
        with contextlib.redirect_stderr(io.StringIO()) as err:
            self.assertEqual(assign_speakers(rows), ["a", "b"])
        self.assertIn("Warning", err.getvalue())

    def test_consistent_labels_do_not_warn(self):
        rows = parse_markdown_table(table(
            ("Guest: Hello.", "Huésped: Hola."),
            ("Receptionist: Welcome.", "Recepcionista: Bienvenido."),
        ))
        with contextlib.redirect_stderr(io.StringIO()) as err:
            assign_speakers(rows)
        self.assertEqual(err.getvalue(), "")

    def test_voices_line_picks_voices(self):
        # Luis speaks first, but Ana (a woman) should get voice a.
        clips = clips_for("Voices: Ana, Luis\n\n" + table(
            ("Luis: Hello.", "Luis: Hola."),
            ("Ana: Hi.", "Ana: Buenas."),
            ("Carla: Hey!", "Carla: ¡Épale!"),
        ))
        self.assertEqual([c["speaker"] for c in by_lang(clips, "en")], ["en_b", "en_a", "en_c"])
        self.assertEqual(clips[0]["file"], "99/audio/en/00-b.mp3")

    def test_voices_line_can_name_a_voice(self):
        # Two women: Elena gets voice d, and the letters skip it.
        clips = clips_for("Voices: Maria, Elena=d\n\n" + table(
            ("Maria: Hello.", "María: Hola."),
            ("Elena: Hi.", "Elena: Buenas."),
            ("Luis: Hey!", "Luis: ¡Épale!"),
            ("Carla: Bye.", "Carla: Adiós."),
            ("Pablo: Bye.", "Pablo: Chao."),
        ))
        self.assertEqual([c["speaker"] for c in by_lang(clips, "en")],
                         ["en_a", "en_d", "en_b", "en_c", "en_e"])
        self.assertEqual(by_lang(clips, "es")[1]["file"], "99/audio/es/01-d.mp3")

    def test_voices_line_must_name_labels(self):
        md = table(("Luis: Hello.", "Luis: Hola."), ("Ana: Hi.", "Ana: Buenas."))
        for line in ("Voices: Ana, Maria", "Voices: Ana, Ana", "Voices: Ana=b, Luis=b",
                     "Voices: Ana=z", "Voices: Ana=a, Ana=b"):
            with self.subTest(line=line), self.assertRaises(SystemExit):
                clips_for(f"{line}\n\n{md}")

    def test_voices_line_needs_labels(self):
        with self.assertRaises(SystemExit):
            clips_for("Voices: Ana\n\n" + table(("Hello.", "Hola."), ("Hi.", "Buenas.")))

    def test_too_many_speakers(self):
        rows = [{"left": f"P{i}: Hi.", "right": f"P{i}: Hola."} for i in range(9)]
        with self.assertRaises(SystemExit):
            assign_speakers(rows)


class Languages(unittest.TestCase):
    def test_spanish_on_the_left(self):
        clips = clips_for(table(("A. ¿Cómo está?", "A. How are you?"), ("B. Bien.", "B. Fine.")))
        self.assertEqual(clips[0], {"file": "99/audio/es/00-a.mp3", "speaker": "es_a",
                                    "lang": "es", "text": "¿Cómo está?"})
        self.assertEqual(clips[1]["lang"], "en")

    def test_accented_place_name_stays_english(self):
        # Compared against the Spanish column, a stray "Volcán" can't flip English.
        self.assertEqual(
            detect_column_languages("We live in Volcán, near the river.",
                                    "Vivimos en Volcán, cerca del río. ¿Y tú?"),
            ("en", "es"))

    def test_undecidable_columns_exit(self):
        with self.assertRaises(SystemExit):
            detect_column_languages("Hello.", "Goodbye.")


if __name__ == "__main__":
    unittest.main()
