#!/usr/bin/env python3
"""Atomized keyword-quality metric.

Splits each keyword into atomic (element-ion, code, type) units, expanding element
and charge ranges (NOT isoelectronic sequences), collapsing isotopes to the base
element-ion. Scores each paper:

  per gold unit:  exact (ion+code+type) = 1.0 ; ion+code match, type differs = 0.5 ; else 0
  extra          = an AI unit not consumed by any gold unit
  paper score    = max(0, (sum_credit - extras) / total_gold)
  empty gold     = 1.0 if AI also empty, else 0.0

Reports macro average (per-paper), micro (pooled over gold-bearing papers), and a
full per-paper table.

Usage:
  python eval/keyword_quality.py --ai-dir Testing/b --exclude 24044,24085,24090,24128,24129 --out eval/out/quality_b.md
"""
import argparse
import glob
import importlib.util
import os
import re
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
DEFAULT_REF = REPO / "Testing" / "test_set_bibtex.txt"


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m

_RK = _load("reformat_keywords", Path(__file__).parent / "reformat_keywords.py")


def _expand_spectra(spec_str):
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


def expand_species(sp):
    """One species string -> list of individual ion tokens (mass kept). Isoelectronic
    sequences and negative ions are kept whole; unparseable parts kept raw."""
    ions = []
    for part in re.sub(r"\s+", " ", sp).split(";"):
        part = part.strip()
        if not part:
            continue
        if "like" in part or part.endswith("-"):
            ions.append(part)
            continue
        m = re.match(r"^(\d*)([A-Z][a-z]?)(?:-([A-Z][a-z]?))?\s+([IVXLCDM,\-]+)$", part)
        if not m:
            ions.append(part)
            continue
        mass, e1, e2, spec = m.groups()
        nums = _expand_spectra(spec)
        if nums is None:
            ions.append(part)
            continue
        if e2:
            if e1 not in _RK.SYM2Z or e2 not in _RK.SYM2Z or _RK.SYM2Z[e1] > _RK.SYM2Z[e2]:
                ions.append(part)
                continue
            elems = [_RK.Z2SYM[z] for z in range(_RK.SYM2Z[e1], _RK.SYM2Z[e2] + 1)]
        else:
            elems = [e1]
        for el in elems:
            for n in nums:
                ions.append(f"{mass}{el} {_RK.int_to_roman(n)}")
    return ions


def base_ion(ion):
    return re.sub(r"^\d+", "", ion).strip()  # strip isotope mass -> base element-ion


def parse_keywords(text):
    """keywords_el block -> list of (species, code, type), GENINT excluded."""
    m = re.search(r"keywords_el=\{(.*?)\}", text, re.DOTALL)
    if not m:
        return []
    out = []
    for ln in m.group(1).split("\n"):
        ln = ln.strip()
        if not ln:
            continue
        parts = ln.rsplit(":", 2)
        if len(parts) != 3:
            continue
        sp, code, typ = (p.strip() for p in parts)
        if sp.upper() == "GENINT" or code.upper() == "GENINT":
            continue
        out.append((sp, code, typ))
    return out


def atomize(kws):
    """list of (species,code,type) -> set of (base_ion, code, type) units."""
    units = set()
    for sp, code, typ in kws:
        for ion in expand_species(sp):
            units.add((base_ion(ion), code, typ))
    return units


def score_paper(gold_units, ai_units):
    golds = list(gold_units)
    ai = list(ai_units)
    used = [False] * len(ai)
    matched = [None] * len(golds)
    # pass 1: exact (ion, code, type)
    for gi, g in enumerate(golds):
        for i, a in enumerate(ai):
            if not used[i] and a == g:
                used[i] = True
                matched[gi] = 1.0
                break
    # pass 2: partial (ion, code) match, type differs
    for gi, g in enumerate(golds):
        if matched[gi] is not None:
            continue
        for i, a in enumerate(ai):
            if not used[i] and a[0] == g[0] and a[1] == g[1]:
                used[i] = True
                matched[gi] = 0.5
                break
    credit = sum(x for x in matched if x)
    extras = sum(1 for u in used if not u)
    total = len(golds)
    if total == 0:
        return (1.0 if len(ai) == 0 else 0.0), total, credit, extras
    return max(0.0, (credit - extras) / total), total, credit, extras


