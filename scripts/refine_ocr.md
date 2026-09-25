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

Apply these three transformations to the raw table:

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
     consistently.
   - Stray OCR garbage (page numbers, running headers, stray characters).

## Guardrails (important)

- **Preserve the dialogue.** Do not translate, reword, add, or remove lines.
  Only correct errors. The English cell and the Spanish cell in a row are a
  translation pair of the *same* utterance.
- **Keep the structure.** One row = one utterance. Do not merge or split rows.
  The number of rows is unchanged.
- **Keep it a valid table.** Two cells per row, `| ... | ... |`. There is no
  header row. The result must be parseable by `make_clips.py`.
- Do not invent content you are not confident about. If a cell is illegible,
  leave it as-is rather than guessing.

## Definition of done

- `texts/NN.md` has a bilingual title, English-left / Spanish-right, no header
  row, and a clean table.
- `make_clips.py texts/NN.md NN` produces a `clips.json` with the expected
  number of clips (2 per row) and no obvious errors.
