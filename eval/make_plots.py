#!/usr/bin/env python3
"""Benchmark visualizations for the EL keyword-extraction eval.

Produces eval/out/benchmark_overview.png with 6 panels that communicate the findings:
  1. Decomposed P/R/F1 by granularity level  (the code bottleneck)
  2. Macro vs Micro F1 by level               (paper-size sensitivity)
  3. Per-paper full-F1 distribution           (shape / how many near-perfect vs near-zero)
  4. Quality vs paper size (gold units)        (model weaker on big papers)
  5. Extra-unit frequency by subject code      (what over-assignment looks like)
  6. Top papers by atomized extras             (concentration; 24076 dominance)

Usage: python eval/make_plots.py --ai-dir Testing/b --exclude 24044,24085,24090,24128,24129 --label B
"""
import argparse, glob, os, importlib.util
from collections import Counter
from pathlib import Path
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

REPO = Path(__file__).resolve().parent.parent
_spec = importlib.util.spec_from_file_location("kq", Path(__file__).parent / "keyword_quality.py")
kq = importlib.util.module_from_spec(_spec); _spec.loader.exec_module(kq)


def prf(g, a):
    if not g and not a:
        return 1.0, 1.0, 1.0
    tp = len(g & a)
    P = tp / len(a) if a else (1.0 if not g else 0.0)
    R = tp / len(g) if g else (1.0 if not a else 0.0)
    F = 2 * P * R / (P + R) if (P + R) else 0.0
    return P, R, F


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ai-dir", required=True)
    ap.add_argument("--ref", default=str(REPO / "Testing" / "test_set_bibtex.txt"))
    ap.add_argument("--exclude", default="")
    ap.add_argument("--label", default="B")
    ap.add_argument("--out", default=str(REPO / "eval" / "out" / "benchmark_overview.png"))
    args = ap.parse_args()
    excl = {e.strip() for e in args.exclude.split(",") if e.strip()}
    gold = kq.parse_bibtex_gold(args.ref)

    papers = []   # dict per paper
    code_extras = Counter()
    oc = dict(exact=0, partial=0, missed=0, matched=0, extra=0)  # pooled unit outcomes
    for eid in sorted(gold, key=int):
        if eid in excl:
            continue
        fs = glob.glob(os.path.join(args.ai_dir, f"*_{eid}"))
        f = os.path.join(fs[0], "bibtex_AI_Generated.txt") if fs else ""
        ai_text = open(f).read() if f and os.path.exists(f) else ""
        g = kq.atomize(gold[eid]); a = kq.atomize(kq.parse_keywords(ai_text))
        gic = {(i, c) for (i, c, t) in g}
        aic = {(i, c) for (i, c, t) in a}
        a_full = set(a)
        extras = [(i, c) for (i, c, t) in a if (i, c) not in gic]
        for (i, c) in extras:
            code_extras[c] += 1
        # pooled outcome accounting
        for u in g:
            if u in a_full:
                oc["exact"] += 1
            elif (u[0], u[1]) in aic:
                oc["partial"] += 1
            else:
                oc["missed"] += 1
        for u in a:
            if (u[0], u[1]) in gic:
                oc["matched"] += 1
            else:
                oc["extra"] += 1
        P1, R1, F1 = prf({u[0] for u in g}, {u[0] for u in a})
        P2, R2, F2 = prf({u[:2] for u in g}, {u[:2] for u in a})
        P3, R3, F3 = prf(g, a)
        papers.append(dict(eid=eid, gsize=len(g), asize=len(a), nextra=len(extras),
                           F1=F1, F2=F2, F3=F3, R3=R3,
                           P=[P1, P2, P3], R=[R1, R2, R3], F=[F1, F2, F3]))
    n = len(papers)
    lvl_names = ["element-ion", "+code", "+code+type"]

    def macro(key, idx):
        return sum(p[key][idx] for p in papers) / n
    def micro(metric, lvlfn):
        tp = gd = ad = 0
        for p in papers:
            pass
        return None  # micro computed inline below

    # micro pooled per level
    pool = [[0, 0, 0] for _ in range(3)]  # tp, gold, ai
    for eid in sorted(gold, key=int):
        if eid in excl:
            continue
        fs = glob.glob(os.path.join(args.ai_dir, f"*_{eid}"))
        f = os.path.join(fs[0], "bibtex_AI_Generated.txt") if fs else ""
        ai_text = open(f).read() if f and os.path.exists(f) else ""
        g = kq.atomize(gold[eid]); a = kq.atomize(kq.parse_keywords(ai_text))
        gl = [{u[0] for u in g}, {u[:2] for u in g}, set(g)]
        al = [{u[0] for u in a}, {u[:2] for u in a}, set(a)]
        for k in range(3):
            pool[k][0] += len(gl[k] & al[k]); pool[k][1] += len(gl[k]); pool[k][2] += len(al[k])

    def microF(k):
        tp, gd, ad = pool[k]
        P = tp / ad if ad else 0; R = tp / gd if gd else 0
        return 2 * P * R / (P + R) if (P + R) else 0

    fig, ax = plt.subplots(2, 2, figsize=(12.5, 9.5))
    fig.suptitle(f"EL Keyword Extraction — Benchmark Overview (Run {args.label}, {n} papers)",
                 fontsize=15, fontweight="bold")

    # Panel 1: decomposed P/R/F1 (macro)
    x = range(3); w = 0.25
    Pm = [macro("P", i) * 100 for i in range(3)]
    Rm = [macro("R", i) * 100 for i in range(3)]
    Fm = [macro("F", i) * 100 for i in range(3)]
    a0 = ax[0, 0]
    a0.bar([i - w for i in x], Pm, w, label="Precision", color="#e07a5f")
    a0.bar(list(x), Rm, w, label="Recall", color="#81b29a")
    a0.bar([i + w for i in x], Fm, w, label="F1", color="#3d405b")
    a0.set_xticks(list(x)); a0.set_xticklabels(lvl_names)
    a0.set_ylabel("%"); a0.set_title("1. Per-paper avg P/R/F1 by detail level")
    a0.set_ylim(0, 100); a0.legend(fontsize=8); a0.grid(axis="y", alpha=0.3)
    for i in range(3):
        a0.text(i + w, Fm[i] + 1, f"{Fm[i]:.0f}", ha="center", fontsize=8)

    # Panel 2: macro vs micro F1
    a1 = ax[0, 1]
    macroF1 = [macro("F", i) * 100 for i in range(3)]
    microF1 = [microF(i) * 100 for i in range(3)]
    a1.plot(lvl_names, macroF1, "o-", label="Per-paper average (each paper equal)", color="#3d405b", lw=2)
    a1.plot(lvl_names, microF1, "s--", label="Per-keyword pooled (each keyword equal)", color="#e07a5f", lw=2)
    a1.set_ylabel("F1 %"); a1.set_title("2. Per-paper avg vs per-keyword pooled F1\n(gap = the model is weaker on big papers)")
    a1.set_ylim(0, 100); a1.legend(fontsize=8); a1.grid(alpha=0.3)

    # Panel 3: per-paper full F1 histogram
    a2 = ax[1, 0]
    a2.hist([p["F3"] * 100 for p in papers], bins=20, color="#81b29a", edgecolor="black")
    a2.set_xlabel("paper score: full-match F1 % (ion+code+type)"); a2.set_ylabel("# papers")
    a2.set_title("3. How many papers at each quality\n(full-match F1 per paper)")
    a2.grid(axis="y", alpha=0.3)

    # Panel 4: quality vs paper size
    a3 = ax[1, 1]
    gs = [p["gsize"] for p in papers]; rr = [p["F3"] * 100 for p in papers]
    a3.scatter(gs, rr, alpha=0.6, color="#3d405b")
    a3.set_xlabel("reference keywords in paper (size)"); a3.set_ylabel("paper full-match F1 %")
    a3.set_title("4. Quality vs paper size\n(bigger papers → lower)")
    a3.grid(alpha=0.3)

    plt.tight_layout(rect=[0, 0, 1, 0.96])
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    plt.savefig(args.out, dpi=130)
    print(f"Wrote {args.out}")
    print(f"  macro F1 by level: {[round(macro('F',i)*100,1) for i in range(3)]}")
    print(f"  micro F1 by level: {[round(microF(i)*100,1) for i in range(3)]}")
    print(f"  top extra codes  : {code_extras.most_common(6)}")


if __name__ == "__main__":
    main()
