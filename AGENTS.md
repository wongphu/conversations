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

The venv is Python 3.14 and gitignored. Deps are pinned in `requirements.txt`
(`.venv/bin/pip install -r requirements.txt`), plus system `ffmpeg` (`brew install ffmpeg`). Source page images go
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
lines. One row = one utterance; keep the row count unchanged — except when the OCR
merged two speakers' turns into one row: split those (and flag it).

## Gotchas (learned the hard way)
- **Raw OCR column order is positional, not labeled.** `extract_text.py` writes no
  `| English | Spanish |` header — just left/right cells. The refine step is what
  guarantees English-left/Spanish-right.
- **`make_clips.py` detects language per *column*, not per line:** whichever column has
  the higher share of accented chars (`á é í ó ú ñ ¿ ¡ ü`) is `es`. It exits if it can't
  tell. A Spanish annotation leaking into the English column can still tip it. Fix the
  source in the refine step; don't patch the detector.
- **Speakers are assigned by row parity** (row 0→a, 1→b, 2→a…), never by label, and
  every conversation must alternate strictly A, B, A, B. If the textbook gives one
  speaker two turns in a row, or mislabels a row (page 36 does both), the voices still
  alternate.
- **Speaker labels are only stripped if they recur in the column** (a real speaker
  talks more than once). That keeps a leading `No.` / `Mr.` as dialogue, so the refine
  step should give every row a label.
- **clips.json column *ordering* is cosmetic.** `generate_html.py` groups by row+lang
  and `generate_audio.py` by file path, so en-first vs es-first never changes the page
  or the audio. Don't "fix" it for its own sake.
- **`generate_audio.py` skips existing MP3s** unless `--force`. To re-voice only the
  lines whose text changed, delete just those MP3s and run without `--force`. Do **not**
  `--force` a whole conversation to change a couple of lines: voice cloning varies
  run-to-run, so unchanged lines would get slightly different voices.
- **Mispronounced names:** add a phonetic respelling to `voices/pronunciations.json`
  (per language, e.g. `"Tizingal": "Tee-seen-gahl"`). It's applied to the TTS input only;
  the page keeps the real spelling. Then delete just the affected MP3s and re-run.
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
  page's H1 (taken by `generate_html.py` from the `# ...` line of `texts/NN.md`) uses an
  em dash.
- **Conversation 36 predates the pipeline:** it has no `ocrs/36.md` or `texts/36.md`, and
  its `docs/36.html` rows were hand-edited (italics, "Volcan"). Don't run
  `generate_html.py 36`: it would drop those edits and fall back to a generic title.
  Edit `docs/36.html` in place instead.
- **Pages must be served over http** (e.g. `python3 -m http.server -d docs`). They load
  audio with `fetch()`, which browsers block on `file://`. A failed load turns that
  line's play button red.
- **The page player must keep working on old iOS Safari** (a user on an older iPhone
  had buttons but no sound). Don't "modernise" these in `generate_html.py`'s script:
  `window.AudioContext || window.webkitAudioContext` (unprefixed is iOS 14.5+), the
  callback form of `decodeAudioData`, `getChannelData(i).set()` instead of
  `copyToChannel`, creating/resuming the context inside the tap (iOS also has an
  `"interrupted"` state, so check `!== "running"`), and the lazy `import()` of the
  PSOLA stretcher. The ring/silent switch mutes Web Audio on iOS: the page sets
  `navigator.audioSession.type = "playback"` (iOS 16.4+), and on older iOS loops a
  silent `<audio>` element while a clip plays. The script is identical in every
  `docs/NN.html`: after changing it, splice the new `<script type="module">` block
  into each page (including 36) rather than regenerating them.

## Voices
`voices/voices.json` defines 4 speakers — `en_a`/`es_a` (woman, 40s) and `en_b`/`es_b`
(man, 60s) — each with a reference WAV that is cloned for all of that speaker's lines.
A voice clones only its own language.

## Platform / performance
TTS is Qwen3-TTS 1.7B via `mlx-audio` — **MLX / Apple Silicon only**. Models live in the
HuggingFace cache (the first run downloads them, several GB). Each `generate_audio.py`
run loads the TTS model once, and Whisper once to transcribe the reference WAVs (~seconds);
each clip is then a few seconds of inference.

## Naming
```
docs/{conv}/audio/{lang}/{row}-{speaker}.mp3   # row zero-padded (00, 01…), speaker a|b
docs/{conv}/clips.json
docs/{conv}.html
docs/index.html                       # hand-maintained landing page; add one link per conversation
```
