# TeleOCR for the conversations pipeline

*Research notes, 7 October 2026. Question: could TeleOCR replace RapidOCR in
`scripts/extract_text.py`?*

## Verdict

**Usable, but as an optional engine rather than a replacement.** TeleOCR fixes
RapidOCR's biggest weakness on these pages: it keeps the textbook's table rows
intact. Its spelling and accents are no better, though, it has a few new failure
modes, and it can't share the project venv.

Rebuilding rows from a collapsed blob is where the refine step is most likely to
lose a line. Character slips are what the refine step already fixes routinely. So
TeleOCR would help with new pages, but not enough to justify replacing RapidOCR
and committing to a second venv.

**Suggested next step:** add `extract_text.py --engine teleocr`, run from a
separate pinned venv, with a spacing fix and a check for Chinese characters. Keep
RapidOCR as the default.

## What TeleOCR is

| | |
|---|---|
| Model | [`XingChen-AGI/TeleOCR`](https://huggingface.co/XingChen-AGI/TeleOCR), formerly NaviDC-OCR (renamed 10 Sep 2026) |
| Released | 17 Aug 2026 (weights and arXiv:2608.12898) |
| Size | ~1.2B parameters, bf16, 2.4 GB of weights |
| Architecture | Qwen2.5-VL vision encoder + Qwen3-style text decoder (per-head q/k RMSNorm), loaded with `trust_remote_code` |
| License | Apache-2.0 |
| Languages | Chinese and English officially; Spanish is not mentioned |
| Benchmarks | OmniDocBench v1.6 overall 96.87, best of the ~1B document parsers listed |
| Outputs | Plain text, tables as OTSL (convertible to HTML), LaTeX formulas, layout boxes |
| Official runtime | PyTorch + transformers 4.57.1 on CUDA; vLLM and SGLang servers |

The remote code (`modeling_naviocr.py`) is plain torch/transformers, with no
network or file I/O.

## How it was tested

- All 14 pages in `inputs/`, run with the official weights through PyTorch on
  MPS (Apple M3 Max), bf16, SDPA attention, greedy decoding.
- Prompt: *"This is the image of a table. Please output the table in OTSL
  format."* The whole page goes in; no layout or crop step.
- Each page run at a longest side of 1600 px and 2400 px.
- Scored against the refined `texts/NN.md`, after:
  - normalizing column order (Spanish column picked by accent share, as
    `make_clips.py` does),
  - stripping speaker labels (the refine step rewrites them),
  - keeping the two wordiest columns when a table has three.
- Character error rate (CER) is Levenshtein distance over each language column's
  concatenated text, divided by the reference length.

## Results

### Summary

| | RapidOCR (current) | TeleOCR, 1600 px | TeleOCR, 2400 px |
|---|---|---|---|
| Row count matches `texts/` | 6/14 | 9/14 | 9/14 |
| Average CER, English | 12.1% | 7.0% | 6.9% |
| Average CER, Spanish | 10.6% | 7.4% | 7.1% |
| Spanish marks lost (`á é í ó ú ñ ¿ ¡`) | 28 | 43 | 38 |
| Time per page | ~2 s | 11–20 s | 13–29 s |

TeleOCR's CER figures include a small regex fix for missing spaces after
punctuation (see below). Without it, the averages are about 0.2–0.3 points higher.

### Per page (RapidOCR vs TeleOCR at 2400 px)

`*` marks a row count that differs from the refined text.

| Page | Rows in `texts/` | RapidOCR rows | CER en / es | Marks lost | TeleOCR rows | CER en / es | Marks lost |
|---:|---:|---:|---|---:|---:|---|---:|
| 5 | 14 | 14 | 1.4% / 0.4% | 1 | 14 | 1.4% / 1.0% | 1 |
| 7 | 10 | 10 | 1.0% / 7.5% | 1 | 10 | 0.8% / 0.4% | 1 |
| 10 | 15 | 17\* | 52.2% / 57.3% | 0 | 17\* | 52.2% / 57.1% | 0 |
| 13 | 18 | 9\* | 15.6% / 17.9% | 0 | 19\* | 2.0% / 2.4% | 0 |
| 15 | 12 | 15\* | 43.9% / 30.4% | 1 | 13\* | 3.7% / 7.0% | 2 |
| 19 | 16 | 19\* | 11.5% / 5.2% | 1 | 16 | 2.7% / 4.8% | 1 |
| 29 | 12 | 2\* | 3.4% / 4.5% | 3 | 12 | 2.8% / 4.2% | 6 |
| 32 | 16 | 16 | 0.4% / 6.5% | 3 | 16 | 0.0% / 3.2% | 4 |
| 33 | 16 | 15\* | 6.4% / 11.7% | 3 | 17\* | 1.2% / 9.1% | 3 |
| 35 | 8 | 10\* | 1.9% / 3.5% | 4 | 10\* | 2.0% / 2.5% | 6 |
| 36 | 12 | 12 | 0.8% / 0.4% | 4 | 12 | 3.4% / 3.1% | 6 |
| 40 | 15 | 2\* | 6.3% / 1.3% | 0 | 15 | 0.5% / 1.3% | 0 |
| 41 | 13 | 13 | 22.9% / 0.7% | 1 | 13 | 22.7% / 1.8% | 2 |
| 42 | 13 | 13 | 1.3% / 1.6% | 6 | 13 | 1.1% / 1.6% | 6 |

Reading the table:

- **Page 10's high CER is the same for both engines.** It's the exercise
  instructions at the top of the page, which the refine step drops.
- **Page 41's English CER is the same for both engines.** It's the `Nota: …`
  annotation, which the refine step removes.
- **Page 36's TeleOCR CER is mostly a scoring artifact.** TeleOCR writes `A.Do`
  with no space, so the label isn't stripped.
- **TeleOCR's extra rows are real table rows** that the refine step drops anyway:
  - page titles (`Shopping | Compras`, `Emergencies | Emergencias`)
  - an `English | Español` header (33, 35)
  - the instructions block (10)
  - one stray fragment (35)

  It never merged or split a line of dialogue.
- **RapidOCR merged dialogue rows on pages 13, 29, 33 and 40.** Pages 29 and 40
  collapsed to 2 rows each:
  - Page 40 has a separate speaker-label column, so it's really a 3-column table,
    and that breaks RapidOCR's midline split.
  - Page 29 has handwritten pronunciation notes between the rows.

## Where TeleOCR is better

- **Table structure.** It reads the ruled cells directly, so it needs no
  row-gap or speaker-label heuristics. This held on all 14 pages, including the
  3-column page 40 and the handwritten page 29.
- **Margin handwriting.** It mostly ignores writing outside the table. On page 15,
  RapidOCR read the margin notes into the dialogue (`brsoc Netherlands 59 1.ana
  2.Yorle … hija`, `Dutch Sandy Married`); TeleOCR left nearly all of it out.
- **Lower overall CER,** mainly because text lands in the right row and column.

## Where TeleOCR is worse, or has new problems

- **Accents.** It often writes `Si` for `Sí`, and `aqui`, `increible`,
  `telefonos`.
  - Neither engine produces a single `¡`: both lost all 20.
  - TeleOCR sometimes reads `¡` as `i`, `j` or even `¿`
    (`¿Ahora ya tengo problemas…!`), which is wrong rather than just missing.
- **Chinese characters leak in.** This happened on page 15 in both runs:
  `Creo que旅游en está herido` at 1600 px and `___,既 cómo te llamas?` at 2400 px.
  The model is trained for Chinese and English.
- **Missing spaces.**
  - After punctuation (`Excuse me.Can you help me?I am`) is systematic. A regex
    repairs most of it (sketch below).
  - Between words (`busstop`, `Gofurther`) happens occasionally and is harder
    to fix.
- **Dropped or changed words.** This is the most serious one: the text still
  reads naturally, so it's easy to miss.
  - `Yes, there a bus stop` with "is" missing (page 7)
  - `será` for `sería`, `Jado` for `lado`, `Atabas` for `Acabas` (page 29)
  - `tranquil` for `tranquilo` (page 15)

  The refine step would need to check against the image to catch these.
- **Only the table prompt works on whole pages.** The plain-text prompt still
  emitted table markup on page 7, with new garbage (`Luegoère à`). On page 15 it
  got stuck repeating `26` until it hit the 4096-token limit (124 s). For
  non-table pages you'd need the layout → crop → recognize pipeline in the
  GitHub repo.
- **Speed.** 13–29 s per page against ~2 s. That's negligible next to TTS, but
  it adds up for batch re-runs.

## Integration cost

- **Can't share the project venv.**
  - The project has transformers 5.18.0, because `mlx-audio==0.5.6` needs
    `transformers>=5.14`.
  - Under 5.18, TeleOCR's remote code crashes on load: `KeyError: 'default'` in
    `ROPE_INIT_FUNCTIONS` (RoPE init).
  - It needs transformers 4.57.1 plus torch, so a second venv (~0.8 GB) on top of
    the 2.4 GB of weights. The alternative is patching and vendoring
    `modeling_naviocr.py`.
- **No easy MLX route.** Stock `mlx-vlm` can't load the q/k-norm decoder. The
  community MLX conversions (`groxaxo/TeleOCR-oQ4/5/6/8-MLX`) need oMLX's custom
  `teleocr_mlx.py` adapter.
- **Young project.** It's 7 weeks old and has already been renamed once, so pin
  the revision that was tested: `e92585356c0d0b7b7a65938f3da035c6593cc9a6`.
- **Large images need downscaling.** The processor allows up to 12.8 MP, and the
  vision encoder's full-attention layers grow with the square of the patch
  count. 2400 px on the long side worked fine; 1600 px was only slightly worse.

## If adopted: sketch

1. A separate venv for OCR, e.g. `.venv-ocr`, created by `scripts/setup.sh`,
   pinning `transformers==4.57.1`, torch, pillow and the model revision.
2. `extract_text.py --engine teleocr`:
   - downscale to 2400 px on the long side
   - send the table prompt
   - parse OTSL (`<fcel>` = new cell, `<nl>` = new row)
   - write the same headerless `| left | right |` rows to `ocrs/NN.md`
   - keep the two wordiest columns when the table has three (page 40), or fold
     the label column into the English cell
3. Post-processing:
   - Add spaces after punctuation. Regex used in testing:
     `((?:[^\W\d_]{2,}|\.\.)[.?!,;:]|[?!,;])(?=[^\W\d_¿¡]|[¿¡])` → `\1 `.
     It leaves `a.m.`, `7:00` and single-letter labels like `A.` alone.
   - Flag any CJK character (`[\u3000-\u9fff]`) as an error for the refine step.
4. The refine step stays the same. It still has to restore `¡`, `Sí` and the
   other accents, and it should read TeleOCR's output against the page image
   because of the dropped-word errors.

## Reproducing

The test harness was throwaway and isn't in the repo. To rerun it:

1. Make a separate venv with Python 3.12, `torch`, `pillow` and
   `transformers==4.57.1`. Don't use the project venv: its transformers 5.18
   can't load the model.
2. Load `XingChen-AGI/TeleOCR` with `AutoProcessor` and `AutoModel`
   (`trust_remote_code=True`, `revision=` the pinned revision above), in bf16
   with `attn_implementation="sdpa"`, moved to `"mps"`. Use the `infer()` helper
   from the model card, with `do_sample=False` and `max_new_tokens=4096`.
3. Downscale each `inputs/NN.jpeg` to 2400 px on the long side and send the
   table prompt above.
4. Parse the OTSL output (split rows on `<nl>`, cells on `<fcel>`/`<ecel>`), then
   score against `texts/NN.md` as described under *How it was tested*.

## Sources

- [XingChen-AGI/TeleOCR on Hugging Face](https://huggingface.co/XingChen-AGI/TeleOCR)
- [StarDoc-AI/TeleOCR on Hugging Face](https://huggingface.co/StarDoc-AI/TeleOCR)
- [caipeng328/TeleOCR on GitHub](https://github.com/caipeng328/TeleOCR)
- [groxaxo/TeleOCR-oQ8-MLX (MLX conversion)](https://huggingface.co/groxaxo/TeleOCR-oQ8-MLX)
