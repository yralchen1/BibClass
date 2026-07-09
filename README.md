# Benchmarking PDFs — Automated Keyword Extraction for Atomic Spectroscopy

This project automates the extraction of atomic-spectroscopy bibliographic keywords from scientific papers in PDF format, across the **three ASBib2 topics** — **EL** (Energy Levels & Spectral Lines), **TP** (Transition Probabilities), and **LB** (Line Broadening & Shifts). It uses **Google Gemini** (via LangChain) to read each paper and produce BibTeX-format keyword annotations following the NIST ASD bibliographic database conventions.

Prompts are **external, per-topic files** in `prompts/` (`el.md`, `tp.md`, `lb.md`) that can be switched with `--prompt`/`--prompt-dir` and **looped** — a paper needing EL keywords usually needs TP and LB too, so all three run per paper into one combined output. A companion **evaluation suite** in `eval/` scores AI output against human-curated gold and produces metrics + a benchmark figure.

---

## Table of Contents

1. [Overview](#overview)
2. [Folder Structure](#folder-structure)
3. [Prerequisites](#prerequisites)
4. [Getting a Gemini API Key](#getting-a-gemini-api-key)
5. [Setting Up the Environment](#setting-up-the-environment)
6. [Choosing a Gemini Model](#choosing-a-gemini-model)
7. [Running the PDF Processing Script](#running-the-pdf-processing-script)
8. [Topics & Prompts (EL / TP / LB)](#topics--prompts-el--tp--lb)
9. [Understanding the Output](#understanding-the-output)
10. [Evaluation & Metrics](#evaluation--metrics)
11. [Other Scripts](#other-scripts)
12. [Troubleshooting](#troubleshooting)

---

## Overview

The core workflow is:

1. **Organize** raw PDFs (named like `Author_el_ID_YEAR.pdf`) into structured folders using `organize_pdfs.py`.
2. **Distribute** existing BibTeX catalogue entries into each folder using `catalogue_bibtex.py`.
3. **Process** each paper through Google Gemini to automatically extract atomic-physics keywords using `process_pdfs_langchain.py`.

The AI-generated keywords are saved alongside each paper as `bibtex_AI_Generated.txt`, which can then be compared with the human-catalogued `bibtex_catalogued.txt` for benchmarking.

---

## Folder Structure

```
Benchmarking PDFs/
│
├── .env                          # Your API key and model configuration (DO NOT SHARE)
├── .env.example                  # Template for the .env file
├── requirements.txt              # Python dependencies
├── process_pdfs_langchain.py     # Main AI processing script
├── organize_pdfs.py              # Organizes raw PDFs into folders
├── catalogue_bibtex.py           # Distributes BibTeX entries to folders
├── bibtex_Sr1_1976-2025.txt      # Master BibTeX catalogue file
├── README.md                     # This file
│
├── 2025_Cheung_el_23861/         # Example paper folder
│   ├── main_article.pdf          # The primary PDF paper
│   ├── bibtex_catalogued.txt     # Human-written BibTeX keywords (ground truth)
│   ├── bibtex_AI_Generated.txt   # AI-generated BibTeX keywords (Gemini output)
│   └── suppl/                    # Supplementary materials (if any)
│
├── 2024_Bothwell_el_22893/       # Another paper folder
│   ├── main_article.pdf
│   ├── bibtex_catalogued.txt
│   ├── bibtex_AI_Generated.txt
│   └── suppl/
│
└── ... (90+ paper folders)
```

---

## Prerequisites

- **Python 3.10+** (tested with Python 3.14)
- **pip** (Python package manager)
- **A Google Gemini API key** (for AI Studio mode) and/or **Google Cloud SDK** (for Vertex AI mode) — see sections below
- **Operating System:** macOS, Linux, or Windows 10/11

---

## Getting a Gemini API Key

You need a Google Gemini API key to run the script in the default (AI Studio) mode. Here's how to get one:

1. **Go to Google AI Studio**: [https://aistudio.google.com/apikey](https://aistudio.google.com/apikey)
2. **Sign in** with your Google account.
3. **Click "Create API Key"**.
4. **Select a Google Cloud project** (or create a new one).
5. **Copy the generated API key** — you'll need it in the next step.

> **⚠️ Important:** Keep your API key secret. Never commit it to version control or share it publicly.

### API Key Pricing

- The **Gemini Flash** models are part of Google's **free tier** for low-volume usage.
- For high-volume processing (100+ papers), check the [Gemini API pricing page](https://ai.google.dev/pricing) for current limits and costs.

---

## Setting Up the Environment

### Step 1 — Clone/Navigate to the project

**macOS / Linux:**
```bash
cd "/path/to/BibClass project folder"
```

**Windows (Command Prompt):**
```cmd
cd "C:\path\to\BibClass project folder"
```

**Windows (PowerShell):**
```powershell
cd "C:\path\to\BibClass project folder"
```

### Step 2 — Create a virtual environment (recommended)

**macOS / Linux:**
```bash
python3 -m venv .venv
source .venv/bin/activate
```

**Windows (Command Prompt):**
```cmd
python -m venv .venv
.venv\Scripts\activate.bat
```

**Windows (PowerShell):**
```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
```

> **Note (Windows PowerShell):** If you get an execution policy error, run:
> ```powershell
> Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
> ```

### Step 3 — Install dependencies

```bash
pip install -r requirements.txt
```

> This command is the same on all platforms once the virtual environment is activated.

This installs:
| Package | Purpose |
|---|---|
| `langchain` | LLM orchestration framework |
| `langchain-google-genai` | Google Gemini integration for LangChain |
| `pypdf` | PDF text extraction |
| `python-dotenv` | Load environment variables from `.env` |

### Step 4 — Configure environment variables

Create a `.env` file in the `Benchmarking PDFs/` directory:

**macOS / Linux:**
```bash
cp .env.example .env
```

**Windows (Command Prompt):**
```cmd
copy .env.example .env
```

**Windows (PowerShell):**
```powershell
Copy-Item .env.example .env
```

Then open `.env` in any text editor and fill in the values. The `.env` file supports the following variables:

```env
# Gemini API Key (required for AI Studio mode, not needed for Vertex AI mode)
GOOGLE_API_KEY=your_gemini_api_key_here

# Default model used in AI Studio mode (optional; defaults to gemini-3-flash-preview)
DEFAULT_MODEL=gemini-3-flash-preview

# Vertex AI-specific parameters (required only when using --use-vertex)
VERTEXAI_PROJECT=your_project_name
VERTEXAI_LOCATION=us-central1
VERTEXAI_MODEL=gemini-2.5-pro
```

Which variables you need depends on which mode you plan to use:

| Variable | AI Studio mode (default) | Vertex AI mode (`--use-vertex`) |
|---|---|---|
| `GOOGLE_API_KEY` | **Required** | Not used |
| `DEFAULT_MODEL` | Optional (defaults to `gemini-3-flash-preview`) | Not used |
| `VERTEXAI_PROJECT` | Not used | **Required** |
| `VERTEXAI_LOCATION` | Not used | **Required** |
| `VERTEXAI_MODEL` | Not used | **Required** |

> **Tip:** You can also set any of these as shell environment variables instead of using the `.env` file.

---

## Choosing a Gemini Model

The script supports two distinct modes for accessing Gemini, controlled by the `--use-vertex` command-line flag.

### How Model Switching Works

The choice of model is determined by two things: the `--use-vertex` flag and the environment variables in your `.env` file.

- **Without `--use-vertex`** (default): The script connects to Google's **AI Studio API** using your `GOOGLE_API_KEY`. The model used is set by the `DEFAULT_MODEL` variable in `.env` (defaults to `gemini-3-flash-preview` if not specified).

- **With `--use-vertex`**: The script connects to **Google Cloud Vertex AI** using Application Default Credentials (no API key needed). The model, project, and region are read from `VERTEXAI_MODEL`, `VERTEXAI_PROJECT`, and `VERTEXAI_LOCATION` in `.env`.

```
# AI Studio mode (default) — uses GOOGLE_API_KEY + DEFAULT_MODEL
python process_pdfs_langchain.py

# Vertex AI mode — uses gcloud credentials + VERTEXAI_* settings
python process_pdfs_langchain.py --use-vertex
```

### Vertex AI vs AI Key: When to Use Which

| | AI Studio (API Key) | Vertex AI |
|---|---|---|
| **Authentication** | API key in `.env` | `gcloud` CLI credentials |
| **Setup complexity** | Minimal | Requires Google Cloud project + gcloud |
| **Default model** | `gemini-3-flash-preview` | `gemini-2.5-pro` |
| **Best for** | Quick setup, individual use | Institutional / GCP-integrated environments |
| **Billing** | Tied to API key / AI Studio project | Tied to Google Cloud project |

### Setting Up Vertex AI

To use Vertex AI mode, you need the Google Cloud SDK (`gcloud`) installed and configured:

1. **Install the gcloud CLI**: Download and install from [https://cloud.google.com/sdk/docs/install](https://cloud.google.com/sdk/docs/install). Follow the instructions for your operating system.

2. **Initialize gcloud** (first time only):
   ```bash
   gcloud init
   ```
   This will prompt you to log in and select a Google Cloud project.

3. **Authenticate for Application Default Credentials**:
   ```bash
   gcloud auth application-default login
   ```
   This opens a browser window for you to sign in. The credentials are stored locally and used automatically by the script.

4. **Set your quota project** (if required):
   ```bash
   gcloud auth application-default set-quota-project your_project_name
   ```
   Replace `your_project_name` with the project ID listed in your `.env` as `VERTEXAI_PROJECT`.

5. **Configure `.env`**: Ensure `VERTEXAI_PROJECT`, `VERTEXAI_LOCATION`, and `VERTEXAI_MODEL` are set (see Step 4 in [Setting Up the Environment](#setting-up-the-environment)).

### Model Performance Comparison

Based on actual benchmarking results with this project's atomic spectroscopy keyword extraction task:

| Model | Access Mode | Speed | Precision | Notes |
|---|---|---|---|---|
| `gemini-2.5-pro` | Vertex AI | Fast | Moderate | Good throughput; suitable for bulk processing |
| `gemini-3-flash-preview` | AI Studio (API Key) | Slower | Highest | Best accuracy for keyword extraction; recommended for quality-critical runs |

**Recommendation:** Use `gemini-3-flash-preview` (the default AI Studio model) when precision matters most. Use `gemini-2.5-pro` via Vertex AI when processing speed is the priority or when operating within a Google Cloud environment.

### Adjusting Temperature

The script uses `temperature=0.0` for maximum determinism. This is configured in the code and generally should not be changed for structured keyword extraction tasks.

---

## Running the PDF Processing Script

The main script is **`process_pdfs_langchain.py`**. It reads each paper's PDF, sends it to Google Gemini, and saves the AI-generated keywords.

### Process All Papers

```bash
# Using AI Studio (default):
python process_pdfs_langchain.py

# Using Vertex AI:
python process_pdfs_langchain.py --use-vertex
```

This will:
1. Scan all subfolders for `main_article.pdf` files (the initial distribution includes only one such subfolder named `sample_paper`). If such folder contains a subfolder `suppl`, its contents are treated as supplementary files for `main_article.pdf` and will be processed together with it.
2. Load each PDF for native upload to Gemini.
3. Send the PDF (and any supplementary text) to Gemini with the keyword-extraction prompt.
4. Save the response as `bibtex_AI_Generated.txt` inside each paper's folder.
5. Print a progress summary showing successes and errors.

> **By default only the EL topic runs.** To run Transition Probabilities and Line Broadening
> too (per paper, into one combined output), and for the flat test-set layout, see
> [Topics & Prompts (EL / TP / LB)](#topics--prompts-el--tp--lb).

**Example terminal output:**
```
🚀 Initializing Google Gemini via AI Studio...
📁 Found 1 paper(s) to process

[1/1] Processing: sample_paper
  📄 Loading PDF for native upload...
  📝 Loaded PDF (~2.1 MB)
  🤖 Sending native PDF + supplementary data to Gemini...
  ✅ Saved to: bibtex_AI_Generated.txt

...

==================================================
Summary:
  ✅ Successful: 1
  ❌ Errors: 0
  📁 Total: 1
```

### Process a Single Paper

To process only one specific paper folder:

```bash
python process_pdfs_langchain.py --single sample_paper

# Or with Vertex AI:
python process_pdfs_langchain.py --single sample_paper --use-vertex
```

The `--single` flag accepts the **folder name** (not the full path). The folder must exist inside the `Benchmarking PDFs/` directory and contain a `main_article.pdf`.

### Dry Run (Preview Without Processing)

To see which papers would be processed without actually calling the API:

```bash
python process_pdfs_langchain.py --dry-run
```

**Output:**
```
📁 Found 1 paper(s) to process

DRY RUN - Would process:
  • sample_paper
  ...
```

### Combine Flags

You can combine `--single`, `--dry-run`, and `--use-vertex`:

```bash
python process_pdfs_langchain.py --single sample_paper --dry-run
python process_pdfs_langchain.py --use-vertex --single sample_paper
```

---

## Understanding the Output

Each processed paper gets a `bibtex_AI_Generated.txt` file saved in its folder. The file contains the extracted keywords in BibTeX format:

**Example output** (`sample_paper/bibtex_AI_Generated.txt`):
```
keywords_el={Ca I; 43Ca I: Hfs: E
Ca I: IS: E
Ca I; 43Ca I: CL: E
Ca I; 43Ca I: W: E},
keywords_tp={},
keywords_lb={}
```

### How to Read the Keywords

Each line inside `keywords_el={...}` follows one of these formats:

- **General Interest:** `GENINT: [Code]: [Method]`
  - Example: `GENINT: 1.8: T` = Atomic codes (Theory)
  - Example: `GENINT: 1.13: E` = Atomic Clocks (Experiment)

- **Element-Specific:** `[Spectrum]: [Subject Code]: [Method]`
  - Example: `Sr I: SE: T` = Strontium I, Stark Effect, Theory
  - Example: `Sr I; 87Sr I: EL: E` = Strontium I & Strontium-87 I, Energy Levels, Experiment

### Method Types
| Code | Meaning |
|---|---|
| `E` | Experimental data |
| `T` | Theoretical calculations |
| `O` | Other / semi-empirical |

### Common Subject Codes
| Code | Full Name |
|---|---|
| `EL` | Energy Levels |
| `W` | Wavelengths / Frequencies |
| `CL` | Classified Lines |
| `TE` | Theoretical Energies |
| `AT` | Ab Initio Theory |
| `SE` | Stark Effect / Polarizability / BBR shifts |
| `ZE` | Zeeman Effect / g-factors |
| `Hfs` | Hyperfine Structure |
| `IS` | Isotope Shifts |
| `IP` | Ionization Potential |
| `QF` | QED / Lamb Shifts |

---

## Topics & Prompts (EL / TP / LB)

The extraction prompts are **external files** in `prompts/` — one per topic. Editing a prompt no longer means editing Python.

| File | Topic | Output field |
|---|---|---|
| `prompts/el.md` | Energy Levels & Spectral Lines | `keywords_el` |
| `prompts/tp.md` | Transition Probabilities | `keywords_tp` |
| `prompts/lb.md` | Line Broadening & Shifts | `keywords_lb` |
| `prompts/el_fewshot.md` | EL variant with grounded worked examples (best EL run to date) | `keywords_el` |
| `prompts/el_recall.md` | EL variant tuned to minimise "zero-match" papers (anti-empty) | `keywords_el` |

### Selecting topics
`--topics` chooses which topics run per paper (comma-separated, default `el`). Each topic's prompt is loaded from `--prompt-dir` (default `prompts/`) as `<topic>.md`; all topic blocks are written to one output file.

```bash
python process_pdfs_langchain.py --topics el,tp,lb   # all three per paper (production)
python process_pdfs_langchain.py --topics tp         # a single topic
```

### Swapping a prompt version
For a single topic, point at any prompt file:
```bash
python process_pdfs_langchain.py --topics el --prompt prompts/el_fewshot.md
```

### Editing a prompt
Open `prompts/<topic>.md` and edit — plain markdown, no code changes. Each prompt is structured: output contract → novelty filter → format laws → subject/method/mechanism codes → species-string conventions → GENINT → worked examples. Keep the `keywords_<topic>={...}` output contract intact.

### Input layouts (auto-detected)
- **folder** — subfolders each with `main_article.pdf` (+ optional `suppl/`) → output written in place as `bibtex_AI_Generated.txt`.
- **flat** — a directory of `<author>_<topic>_<id>_<year>.pdf` files (+ `..._suppl*`, matched by id) → output to `--out-dir/<pdf-stem>/bibtex_AI_Generated.txt` (default `./ai_out/`). This is how `Testing/pdf/{EL,TP,LB}_test_set/` are laid out.

### EL two-pass (optional)
`--two-pass` adds a verification pass on the EL topic that prunes unsupported keywords (`prompts/el_verify.md`). It over-pruned in benchmarking; the deterministic reformatter (`eval/reformat_keywords.py`) is preferred.

---

## Evaluation & Metrics

The `eval/` suite scores AI output against human-curated gold (`test_set_bibtex.txt`) — pure Python, no API needed.

| Script | Purpose |
|---|---|
| `eval/score_eval.py` | Paper-level scoring: perfect-match, zero-match, extras (notation-normalized) |
| `eval/keyword_quality.py` | Atomized per-keyword quality (element-ion × code × type); penalized + recall variants |
| `eval/keyword_prf.py` | Decomposed Precision/Recall/F1 at species / +code / +type levels (recommended metric) |
| `eval/reformat_keywords.py` | Deterministic notation normalizer (isoelectronic compression, range-merge, exotic→H I) |
| `eval/make_plots.py` | 4-panel benchmark overview figure |
| `eval/METRICS.md` | Written metrics summary |
| `eval/README.md` | Full eval + per-topic run protocol (held-out examples, stop conditions) |

```bash
python eval/keyword_prf.py --ai-dir <output-dir> --exclude <held-out-ids>
python eval/make_plots.py  --ai-dir <output-dir> --out Testing/benchmark_overview.png
```

Current EL benchmark (best run, 95 papers): species-level F1 ≈ 85%, dropping ~15 pts once the subject code must also match (over-assignment is the dominant error); method type is nearly solved. Details in `eval/METRICS.md`.

**TP / LB status:** prompts + generation are ready; scoring awaits their gold `test_set_bibtex.txt`.

---

## Other Scripts

### `organize_pdfs.py` — Organize Raw PDFs into Folders

Takes flat PDF files named `Author_el_23861_2025.pdf` and organizes them into structured folders.

```bash
# Preview what would happen (dry run):
python organize_pdfs.py --dry-run

# Actually organize the PDFs:
python organize_pdfs.py

# Organize PDFs in a different directory:
python organize_pdfs.py /path/to/pdf/directory
```

**Input:** `Cheung_el_23861_2025.pdf`
**Output:** `2025_Cheung_el_23861/main_article.pdf` + `suppl/` subdirectory

### `catalogue_bibtex.py` — Distribute BibTeX Entries

Reads the master BibTeX file (`bibtex_Sr1_1976-2025.txt`) and places the relevant entry into each paper's folder as `bibtex_catalogued.txt`.

```bash
python catalogue_bibtex.py
```

---

## Troubleshooting

### ❌ "GOOGLE_API_KEY not found!"

Your `.env` file is missing or doesn't contain the key. This error only applies to the default AI Studio mode (without `--use-vertex`).

**macOS / Linux:**
```bash
cat .env
# Should contain: GOOGLE_API_KEY=AIza...your_key_here
```

**Windows:**
```cmd
type .env
```

### ❌ "Missing Vertex AI configuration in .env file"

When using `--use-vertex`, all three Vertex AI variables must be set in `.env`:
```env
VERTEXAI_PROJECT=your_project_name
VERTEXAI_LOCATION=us-central1
VERTEXAI_MODEL=gemini-2.5-pro
```

### ❌ Vertex AI Authentication or Permission Errors

If you see `PermissionDenied` or `Could not automatically determine credentials` when using `--use-vertex`, follow these steps:

1. **Install the gcloud CLI** if not already installed: [https://cloud.google.com/sdk/docs/install](https://cloud.google.com/sdk/docs/install)

2. **Log in with Application Default Credentials:**
   ```bash
   gcloud auth application-default login
   ```

3. **Set your quota project** (often needed when using Vertex AI):
   ```bash
   gcloud auth application-default set-quota-project your_project_name
   ```
   Replace `your_project_name` with the value of `VERTEXAI_PROJECT` in your `.env`.

4. **Verify you have the required IAM permissions** on the Google Cloud project. You need at minimum the `Vertex AI User` role (`roles/aiplatform.user`).

5. **If credentials expire**, re-run step 2. Application Default Credentials may need to be refreshed periodically.

### ❌ "ModuleNotFoundError: No module named 'langchain'"

Dependencies are not installed. Make sure you're in the virtual environment:

**macOS / Linux:**
```bash
source .venv/bin/activate
pip install -r requirements.txt
```

**Windows (Command Prompt):**
```cmd
.venv\Scripts\activate.bat
pip install -r requirements.txt
```

**Windows (PowerShell):**
```powershell
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

### ❌ "Failed to extract text from PDF"

The PDF may be image-based (scanned) rather than text-based. `pypdf` can only extract text from text-based PDFs. For scanned PDFs, you would need OCR (e.g., `pytesseract`).

### ❌ API Rate Limit Errors

If processing many papers at once, you may hit Gemini's rate limits. Try:
- Using `--single` to process one paper at a time.
- Waiting a few minutes between batches.
- Upgrading to a paid API tier.

### ❌ Truncated Output

Very long papers or supplementary materials may be truncated. Supplementary text is capped at approximately 3,000,000 characters. For most papers, this is more than sufficient.

> **Note:** Larger inputs consume more tokens and may increase API costs.

---

## Quick Reference

**macOS / Linux:**
```bash
# Setup (one-time):
cd "Benchmarking PDFs"
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# Edit .env with your API key and/or Vertex AI settings

# Run (AI Studio mode — default):
python process_pdfs_langchain.py                  # all papers, EL topic
python process_pdfs_langchain.py --topics el,tp,lb # all three topics per paper
python process_pdfs_langchain.py --topics tp      # single topic (e.g. the TP set)
python process_pdfs_langchain.py --single X       # process folder/PDF X only
python process_pdfs_langchain.py --dry-run        # preview only

# Run (Vertex AI mode):
python process_pdfs_langchain.py --use-vertex

# Evaluate AI output against gold (pure Python, no API):
python eval/keyword_prf.py --ai-dir <output-dir>
python eval/make_plots.py  --ai-dir <output-dir> --out Testing/benchmark_overview.png
```

**Windows (Command Prompt):**
```cmd
:: Setup (one-time):
cd "Benchmarking PDFs"
python -m venv .venv
.venv\Scripts\activate.bat
pip install -r requirements.txt
copy .env.example .env
:: Edit .env with your API key and/or Vertex AI settings

:: Run (AI Studio mode — default):
python process_pdfs_langchain.py
python process_pdfs_langchain.py --single X
python process_pdfs_langchain.py --dry-run

:: Run (Vertex AI mode):
python process_pdfs_langchain.py --use-vertex
```

**Windows (PowerShell):**
```powershell
# Setup (one-time):
cd "Benchmarking PDFs"
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env
# Edit .env with your API key and/or Vertex AI settings

# Run (AI Studio mode — default):
python process_pdfs_langchain.py
python process_pdfs_langchain.py --single X
python process_pdfs_langchain.py --dry-run

# Run (Vertex AI mode):
python process_pdfs_langchain.py --use-vertex
```
