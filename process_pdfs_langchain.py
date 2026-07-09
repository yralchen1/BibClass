#!/usr/bin/env python3
"""
LangChain PDF Processing Script for Atomic Energy Levels Keywords
Uses Google Gemini to extract keywords_el from scientific papers.

Usage:
    python process_pdfs_langchain.py                       # all papers in cwd, EL topic
    python process_pdfs_langchain.py --topics el,tp,lb     # run all three topics per paper
    python process_pdfs_langchain.py --topics tp           # single topic (e.g. scoring the TP set)
    python process_pdfs_langchain.py --single FOLDER_OR_PDF
    python process_pdfs_langchain.py --dry-run             # show what would be processed
    python process_pdfs_langchain.py --two-pass            # EL verification pass (prune extras)

Prompts are loaded per topic from prompts/<topic>.md (el.md, tp.md, lb.md) so they can be
switched without editing this script. Multiple topics loop per paper — a paper needing EL
keywords usually needs TP and LB too — and all topic blocks are written to one output file.

Input layouts (auto-detected):
  folder — subfolders with main_article.pdf → output written in place (bibtex_AI_Generated.txt).
  flat   — a dir of `<author>_<topic>_<id>_<year>.pdf` (+ `..._suppl*` files) → output to
           --out-dir/<pdf-stem>/bibtex_AI_Generated.txt.
"""

import warnings
# Suppress Pydantic V1 compatibility warning with Python 3.14+
warnings.filterwarnings("ignore", message="Core Pydantic V1 functionality")

import os
import sys
import argparse
from pathlib import Path
from dotenv import load_dotenv
import base64
import zipfile
import tarfile
import io
import re
import time
# import mimetypes

try:
    from pypdf import PdfReader
except ImportError:
    PdfReader = None

try:
    import docx
except ImportError:
    docx = None

try:
    import openpyxl
except ImportError:
    openpyxl = None

# Load environment variables
load_dotenv()

# LangChain imports
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import HumanMessage, SystemMessage


# Configuration
#BASE_DIR = Path(__file__).parent
BASE_DIR = Path.cwd()
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")

# System prompt for atomic physics EL keyword extraction.
# Externalized to prompts/el.md so prompt versions can be swapped via --prompt
# without editing code. See plan: prompts/el.md is seeded from Prompt_EL_v4.
DEFAULT_PROMPT_PATH = Path(__file__).parent / "prompts" / "el.md"
DEFAULT_VERIFY_PROMPT_PATH = Path(__file__).parent / "prompts" / "el_verify.md"


def load_prompt(path: Path) -> str:
    """Load a system prompt from a text/markdown file."""
    try:
        return path.read_text(encoding="utf-8")
    except Exception as e:
        print(f"❌ Error: could not read prompt file {path}: {e}")
        sys.exit(1)


def load_pdf_as_base64(pdf_path: Path) -> str:
    """Load a PDF file and return its base64-encoded content."""
    try:
        with open(pdf_path, "rb") as f:
            pdf_bytes = f.read()
        return base64.b64encode(pdf_bytes).decode("utf-8")
    except Exception as e:
        print(f"  ⚠ Error reading PDF: {e}")
        return ""


def extract_text_from_pdf_bytes(pdf_bytes: bytes) -> str:
    """Extract text from raw PDF bytes using pypdf."""
    if not PdfReader:
        return "[PDF extraction failed: pypdf not installed]"
    try:
        reader = PdfReader(io.BytesIO(pdf_bytes))
        text = "\n".join(page.extract_text() for page in reader.pages if page.extract_text())
        return text
    except Exception as e:
        return f"[Error extracting PDF text: {e}]"


def extract_text_from_docx_bytes(docx_bytes: bytes) -> str:
    """Extract text from raw DOCX bytes using python-docx."""
    if not docx:
        return "[DOCX extraction failed: python-docx not installed]"
    try:
        doc = docx.Document(io.BytesIO(docx_bytes))
        return "\n".join(para.text for para in doc.paragraphs if para.text)
    except Exception as e:
        return f"[Error extracting DOCX text: {e}]"


def extract_text_from_xlsx_bytes(xlsx_bytes: bytes) -> str:
    """Extract text from raw XLSX bytes using openpyxl."""
    if not openpyxl:
        return "[XLSX extraction failed: openpyxl not installed]"
    try:
        wb = openpyxl.load_workbook(io.BytesIO(xlsx_bytes), data_only=True)
        text_parts = []
        for sheet in wb.worksheets:
            text_parts.append(f"--- Sheet: {sheet.title} ---")
            for row in sheet.iter_rows(values_only=True):
                # Join non-empty cells in the row
                row_text = "\t".join(str(cell) for cell in row if cell is not None)
                if row_text.strip():
                    text_parts.append(row_text)
        return "\n".join(text_parts)
    except Exception as e:
        return f"[Error extracting XLSX text: {e}]"


