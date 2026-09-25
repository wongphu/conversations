# Conversations

Interactive bilingual (English/Spanish) conversation pages with voice-cloned audio, built from textbook page images.

## How It Works

```
textbook image  →  OCR  →  refine (AI)  →  clips.json  →  TTS  →  HTML page
  inputs/NN.jpeg   ocrs/NN.md   texts/NN.md    docs/NN/...    docs/NN.html
  (extract_text.py) (refine_ocr.md) (make_clips.py) (generate_audio.py) (generate_html.py)
```

Each conversation page is a self-contained HTML file with:
- A two-column table (English left, Spanish right)
- Play buttons on each line
- A speed slider (50%–150%) that changes playback rate without pitch distortion

## Directory Structure

```
├── voices/                  # Shared voice resources
│   ├── voices.json          # Model names + speaker definitions
│   ├── en_a.en.wav          # Reference audio for each speaker
│   ├── en_b.en.wav
│   ├── es_a.es.wav
│   └── es_b.es.wav
│
├── docs/
│   ├── 36.html              # Conversation page (interactive)
│   ├── 36/
│   │   ├── clips.json       # Audio clip manifest
│   │   └── audio/
│   │       ├── en/          # English MP3 clips
│   │       └── es/          # Spanish MP3 clips
│   └── 41/
│       ├── clips.json
│       └── audio/
│
├── scripts/
│   ├── extract_text.py      # Image → raw markdown (ocrs/)
│   ├── refine_ocr.md        # AI step: ocrs/ → texts/ (agent task, not a script)
│   ├── make_clips.py        # Markdown (texts/) → clips.json
│   ├── generate_audio.py    # clips.json → MP3 files (TTS)
│   └── generate_html.py     # clips.json → interactive HTML page
│
├── inputs/                  # Source images (textbook pages)
│   ├── 36.jpeg
│   └── 41.jpeg
│
├── ocrs/                    # Raw OCR output (extract_text.py)
│   └── 41.md
│
├── texts/                   # Refined markdown (after the refine step)
│   └── 41.md
└── .venv/                   # Python virtual environment
```

## Scripts

### `extract_text.py` — Image to raw markdown (OCR)

Uses RapidOCR to extract the two-column table from a textbook page image into
`ocrs/`. The column order is whatever appears in the page (left / right), so
the raw output is **not** guaranteed to be English-left / Spanish-right and may
contain OCR errors — the refine step below cleans that up.

```bash
.venv/bin/python scripts/extract_text.py inputs/41.jpeg   # → ocrs/41.md
```

**Design decisions:**
- **RapidOCR** over alternatives (macOS Vision, EasyOCR, PaddleOCR): best Spanish accent accuracy, lightweight (ONNX Runtime, ~10MB models), runs in ~2s per page
- **Gap-based row detection**: lines are grouped into rows by vertical spacing. A gap > 100px indicates a new row; smaller gaps mean continuation within a cell
- **Speaker pattern heuristic**: text matching `^\w+[.:]\s` (e.g., "R:", "A.", "Huésped:") with a gap > 30px from the previous line triggers a new row. This fixes cases where annotation blocks cause rows to merge
- **Column detection**: x-center of each text fragment determines left vs. right column

### Refine OCR output — AI step (`refine_ocr.md`)

A coding-agent step (not a script) that cleans the raw OCR output. It reads
`ocrs/NN.md` and writes a refined `texts/NN.md`, doing three things:

1. Add a title at the top (a short H1 including the conversation number, e.g. `# 41. Hotel Check-In — Check-in en el hotel`).
2. Normalize column order to **English left, Spanish right** (the raw OCR output may be reversed).
3. Correct misspellings and inconsistencies (OCR artifacts, inconsistent speaker labels, broken punctuation) — while preserving the dialogue.

Full instructions live in [`scripts/refine_ocr.md`](scripts/refine_ocr.md). Run it by asking a coding agent such as pi:

> Refine `ocrs/41.md` per `scripts/refine_ocr.md` and write the result to `texts/41.md`.

### `make_clips.py` — Markdown to clips.json

Parses the refined markdown table (from `texts/`) and generates the clip
manifest for audio generation.

```bash
.venv/bin/python scripts/make_clips.py texts/41.md 41 -o docs/41/clips.json
```

**Design decisions:**
- **Column-level language detection**: the entire column is analyzed together (counting Spanish indicator characters: á, é, í, ó, ú, ñ, ¿, ¡) rather than per-line. This is more reliable since each column is always one language
- **Two-person alternating speakers**: rows alternate speaker `a`/`b` (row 0→a, row 1→b, row 2→a…). This avoids issues with inconsistent OCR speaker labels (e.g., "H:" in Spanish vs. "G:" in English for the same person)
- **Speaker label stripping**: regex `^(\w+)[.:]\s+` removes the label from the text. Uses `\w` (not `[a-z]`) to handle accented characters like "Huésped:"

