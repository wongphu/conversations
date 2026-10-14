"""Tests for scripts/generate_audio.py's pitch check (the TTS itself needs the models).

Run from the project root:
    .venv/bin/python -m unittest discover tests
"""

import contextlib
import io
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import numpy as np
import soundfile as sf

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))

import generate_audio  # noqa: E402
from generate_audio import MAX_TAKES, best_take, median_pitch, semitones  # noqa: E402


class MedianPitch(unittest.TestCase):
    def write(self, samples: np.ndarray) -> Path:
        path = Path(self.tmp.name) / "clip.wav"
        sf.write(path, samples, 24000)
        return path

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)

    def test_measures_a_voice_like_tone(self):
        t = np.arange(24000) / 24000
        tone = sum(np.sin(2 * np.pi * 220 * k * t) / k for k in range(1, 6)) * 0.2
        self.assertAlmostEqual(median_pitch(self.write(tone)), 220, delta=1)

    def test_silence_has_no_pitch(self):
        self.assertIsNone(median_pitch(self.write(np.zeros(24000))))

    def test_semitones(self):
        self.assertAlmostEqual(semitones(440, 220), 12)
        self.assertAlmostEqual(semitones(220, 440), -12)


class BestTake(unittest.TestCase):
    """best_take() with fake takes: take n's pitch is pitches[n - 1]."""

    def run_takes(self, pitches: list, ref_pitch=232.0) -> tuple[Path | None, list[int]]:
        recorded = []

        def record(n):
            recorded.append(n)
            return None if pitches[n - 1] == "no audio" else Path(f"take{n}.wav")

        def pitch_of(wav):
            return pitches[int(wav.stem[4:]) - 1]

        with mock.patch.object(generate_audio, "median_pitch", pitch_of), \
                contextlib.redirect_stdout(io.StringIO()):
            return best_take(record, ref_pitch), recorded

    def test_keeps_a_first_take_on_pitch(self):
        self.assertEqual(self.run_takes([250]), (Path("take1.wav"), [1]))

    def test_re_records_until_on_pitch(self):
        # 333 Hz is +6.2 semitones from 232 Hz, 180 Hz is -4.4: both re-recorded
        self.assertEqual(self.run_takes([333, 180, 240]), (Path("take3.wav"), [1, 2, 3]))

    def test_accepts_a_take_just_inside_the_limit(self):
        self.assertEqual(self.run_takes([185]), (Path("take1.wav"), [1]))  # -3.9 semitones

    def test_keeps_the_closest_when_no_take_is_on_pitch(self):
        wav, recorded = self.run_takes([333, 300, 175, 346, 310])
        self.assertEqual(recorded, list(range(1, MAX_TAKES + 1)))
        self.assertEqual(wav, Path("take2.wav"))  # 300 Hz: +4.4 semitones, the closest

    def test_retries_a_take_without_audio(self):
        self.assertEqual(self.run_takes(["no audio", 230]), (Path("take2.wav"), [1, 2]))
        self.assertEqual(self.run_takes(["no audio"] * MAX_TAKES), (None, list(range(1, MAX_TAKES + 1))))

    def test_keeps_a_take_too_short_to_judge(self):
        self.assertEqual(self.run_takes([None]), (Path("take1.wav"), [1]))
        self.assertEqual(self.run_takes([400], ref_pitch=None), (Path("take1.wav"), [1]))


if __name__ == "__main__":
    unittest.main()
