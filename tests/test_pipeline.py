"""Tests for scripts/pipeline.py and scripts/check.py.

Run from the project root:
    .venv/bin/python -m unittest discover tests
"""

import contextlib
import io
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))

import pipeline  # noqa: E402


def clip(file: str, text: str) -> dict:
    return {"file": file, "speaker": "en_a", "lang": "en", "text": text}


class DeleteChangedAudio(unittest.TestCase):
    def test_deletes_only_changed_lines(self):
        with tempfile.TemporaryDirectory() as tmp:
            docs = Path(tmp)
            for name in ("00-a", "01-b", "02-a"):
                (docs / f"{name}.mp3").write_bytes(b"mp3")
            old = [clip("00-a.mp3", "Hello."), clip("01-b.mp3", "Hi *there*."), clip("02-a.mp3", "Bye.")]
            new = [clip("00-a.mp3", "Hello!"),        # changed: re-voice
                   clip("01-b.mp3", "Hi there."),     # only italics changed: keep
                   clip("02-a.mp3", "Bye."),          # unchanged: keep
                   clip("03-b.mp3", "New line.")]     # new: nothing to delete
            with mock.patch.object(pipeline, "DOCS_DIR", docs), \
                    contextlib.redirect_stdout(io.StringIO()):
                pipeline.delete_changed_audio(old, new)
            self.assertEqual(sorted(p.name for p in docs.iterdir()), ["01-b.mp3", "02-a.mp3"])


class CheckRepository(unittest.TestCase):
    def test_committed_conversations_have_no_problems(self):
        result = subprocess.run([sys.executable, "scripts/check.py"], cwd=PROJECT_ROOT,
                                capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stdout)


if __name__ == "__main__":
    unittest.main()
