---
description: Run the full pipeline for a conversation (OCR → refine → clips → audio → HTML → index)
argument-hint: "<conversation-number>"
---
Run the full pipeline for conversation ${1}, following `AGENTS.md` and `scripts/refine_ocr.md`. Work from the project root with `.venv/bin/python`.

1. **OCR:** `scripts/extract_text.py inputs/${1}.jpeg` → writes `ocrs/${1}.md`.
2. **Refine (you):** read `ocrs/${1}.md` → write `texts/${1}.md`. Add a `# ${1}. <EN title> — <ES title>` title, normalize to English-left / Spanish-right, fix OCR errors, drop stray textbook annotations. Preserve the dialogue exactly (correct errors only, no rewording; keep the row count, except to split a row where the OCR merged two speakers' turns). Flag any judgment call, especially row splits.
3. **Clips:** `scripts/make_clips.py texts/${1}.md ${1} -o docs/${1}/clips.json`.
4. **Audio:** `scripts/generate_audio.py ${1}` (slow; only pass `--force` if I ask).
5. **HTML:** `scripts/generate_html.py ${1}` → `docs/${1}.html`.
6. **Index:** add a link to `docs/index.html`, keeping ascending conversation-number order, using the titles from `texts/${1}.md`: `<li><a href="${1}.html"><span class="num">${1}</span> <EN title> / <ES title></a></li>`.

Verify at each step (row counts, speaker alternation, audio files present and non-empty, every HTML `data-audio` reference resolves). Report the final state when done.
