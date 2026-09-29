#!/usr/bin/env python3
"""
Extract clips.json from a markdown conversation table.

Usage:
    python make_clips.py <markdown_file> <conversation_number> [-o output.json]

Example:
    python make_clips.py 41.md 41
    python make_clips.py 36.md 36 -o docs/36/clips.json

Reads a refined two-column markdown table (texts/NN.md, see refine_ocr.md) and
generates a clips.json file with file paths, speaker IDs, language, and text.
"""

import argparse
import json
import re
import sys
from collections import Counter
from pathlib import Path


SPANISH_INDICATORS = set("áéíóúñ¿¡ü")

# Matches patterns like: "A. text", "B. text", "R: text", "H: text",
# "Recepcionista: text", "Huésped: text", "Guest: text", "Customer 2: text"
SPEAKER_RE = re.compile(r'^(\w+(?: \d+)?)[.:]\s+(.*)')

SPEAKER_IDS = "abcdefgh"


def spanish_score(text: str) -> float:
    """Fraction of characters that are Spanish indicators (accents, ñ, ¿, ¡)."""
    normalized = text.lower()
    if not normalized:
        return 0.0
    return sum(1 for c in normalized if c in SPANISH_INDICATORS) / len(normalized)


def detect_column_languages(left_text: str, right_text: str) -> tuple[str, str]:
    """Return (left_lang, right_lang): the more Spanish-looking column is "es".

    Comparing the two columns (rather than thresholding each one) keeps an
    English column with a few accented proper nouns ("Chiriquí", "Volcán")
    from being mistaken for Spanish.
    """
    left, right = spanish_score(left_text), spanish_score(right_text)
    if left == right:
        sys.exit("Error: cannot tell which column is Spanish (equal accent scores)")
    return ("es", "en") if left > right else ("en", "es")


def row_label(text: str) -> str | None:
    match = SPEAKER_RE.match(text)
    return match.group(1) if match else None


def speaker_labels(texts: list[str]) -> set[str]:
    """The column's real speaker names.

    If every row starts with a label, they all are (a third speaker may talk
    only once). Otherwise only labels that recur count: a leading "No." or
    "Mr." looks like a label but only appears once, so it is kept as dialogue.
    """
    labels = [row_label(t) for t in texts]
    if all(labels):
        return set(labels)
    counts = Counter(label for label in labels if label)
    return {label for label, n in counts.items() if n >= 2}


def assign_speakers(rows: list[dict]) -> list[str]:
    """Speaker id ("a", "b", "c"…) for each row.

    If every English cell has a label, speakers follow the labels, lettered in
    order of first appearance, so any number of speakers (and a speaker taking
    two turns in a row) works. Otherwise it is a two-person dialogue and rows
    alternate a, b, a, b….
    """
    labels = [row_label(row["left"]) for row in rows]
    if not all(labels):
        return ["a" if i % 2 == 0 else "b" for i in range(len(rows))]

    ids: dict[str, str] = {}
    for label in labels:
        if label not in ids:
            if len(ids) == len(SPEAKER_IDS):
                sys.exit(f"Error: more than {len(SPEAKER_IDS)} speakers")
            ids[label] = SPEAKER_IDS[len(ids)]

    # The refine step makes labels consistent, so an English label paired with
    # two different Spanish labels (or vice versa) means it missed one.
    pairs = {(en, es) for en, row in zip(labels, rows) if (es := row_label(row["right"]))}
    for side in (0, 1):
        for name, n in Counter(pair[side] for pair in pairs).items():
            if n > 1:
                print(f"Warning: label {name!r} pairs with {n} different labels "
                      "in the other column", file=sys.stderr)

    return [ids[label] for label in labels]


def strip_speaker(text: str, labels: set[str]) -> str:
    """Remove a leading speaker label if it is one of the column's labels."""
    match = SPEAKER_RE.match(text)
    if match and match.group(1) in labels:
        return match.group(2)
    return text


def parse_markdown_table(md_text: str) -> list[dict]:
    """Parse a two-column markdown table into row data."""
    rows = []
    for line in md_text.strip().split("\n"):
        line = line.strip()
        if not line.startswith("|"):
            continue
        # Split into cells
        cells = [c.strip() for c in line.split("|")[1:-1]]
        if len(cells) < 2:
            continue
        # Skip header and separator rows
        if cells[0].lower() in ("english", "spanish", "left", "right"):
            continue
        if set(cells[0]) <= set("-: ") and set(cells[1]) <= set("-: "):
            continue
        rows.append({"left": cells[0], "right": cells[1]})
    return rows


def build_clips(rows: list[dict], conv_num: int) -> list[dict]:
    """Build clips.json entries from parsed table rows.

    Speakers come from the row labels (see assign_speakers).
    Each column has a single language detected from all its texts.
    """
    # Detect language per column using all texts in that column
    left_text = " ".join(row["left"] for row in rows if row["left"])
    right_text = " ".join(row["right"] for row in rows if row["right"])
    left_lang, right_lang = detect_column_languages(left_text, right_text)
    labels = {col: speaker_labels([row[col] for row in rows]) for col in ("left", "right")}
    speakers = assign_speakers(rows)

    clips = []

    for i, row in enumerate(rows):
        row_num = f"{i:02d}"
        speaker_char = speakers[i]

        for col, lang in [("left", left_lang), ("right", right_lang)]:
            text = row[col]
            if not text:
                continue

            clean_text = strip_speaker(text, labels[col])
            file_path = f"{conv_num}/audio/{lang}/{row_num}-{speaker_char}.mp3"
            speaker_id = f"{lang}_{speaker_char}"

            clips.append({
                "file": file_path,
                "speaker": speaker_id,
                "lang": lang,
                "text": clean_text,
            })

    return clips


def main():
    parser = argparse.ArgumentParser(description="Extract clips.json from a markdown conversation table.")
    parser.add_argument("markdown", type=str, help="Path to the markdown file")
    parser.add_argument("conversation", type=int, help="Conversation number")
    parser.add_argument("-o", "--output", type=str, default=None, help="Output JSON file (default: stdout)")
    args = parser.parse_args()

    md_path = Path(args.markdown)
    if not md_path.exists():
        sys.exit(f"Error: {md_path} not found")

    md_text = md_path.read_text()
    rows = parse_markdown_table(md_text)

    if not rows:
        sys.exit("Error: no table rows found in markdown")

    clips = build_clips(rows, args.conversation)

    output = json.dumps(clips, indent=2, ensure_ascii=False)

    if args.output:
        out_path = Path(args.output)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(output + "\n")
        print(f"Written {len(clips)} clips to {out_path}", file=sys.stderr)
    else:
        print(output)


if __name__ == "__main__":
    main()
