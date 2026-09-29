---
description: Run the full pipeline for a conversation (OCR → refine → clips → audio → HTML → index)
argument-hint: "<conversation-number>"
---
Run the full pipeline for conversation ${1}, following `AGENTS.md` and `scripts/refine_ocr.md`. Work from the project root with `.venv/bin/python`.

1. **OCR:** `scripts/extract_text.py inputs/${1}.jpeg` → writes `ocrs/${1}.md`.
2. **Refine (you):** read `ocrs/${1}.md` → write `texts/${1}.md`. Add a `# ${1}. <EN title> — <ES title>` title, normalize to English-left / Spanish-right, fix OCR errors, drop stray textbook annotations. Preserve the dialogue exactly (correct errors only, no rewording; keep the row count, except to split a row where the OCR merged two speakers' turns or join one utterance the OCR broke across two rows). Flag any judgment call, especially row splits.
3. **Build:** `scripts/pipeline.py ${1}` — clips → audio (slow) → `docs/${1}.html` + index → `check.py`. Only run `generate_audio.py --force` if I ask.

Verify the refine (row counts; one speaker letter per label in `docs/${1}/clips.json`), make sure `check.py` reports no problems, then run `.venv/bin/python -m unittest discover tests`. Report the final state when done.
