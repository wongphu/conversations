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
    voices/pronunciations.json  – optional phonetic respellings for the TTS
    docs/<N>/clips.json         – list of clips to generate

Writes:
    docs/<N>/<file>             – generated MP3 audio clips

Each new clip's pitch is checked against its voice's reference WAV: a take
whose median pitch is PITCH_TOLERANCE semitones or more off is recorded
again, up to MAX_TAKES takes, keeping the closest. Voice cloning varies take
to take, and an off-pitch line sounds like a different mood next to its
neighbours. Existing MP3s are not re-checked.

Dependencies:
    pip install mlx-audio soundfile praat-parselmouth
    brew install ffmpeg
"""

import argparse
import json
import math
import re
import subprocess
import sys
import tempfile
from pathlib import Path

import numpy as np
import parselmouth
import soundfile as sf

# --- Config ---

PROJECT_ROOT = Path(__file__).resolve().parent.parent
VOICES_DIR = PROJECT_ROOT / "voices"
DOCS_DIR = PROJECT_ROOT / "docs"

# Transcribes each reference WAV (its text is part of the voice-cloning prompt).
# Same model mlx-audio's generate_audio() defaults to when no ref_text is given.
STT_MODEL = "mlx-community/whisper-large-v3-turbo-asr-fp16"

# Pitch check: re-record a take whose median pitch is this many semitones or
# more from its voice's reference WAV, keeping the closest of MAX_TAKES takes.
PITCH_TOLERANCE = 4.0
MAX_TAKES = 5
PITCH_FLOOR, PITCH_CEILING = 75, 600  # Hz; covers the voices without octave errors
MIN_VOICED_FRAMES = 10  # ~0.1 s of voiced sound; less is too little to judge


def load_json(path: Path) -> dict | list:
    with open(path) as f:
        return json.load(f)


def apply_pronunciations(text: str, lang: str, pronunciations: dict) -> str:
    """Swap whole words for their phonetic respellings (TTS input only)."""
    for word, spoken in pronunciations.get(lang, {}).items():
        text = re.sub(rf"\b{re.escape(word)}\b", spoken, text)
    return text


def median_pitch(path: Path) -> float | None:
    """Median pitch (Hz) of a recording's voiced parts, or None if too little is voiced."""
    pitch = parselmouth.Sound(str(path)).to_pitch(pitch_floor=PITCH_FLOOR, pitch_ceiling=PITCH_CEILING)
    f0 = pitch.selected_array["frequency"]
    voiced = f0[f0 > 0]
    return float(np.median(voiced)) if len(voiced) >= MIN_VOICED_FRAMES else None


def semitones(pitch: float, ref: float) -> float:
    return 12 * math.log2(pitch / ref)


def best_take(record, ref_pitch: float | None) -> Path | None:
    """Record takes until one is within PITCH_TOLERANCE of ref_pitch, at most MAX_TAKES.

    record(n) records take n and returns its WAV (None if nothing was generated).
    Returns the take closest to the reference pitch, or None if no take produced audio.
    """
    best, best_off = None, math.inf
    for n in range(1, MAX_TAKES + 1):
        wav = record(n)
        if wav is None:
            continue
        pitch = median_pitch(wav)
        if pitch is None or ref_pitch is None:
            return wav  # too short to judge: keep it
        off = semitones(pitch, ref_pitch)
        if abs(off) < abs(best_off):
            best, best_off = wav, off
        if abs(off) < PITCH_TOLERANCE:
            return wav
        print(f"         take {n}: pitch {pitch:.0f} Hz, {off:+.1f} semitones from the voice's "
              f"{ref_pitch:.0f} Hz" + ("; recording another" if n < MAX_TAKES else ""))
    if best is not None:
        print(f"         ! kept the closest of {MAX_TAKES} takes ({best_off:+.1f} semitones)")
    return best


