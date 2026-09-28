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
# "Recepcionista: text", "Huésped: text", "Guest: text"
SPEAKER_RE = re.compile(r'^(\w+)[.:]\s+(.*)')


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


def speaker_labels(texts: list[str]) -> set[str]:
    """Labels that recur in a column, i.e. real speaker names.

    A leading "No." or "Mr." looks like a label but only appears once, so it
    is kept as dialogue. Each speaker in a two-person dialogue speaks more than
    once, so their label always recurs.
    """
    counts = Counter(m.group(1) for t in texts if (m := SPEAKER_RE.match(t)))
    return {label for label, n in counts.items() if n >= 2}


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
    
    Two-person conversation: speakers alternate by row.
    Row 0 → a, row 1 → b, row 2 → a, etc.
    Each column has a single language detected from all its texts.
    """
    # Detect language per column using all texts in that column
    left_text = " ".join(row["left"] for row in rows if row["left"])
    right_text = " ".join(row["right"] for row in rows if row["right"])
    left_lang, right_lang = detect_column_languages(left_text, right_text)
    labels = {col: speaker_labels([row[col] for row in rows]) for col in ("left", "right")}

    clips = []

    for i, row in enumerate(rows):
        row_num = f"{i:02d}"
        speaker_char = "a" if i % 2 == 0 else "b"

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