def process_file_bytes(filename: str, file_bytes: bytes) -> str:
    """Determine file type by extension and extract text accordingly."""
    text_content = f"--- SUPPLEMENTARY FILE: {filename} ---\n"
    ext = Path(filename).suffix.lower()
    
    # PDF
    if ext == ".pdf":
        text_content += extract_text_from_pdf_bytes(file_bytes)
    # Word
    elif ext in [".docx"]:
        text_content += extract_text_from_docx_bytes(file_bytes)
    # Excel
    elif ext in [".xlsx", ".xlsm"]:  # Old .xls needs xlrd, ignoring for now as usually .xlsx
        text_content += extract_text_from_xlsx_bytes(file_bytes)
    # Archives - ZIP
    elif ext == ".zip":
        text_content += "[Unzipping Archive...]\n"
        try:
            with zipfile.ZipFile(io.BytesIO(file_bytes)) as z:
                for zinfo in z.infolist():
                    if not zinfo.is_dir() and not zinfo.filename.startswith("__MACOSX"):
                        zfile_bytes = z.read(zinfo.filename)
                        text_content += process_file_bytes(f"{filename}/{zinfo.filename}", zfile_bytes) + "\n"
        except Exception as e:
            text_content += f"[Error reading Zip {filename}: {e}]"
    # Archives - TAR.GZ
    elif ext in [".tar.gz", ".tgz"]:
        text_content += "[Extracting Tar.gz Archive...]\n"
        try:
            with tarfile.open(fileobj=io.BytesIO(file_bytes), mode="r:gz") as tar:
                for member in tar.getmembers():
                    if member.isfile() and not member.name.startswith("__MACOSX"):
                        fobj = tar.extractfile(member)
                        if fobj:
                            tfile_bytes = fobj.read()
                            text_content += process_file_bytes(f"{filename}/{member.name}", tfile_bytes) + "\n"
        except Exception as e:
            text_content += f"[Error reading Tar.gz {filename}: {e}]"
    # Standard Text or Code Files
    else:
        # Check if it's likely a text file (including code formats like .py, .csv, .f, .tex, .pl)
        # Try to decode as utf-8
        try:
            text_str = file_bytes.decode('utf-8')
            # Very basic check: if it has null bytes it's probably binary
            if '\x00' not in text_str:
                text_content += text_str
            else:
                text_content += f"[Skipped binary file: {filename}]"
        except UnicodeDecodeError:
            # Fallback to latin-1
            try:
                text_str = file_bytes.decode('latin-1')
                if '\x00' not in text_str:
                    text_content += text_str
                else:
                    text_content += f"[Skipped binary file: {filename}]"
            except Exception:
                 text_content += f"[Skipped unreadable/binary file: {filename}]"
                 
    return text_content + "\n"


def extract_supplementary_text(suppl_dir: Path) -> str:
    """Traverse the suppl directory and extract text from all understandable files."""
    if not suppl_dir.exists() or not suppl_dir.is_dir():
        return ""
        
    combined_text = "\n\n=== SUPPLEMENTARY MATERIALS ===\n\n"
    found_files = False
    
    for path in suppl_dir.rglob('*'):
        if path.is_file() and not path.name.startswith('.'):
            found_files = True
            try:
                with open(path, "rb") as f:
                    file_bytes = f.read()
                combined_text += process_file_bytes(path.name, file_bytes)
            except Exception as e:
                combined_text += f"\n[Error reading file {path.name}: {e}]\n"
                
    if not found_files:
        return ""
        
    # Optional: Truncate if the supplementary text is absurdly large (e.g. > 2 million chars)
    # Gemini 1.5/2.5 flash can handle ~1M tokens (roughly 4M chars)
    if len(combined_text) > 3000000:
        combined_text = combined_text[:3000000] + "\n...[SUPPLEMENTARY DATA TRUNCATED DUE TO SIZE]..."
        
    return combined_text


def _flatten_content(content) -> str:
    """Flatten a LangChain response .content into a plain string.

    Some models return a list of parts (dicts with a 'text' key, or strings)
    instead of a single string.
    """
    if isinstance(content, list):
        text_parts = []
        for part in content:
            if isinstance(part, dict) and 'text' in part:
                text_parts.append(part['text'])
            elif isinstance(part, str):
                text_parts.append(part)
            else:
                text_parts.append(str(part))
        return "\n".join(text_parts)
    return content


