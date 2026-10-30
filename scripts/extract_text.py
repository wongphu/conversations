#!/usr/bin/env python3
"""
Convert a conversation page (image or Word file) to a RAW markdown table.

Usage:
    python extract_text.py <source> [-o output.md]

Example:
    python extract_text.py inbox/41.jpeg             # writes ocrs/41.md
    python extract_text.py inbox/36.jpeg -o ocrs/36.md
    python extract_text.py 1                         # finds inbox/1 - Greetings, introductions.docx

<source> is a page image (.jpeg, .jpg, .png), read with RapidOCR, or a Word
file (.docx), whose tables are read directly. It can also be a conversation
number: the file whose name starts with that number, in inbox/ or, once
pipeline.py has built its page, in done/. Writes a raw
markdown table into ocrs/NN.md by default, NN being the number the source's
name starts with ("1 - Greetings.docx" → ocrs/1.md), or to the path given with -o.

Note: the column order is whatever appears in the page, so the raw output is
NOT guaranteed to be English-left / Spanish-right, and it may contain OCR
errors (or, from a Word file, the author's typos, a title row and
instructions). That normalization is done by the refine step (see
refine_ocr.md), which reads from ocrs/ and writes the cleaned result to texts/.
"""

import argparse
import re
import sys
import zipfile
import xml.etree.ElementTree as ET
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
INBOX_DIR = PROJECT_ROOT / "inbox"
DONE_DIR = PROJECT_ROOT / "done"  # sources pipeline.py has built a page from

IMAGE_SUFFIXES = {".jpeg", ".jpg", ".png"}
INPUT_SUFFIXES = IMAGE_SUFFIXES | {".docx"}

# Matches speaker labels at the start of a line:
#   "R: ", "H. ", "A. ", "B. ", "Recepcionista: ", "Huésped: "
# The tail is any letters (not just [a-z]) so accented names match, including
# OCR misreads like "Anņa:".
SPEAKER_RE = re.compile(r'^[A-ZÁÉÍÓÚÑ][^\W\d_]*[.:] ')

W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
MC_FALLBACK = "{http://schemas.openxmlformats.org/markup-compatibility/2006}Fallback"

# Invisible characters Word documents pick up from pasted text
INVISIBLE_RE = re.compile("[­​‌‍⁠﻿]")


def conversation_number(path: Path) -> int | None:
    """The number a source file's name starts with: 41.jpeg → 41, "1 - Greetings.docx" → 1."""
    match = re.match(r"\d+", path.stem)
    return int(match.group()) if match else None


def sources_in(folder: Path) -> list[Path]:
    """The page images and Word files directly in <folder>."""
    if not folder.is_dir():
        return []
    return sorted(p for p in folder.iterdir() if p.is_file() and p.suffix.lower() in INPUT_SUFFIXES)


def input_files() -> list[Path]:
    """Every source file: new ones in inbox/, processed ones in done/."""
    return sources_in(INBOX_DIR) + sources_in(DONE_DIR)


def find_input(conv: int) -> Path:
    """Conversation <conv>'s file in inbox/, or else in done/."""
    for folder in (INBOX_DIR, DONE_DIR):
        matches = [p for p in sources_in(folder) if conversation_number(p) == conv]
        if len(matches) > 1:
            names = ", ".join(p.name for p in matches)
            sys.exit(f"Error: several inputs for conversation {conv} ({names}); pass the path instead")
        if matches:
            return matches[0]
    sys.exit(f"Error: no page image or .docx in inbox/ or done/ whose name starts with {conv}")


def move_to_done(conv: int) -> None:
    """Move conversation <conv>'s sources from inbox/ to done/ (pipeline.py
    does this once the page is built, so inbox/ lists only what's left to do)."""
    for source in sources_in(INBOX_DIR):
        if conversation_number(source) == conv:
            DONE_DIR.mkdir(exist_ok=True)
            source.replace(DONE_DIR / source.name)
            print(f"  moved inbox/{source.name} to done/")


