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
import re
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


# ── Notation canonicalization (treat equivalent species notations as equal) ──
def _load_reformat():
    p = Path(__file__).parent / "reformat_keywords.py"
    spec = importlib.util.spec_from_file_location("reformat_keywords", p)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m

_RK = _load_reformat()


def _expand_spectra(spec_str):
    """'XLV-XLVIII,LXIII-LXVI' -> [45,46,47,48,63,64,65,66]; None if unparseable."""
    out = []
    for part in spec_str.split(","):
        part = part.strip()
        if not part:
            return None
        if "-" in part:
            a, b = part.split("-", 1)
            na, nb = _RK.roman_to_int(a.strip()), _RK.roman_to_int(b.strip())
            if na is None or nb is None or na > nb:
                return None
            out.extend(range(na, nb + 1))
        else:
            n = _RK.roman_to_int(part)
            if n is None:
                return None
            out.append(n)
    return out


def _expand_part(part):
    """One ';'-part -> set of canonical 'Elem RN' ions (with optional mass prefix), or None."""
    part = part.strip()
    if not part or "like" in part or part.endswith("-"):  # iso-sequence / negative ions: leave raw
        return None
    m = re.match(r"^(\d*)([A-Z][a-z]?)(?:-([A-Z][a-z]?))?\s+([IVXLCDM,\-]+)$", part)
    if not m:
        return None
    mass, e1, e2, spec = m.groups()
    nums = _expand_spectra(spec)
    if nums is None:
        return None
    if e2:  # element range, same spectra
        if e1 not in _RK.SYM2Z or e2 not in _RK.SYM2Z or _RK.SYM2Z[e1] > _RK.SYM2Z[e2]:
            return None
        elems = [_RK.Z2SYM[z] for z in range(_RK.SYM2Z[e1], _RK.SYM2Z[e2] + 1)]
    else:
        elems = [e1]
    return {f"{mass}{el} {_RK.int_to_roman(n)}" for el in elems for n in nums}


def canonical_ions(species):
    """Expand a species string to a frozenset of individual ions; unparseable parts kept raw."""
    ions = set()
    for p in re.sub(r"\s+", " ", species).split(";"):
        p = p.strip()
        if not p:
            continue
        ex = _expand_part(p)
        ions |= ex if ex is not None else {p}
    return frozenset(ions)


def make_normalized_classify(az):
    """Wrap az.classify_species: upgrade NO-MATCH to MATCH when canonical ion sets are EXACTLY
    equal (e.g. 'Te IV,V' == 'Te IV-V'). Never downgrades; off-by-one ranges stay non-matches."""
    base = az.classify_species

    def classify(orig_sp, ai_sp):
        s, l, method = base(orig_sp, ai_sp)
        if s == "MATCH":
            return s, l, method
        try:
            if canonical_ions(orig_sp) == canonical_ions(ai_sp):
                return "MATCH", "MATCH", "notation_normalized"
        except Exception:
            pass
        return s, l, method

    return classify


def perfect_counts(results):
    """Locked metric: per reference entry, perfect = all keywords matched AND zero extras.

    Headline denominator is the number of EVALUABLE entries (those with >=1 reference
    keyword). Entries with no reference keywords cannot be 100% and are excluded.
    n_total (all reference entries) is also reported for context.
    """
    n_total = len(results)
    n_evaluable = 0
    n_empty_gold = 0
    strict_perfect = []
    lenient_perfect = []
    empty_gold_correct = []     # empty gold AND AI also produced nothing
    all_matched_strict = 0
    zero_match_strict = 0
    for eid, r in results.items():
        matched = r["matched"]
        n_orig = len(matched)
        n_strict = sum(1 for m in matched if m[1] == "MATCH")
        n_lenient = sum(1 for m in matched if m[2] == "MATCH")
        n_extras = len(r["extras"])
        if n_orig == 0:
            # empty-gold paper: AI is "perfect" iff it also emitted no keywords
            n_empty_gold += 1
            if n_extras == 0:
                empty_gold_correct.append(eid)
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
        "n_empty_gold": n_empty_gold,
        "strict_perfect": sorted(strict_perfect, key=int),
        "lenient_perfect": sorted(lenient_perfect, key=int),
        "empty_gold_correct": sorted(empty_gold_correct, key=int),
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
    ap.add_argument("--no-normalize", action="store_true", help="Disable notation canonicalization (Te IV,V == Te IV-V)")
    args = ap.parse_args()

    az = load_analyzer(Path(args.analyzer))
    if not args.no_normalize:
        az.classify_species = make_normalized_classify(az)  # upgrade notation-equivalent matches

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
    n = pc["n_evaluable"]           # entries with >=1 reference keyword
    ne = pc["n_empty_gold"]         # entries with empty gold (AI should also be empty)
    n_comb = n + ne                 # all scored papers
    sp = len(pc["strict_perfect"])
    lp = len(pc["lenient_perfect"])
    egc = len(pc["empty_gold_correct"])
    comb = sp + egc                 # combined perfect (incl. correctly-empty)
    pct = lambda x, d: f"{100*x//d}%" if d else "—"

    # Append the locked metric to the report.
    with open(out_path, "a") as f:
        f.write("\n## Locked Metric — Perfect Match + Zero Extras\n\n")
        f.write(f"Evaluable (gold>0) = {n}; empty-gold (AI must be empty) = {ne}; combined = {n_comb}.\n\n")
        f.write("| Metric | Strict | Lenient |\n|---|---|---|\n")
        f.write(f"| Perfect (gold>0) | {sp}/{n} ({pct(sp,n)}) | {lp}/{n} ({pct(lp,n)}) |\n")
        f.write(f"| Empty-gold correct (AI empty) | {egc}/{ne} ({pct(egc,ne)}) | {egc}/{ne} ({pct(egc,ne)}) |\n")
        f.write(f"| **Combined perfect** | **{comb}/{n_comb} ({pct(comb,n_comb)})** | **{comb+ (lp-sp)}/{n_comb}** |\n\n")
        f.write(f"All-matched (strict): {pc['all_matched_strict']}/{n} · "
                f"Zero-match (strict): {pc['zero_match_strict']}/{n}\n\n")
        f.write(f"Strict perfect (gold>0): {', '.join(pc['strict_perfect'])}\n\n")
        f.write(f"Empty-gold correct: {', '.join(pc['empty_gold_correct'])}\n")

    tag = f"[{args.label}] " if args.label else ""
    print("=" * 56)
    print(f"{tag}🎯 PERFECT + NO EXTRAS")
    print(f"  Perfect (gold>0)        : {sp}/{n} ({pct(sp,n)}) strict | {lp}/{n} lenient")
    print(f"  Empty-gold correct      : {egc}/{ne} ({pct(egc,ne)})  (AI correctly emitted nothing)")
    print(f"  COMBINED perfect        : {comb}/{n_comb} ({pct(comb,n_comb)})")
    print(f"  All-matched (gold>0)    : {pc['all_matched_strict']}/{n}")
    print(f"  Zero-match  (gold>0)    : {pc['zero_match_strict']}/{n}")
    print(f"  Report: {out_path}")
    print("=" * 56)


if __name__ == "__main__":
    main()