def process_paper(pdf_base64: str, suppl_text: str, llm: ChatGoogleGenerativeAI, system_prompt: str) -> str:
    """Process a paper's native PDF and supplementary text through Gemini to extract keywords_el.

    The prompt is delivered as a SystemMessage (measured ~2 perfect-matches better than
    folding it into the user turn). The PDF is sent in the user turn.
    """
    pdf_data_uri = f"data:application/pdf;base64,{pdf_base64}"

    prompt_text = ("Please analyze the attached scientific paper (and any supplementary "
                   "materials below) and extract the keywords_el.")
    if suppl_text:
        prompt_text += f"\n\nHere is the text extracted from the supplementary files:\n{suppl_text}"

    messages = [
        SystemMessage(content=system_prompt),
        HumanMessage(content=[
            {"type": "image_url", "image_url": pdf_data_uri},
            {"type": "text", "text": prompt_text},
        ])
    ]

    try:
        response = llm.invoke(messages)
        return _flatten_content(response.content)
    except Exception as e:
        return f"ERROR: {e}"


def verify_keywords(pdf_base64: str, candidate_keywords: str, llm: ChatGoogleGenerativeAI,
                    verify_prompt: str) -> str:
    """Second pass: re-read the PDF and prune candidate keywords that the paper does not
    support as its own NEW result. Removal-only — returns a cleaned keywords_el block."""
    pdf_data_uri = f"data:application/pdf;base64,{pdf_base64}"

    # PDF first (identical to pass 1 → implicit cache hit), differing instructions after.
    instruction = (
        f"{verify_prompt}\n\n"
        "---\n"
        "Here are CANDIDATE keywords_el extracted from the attached paper in a first pass. "
        "Verify each line against the paper and return the cleaned keywords_el block "
        "following the instructions above.\n\n"
        f"{candidate_keywords}"
    )

    messages = [
        HumanMessage(content=[
            {"type": "image_url", "image_url": pdf_data_uri},   # shared, cacheable prefix
            {"type": "text", "text": instruction},
        ])
    ]

    try:
        response = llm.invoke(messages)
        return _flatten_content(response.content)
    except Exception as e:
        return f"ERROR: {e}"


#def get_paper_folders(base_dir: Path) -> list[Path]:
#    """Get all paper folders containing main_article.pdf."""
#    folders = []
#    for item in sorted(base_dir.iterdir()):
##        print(f"{item}")
#        if item.is_dir() and (item / "main_article.pdf").exists():
#            folders.append(item)
#    return folders

# Topic → default prompt filename (in the prompts/ dir). Each prompt emits keywords_<topic>.
TOPIC_PROMPTS = {"el": "el.md", "tp": "tp.md", "lb": "lb.md"}
PROMPTS_DIR = Path(__file__).parent / "prompts"


def extract_suppl_from_files(files: list) -> str:
    """Supplementary text from an explicit list of files (flat test-set layout)."""
    if not files:
        return ""
    combined = "\n\n=== SUPPLEMENTARY MATERIALS ===\n\n"
    found = False
    for path in files:
        if not path.is_file() or path.name.startswith('.'):
            continue
        found = True
        try:
            with open(path, "rb") as f:
                combined += process_file_bytes(path.name, f.read())
        except Exception as e:
            combined += f"\n[Error reading file {path.name}: {e}]\n"
    if not found:
        return ""
    if len(combined) > 3000000:
        combined = combined[:3000000] + "\n...[SUPPLEMENTARY DATA TRUNCATED DUE TO SIZE]..."
    return combined


def discover_papers(base_dir: Path, out_dir: Path):
    """Return (papers, mode). Supports two input layouts:

    folder mode — subfolders each containing main_article.pdf (+ optional suppl/); output
                  written in place as bibtex_AI_Generated.txt.
    flat mode   — a directory of `<author>_<topic>_<id>_<year>.pdf` files (+ `..._suppl*` files);
                  output written to out_dir/<pdf-stem>/bibtex_AI_Generated.txt.
    """
    # Never treat scratch / review / output / vcs dirs as paper inputs.
    ignore = {"ai_out", "zero_match_review", "tmp", ".git", "venv", ".venv",
              "__pycache__", "node_modules", "eval"}
    main_pdfs = sorted(p for p in base_dir.rglob("main_article.pdf")
                       if not any(part in ignore for part in p.parts))
    if main_pdfs:
        papers = [dict(name=p.parent.name, pdf=p, suppl_dir=p.parent / "suppl",
                       suppl_files=[], out=p.parent / "bibtex_AI_Generated.txt")
                  for p in main_pdfs]
        return papers, "folder"

    # flat mode
    pdfs = sorted(p for p in base_dir.glob("*.pdf") if "suppl" not in p.name.lower())
    all_files = list(base_dir.glob("*"))
    papers = []
    for pdf in pdfs:
        m = re.search(r"_(el|tp|lb)_(\d+)_", pdf.name)
        pid = m.group(2) if m else pdf.stem
        suppl = [f for f in all_files if "suppl" in f.name.lower() and f"_{pid}_" in f.name]
        papers.append(dict(name=pdf.stem, pdf=pdf, suppl_dir=None, suppl_files=suppl,
                           out=out_dir / pdf.stem / "bibtex_AI_Generated.txt"))
    return papers, "flat"