def extract_table(image_path: str, row_gap_threshold: float = 100.0) -> str:
    """Extract a two-column markdown table from an image."""
    from rapidocr import RapidOCR  # loaded here so Word files don't need the OCR engine

    engine = RapidOCR()
    result = engine(image_path)

    if not result.txts:
        return "No text detected."

    img = result.img
    h, w = img.shape[:2]
    mid_x = w / 2

    # Collect all text fragments with positions
    items = []
    for i in range(len(result.txts)):
        box = result.boxes[i]
        x_center = (box[0][0] + box[2][0]) / 2
        y_center = (box[0][1] + box[2][1]) / 2
        text = result.txts[i].strip()
        if text:
            items.append({"y": y_center, "x": x_center, "text": text})

    # Filter out page number (standalone short text at the very bottom)
    if items:
        max_y = max(item["y"] for item in items)
        items = [item for item in items if item["y"] < max_y - 50 or len(item["text"]) > 3]

    # Sort by y position
    items.sort(key=lambda item: item["y"])

    # Group into rows using gap detection
    # If the gap from the previous item exceeds the threshold, start a new row
    rows: list[list[dict]] = []
    current_row: list[dict] = []
    prev_y = None

    for item in items:
        gap = (item["y"] - prev_y) if prev_y is not None else 0
        if gap > row_gap_threshold:
            rows.append(current_row)
            current_row = []
        elif gap > 30 and SPEAKER_RE.match(item["text"]) and current_row:
            # A speaker label after a significant gap starts a new row
            rows.append(current_row)
            current_row = []
        current_row.append(item)
        prev_y = item["y"]

    if current_row:
        rows.append(current_row)

    # Build markdown table (no header row — the two columns are positional,
    # left / right, and their language is detected downstream)
    lines = []

    for row in rows:
        left = [item for item in row if item["x"] < mid_x]
        right = [item for item in row if item["x"] >= mid_x]

        # Join multi-line cells with a space
        left_text = " ".join(item["text"] for item in left)
        right_text = " ".join(item["text"] for item in right)

        # Skip rows with no content in either column
        if not left_text and not right_text:
            continue

        # Escape pipes
        left_text = left_text.replace("|", "\\|")
        right_text = right_text.replace("|", "\\|")

        lines.append(f"| {left_text} | {right_text} |")

    return "\n".join(lines)


def word_text(element: ET.Element) -> str:
    """The visible text of a Word element, its paragraphs and line breaks as spaces."""
    parts = []
    for child in element:
        if child.tag == f"{W}t":
            parts.append(child.text or "")
        elif child.tag in (f"{W}tab", f"{W}br", f"{W}cr"):
            parts.append(" ")
        elif child.tag == f"{W}noBreakHyphen":
            parts.append("-")
        elif child.tag == f"{W}p":
            parts.append(f" {word_text(child)} ")
        elif child.tag != MC_FALLBACK:  # a Fallback repeats its Choice (e.g. a text box)
            parts.append(word_text(child))
    return "".join(parts)


def clean(text: str) -> str:
    return " ".join(INVISIBLE_RE.sub("", text).split())


def blocks(element: ET.Element):
    """Children of a Word element, looking through content controls (w:sdt)."""
    for child in element:
        if child.tag == f"{W}sdt":
            content = child.find(f"{W}sdtContent")
            if content is not None:
                yield from blocks(content)
        else:
            yield child


def extract_docx(docx_path: str) -> str:
    """Extract a Word file's tables as markdown rows, one per table row.

    Cells are kept as they are, left to right, so a two-column table gives
    the same raw two-column rows as the OCR. Paragraphs outside a table (a
    heading, say) are kept as plain lines in document order. Headers and
    footers (e.g. a page or conversation number) are left out.
    """
    with zipfile.ZipFile(docx_path) as docx:
        body = ET.fromstring(docx.read("word/document.xml")).find(f"{W}body")

    lines = []
    for block in blocks(body):
        if block.tag == f"{W}p":
            if text := clean(word_text(block)):
                lines.append(text)
        elif block.tag == f"{W}tbl":
            for row in blocks(block):
                if row.tag != f"{W}tr":
                    continue
                cells = [clean(word_text(cell)).replace("|", "\\|")
                         for cell in blocks(row) if cell.tag == f"{W}tc"]
                if any(cells):
                    lines.append(f"| {' | '.join(cells)} |")

    return "\n".join(lines) if lines else "No text found."


def main():
    parser = argparse.ArgumentParser(description="Convert a conversation page to a raw markdown table.")
    parser.add_argument("source", type=str,
                        help="Page image or .docx, or a conversation number to find in inbox/ or done/")
    parser.add_argument("-o", "--output", type=str, default=None,
                        help="Output markdown file (default: ocrs/<number>.md; use - for stdout)")
    parser.add_argument("--row-gap", type=float, default=100.0,
                        help="Min pixel gap between rows in an image (default: 100)")
    args = parser.parse_args()

    source = find_input(int(args.source)) if args.source.isdigit() else Path(args.source)
    if not source.exists():
        sys.exit(f"Error: {source} not found")
    suffix = source.suffix.lower()
    if suffix not in INPUT_SUFFIXES:
        sys.exit(f"Error: {source.name}: expected a page image ({', '.join(sorted(IMAGE_SUFFIXES))}) "
                 f"or a .docx (save a .doc as .docx first)")

    if suffix == ".docx":
        markdown = extract_docx(str(source))
    else:
        markdown = extract_table(str(source), row_gap_threshold=args.row_gap)

    if args.output == "-":
        print(markdown)
        return

    if args.output is None:
        conv = conversation_number(source)
        out_path = PROJECT_ROOT / "ocrs" / f"{source.stem if conv is None else conv}.md"
    else:
        out_path = Path(args.output)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(markdown + "\n")
    print(f"Written to {out_path}", file=sys.stderr)


if __name__ == "__main__":
    main()