def wav_to_mp3(wav_path: Path, mp3_path: Path) -> None:
    """Convert WAV to MP3 via ffmpeg.

    Encodes to a temporary name first, so an interrupted run never leaves a
    partial MP3 that later runs would skip as "exists".
    """
    part_path = mp3_path.with_name(mp3_path.name + ".part")
    subprocess.run(
        ["ffmpeg", "-y", "-loglevel", "error", "-i", str(wav_path),
         "-codec:a", "libmp3lame", "-qscale:a", "2", "-f", "mp3", str(part_path)],
        check=True,
    )
    part_path.replace(mp3_path)
    wav_path.unlink()


def transcribe_refs(ref_paths: list[Path], sample_rate: int) -> dict[Path, str]:
    """Transcribe each reference WAV once, loading the STT model once.

    Mirrors what generate_audio() does per call when ref_text is omitted, so
    the cloning prompt (and the voices) stay the same as before.
    """
    import mlx.core as mx
    from mlx_audio.stt import load as load_stt_model
    from mlx_audio.utils import load_audio

    stt_model = load_stt_model(STT_MODEL)
    texts = {}
    for path in ref_paths:
        audio = load_audio(str(path), sample_rate=sample_rate, volume_normalize=False)
        texts[path] = stt_model.generate(audio).text
        print(f"  ref   {path.name}: {texts[path]}")
    del stt_model
    mx.clear_cache()
    return texts


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
    pronunciations_path = VOICES_DIR / "pronunciations.json"
    pronunciations = load_json(pronunciations_path) if pronunciations_path.exists() else {}
    clips = load_json(clips_path)

    model_name = args.model or voices_config["clone_model"]
    print(f"Model:   {model_name}")
    print(f"Clips:   {clips_path}")
    print(f"Output:  {DOCS_DIR / str(conv_num)}/")
    print()

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

    ref_paths = {clip["file"]: VOICES_DIR / f"{clip['speaker']}.{clip['lang']}.wav"
                 for clip in to_generate}
    for ref_path in set(ref_paths.values()):
        if not ref_path.exists():
            sys.exit(f"Error: reference audio not found: {ref_path}")

    # Load the TTS model once; passing generate_audio() a model *name* would
    # reload it (and re-transcribe the reference WAV) on every clip.
    from mlx_audio.tts.generate import generate_audio
    from mlx_audio.tts.utils import load_model

    model = load_model(model_path=model_name)
    ref_texts = transcribe_refs(sorted(set(ref_paths.values())), model.sample_rate)
    ref_pitches = {path: median_pitch(path) for path in ref_texts}

    print(f"\nGenerating {len(to_generate)} clips...\n")
    failed = 0

    for i, clip in enumerate(to_generate, 1):
        out_path = DOCS_DIR / clip["file"]
        out_path.parent.mkdir(parents=True, exist_ok=True)

        speaker = clip["speaker"]
        text = clip["text"].replace("*", "")  # markdown italics are display-only
        text = apply_pronunciations(text, clip["lang"], pronunciations)
        ref_path = ref_paths[clip["file"]]

        print(f"  [{i}/{len(to_generate)}] {clip['file']}")
        print(f"         {speaker}  \"{text[:60]}{'...' if len(text) > 60 else ''}\"")

        # Generate into a temp directory (mlx-audio uses output_path as a dir),
        # one subdirectory per take
        with tempfile.TemporaryDirectory() as tmpdir:
            def record(take: int) -> Path | None:
                take_dir = Path(tmpdir) / f"take{take}"
                take_dir.mkdir()
                generate_audio(
                    text=text,
                    model=model,
                    ref_audio=str(ref_path),
                    ref_text=ref_texts[ref_path],
                    output_path=str(take_dir),
                    file_prefix="clip",
                    verbose=False,
                )
                return next(take_dir.glob("*.wav"), None)

            wav_path = best_take(record, ref_pitches[ref_path])
            if wav_path is None:
                print(f"         ✗ no output generated")
                failed += 1
                continue

            duration = sf.info(str(wav_path)).duration

            # Convert to MP3
            wav_to_mp3(wav_path, out_path)

        print(f"         ✓ saved ({duration:.1f}s)")

    print(f"\nDone. Generated {len(to_generate) - failed} clips.")
    if failed:
        sys.exit(f"Error: {failed} clip(s) produced no audio")


if __name__ == "__main__":
    main()
