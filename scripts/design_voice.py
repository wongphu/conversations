#!/usr/bin/env python3
"""
Design a speaker's reference voice with the Qwen3-TTS VoiceDesign model.

Usage:
    python scripts/design_voice.py <speaker> [<speaker> ...] [--force]

Example:
    python scripts/design_voice.py en_c es_c

Reads:
    voices/voices.json          – the speaker's "instruct" (voice description),
                                  "lang", and "ref_<lang>" (the sentence to say)

Writes:
    voices/<speaker>.<lang>.wav – the reference WAV generate_audio.py clones

A designed voice is random: each run gives a different person. Listen to the
WAV and re-run with --force until it fits. Once lines are voiced with it,
changing it means re-voicing that speaker in every conversation.
"""

import argparse
import json
import shutil
import sys
import tempfile
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
VOICES_DIR = PROJECT_ROOT / "voices"

LANGUAGES = {"en": "english", "es": "spanish"}


def main():
    parser = argparse.ArgumentParser(description="Design reference voices from voices.json.")
    parser.add_argument("speakers", nargs="+", help="Speaker ids (e.g. en_c es_c)")
    parser.add_argument("--force", action="store_true", help="Overwrite an existing WAV")
    args = parser.parse_args()

    config = json.loads((VOICES_DIR / "voices.json").read_text())
    jobs = []
    for speaker_id in args.speakers:
        speaker = config["speakers"].get(speaker_id)
        if not speaker:
            sys.exit(f"Error: {speaker_id} is not in voices/voices.json")
        lang = speaker["lang"]
        out_path = VOICES_DIR / f"{speaker_id}.{lang}.wav"
        if out_path.exists() and not args.force:
            sys.exit(f"Error: {out_path} exists (use --force to replace it)")
        jobs.append((speaker, lang, out_path))

    from mlx_audio.tts.generate import generate_audio
    from mlx_audio.tts.utils import load_model

    model = load_model(model_path=config["voice_design_model"])

    for speaker, lang, out_path in jobs:
        print(f"Designing {out_path.name}: {speaker['instruct']}")
        with tempfile.TemporaryDirectory() as tmpdir:
            generate_audio(
                text=speaker[f"ref_{lang}"],
                model=model,
                instruct=speaker["instruct"],
                lang_code=LANGUAGES[lang],
                output_path=tmpdir,
                file_prefix="voice",
                verbose=False,
            )
            wavs = list(Path(tmpdir).glob("*.wav"))
            if not wavs:
                sys.exit(f"Error: no audio generated for {out_path.name}")
            shutil.move(wavs[0], out_path)
        print(f"  ✓ {out_path}")


if __name__ == "__main__":
    main()
