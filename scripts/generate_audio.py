#!/usr/bin/env python3
"""
Generate audio clips for a conversation using Qwen3-TTS 1.7B voice cloning (MLX).

Usage:
    python generate_audio.py <conversation_number> [--force]

Example:
    python generate_audio.py 36
    python generate_audio.py 99 --force

Reads:
    voices/voices.json          – model names and speaker definitions
    voices/<speaker>.<lang>.wav – reference voice samples
    docs/<N>/clips.json         – list of clips to generate

Writes:
    docs/<N>/<file>             – generated MP3 audio clips

Dependencies:
    pip install mlx-audio soundfile
    brew install ffmpeg
"""

import argparse
import json
import subprocess
import sys
import tempfile
from pathlib import Path

import soundfile as sf

# --- Config ---

PROJECT_ROOT = Path(__file__).parent
VOICES_DIR = PROJECT_ROOT / "voices"
DOCS_DIR = PROJECT_ROOT / "docs"


def load_json(path: Path) -> dict | list:
    with open(path) as f:
        return json.load(f)


def wav_to_mp3(wav_path: Path, mp3_path: Path) -> None:
    """Convert WAV to MP3 via ffmpeg."""
    subprocess.run(
        ["ffmpeg", "-y", "-loglevel", "error", "-i", str(wav_path),
         "-codec:a", "libmp3lame", "-qscale:a", "2", str(mp3_path)],
        check=True,
    )
    wav_path.unlink()


def main():
    parser = argparse.ArgumentParser(description="Generate TTS audio clips for a conversation.")
    parser.add_argument("conversation", type=int, help="Conversation number (e.g. 36, 99)")
    parser.add_argument("--force", action="store_true", help="Regenerate even if file exists")
    parser.add_argument("--model", type=str, default=None, help="Override clone model name")
    args = parser.parse_args()

    conv_num = args.conversation
    clips_path = DOCS_DIR / str(conv_num) / "clips.json"
    if not clips_path.exists():
        sys.exit(f"Error: {clips_path} not found")

    # Load config
    voices_config = load_json(VOICES_DIR / "voices.json")
    clips = load_json(clips_path)

    model_name = args.model or voices_config["clone_model"]
    print(f"Model:   {model_name}")
    print(f"Clips:   {clips_path}")
    print(f"Output:  {DOCS_DIR / str(conv_num)}/")
    print()

    # Import mlx-audio (loads model on first call)
    from mlx_audio.tts.generate import generate_audio

    # Determine which clips to generate
    to_generate = []
    for clip in clips:
        out_path = DOCS_DIR / clip["file"]
        if out_path.exists() and not args.force:
            print(f"  SKIP  {clip['file']} (exists)")
            continue
        to_generate.append(clip)

    if not to_generate:
        print("\nAll clips already exist. Use --force to regenerate.")
        return

    print(f"Generating {len(to_generate)} clips...\n")

    for i, clip in enumerate(to_generate, 1):
        out_path = DOCS_DIR / clip["file"]
        out_path.parent.mkdir(parents=True, exist_ok=True)

        speaker = clip["speaker"]
        lang = clip["lang"]
        text = clip["text"]

        ref_path = VOICES_DIR / f"{speaker}.{lang}.wav"
        if not ref_path.exists():
            sys.exit(f"Error: reference audio not found: {ref_path}")

        print(f"  [{i}/{len(to_generate)}] {clip['file']}")
        print(f"         {speaker}  \"{text[:60]}{'...' if len(text) > 60 else ''}\"")

        # Generate into a temp directory (mlx-audio uses output_path as a dir)
        with tempfile.TemporaryDirectory() as tmpdir:
            generate_audio(
                text=text,
                model=model_name,
                ref_audio=str(ref_path),
                output_path=tmpdir,
                file_prefix="clip",
                verbose=False,
            )

            # Find the generated WAV
            wavs = list(Path(tmpdir).glob("*.wav"))
            if not wavs:
                print(f"         ✗ no output generated")
                continue

            wav_path = wavs[0]
            duration = sf.info(str(wav_path)).duration

            # Convert to MP3
            wav_to_mp3(wav_path, out_path)

        print(f"         ✓ saved ({duration:.1f}s)")

    print(f"\nDone. Generated {len(to_generate)} clips.")


if __name__ == "__main__":
    main()
