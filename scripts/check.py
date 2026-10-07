#!/usr/bin/env python3
"""
Check that the built conversations are complete and up to date.

Usage:
    python scripts/check.py [<conversation_number>]

Example:
    python scripts/check.py        # every conversation, and the index
    python scripts/check.py 10     # one conversation, and the index

Problems (exit status 1):
    - texts/NN.md has no "Level: A1…C2" line (the CEFR level the index shows)
    - docs/NN/clips.json, docs/NN.html or docs/index.html differ from what
      make_clips.py / generate_html.py would produce from the current sources
    - an MP3 in clips.json is missing or empty, or an MP3 on disk is in no
      clips.json (orphan), or a .part file was left by an interrupted run
    - a clip's voice has no reference WAV in voices/

Notes (informational):
    - inputs/NN.jpeg or ocrs/NN.md without texts/NN.md (not refined yet)
    - texts/NN.md not built yet
    - voices no conversation uses

It can't tell whether an existing MP3 still says its clip's current text:
pipeline.py handles that by deleting the MP3s of lines whose text changed.
"""

import argparse
import json
import sys
from pathlib import Path

from generate_html import generate_html, generate_index, parse_level
from make_clips import build_clips, parse_markdown_table

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DOCS_DIR = PROJECT_ROOT / "docs"
TEXTS_DIR = PROJECT_ROOT / "texts"
VOICES_DIR = PROJECT_ROOT / "voices"


def conversation_numbers() -> set[int]:
    """Every conversation with a source or a built file."""
    paths = [*(PROJECT_ROOT / "inputs").glob("*.jpeg"), *(PROJECT_ROOT / "ocrs").glob("*.md"),
             *TEXTS_DIR.glob("*.md"), *DOCS_DIR.glob("*.html"), *DOCS_DIR.glob("*/clips.json")]
    stems = [p.parent.name if p.name == "clips.json" else p.stem for p in paths]
    return {int(s) for s in stems if s.isdigit()}


def check_conversation(conv: int, problems: list[str], notes: list[str]) -> set[str]:
    """Check one conversation; returns the voices its clips use."""
    texts_path = TEXTS_DIR / f"{conv}.md"
    clips_path = DOCS_DIR / str(conv) / "clips.json"
    page_path = DOCS_DIR / f"{conv}.html"

    if not texts_path.exists():
        if clips_path.exists() or page_path.exists():
            problems.append(f"{conv}: built, but texts/{conv}.md is missing")
        else:
            notes.append(f"{conv}: not refined yet (no texts/{conv}.md)")
        return set()
    if parse_level(texts_path.read_text()) is None:
        problems.append(f"{conv}: texts/{conv}.md has no CEFR level "
                        f"(add a 'Level: A2' line under the title; see scripts/refine_ocr.md)")
    if not clips_path.exists():
        notes.append(f"{conv}: not built yet (run scripts/pipeline.py {conv})")
        return set()

    clips = json.loads(clips_path.read_text())
    expected = build_clips(parse_markdown_table(texts_path.read_text()), conv)
    if clips != expected:
        problems.append(f"{conv}: clips.json is out of date with texts/{conv}.md")

    for clip in clips:
        mp3 = DOCS_DIR / clip["file"]
        if not mp3.exists():
            problems.append(f"{conv}: missing {clip['file']}")
        elif mp3.stat().st_size == 0:
            problems.append(f"{conv}: empty {clip['file']}")

    listed = {DOCS_DIR / clip["file"] for clip in clips}
    audio_dir = DOCS_DIR / str(conv) / "audio"
    for path in sorted(audio_dir.rglob("*")):
        if path.suffix == ".part":
            problems.append(f"{conv}: leftover {path.relative_to(DOCS_DIR)} (interrupted run; delete it)")
        elif path.is_file() and path not in listed:
            problems.append(f"{conv}: orphan {path.relative_to(DOCS_DIR)} (in no clip; delete it)")

    if not page_path.exists():
        problems.append(f"{conv}: docs/{conv}.html is missing")
    elif page_path.read_text() != generate_html(conv):
        problems.append(f"{conv}: docs/{conv}.html is out of date "
                        f"(run scripts/generate_html.py {conv}, or --all after editing player.js)")

    return {clip["speaker"] for clip in clips}


def main():
    parser = argparse.ArgumentParser(description="Check built conversations are complete and up to date.")
    parser.add_argument("conversation", type=int, nargs="?", help="Conversation number (default: all)")
    args = parser.parse_args()

    problems: list[str] = []
    notes: list[str] = []
    convs = [args.conversation] if args.conversation is not None else sorted(conversation_numbers())
    used_voices = set()
    for conv in convs:
        used_voices |= check_conversation(conv, problems, notes)

    for voice in sorted(used_voices):
        lang = voice.split("_")[0]
        if not (VOICES_DIR / f"{voice}.{lang}.wav").exists():
            problems.append(f"voice {voice}: no voices/{voice}.{lang}.wav")
    if args.conversation is None:
        defined = json.loads((VOICES_DIR / "voices.json").read_text())["speakers"]
        for voice in sorted(set(defined) - used_voices):
            notes.append(f"voice {voice}: not used by any conversation")

    if (DOCS_DIR / "index.html").read_text() != generate_index():
        problems.append("docs/index.html is out of date (run scripts/generate_html.py)")

    for note in notes:
        print(f"  note     {note}")
    for problem in problems:
        print(f"  PROBLEM  {problem}")
    checked = f"conversation {args.conversation}" if args.conversation is not None else f"{len(convs)} conversations"
    print(f"{checked}: {len(problems)} problem(s), {len(notes)} note(s)")
    sys.exit(1 if problems else 0)


if __name__ == "__main__":
    main()
