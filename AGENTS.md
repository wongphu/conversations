# AGENTS.md

Notes for coding agents (pi, etc.) working in this repo. `README.md` has the full
project description and design rationale; this file is the operational runbook and
the non-obvious gotchas. Prefer this for *how to act*; consult README for *why*.

## What this is
Bilingual (English/Spanish) textbook conversation pages, each rendered as a
self-contained HTML page with voice-cloned TTS audio, built from textbook page
images.

## The pipeline
```
inputs/NN.jpeg
  └─(extract_text.py)─→  ocrs/NN.md        # raw OCR: 2 positional columns, either order, has typos + annotations
       └─(refine step, YOU)─→  texts/NN.md  # agent step: title + EN-left/ES-right + fixes
            └─(make_clips.py)─→  docs/NN/clips.json
                 ├─(generate_audio.py)─→  docs/NN/audio/{en,es}/*.mp3
                 └─(generate_html.py)─→  docs/NN.html
```

Run every script from the **project root** with the project venv:

```bash
.venv/bin/python scripts/<name>.py ...
```

The venv is Python 3.14 and gitignored. Deps: `mlx-audio`, `rapidocr`, `soundfile`,
`transformers`, plus system `ffmpeg` (`brew install ffmpeg`). Source page images go
in `inputs/`.

After a full run (through `generate_html.py`), one **manual** step remains: add the
new page to `docs/index.html`. No script updates the index (see the Gotchas below).

## The refine step is YOUR job (there is no script for it)
`scripts/refine_ocr.md` documents an **agent step**, not a runnable program. When
asked to run the pipeline (or anything up to refine) for a page, **you** perform it:
read `ocrs/NN.md`, apply the transforms in `refine_ocr.md`, write `texts/NN.md`.

The transforms:
1. Add a title: conversation number + English title + Spanish translation
   (e.g. `# 41. Hotel Check-In — Check-in en el hotel`). Number comes from the filename.
2. Normalize to **English on the left, Spanish on the right** (the raw OCR may be reversed).
3. Fix typos / inconsistent speaker labels / broken punctuation.
4. **Remove stray textbook annotations** that OCR picks up (e.g. `Nota: ...`) — they
   are marginal notes, not dialogue.

Preserve the dialogue: correct errors only; do not reword, translate, add, or remove
lines. One row = one utterance; keep the row count unchanged.

## Gotchas (learned the hard way)
- **Raw OCR column order is positional, not labeled.** `extract_text.py` writes no
  `| English | Spanish |` header — just left/right cells. The refine step is what
  guarantees English-left/Spanish-right.
- **`make_clips.py` detects language per *column* (accented chars), not per line,** and
  assigns speakers by row parity (row 0→a, 1→b, 2→a…). A Spanish annotation leaking
  into the English column can flip the *whole* column to `es`. Fix the source in the
  refine step; don't patch the detector.
- **clips.json column *ordering* is cosmetic.** `generate_html.py` groups by row+lang
  and `generate_audio.py` by file path, so en-first vs es-first never changes the page
  or the audio. Don't "fix" it for its own sake.
- **`generate_audio.py` skips existing MP3s** unless `--force`. To re-voice only the
  lines whose text changed, delete just those MP3s and run without `--force`. Do **not**
  `--force` a whole conversation to change a couple of lines: voice cloning varies
  run-to-run, so unchanged lines would get slightly different voices.
- **mlx-audio logs `Language: en` even for Spanish.** The script drives Spanish via the
  voice-cloned reference WAV (`voices/es_*.wav`), not a language arg. It's pre-existing
  and uniform, so a conversation stays internally consistent. (Optional: pass
  `language="es"` in the `generate_audio()` call for crisper Spanish — but that means
  re-voicing the whole Spanish set.)
- **`PROJECT_ROOT`** in `generate_audio.py` was once `Path(__file__).parent` (→ `scripts/`),
  which silently broke `docs/`/`voices/` lookups. It's now `Path(__file__).resolve().parent.parent`.
  If you refactor paths, keep it CWD-independent.
- **`docs/index.html` is hand-maintained — no script writes it.** `generate_html.py`
  only emits `docs/NN.html`; the landing-page listing is not touched, so a "finished"
  conversation is silently missing from the index. After finishing a page, add its link
  by hand, keeping the list in ascending conversation-number order:
  `<li><a href="NN.html"><span class="num">NN</span> English title / Spanish title</a></li>`.
  Note the index joins the two titles with a slash (`English / Spanish`), whereas each
  page's H1 uses an em dash.

## Voices
`voices/voices.json` defines 4 speakers — `en_a`/`es_a` (woman, 40s) and `en_b`/`es_b`
(man, 60s) — each with a reference WAV that is cloned for all of that speaker's lines.
A voice clones only its own language.

## Platform / performance
TTS is Qwen3-TTS 1.7B via `mlx-audio` — **MLX / Apple Silicon only**. Models live in the
HuggingFace cache. The first `generate_audio` call pays a one-time model-load cost
(~seconds); each clip is a few seconds of inference.

## Naming
```
docs/{conv}/audio/{lang}/{row}-{speaker}.mp3   # row zero-padded (00, 01…), speaker a|b
docs/{conv}/clips.json
docs/{conv}.html
docs/index.html                       # hand-maintained landing page; add one link per conversation
```
