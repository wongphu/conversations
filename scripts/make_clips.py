#!/usr/bin/env python3
"""
Extract clips.json from a markdown conversation table.

Usage:
    python make_clips.py <markdown_file> <conversation_number> [-o output.json]

Example:
    python make_clips.py 41.md 41
    python make_clips.py 36.md 36 -o docs/36/clips.json

Reads a two-column markdown table (as produced by extract_text.py) and
generates a clips.json file with file paths, speaker IDs, language, and text.
"""

import argparse
import json
import re
import sys
import unicodedata
from pathlib import Path


def detect_language(text: str) -> str:
    """Detect if text is Spanish or English using character heuristics."""
    spanish_indicators = set("áéíóúñ¿¡ü")
    normalized = text.lower()
    score = sum(1 for c in normalized if c in spanish_indicators)
    return "es" if score >= 2 else "en"


def parse_speaker(text: str) -> tuple[str | None, str]:
    """
    Extract speaker label and clean text.
    
    Returns (speaker_char, clean_text) where speaker_char is the raw label
    (e.g., "A", "B", "R", "H") or None if not detected.
    """
    # Match patterns like: "A. text", "B. text", "R: text", "H: text",
    # "Recepcionista: text", "Huésped: text", "Guest: text"
    match = re.match(r'^(\w+)[.:]\s+(.*)', text)
    if match:
        return match.group(1)[0].upper(), match.group(2)
    return None, text


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
    left_lang = detect_language(left_text)
    right_lang = detect_language(right_text)

    clips = []

    for i, row in enumerate(rows):
        row_num = f"{i:02d}"
        speaker_char = "a" if i % 2 == 0 else "b"

        for col, lang in [("left", left_lang), ("right", right_lang)]:
            text = row[col]
            if not text:
                continue

            _, clean_text = parse_speaker(text)
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
