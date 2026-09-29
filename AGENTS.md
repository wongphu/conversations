# AGENTS.md

Notes for coding agents (pi, etc.) working in this repo. `README.md` has the full
project description and design rationale; this file is the operational runbook and
the non-obvious gotchas. Prefer this for *how to act*; consult README for *why*.

## What this is
Bilingual (English/Spanish) textbook conversation pages, each rendered as a
static HTML page with voice-cloned TTS audio, built from textbook page
images.

## The pipeline
```
inputs/NN.jpeg
  └─(extract_text.py)─→  ocrs/NN.md        # raw OCR: 2 positional columns, either order, has typos + annotations
       └─(refine step, YOU)─→  texts/NN.md  # agent step: title + EN-left/ES-right + fixes
            └─(make_clips.py)─→  docs/NN/clips.json
                 ├─(generate_audio.py)─→  docs/NN/audio/{en,es}/*.mp3
                 └─(generate_html.py)─→  docs/NN.html + docs/index.html
```

After the refine step, **`scripts/pipeline.py NN`** runs everything below it —
make_clips → generate_audio → generate_html → check — and is safe to re-run after
editing `texts/NN.md` (see the `generate_audio.py` gotcha). **`scripts/check.py [NN]`**
reports what's missing or stale: clips/page/index out of date with their sources,
missing, empty or orphan MP3s, leftover `.part` files, missing voice WAVs, and
pages not refined or built yet. It exits 1 on a problem.

Run every script from the **project root** with the project venv:

```bash
.venv/bin/python scripts/<name>.py ...
```

The venv is Python 3.14 and gitignored. Deps are pinned in `requirements.txt`
(`.venv/bin/pip install -r requirements.txt`), plus system `ffmpeg` (`brew install ffmpeg`). Source page images go
in `inputs/`.

`generate_html.py NN` also rebuilds `docs/index.html`, so a full run needs no manual
steps. `generate_html.py` with no number rebuilds just the index.

Run the tests after changing any script (stdlib `unittest`, no extra deps; well under
a second):

```bash
.venv/bin/python -m unittest discover tests
```

Besides unit tests of the label/speaker/language rules, they check that every
`texts/NN.md` still produces its committed `clips.json`, that every page and the index
match what the generator produces, and that every `data-audio`/`src`/`href` in `docs/`
resolves. So a change that alters committed output fails until you regenerate and commit
it on purpose.

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
merged two speakers' turns into one row: split those (and flag it); or when it broke one
utterance across two rows (an unlabeled continuation row): join those (and flag it).

## Gotchas (learned the hard way)
- **Raw OCR column order is positional, not labeled.** `extract_text.py` writes no
  `| English | Spanish |` header — just left/right cells. The refine step is what
  guarantees English-left/Spanish-right.
- **`make_clips.py` detects language per *column*, not per line:** whichever column has
  the higher share of accented chars (`á é í ó ú ñ ¿ ¡ ü`) is `es`. It exits if it can't
  tell. A Spanish annotation leaking into the English column can still tip it. Fix the
  source in the refine step; don't patch the detector.
- **Speakers are assigned by the English column's labels** when every English cell has
  one: the first label seen is `a`, the next new one `b`, then `c` (e.g. page 10:
  Waiter→a, Customer→b, `Customer 2`→c). So a speaker may take two turns in a row, and
  there can be more than two speakers — but a textbook mislabel now changes the voice,
  so the refine step must fix labels. Labels are `Word` or `Word N` followed by `.`/`:`.
  If any English row is unlabeled, it falls back to row parity (a, b, a, b…).
  Spanish labels don't pick voices; `make_clips.py` only warns if they don't pair 1:1
  with the English ones.
- **Speaker labels are stripped when every row in the column has one**; otherwise only
  labels that recur in the column are (that keeps a leading `No.` / `Mr.` as dialogue).
  Either way, the refine step should give every row a label.
- **clips.json column *ordering* is cosmetic.** `generate_html.py` groups by row+lang
  and `generate_audio.py` by file path, so en-first vs es-first never changes the page
  or the audio. Don't "fix" it for its own sake.
