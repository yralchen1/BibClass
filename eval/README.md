# EL Keyword Extraction — Run & Eval Guide

For whoever runs the pipeline (needs Google AI Studio / Vertex set up). Goal: compare
the **single-pass** baseline against the new **two-pass** (generate → verify) pipeline on
the locked metric **STRICT perfect-match + zero-extras**.

## 0. What you need
- This repo checked out.
- The **source paper folders** — each folder contains `main_article.pdf` (and optionally a
  `suppl/` subfolder). These are the same ~100 papers used for the v1–v4 runs. The
  `Testing/EL_test_set*` folders hold only AI *outputs*, NOT the source PDFs, so you cannot
  run the pipeline against them — point the pipeline at your folder of source PDFs.
- A `.env` with `GOOGLE_API_KEY=...` (AI Studio), or Vertex vars (`VERTEXAI_PROJECT`,
  `VERTEXAI_LOCATION`, `VERTEXAI_MODEL`) and the `--use-vertex` flag.

## 1. Setup
```bash
python3 -m venv venv
./venv/bin/pip install -r requirements.txt
```

## 2. Important: outputs are written in place
The pipeline writes `bibtex_AI_Generated.txt` **inside each paper folder**, overwriting any
existing one. To compare two variants, run each on a **separate copy** of the source papers:

```bash
cp -R /path/to/source_papers  run_baseline
cp -R /path/to/source_papers  run_twopass
```

## 3. Run — baseline (single pass, new externalized v4 prompt)
```bash
cd run_baseline
../venv/bin/python ../process_pdfs_langchain.py            # uses prompts/el.md by default
cd ..
```

## 4. Run — two-pass (generate, then verify/prune)
```bash
cd run_twopass
../venv/bin/python ../process_pdfs_langchain.py --two-pass # adds prompts/el_verify.md pass
cd ..
```
Two-pass = two Gemini calls per paper (generate, then verify).

**Cost — implicit caching is on automatically.** Both calls send the same PDF as the first
part of the request, so Gemini's implicit cache reuses it on the verify pass (cached input is
much cheaper). Net cost per paper ≈ **~1.3x** the single-pass cost, not 2x. Nothing to enable
— it works as long as the PDF is identical and leads the request (the code already does this).
You can confirm cache hits in the response usage metadata (`cached_content_token_count` /
`usage_cached_tokens`).

Useful flags: `--single FOLDER` (one paper), `--dry-run` (list only, no API),
`--prompt FILE` (swap generation prompt), `--verify-prompt FILE`, `--use-vertex`.

## 5. Score each run (no API needed — pure Python)
```bash
./venv/bin/python eval/score_eval.py --ai-dir run_baseline --label baseline \
    --out eval/out/baseline.md
./venv/bin/python eval/score_eval.py --ai-dir run_twopass  --label two-pass \
    --out eval/out/two_pass.md
```
Each prints the locked metric and writes a per-entry report. Reference defaults to
`Testing/test_set_bibtex.txt`; override with `--ref`.

## 6. What to send back
- The two run dirs (or just the `*/bibtex_AI_Generated.txt` files), and
- `eval/out/baseline.md` + `eval/out/two_pass.md` (or the printed summaries).

## Baseline to beat
v4 (prior best single pass): **18 strict perfect** (141/237 strict keyword matches, 125 extras,
39 all-matched, 29 zero-match). Two-pass target: convert the ~21 "all-matched-but-has-extras"
papers into perfects by pruning extras without dropping real matches → aim **≥28 strict perfect**.

Note: the message layout changed for caching — the prompt now rides in the user turn after the
PDF instead of a system message. So **run the single-pass baseline with this same code** (step 3)
rather than comparing two-pass against the old 18; that keeps the comparison fair (both use the
identical code path, differing only by `--two-pass`).

## Files in this change
- `prompts/el.md` — generation prompt (externalized from the script; was v4).
- `prompts/el_verify.md` — verifier prompt used by `--two-pass`.
- `process_pdfs_langchain.py` — loads prompt from file (`--prompt`); adds `--two-pass`.
- `eval/score_eval.py` — parameterized scorer (reuses `Testing/analyze_keywords.py`).
