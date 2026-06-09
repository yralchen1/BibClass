#!/usr/bin/env python3
"""Parameterized scorer for EL-keyword extraction.

Reuses the matching logic in Testing/analyze_keywords.py (imported, not copied, so
the two never diverge) and adds the locked primary metric:
**STRICT perfect-match + zero-extras** — entries where every reference keyword
matched AND the AI produced no extra keywords.

Usage:
    python eval/score_eval.py --ai-dir "Testing/EL_test_set 3" \
        --ref Testing/test_set_bibtex.txt --out eval/out/v4.md
"""
import argparse
import importlib.util
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
DEFAULT_REF = REPO / "Testing" / "test_set_bibtex.txt"
DEFAULT_ANALYZER = REPO / "Testing" / "analyze_keywords.py"


def load_analyzer(path: Path):
    """Import analyze_keywords.py as a module (its __main__ block does not run on import)."""
    spec = importlib.util.spec_from_file_location("analyze_keywords", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def perfect_counts(results):
    """Locked metric: per reference entry, perfect = all keywords matched AND zero extras.

    Headline denominator is the number of EVALUABLE entries (those with >=1 reference
    keyword). Entries with no reference keywords cannot be 100% and are excluded.
    n_total (all reference entries) is also reported for context.
    """
    n_total = len(results)
    n_evaluable = 0
    strict_perfect = []
    lenient_perfect = []
    all_matched_strict = 0
    zero_match_strict = 0
    for eid, r in results.items():
        matched = r["matched"]
        n_orig = len(matched)
        n_strict = sum(1 for m in matched if m[1] == "MATCH")
        n_lenient = sum(1 for m in matched if m[2] == "MATCH")
        n_extras = len(r["extras"])
        if n_orig == 0:
            continue
        n_evaluable += 1
        if n_strict == n_orig:
            all_matched_strict += 1
        if n_strict == 0:
            zero_match_strict += 1
        if n_strict == n_orig and n_extras == 0:
            strict_perfect.append(eid)
        if n_lenient == n_orig and n_extras == 0:
            lenient_perfect.append(eid)
    return {
        "n_total": n_total,
        "n_evaluable": n_evaluable,
        "strict_perfect": sorted(strict_perfect, key=int),
        "lenient_perfect": sorted(lenient_perfect, key=int),
        "all_matched_strict": all_matched_strict,
        "zero_match_strict": zero_match_strict,
    }


def main():
    ap = argparse.ArgumentParser(description="Score EL-keyword AI output against the reference set.")
    ap.add_argument("--ai-dir", required=True, help="Folder of <paper>/bibtex_AI_Generated.txt outputs")
    ap.add_argument("--ref", default=str(DEFAULT_REF), help=f"Reference bibtex (default: {DEFAULT_REF})")
    ap.add_argument("--out", default=str(REPO / "eval" / "out" / "match_analysis.md"),
                    help="Output markdown report path")
    ap.add_argument("--analyzer", default=str(DEFAULT_ANALYZER),
                    help=f"analyze_keywords.py to reuse (default: {DEFAULT_ANALYZER})")
    ap.add_argument("--label", default="", help="Optional label for stdout (e.g. 'v4', 'two-pass')")
    ap.add_argument("--exclude", default="", help="Comma-separated reference IDs to exclude (e.g. few-shot example papers held out of scoring)")
    args = ap.parse_args()

    az = load_analyzer(Path(args.analyzer))

    orig = az.parse_bibtex(args.ref)
    ai = az.parse_ai_folders(args.ai_dir)
    results = az.analyze(orig, ai)

    excluded = {e.strip() for e in args.exclude.split(",") if e.strip()}
    if excluded:
        results = {eid: r for eid, r in results.items() if eid not in excluded}
        print(f"Excluded {len(excluded)} held-out entries: {', '.join(sorted(excluded))}")

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    az.write_report(results, str(out_path))

    pc = perfect_counts(results)
    n = pc["n_evaluable"]           # headline denominator: entries with >=1 reference keyword
    n_all = pc["n_total"]           # all reference entries (context)
    sp = len(pc["strict_perfect"])
    lp = len(pc["lenient_perfect"])
    pct = lambda x: f"{100*x//n}%" if n else "—"

    # Append the locked metric to the report.
    with open(out_path, "a") as f:
        f.write("\n## Locked Metric — Perfect Match + Zero Extras\n\n")
        f.write(f"Denominator = evaluable entries (>=1 reference keyword) = {n}. "
                f"Total reference entries = {n_all}.\n\n")
        f.write("| Metric | Strict | Lenient |\n|---|---|---|\n")
        f.write(f"| Perfect + no extras | {sp}/{n} ({pct(sp)}) | {lp}/{n} ({pct(lp)}) |\n\n")
        f.write(f"All-matched (strict): {pc['all_matched_strict']}/{n} · "
                f"Zero-match (strict): {pc['zero_match_strict']}/{n}\n\n")
        f.write(f"Strict perfect entries: {', '.join(pc['strict_perfect'])}\n")

    tag = f"[{args.label}] " if args.label else ""
    print("=" * 56)
    print(f"{tag}🎯 PERFECT + NO EXTRAS (locked metric)")
    print(f"  Denominator = {n} evaluable entries (>=1 ref keyword); {n_all} ref entries total")
    print(f"  Strict : {sp}/{n} ({pct(sp)})")
    print(f"  Lenient: {lp}/{n} ({pct(lp)})")
    print(f"  All-matched (strict): {pc['all_matched_strict']}/{n}")
    print(f"  Zero-match  (strict): {pc['zero_match_strict']}/{n}")
    print(f"  Report: {out_path}")
    print("=" * 56)


if __name__ == "__main__":
    main()