def parse_bibtex_gold(path):
    content = open(path).read()
    res = {}
    for m in re.finditer(r"@\w+\{(\d+)EL,(.*?keywords_el=\{.*?\})\}", content, re.DOTALL):
        eid = m.group(1)
        g = re.search(r"keywords_el=\{(.*?)\}", m.group(2), re.DOTALL)
        res[eid] = parse_keywords("keywords_el={" + (g.group(1) if g else "") + "}")
    return res


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ai-dir", required=True)
    ap.add_argument("--ref", default=str(DEFAULT_REF))
    ap.add_argument("--exclude", default="")
    ap.add_argument("--out", default=str(REPO / "eval" / "out" / "keyword_quality.md"))
    ap.add_argument("--label", default="")
    args = ap.parse_args()

    excluded = {e.strip() for e in args.exclude.split(",") if e.strip()}
    gold = parse_bibtex_gold(args.ref)

    rows = []  # (eid, score, credit, total_gold, extras, n_ai_units)
    for eid in sorted(gold, key=int):
        if eid in excluded:
            continue
        folders = glob.glob(os.path.join(args.ai_dir, f"*_{eid}"))
        ai_text = ""
        if folders:
            f = os.path.join(folders[0], "bibtex_AI_Generated.txt")
            if os.path.exists(f):
                ai_text = open(f).read()
        g_units = atomize(gold[eid])
        a_units = atomize(parse_keywords(ai_text))
        sc, total, credit, extras = score_paper(g_units, a_units)
        rows.append((eid, sc, credit, total, extras, len(a_units)))

    gold_bearing = [r for r in rows if r[3] > 0]
    empty_gold = [r for r in rows if r[3] == 0]

    # Penalized (extras subtract): r[1] is already the penalized per-paper score.
    macro = sum(r[1] for r in rows) / len(rows) if rows else 0.0
    sum_credit = sum(r[2] for r in gold_bearing)
    sum_extra = sum(r[4] for r in gold_bearing)
    sum_gold = sum(r[3] for r in gold_bearing)
    micro = max(0.0, (sum_credit - sum_extra) / sum_gold) if sum_gold else 0.0
    empty_correct = sum(1 for r in empty_gold if r[1] == 1.0)

    # No-penalty (pure recall with partial credit: credit/gold, extras ignored).
    # Empty-gold handled the same way (100% iff AI empty) so the two metrics stay comparable.
    def recall_score(r):
        eid, sc, credit, total, extras, nai = r
        if total == 0:
            return 1.0 if nai == 0 else 0.0
        return credit / total
    macro_np = sum(recall_score(r) for r in rows) / len(rows) if rows else 0.0
    micro_np = sum_credit / sum_gold if sum_gold else 0.0
    perfect_np = sum(1 for r in rows if recall_score(r) == 1.0)

    lines = ["# Atomized Keyword-Quality Metric\n",
             f"AI dir: `{args.ai_dir}` | excluded: {', '.join(sorted(excluded)) or 'none'}\n",
             "Unit = (element-ion, code, type). Element & charge ranges expanded; isoelectronic kept whole; "
             "isotopes collapsed to base. Exact=1.0, type-only mismatch=0.5, extra subtracts 1.\n",
             f"\n**Papers scored:** {len(rows)}  ({len(gold_bearing)} gold-bearing + {len(empty_gold)} empty-gold)\n",
             f"\n| Metric | Penalize extras | No penalty (recall) |\n|---|---|---|\n",
             f"| **Macro** (avg per-paper) | **{macro*100:.1f}%** | **{macro_np*100:.1f}%** |\n",
             f"| **Micro** (pooled) | **{micro*100:.1f}%** | **{micro_np*100:.1f}%** |\n",
             f"| Perfect papers (100%) | {sum(1 for r in rows if r[1]==1.0)}/{len(rows)} | {perfect_np}/{len(rows)} |\n",
             f"| Empty-gold correct (AI empty) | {empty_correct}/{len(empty_gold)} | {empty_correct}/{len(empty_gold)} |\n",
             "\n## Per-paper\n\n| ID | Quality | credit | gold units | extras | AI units |\n|---|---|---|---|---|---|\n"]
    for eid, sc, credit, total, extras, nai in rows:
        lines.append(f"| {eid} | {sc*100:.0f}% | {credit:g} | {total} | {extras} | {nai} |\n")
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    open(args.out, "w").writelines(lines)

    tag = f"[{args.label}] " if args.label else ""
    print("=" * 56)
    print(f"{tag}ATOMIZED KEYWORD QUALITY    (penalize-extras | no-penalty/recall)")
    print(f"  Papers scored      : {len(rows)} ({len(gold_bearing)} gold + {len(empty_gold)} empty-gold)")
    print(f"  MACRO (avg/paper)  : {macro*100:.1f}%   |   {macro_np*100:.1f}%")
    print(f"  MICRO (pooled)     : {micro*100:.1f}%   |   {micro_np*100:.1f}%")
    print(f"  Perfect (100%)     : {sum(1 for r in rows if r[1]==1.0)}/{len(rows)}   |   {perfect_np}/{len(rows)}")
    print(f"  Empty-gold correct : {empty_correct}/{len(empty_gold)}")
    print(f"  Report: {args.out}")
    print("=" * 56)


if __name__ == "__main__":
    main()
