---
description: Run the pipeline up to refine for a conversation (OCR → texts/NN.md), then check in
argument-hint: "<conversation-number>"
---
Run the pipeline for conversation ${1} **up to and including the refine step**, per `AGENTS.md` and `scripts/refine_ocr.md`. Work from the project root with `.venv/bin/python`.

1. **OCR:** `scripts/extract_text.py inputs/${1}.jpeg` → writes `ocrs/${1}.md`.
2. **Refine (you):** read `ocrs/${1}.md` → write `texts/${1}.md`. Add a `# ${1}. <EN title> — <ES title>` title and a `Level: <A1–C2>` line under it (CEFR rubric in `refine_ocr.md`), normalize to English-left / Spanish-right, fix OCR errors, drop stray textbook annotations. Preserve the dialogue exactly — correct errors only, no rewording; keep the row count, except to split a row where the OCR merged two speakers' turns or join one utterance the OCR broke across two rows.

Then **stop and check in** before continuing: summarize what you did and flag any judgment calls (especially row splits, ambiguous fixes, or a level on a boundary). Do NOT run `make_clips` / `generate_audio` / `generate_html` yet.