def main():
    time0 = time.time()
    parser = argparse.ArgumentParser(description="Process PDFs to extract atomic physics keywords")
    parser.add_argument("--single", metavar="FOLDER", help="Process only a single folder")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be processed without running")
    parser.add_argument("--use-vertex", action="store_true", help="Use Vertex AI (requires gcloud auth)")
    parser.add_argument("--topics", default="el",
                        help="Comma-separated topics to run per paper: el,tp,lb (default: el)")
    parser.add_argument("--prompt-dir", metavar="DIR", default=str(PROMPTS_DIR),
                        help=f"Directory holding <topic>.md prompts (default: {PROMPTS_DIR})")
    parser.add_argument("--prompt", metavar="FILE", default=None,
                        help="Override the prompt file (only valid with a single --topics topic)")
    parser.add_argument("--out-dir", metavar="DIR", default=None,
                        help="Output dir for flat-PDF input (default: alongside, ./ai_out)")
    parser.add_argument("--two-pass", action="store_true",
                        help="Run a second verification pass on the EL topic (prunes unsupported keywords)")
    parser.add_argument("--verify-prompt", metavar="FILE", default=str(DEFAULT_VERIFY_PROMPT_PATH),
                        help=f"Verifier prompt file for --two-pass (default: {DEFAULT_VERIFY_PROMPT_PATH})")
    args = parser.parse_args()

    topics = [t.strip().lower() for t in args.topics.split(",") if t.strip()]
    bad = [t for t in topics if t not in TOPIC_PROMPTS]
    if bad:
        print(f"❌ Unknown topic(s): {bad}. Valid: {list(TOPIC_PROMPTS)}")
        sys.exit(1)
    if args.prompt and len(topics) != 1:
        print("❌ --prompt override requires exactly one topic in --topics.")
        sys.exit(1)

    # Load one system prompt per topic (externalized so versions/topics are swappable).
    prompt_dir = Path(args.prompt_dir)
    topic_prompts = {}
    for t in topics:
        path = Path(args.prompt) if (args.prompt and len(topics) == 1) else prompt_dir / TOPIC_PROMPTS[t]
        topic_prompts[t] = load_prompt(path)
        print(f"📜 [{t}] prompt: {path} ({len(topic_prompts[t]):,} chars)")
    verify_prompt = None
    if args.two_pass:
        verify_prompt = load_prompt(Path(args.verify_prompt))
        print(f"📜 verifier prompt (EL): {args.verify_prompt} ({len(verify_prompt):,} chars)")

    # llm = None
    VERTEXAI_PROJECT = "" # Init for error message

    if args.use_vertex:
        print("🚀 Initializing Google Gemini via Vertex AI...")
        VERTEXAI_PROJECT = os.getenv("VERTEXAI_PROJECT")
        VERTEXAI_LOCATION = os.getenv("VERTEXAI_LOCATION")
        VERTEXAI_MODEL = os.getenv("VERTEXAI_MODEL")

        if not all([VERTEXAI_PROJECT, VERTEXAI_LOCATION, VERTEXAI_MODEL]):
            print("❌ Error: Missing Vertex AI configuration in .env file.")
            print("   Please ensure VERTEXAI_PROJECT, VERTEXAI_LOCATION, and VERTEXAI_MODEL are set.")
            sys.exit(1)

        llm = ChatGoogleGenerativeAI(
            model=VERTEXAI_MODEL,
            project=VERTEXAI_PROJECT,
            location=VERTEXAI_LOCATION,
            temperature=0.0
        ) if VERTEXAI_LOCATION != 'us' else \
            ChatGoogleGenerativeAI(
                model=VERTEXAI_MODEL,
                project=VERTEXAI_PROJECT,
                location=VERTEXAI_LOCATION,
                temperature=0.0,
                base_url="https://aiplatform.us.rep.googleapis.com"  # Explicit multi-region URL override
            )
    else:
        # Check API key (only for non-vertex)
        if not GOOGLE_API_KEY:
            print("❌ Error: GOOGLE_API_KEY not found!")
            print("   Please create a .env file with your API key:")
            print("   GOOGLE_API_KEY=your_key_here")
            sys.exit(1)

        print("🚀 Initializing Google Gemini via AI Studio...")
        DEFAULT_MODEL = os.getenv("DEFAULT_MODEL", "gemini-3-flash-preview")
        llm = ChatGoogleGenerativeAI(
            model=DEFAULT_MODEL,
            google_api_key=GOOGLE_API_KEY,
            temperature=0.0
        )

    # Discover papers (folder layout or flat-PDF layout)
    out_dir = Path(args.out_dir) if args.out_dir else (BASE_DIR / "ai_out")
    if args.single:
        target = BASE_DIR / args.single
        if not target.exists():
            print(f"❌ Path not found: {args.single}")
            sys.exit(1)
        papers, mode = discover_papers(target if target.is_dir() else target.parent, out_dir)
        if target.is_file():
            papers = [p for p in papers if p["pdf"] == target]
    else:
        papers, mode = discover_papers(BASE_DIR, out_dir)

    print(f"📁 Found {len(papers)} paper(s) [{mode} layout] · topics: {topics}\n")

    if args.dry_run:
        print("DRY RUN - Would process:")
        for p in papers:
            print(f"  • {p['name']}  (suppl: {'dir' if p['suppl_dir'] and p['suppl_dir'].exists() else len(p['suppl_files'])}) → {p['out']}")
        sys.exit(0)

    success_count = 0
    error_count = 0

    for i, p in enumerate(papers, 1):
        print(f"[{i}/{len(papers)}] Processing: {p['name']}")
        print("  📄 Loading PDF for native upload...")
        pdf_base64 = load_pdf_as_base64(p["pdf"])
        if not pdf_base64:
            print("  ❌ Failed to read PDF file")
            error_count += 1
            continue
        print(f"  📝 Loaded PDF (~{len(pdf_base64) * 3 / 4 / (1024*1024):.1f} MB)")

        # Supplementary materials (dir in folder mode, file list in flat mode)
        if p["suppl_dir"] and p["suppl_dir"].exists():
            suppl_text = extract_supplementary_text(p["suppl_dir"])
        else:
            suppl_text = extract_suppl_from_files(p["suppl_files"])
        if suppl_text:
            print(f"  📝 Added {len(suppl_text):,} characters of supplementary data")

        # Run each requested topic, collect its keyword block
        blocks = []
        failed = False
        try:
            for t in topics:
                print(f"  🤖 [{t}] querying Gemini...")
                res = process_paper(pdf_base64, suppl_text, llm, topic_prompts[t])
                if res.startswith("ERROR:"):
                    raise Exception(res.replace("ERROR: ", ""))
                if t == "el" and args.two_pass and verify_prompt:
                    print("  🔎 [el] verification pass...")
                    res = verify_keywords(pdf_base64, res, llm, verify_prompt)
                    if res.startswith("ERROR:"):
                        raise Exception(res.replace("ERROR: ", ""))
                blocks.append(res.strip())
        except Exception as e:
            error_str = str(e)
            if args.use_vertex and (
                "permissiondenied" in error_str.lower().replace(" ", "") or
                "could not automatically determine credentials" in error_str.lower()
            ):
                print("\n  ❌ Vertex AI Error: Authentication or Permission issue.")
                print("     1. Install gcloud CLI: https://cloud.google.com/sdk/docs/install")
                print("     2. Authenticate: `gcloud auth application-default login`")
                print(f"     3. Set quota project: `gcloud auth application-default set-quota-project {VERTEXAI_PROJECT or '<your-gcloud-project>'}`")
                print(f"\n     Original Error: {error_str}\n")
            else:
                print(f"  ❌ An unexpected error occurred: {error_str}\n")
            failed = True

        if failed:
            error_count += 1
            continue

        p["out"].parent.mkdir(parents=True, exist_ok=True)
        with open(p["out"], "w", encoding="utf-8") as f:
            f.write("\n\n".join(blocks) + "\n")
        print(f"  ✅ Saved {len(blocks)} topic block(s) → {p['out']}")
        success_count += 1
        print()

    # Summary
    print("=" * 50)
    print("Summary:")
    print(f"  ✅ Successful: {success_count}")
    print(f"  ❌ Errors: {error_count}")
    print(f"  📁 Total: {len(papers)}")

    time1 = time.time()
    print(f"Execution time: {round(time1-time0):d} seconds")
    print("-" * 50)

if __name__ == "__main__":
    main()
