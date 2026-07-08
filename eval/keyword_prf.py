#!/usr/bin/env python3
"""Decomposed Precision/Recall/F1 for atomized keyword extraction.

Standard, bounded [0,1], balanced metric. Computed at 3 granularity levels to localize
where quality is lost:
  L1  element-ion only        (did it find the right species?)
  L2  element-ion + code      (right subject code?)
  L3  element-ion + code + type   (right E/T/O?)

Macro = average per paper (papers equal); Micro = pooled over all units.
Empty-gold + empty-AI paper = 1.0; empty-gold + non-empty-AI = 0.0.

Usage: python eval/keyword_prf.py --ai-dir Testing/b --exclude 24044,24085,24090,24128,24129
"""
import argparse, glob, os
from pathlib import Path
import importlib.util

REPO = Path(__file__).resolve().parent.parent
DEFAULT_REF = REPO / "Testing" / "test_set_bibtex.txt"
_spec = importlib.util.spec_from_file_location("kq", Path(__file__).parent / "keyword_quality.py")
kq = importlib.util.module_from_spec(_spec); _spec.loader.exec_module(kq)


def levels(units):
    L1 = {u[0] for u in units}
    L2 = {(u[0], u[1]) for u in units}
    L3 = set(units)
    return L1, L2, L3


def prf(g, a):
    if not g and not a:
        return 1.0, 1.0, 1.0, 0, 0, 0
    tp = len(g & a)
    P = tp / len(a) if a else (1.0 if not g else 0.0)
    R = tp / len(g) if g else (1.0 if not a else 0.0)
    F = 2 * P * R / (P + R) if (P + R) else 0.0
    return P, R, F, tp, len(g), len(a)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ai-dir", required=True)
    ap.add_argument("--ref", default=str(DEFAULT_REF))
    ap.add_argument("--exclude", default="")
    ap.add_argument("--label", default="")
    args = ap.parse_args()
    excl = {e.strip() for e in args.exclude.split(",") if e.strip()}
    gold = kq.parse_bibtex_gold(args.ref)

    macro = {1: [], 2: [], 3: []}           # per-paper F1 lists
    macroP = {1: [], 2: [], 3: []}
    macroR = {1: [], 2: [], 3: []}
    pool = {1: [0, 0, 0], 2: [0, 0, 0], 3: [0, 0, 0]}  # [tp, gold, ai]
    n = 0
    for eid in sorted(gold, key=int):
        if eid in excl:
            continue
        fs = glob.glob(os.path.join(args.ai_dir, f"*_{eid}"))
        ai_text = open(os.path.join(fs[0], "bibtex_AI_Generated.txt")).read() if fs and os.path.exists(os.path.join(fs[0], "bibtex_AI_Generated.txt")) else ""
        g_units = kq.atomize(gold[eid]); a_units = kq.atomize(kq.parse_keywords(ai_text))
        gL = levels(g_units); aL = levels(a_units)
        n += 1
        for i, lvl in enumerate((1, 2, 3)):
            P, R, F, tp, ng, na = prf(gL[i], aL[i])
            macro[lvl].append(F); macroP[lvl].append(P); macroR[lvl].append(R)
            pool[lvl][0] += tp; pool[lvl][1] += ng; pool[lvl][2] += na

    names = {1: "element-ion", 2: "ion + code", 3: "ion+code+type"}
    print("=" * 70)
    print(f"[{args.label}] DECOMPOSED P/R/F1  ({n} papers)")
    print(f"{'Level':16}{'macroP':>8}{'macroR':>8}{'macroF1':>9}{'microP':>9}{'microR':>9}{'microF1':>9}")
    for lvl in (1, 2, 3):
        mP = sum(macroP[lvl]) / n; mR = sum(macroR[lvl]) / n; mF = sum(macro[lvl]) / n
        tp, ng, na = pool[lvl]
        uP = tp / na if na else 0.0; uR = tp / ng if ng else 0.0
        uF = 2 * uP * uR / (uP + uR) if (uP + uR) else 0.0
        print(f"{names[lvl]:16}{mP*100:>7.1f}%{mR*100:>7.1f}%{mF*100:>8.1f}%{uP*100:>8.1f}%{uR*100:>8.1f}%{uF*100:>8.1f}%")
    print("=" * 70)


if __name__ == "__main__":
    main()
