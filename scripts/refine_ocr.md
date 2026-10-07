# Refine OCR Output (AI step)

This is a **coding-agent step** in the pipeline (not a script). Given the raw
OCR markdown in `ocrs/`, produce the cleaned conversation markdown in `texts/`.

```
ocrs/NN.md  ──(this step)──►  texts/NN.md
```

A coding agent such as **pi** performs this step. Run it by asking the agent
to follow the instructions below on a specific file, e.g.:

> Refine `ocrs/41.md` per `scripts/refine_ocr.md` and write the result to `texts/41.md`.

## Input / Output

- **Read:** `ocrs/NN.md` — the raw two-column markdown table from `extract_text.py`.
  It has **no header row**; the two columns are positional (left / right) and
  their order is whatever appeared in the page image (may be either way round),
  and it may contain OCR errors.
- **Write:** `texts/NN.md` — the refined table (a human/agent-edited artifact).

## What to do

Apply these four transformations to the raw table:

1. **Add a title at the top.** A single H1 line starting with the conversation
   number, then the title in English and its Spanish translation (separated by
   an em dash), e.g. `# 41. Hotel Check-In — Check-in en el hotel`. Take the
   number from the filename (`ocrs/NN.md`). Derive the words from the content;
   keep it short (a few words).

2. **Normalize column order: English on the left, Spanish on the right.**
   Detect which column is which (Spanish is reliably identifiable by accented
   characters `á é í ó ú ñ ¿ ¡` and words like `el`, `de`, `que`, `no`, `sí`).
   If Spanish is currently on the left, swap the two cells of **every** row so
   English is the left column and Spanish is the right column. Do **not** add a
   header row — the file is the bare two-column table.

3. **Correct misspellings and inconsistencies.** Fix obvious OCR artifacts:
   - Misspelled or mangled words in either language.
   - Broken or missing punctuation (e.g. a Spanish `!` without the opening `¡`).
   - Inconsistent speaker labels for the same person (e.g. `R:` one row and
     `Recepcionista:` another) — pick one label per speaker and use it
     consistently. Labels pick the voices, so every row needs one, and a
     textbook mislabel must be fixed (flag it). A label is one word, optionally
     followed by a number (`Customer 2:`).
   - Stray OCR garbage (page numbers, running headers, stray characters).
   - Text the textbook sets in italics can be marked `*like this*`; the page
     shows it as italics and the audio ignores the asterisks. OCR can't see
     italics, so check the page image.

4. **Add the CEFR level.** Under the title, on a line of its own, write
   `Level: ` and one of `A1 A2 B1 B2 C1 C2` (e.g. `Level: A2`). The index
   and the page header show it as a badge; `pipeline.py` won't build a conversation without it,
   and `check.py` flags a missing one. Judge the whole dialogue, in both
   languages, by what a learner must understand and say: its typical turn, not
   its hardest sentence. A set phrase (*que tenga un buen día*) or a few
   subjunctives don't lift a conversation whose English is plainly A2 (33 stays
   A2). Keep new levels consistent with the existing conversations:

   | Level | What it looks like | Conversations |
   |-------|--------------------|---------------|
   | A1 | Short turns of set phrases in the present: greetings, asking for things, prices and quantities | 5, 10, 13 |
   | A2 | Simple past, *going to* / *will*, comparatives, polite formal requests; directions, travel information, simple symptoms; turns of a few sentences | 7, 15, 19, 32, 33, 41, 42 |
   | B1 | Present perfect continuous, past habits against events (Spanish imperfect vs preterite), wishes and hypotheticals, subjunctive beyond set phrases (*puede que*, *cuando* + subjunctive, *ojalá* + imperfect subjunctive); longer turns that narrate or explain | 29, 36, 40 |
   | B2 | Long turns weighing options or arguing a view; idiomatic, descriptive vocabulary | 35 |
   | C1–C2 | Abstract or nuanced discussion, implied meaning, rare idioms | none yet |

   If it sits on a boundary, pick one level and say why when you report.

## Guardrails (important)

- **Preserve the dialogue.** Do not translate, reword, add, or remove lines.
  Only correct errors. The English cell and the Spanish cell in a row are a
  translation pair of the *same* utterance.
- **Keep the structure.** One row = one utterance. Do not merge rows, and do
  not split an utterance across rows. The one exception: if the OCR merged two
  speakers' turns into one row (e.g. `... main street. Anna: Thank you. ...`),
  split them so each row is one utterance, and flag the split. Likewise, if the
  OCR broke one utterance across two rows (a row that continues the previous
  sentence and has no label), join them and flag it. Otherwise the number of
  rows is unchanged.
- **Keep it a valid table.** Two cells per row, `| ... | ... |`. There is no
  header row. The result must be parseable by `make_clips.py`.
- Do not invent content you are not confident about. If a cell is illegible,
  leave it as-is rather than guessing.

## Definition of done

- `texts/NN.md` has a bilingual title, a `Level: A1…C2` line, English-left /
  Spanish-right, no header row, and a clean table.
- `make_clips.py texts/NN.md NN` produces a `clips.json` with the expected
  number of clips (2 per row) and no obvious errors.
- Every English row has a speaker label, one per person: `make_clips.py`
  gives each distinct label its own voice (`a`, `b`, `c`…, in order of first
  appearance). A third speaker needs `en_c`/`es_c`; more need new voices (see
  README "Voices").