### `generate_audio.py` — Generate Audio Clips

Uses Qwen3-TTS 1.7B with voice cloning to generate MP3 clips.

```bash
.venv/bin/python scripts/generate_audio.py 41
.venv/bin/python scripts/generate_audio.py 41 --force   # regenerate all
```

**Design decisions:**
- **MLX** (not PyTorch): the models are MLX-optimized for Apple Silicon. PyTorch loading of MLX models causes tensor layout mismatches
- **`mlx-audio`** library: provides a simple `generate_audio()` API that handles model loading, voice cloning, and output
- **Voice cloning via reference WAVs**: each speaker has a short reference recording. The model clones that voice for all their lines. References live in `voices/` shared across conversations
- **MP3 output via ffmpeg**: `mlx-audio` outputs WAV; ffmpeg converts to MP3 (libmp3lame, quality 2) for smaller file sizes
- **Skip existing files**: by default, clips that already exist are skipped. Use `--force` to regenerate

### `generate_html.py` — clips.json to HTML

Builds the self-contained `docs/NN.html` page from `docs/NN/clips.json`
(English in the left column, Spanish in the right, with a play button and a
speed control per line).

```bash
.venv/bin/python scripts/generate_html.py 41
```

### HTML Pages — Playback

Each `docs/NN.html` is a self-contained interactive page.

**Design decisions:**
- **PSOLA time-stretching** (`@audio/stretch-psola`): replaces the native `playbackRate` + `preservePitch` approach. PSOLA aligns grains to detected pitch-cycle boundaries, producing significantly fewer artifacts (no metallic/chirping) at speed extremes. Chosen over:
  - `signalsmith-stretch` — overkill (227KB, real-time AudioWorklet) for short clips
  - `rubberband-wasm` — GPLv2 licensing, batch model overkill
  - Native `preservePitch` — basic WSOLA, audible artifacts at 50%/150%
- **Batch reprocessing on speed change**: when the slider moves during playback, the cached decoded buffer is re-processed at the new factor and restarted. Clips are short (1–7s) so this is instant and imperceptible
- **Buffer caching**: decoded `AudioBuffer`s are cached in a `Map` to avoid re-fetching/re-decoding on speed changes or re-playback
- **No build step**: the PSOLA library is loaded via ESM import from CDN (`esm.sh`). Pages work over `file://` or any static server

## Audio File Naming

```
docs/{conv}/audio/{lang}/{row}-{speaker}.mp3
```

- `conv` — conversation number (36, 41)
- `lang` — `en` or `es`
- `row` — zero-padded row index (00, 01, 02…)
- `speaker` — `a` or `b`

## Dependencies

| Package | Purpose |
|---------|---------|
| `mlx-audio` | TTS generation (Qwen3-TTS via MLX) |
| `rapidocr` | OCR (PaddleOCR-based, ONNX Runtime) |
| `soundfile` | WAV read/write |
| `ffmpeg` (system) | MP3 encoding |
| `@audio/stretch-psola` | Browser-side time-stretching (loaded from CDN) |

Python dependencies are in `.venv/`. No `requirements.txt` yet — install with:
```bash
python3 -m venv .venv
.venv/bin/pip install mlx-audio rapidocr soundfile
brew install ffmpeg
```

## Voices

Four voices defined in `voices/voices.json`:

| ID | Description | Language |
|----|-------------|----------|
| `en_a` | Woman, 40s, warm American English | English |
| `en_b` | Man, early 60s, reflective American English | English |
| `es_a` | Woman, 40s, warm Latin American Spanish | Spanish |
| `es_b` | Man, early 60s, reflective Latin American Spanish | Spanish |

Each voice is designed once (using the VoiceDesign model) and the resulting WAV is used as a reference for cloning all subsequent lines.

## Conversation Pipeline (New Page)

Given a new textbook page image:

```bash
# 1. OCR the page image → ocrs/NN.md
.venv/bin/python scripts/extract_text.py inputs/new_page.jpeg -o ocrs/NN.md

# 2. Refine the OCR output (AI agent step) → texts/NN.md
#    Ask a coding agent (e.g. pi) to follow scripts/refine_ocr.md, which
#    reads ocrs/NN.md and writes texts/NN.md, then:
#      - add a title at the top (including the conversation number)
#      - put English in the left column, Spanish in the right column
#      - fix misspellings and inconsistencies

# 3. Generate clips.json from the refined markdown
.venv/bin/python scripts/make_clips.py texts/NN.md NN -o docs/NN/clips.json

# 4. Generate audio
.venv/bin/python scripts/generate_audio.py NN

# 5. Generate the HTML page
.venv/bin/python scripts/generate_html.py NN
```
