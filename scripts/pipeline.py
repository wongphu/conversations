#!/usr/bin/env python3
"""
Build a refined conversation: clips → audio → HTML (+ index) → check.

Usage:
    python scripts/pipeline.py <conversation_number> [--skip-audio]

Example:
    python scripts/pipeline.py 10

Starts from texts/NN.md, so run it after the refine step (OCR and refine come
first; see AGENTS.md), which also gives it the "Level: A2" line the index needs. Safe to re-run after editing texts/NN.md: it deletes the
MP3s of only the lines whose text changed, and generate_audio.py voices just
those (plus any new lines). Unchanged lines keep their audio, since re-voicing
them would drift the voices slightly. It never passes --force.
"""

import argparse
import json
import subprocess
import sys
from pathlib import Path

from generate_html import parse_level

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = PROJECT_ROOT / "scripts"
DOCS_DIR = PROJECT_ROOT / "docs"
TEXTS_DIR = PROJECT_ROOT / "texts"


def run(script: str, *args: str) -> None:
    print(f"\n== {script} {' '.join(args)}", flush=True)
    result = subprocess.run([sys.executable, str(SCRIPTS_DIR / script), *args], cwd=PROJECT_ROOT)
    if result.returncode:
        sys.exit(f"Error: {script} failed (exit {result.returncode})")


def spoken(text: str) -> str:
    """The text as generate_audio.py voices it (italic markers are display-only)."""
    return text.replace("*", "")


def delete_changed_audio(old_clips: list[dict], new_clips: list[dict]) -> None:
    """Delete MP3s whose line now has different text, so they get re-voiced."""
    old_text = {clip["file"]: spoken(clip["text"]) for clip in old_clips}
    for clip in new_clips:
        mp3 = DOCS_DIR / clip["file"]
        before = old_text.get(clip["file"])
        if before is not None and before != spoken(clip["text"]) and mp3.exists():
            mp3.unlink()
            print(f"  text changed, deleted {clip['file']} to re-voice it")


def main():
    parser = argparse.ArgumentParser(description="Build a refined conversation: clips, audio, HTML, check.")
    parser.add_argument("conversation", type=int, help="Conversation number")
    parser.add_argument("--skip-audio", action="store_true",
                        help="Don't generate audio (e.g. off Apple Silicon); check will flag missing MP3s")
    args = parser.parse_args()

    conv = str(args.conversation)
    texts_path = TEXTS_DIR / f"{conv}.md"
    if not texts_path.exists():
        sys.exit(f"Error: texts/{conv}.md not found; OCR and refine it first")
    if parse_level(texts_path.read_text()) is None:
        sys.exit(f"Error: texts/{conv}.md has no CEFR level; add a 'Level: A2' line under "
                 f"the title (the refine step, scripts/refine_ocr.md)")

    clips_path = DOCS_DIR / conv / "clips.json"
    old_clips = json.loads(clips_path.read_text()) if clips_path.exists() else []
    run("make_clips.py", f"texts/{conv}.md", conv, "-o", f"docs/{conv}/clips.json")
    delete_changed_audio(old_clips, json.loads(clips_path.read_text()))

    if not args.skip_audio:
        run("generate_audio.py", conv)
    run("generate_html.py", conv)
    run("check.py", conv)


if __name__ == "__main__":
    main()
