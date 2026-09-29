#!/bin/sh
# First-time setup (safe to re-run): creates .venv with the pinned Python
# dependencies, checks the system requirements, and runs the tests.
#
#     scripts/setup.sh
#
# Needs: macOS on Apple Silicon (the TTS is MLX-only), Python 3.14
# (brew install python@3.14) and ffmpeg (brew install ffmpeg).
set -eu
cd "$(dirname "$0")/.."

PYTHON_VERSION=$(cat .python-version)
missing=0

if [ "$(uname -sm)" != "Darwin arm64" ]; then
  echo "warning: audio generation (mlx-audio) needs macOS on Apple Silicon; OCR, clips," \
       "HTML and check still work (use pipeline.py --skip-audio)"
fi

if ! command -v ffmpeg >/dev/null 2>&1; then
  echo "error: ffmpeg not found (brew install ffmpeg); generate_audio.py needs it"
  missing=1
fi

if [ -x .venv/bin/python ]; then
  have=$(.venv/bin/python -c 'import sys; print("%d.%d" % sys.version_info[:2])')
  if [ "$have" != "$PYTHON_VERSION" ]; then
    echo "error: .venv is Python $have, not $PYTHON_VERSION; delete .venv and re-run"
    exit 1
  fi
else
  python=$(command -v "python$PYTHON_VERSION" || true)
  if [ -z "$python" ]; then
    echo "error: python$PYTHON_VERSION not found (brew install python@$PYTHON_VERSION)"
    exit 1
  fi
  echo "Creating .venv with $python"
  "$python" -m venv .venv
fi

echo "Installing requirements.txt"
.venv/bin/pip install --quiet --disable-pip-version-check -r requirements.txt

echo "Running tests"
.venv/bin/python -m unittest discover tests

if [ "$missing" -ne 0 ]; then
  exit 1
fi
echo "Setup OK. The first audio run downloads the TTS and Whisper models (several GB)."
