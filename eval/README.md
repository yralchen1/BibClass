# EL Keyword Extraction — Run & Eval Guide

For whoever runs the pipeline (needs Google AI Studio / Vertex set up). Goal metric:
**STRICT perfect-match + zero-extras** per paper (every reference keyword matched AND no AI extras).

This round compares two single-pass prompt variants, then applies a deterministic
notation normalizer, then scores. The earlier LLM "verifier" two-pass is abandoned (it
over-pruned: 16→14). The new second pass is **deterministic Python** (`reformat_keywords.py`),
which only fixes notation and can never drop a keyword.

## 0. What you need
- This repo checked out.
- The **source paper folders** — each contains `main_article.pdf` (+ optional `suppl/`). Same
  ~100 papers as the v1–v4 runs. (`Testing/EL_test_set*` hold only AI outputs, no PDFs.)
- `.env` with `GOOGLE_API_KEY=...` (AI Studio), or Vertex vars + `--use-vertex`.

## 1. Setup
```bash
python3 -m venv venv
./venv/bin/pip install -r requirements.txt
```

## 2. Two runs (outputs are written in place → use separate copies)
```bash
cp -R /path/to/source_papers  run_A      # prompt: el.md         (restored conventions)
cp -R /path/to/source_papers  run_B      # prompt: el_fewshot.md (+ grounded examples)

cd run_A && ../venv/bin/python ../process_pdfs_langchain.py --prompt ../prompts/el.md         && cd ..
cd run_B && ../venv/bin/python ../process_pdfs_langchain.py --prompt ../prompts/el_fewshot.md && cd ..
```
Single Gemini call per paper. Flags: `--single FOLDER`, `--dry-run`, `--use-vertex`.

## 3. Deterministic reformat (no API) — run on each output dir
```bash
./venv/bin/python eval/reformat_keywords.py --ai-dir run_A --out-dir run_A_fmt --verbose
./venv/bin/python eval/reformat_keywords.py --ai-dir run_B --out-dir run_B_fmt --verbose
```
Fixes mechanical notation only (isoelectronic compression, same-element range merge,
exotic→`H I`). Never deletes a keyword.

## 4. Score (no API). Exclude the 5 held-out few-shot example papers for a fair number.
```bash
EX=24044,24085,24090,24128,24129
./venv/bin/python eval/score_eval.py --ai-dir run_A_fmt --exclude $EX --label A --out eval/out/A.md
./venv/bin/python eval/score_eval.py --ai-dir run_B_fmt --exclude $EX --label B --out eval/out/B.md
```
Each prints the locked metric (strict perfect+no-extras over 86 evaluable papers).

## 5. Send back
The four output dirs (or just the `*/bibtex_AI_Generated.txt`) and `eval/out/A.md`, `eval/out/B.md`.
(If easier: send only raw `run_A` / `run_B` — reformat+score are pure Python and can be run here.)

## The bar
- **Control** (prior baseline + reformat, 86 papers): **18/86 strict perfect.**
- **A vs control** = effect of the restored-convention prompt fixes.
- **B vs A** = effect of the grounded few-shot (the clean comparison; both use the same
  SystemMessage layout).
- **Stop condition:** if B (reformatted) does not clear **~22/86 strict perfect**, the
  prompt-only path is exhausted for this model. Honest deliverable then: "ceiling ≈ 18–20;
  the deterministic reformatter is the reliable floor; further gains need human-in-the-loop
  or a different pipeline." Do not spin v6/v7.

## Why these example papers are held out
`el_fewshot.md` teaches restraint using 5 real papers (24044, 24085, 24090, 24128, 24129).
Testing on a paper shown as its own example = leakage, so those 5 are excluded from scoring.
Patterns they teach still have other papers left in the scored set to test generalization.

## Files
- `prompts/el.md` — generation prompt: v4 + restored isoelectronic/exotic conventions + reframed assignment principle.
- `prompts/el_fewshot.md` — el.md + 5 grounded curated examples (restraint + conventions).
- `prompts/el_verify.md` — old LLM verifier (abandoned; kept for reference, `--two-pass`).
- `process_pdfs_langchain.py` — `--prompt FILE` loads the system prompt.
- `eval/reformat_keywords.py` — deterministic notation normalizer (the real "second pass").
- `eval/score_eval.py` — scorer; `--exclude` drops held-out IDs.
