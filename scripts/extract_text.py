#!/usr/bin/env python3
"""
Convert a conversation page image to a markdown table using RapidOCR.

Usage:
    python extract_text.py <image_path> [-o output.md]

Example:
    python extract_text.py 41.jpeg
    python extract_text.py 36.png -o conversation.md

Outputs a markdown table matching the two-column layout in the image.
"""

import argparse
import re
import sys
from pathlib import Path

from rapidocr import RapidOCR

# Matches speaker labels at the start of a line:
#   "R: ", "H. ", "A. ", "B. ", "Recepcionista: ", "Huésped: "
SPEAKER_RE = re.compile(r'^[A-Z][a-z]*[.:] ')


def extract_table(image_path: str, row_gap_threshold: float = 100.0) -> str:
    """Extract a two-column markdown table from an image."""
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

    # Build markdown table
    lines = []
    lines.append("| English | Spanish |")
    lines.append("|---------|---------|")

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


def main():
    parser = argparse.ArgumentParser(description="Convert a conversation image to a markdown table.")
    parser.add_argument("image", type=str, help="Path to the image file")
    parser.add_argument("-o", "--output", type=str, default=None, help="Output markdown file (default: stdout)")
    parser.add_argument("--row-gap", type=float, default=100.0,
                        help="Min pixel gap between rows (default: 100)")
    args = parser.parse_args()

    image_path = Path(args.image)
    if not image_path.exists():
        sys.exit(f"Error: {image_path} not found")

    markdown = extract_table(str(image_path), row_gap_threshold=args.row_gap)

    if args.output:
        out_path = Path(args.output)
        out_path.write_text(markdown + "\n")
        print(f"Written to {out_path}", file=sys.stderr)
    else:
        print(markdown)


if __name__ == "__main__":
    main()