- **`generate_audio.py` skips existing MP3s** unless `--force`. To re-voice only the
  lines whose text changed, delete just those MP3s and run without `--force` —
  `pipeline.py` does exactly this, comparing the old and new `clips.json` (ignoring
  `*italics*`). It can't see a `pronunciations.json` change, so delete those MP3s by
  hand. An existing MP3 is never compared with its text, so `check.py` can't flag a
  stale one either. Do **not**
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
- **`docs/index.html` is generated — don't edit it by hand.** Every `generate_html.py`
  run rewrites it: one link per `docs/NN.html`, in number order, labelled from the
  `# NN. English — Spanish` line of `texts/NN.md` with the em dash shown as a slash.
  To change the index's look, edit `INDEX_HEAD`/`INDEX_ROW`/`INDEX_TAIL` in
  `generate_html.py`. To drop a page from it, delete `docs/NN.html` and re-run.
- **`*italics*` in `texts/NN.md` are display-only:** `generate_html.py` renders them as
  `<em>`, and `generate_audio.py` drops the `*` before TTS. Page 36 uses them to mirror
  the textbook's italics.
- **Conversation 36 predates the pipeline**, so its `texts/36.md` was written to match its
  already-voiced page, not refined from `ocrs/36.md`. Its row 09 audio was voiced from
  "best part, it is free!" while the text now says "part-", so if you re-voice it, the
  new clip will read the dash.
- **Pages must be served over http** (e.g. `python3 -m http.server -d docs`). They load
  audio with `fetch()`, which browsers block on `file://`. A failed load turns that
  line's play button red.
- **The page player must keep working on old iOS Safari** (a user on an older iPhone
  had buttons but no sound). Don't "modernise" these in `docs/player.js`:
  `window.AudioContext || window.webkitAudioContext` (unprefixed is iOS 14.5+), the
  callback form of `decodeAudioData`, `getChannelData(i).set()` instead of
  `copyToChannel`, creating/resuming the context inside the tap (iOS also has an
  `"interrupted"` state, so check `!== "running"`), and the lazy `import()` of the
  PSOLA stretcher. That stretcher is vendored as an ES2015 bundle in `docs/vendor/`
  because the package source uses `?.`/`??`. To upgrade it, re-download esm.sh's
  `/es2015/…bundle.mjs` build; don't copy the npm source. The ring/silent switch
  mutes Web Audio on iOS: the page sets
  `navigator.audioSession.type = "playback"` (iOS 16.4+), and on older iOS loops a
  silent `<audio>` element while a clip plays.
- **`docs/player.js` is the player's source, not a build output.** Every page loads it with
  `<script type="module" src="player.js">`, so a player fix is one edit there — no
  regenerating pages. It relies on the page's `#speed`/`#speedValue` controls and
  `p[data-audio]` rows that `generate_html.py` emits, so keep the two in step.

## Voices
`voices/voices.json` defines 3 speakers in both languages — `en_a`/`es_a` (woman, 40s),
`en_b`/`es_b` (man, 60s) and `en_c`/`es_c` (young man, 20s, for a third speaker) — each
with a reference WAV that is cloned for all of that speaker's lines. A voice clones only
its own language. A conversation with a 4th speaker needs `en_d`/`es_d`: add them to
`voices.json` (an `instruct` description plus `ref_en`/`ref_es` sentences), then
`scripts/design_voice.py en_d es_d` writes the WAVs. Design is random, so listen and
re-run with `--force` until it fits — but never redesign a voice already used by a
page, or its old lines won't match new ones.

## Platform / performance
TTS is Qwen3-TTS 1.7B via `mlx-audio` — **MLX / Apple Silicon only**. Models live in the
HuggingFace cache (the first run downloads them, several GB). Each `generate_audio.py`
run loads the TTS model once, and Whisper once to transcribe the reference WAVs (~seconds);
each clip is then a few seconds of inference.

## Naming
```
docs/{conv}/audio/{lang}/{row}-{speaker}.mp3   # row zero-padded (00, 01…), speaker a|b|c…
docs/{conv}/clips.json
docs/{conv}.html
docs/player.js                        # shared page player (hand-edited source)
docs/index.html                       # landing page, rebuilt by generate_html.py
```
