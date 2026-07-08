#!/usr/bin/env python3
"""
LangChain PDF Processing Script for Atomic Energy Levels Keywords
Uses Google Gemini to extract keywords_el from scientific papers.

Usage:
    python process_pdfs_langchain.py                    # Process all papers from the current directory
    python process_pdfs_langchain.py --single FOLDER    # Process single paper folder
    python process_pdfs_langchain.py --dry-run          # Show what would be processed
    python process_pdfs_langchain.py --prompt FILE      # Use a specific system prompt (default: prompts/el.md)
    python process_pdfs_langchain.py --two-pass         # Add a verification pass that prunes unsupported keywords

The system prompt is loaded from a file (default prompts/el.md) so prompt versions
can be swapped without editing this script. --two-pass runs a second Gemini call
(prompts/el_verify.md) that re-reads the PDF and removes keywords the paper does not
support as its own new result.
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

# Claude's suggestion
def get_paper_folders(base_dir: Path) -> list[Path]:
    """Get all paper folders containing main_article.pdf."""
    folders = sorted(
        p.parent for p in base_dir.rglob("main_article.pdf")
    )
    return folders


def main():
    time0 = time.time()
    parser = argparse.ArgumentParser(description="Process PDFs to extract atomic physics keywords")
    parser.add_argument("--single", metavar="FOLDER", help="Process only a single folder")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be processed without running")
    parser.add_argument("--use-vertex", action="store_true", help="Use Vertex AI (requires gcloud auth)")
    parser.add_argument("--prompt", metavar="FILE", default=str(DEFAULT_PROMPT_PATH),
                        help=f"System prompt file (default: {DEFAULT_PROMPT_PATH})")
    parser.add_argument("--two-pass", action="store_true",
                        help="Run a second verification pass that prunes unsupported keywords")
    parser.add_argument("--verify-prompt", metavar="FILE", default=str(DEFAULT_VERIFY_PROMPT_PATH),
                        help=f"Verifier prompt file for --two-pass (default: {DEFAULT_VERIFY_PROMPT_PATH})")
    args = parser.parse_args()

    # Load the system prompt from file (externalized so versions are swappable).
    system_prompt = load_prompt(Path(args.prompt))
    print(f"📜 Loaded system prompt: {args.prompt} ({len(system_prompt):,} chars)")
    verify_prompt = None
    if args.two_pass:
        verify_prompt = load_prompt(Path(args.verify_prompt))
        print(f"📜 Loaded verifier prompt: {args.verify_prompt} ({len(verify_prompt):,} chars)")

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
            location=VERTEXAI_LOCATION,  # "us"
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

    # Get folders to process
    if args.single:
        folder_path = BASE_DIR / args.single
        if not folder_path.exists():
            print(f"❌ Folder not found: {args.single}")
            sys.exit(1)
        folders = [folder_path]
    else:
        folders = get_paper_folders(BASE_DIR)

    print(f"📁 Found {len(folders)} paper(s) to process\n")

    if args.dry_run:
        print("DRY RUN - Would process:")
        for folder in folders:
            print(f"  • {folder.name}")
        sys.exit(0)

    # Process each paper
    success_count = 0
    error_count = 0

    for i, folder in enumerate(folders, 1):
        pdf_path = folder / "main_article.pdf"
        output_path = folder / "bibtex_AI_Generated.txt"
        
        print(f"[{i}/{len(folders)}] Processing: {folder.name}")
        
        # Load PDF as base64 for native upload
        print("  📄 Loading PDF for native upload...")
        pdf_base64 = load_pdf_as_base64(pdf_path)
        
        if not pdf_base64:
            print("  ❌ Failed to read PDF file")
            error_count += 1
            continue
        
        pdf_size_mb = len(pdf_base64) * 3 / 4 / (1024 * 1024)  # Approximate original file size
        print(f"  📝 Loaded PDF (~{pdf_size_mb:.1f} MB)")
        
        # Extract Supplementary Materials
        suppl_dir = folder / "suppl"
        suppl_text = ""
        if suppl_dir.exists():
            print("  📂 Extracting supplementary materials...")
            suppl_text = extract_supplementary_text(suppl_dir)
            if suppl_text:
                print(f"  📝 Added {len(suppl_text):,} characters of supplementary data")
        
        # Process with Gemini
        print("  🤖 Sending native PDF + supplementary data to Gemini...")
        try:
            result = process_paper(pdf_base64, suppl_text, llm, system_prompt)
            if result.startswith("ERROR:"):
                raise Exception(result.replace("ERROR: ", ""))
            if args.two_pass and verify_prompt:
                print("  🔎 Verification pass (pruning unsupported keywords)...")
                result = verify_keywords(pdf_base64, result, llm, verify_prompt)
            if result.startswith("ERROR:"):
                # Re-raise to be caught by the except block
                raise Exception(result.replace("ERROR: ", ""))
        except Exception as e:
            error_str = str(e)
            if args.use_vertex and (
                "permissiondenied" in error_str.lower().replace(" ", "") or
                "could not automatically determine credentials" in error_str.lower()
            ):
                 print("\n  ❌ Vertex AI Error: Authentication or Permission issue.")
                 print("     This is likely due to missing or incorrect Google Cloud configuration.")
                 print("\n     TROUBLESHOOTING:")
                 print("     1. Install the gcloud CLI: https://cloud.google.com/sdk/docs/install")
                 print("     2. Authenticate by running: `gcloud auth application-default login`")
                 print(f"     3. If needed, set your quota project: `gcloud auth application-default set-quota-project {VERTEXAI_PROJECT or '<your-gcloud-project>'}`")
                 print(f"\n     Original Error: {error_str}\n")
            else:
                print(f"  ❌ An unexpected error occurred: {error_str}\n")

            error_count += 1
            continue
        
        # Save output
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(result)
        
        print(f"  ✅ Saved to: bibtex_AI_Generated.txt")
        success_count += 1
        print()

    # Summary
    print("=" * 50)
    print("Summary:")
    print(f"  ✅ Successful: {success_count}")
    print(f"  ❌ Errors: {error_count}")
    print(f"  📁 Total: {len(folders)}")

    time1 = time.time()
    print(f"Execution time: {round(time1-time0):d} seconds")
    print("-" * 50)

if __name__ == "__main__":
    main()
