#!/usr/bin/env python3
"""Deterministic notation normalizer for keywords_el (candidate "reformat" second pass).

Transforms the SPECIES STRING of AI-generated keywords toward the ASBib2 reference
conventions WITHOUT ever dropping a keyword line. Because a mis-notated keyword counts
as both a miss and an extra, fixing its notation can simultaneously create a match and
remove an extra → directly serving the "complete match + no extras" goal.

Transforms (conservative, mechanical):
  T1  Same-element range merge:  `W XLV-XLVIII; W LXIII-LXVI` -> `W XLV-XLVIII,LXIII-LXVI`
  T2  Isoelectronic compression: explicit ion list OR cross-element charge range whose
      members all share the same electron count -> `ElMin-ElMax Seq-like`
      (fires only when >=5 elements, per SPECS line 142: ">4 elements, smooth variation").
  T3  Exotic-atom mapping:        `Ps I`/`Ps`/`Mu`/`Mu I` -> `H I`  (SPECS line 187)

Usage:
    python eval/reformat_keywords.py --ai-dir DIR --out-dir DIR2
Then score DIR2 with eval/score_eval.py and compare to DIR.
"""
import argparse
import re
import shutil
from pathlib import Path

# Z -> symbol (1..118)
_SYMBOLS = ("H He Li Be B C N O F Ne Na Mg Al Si P S Cl Ar K Ca Sc Ti V Cr Mn Fe Co Ni "
            "Cu Zn Ga Ge As Se Br Kr Rb Sr Y Zr Nb Mo Tc Ru Rh Pd Ag Cd In Sn Sb Te I Xe "
            "Cs Ba La Ce Pr Nd Pm Sm Eu Gd Tb Dy Ho Er Tm Yb Lu Hf Ta W Re Os Ir Pt Au Hg "
            "Tl Pb Bi Po At Rn Fr Ra Ac Th Pa U Np Pu Am Cm Bk Cf Es Fm Md No Lr Rf Db Sg "
            "Bh Hs Mt Ds Rg Cn Nh Fl Mc Lv Ts Og").split()
SYM2Z = {s: i + 1 for i, s in enumerate(_SYMBOLS)}
Z2SYM = {i + 1: s for i, s in enumerate(_SYMBOLS)}

_ROMAN = [(1000, "M"), (900, "CM"), (500, "D"), (400, "CD"), (100, "C"), (90, "XC"),
          (50, "L"), (40, "XL"), (10, "X"), (9, "IX"), (5, "V"), (4, "IV"), (1, "I")]


def roman_to_int(s):
    vals = {"I": 1, "V": 5, "X": 10, "L": 50, "C": 100, "D": 500, "M": 1000}
    if not s or any(c not in vals for c in s):
        return None
    total, prev = 0, 0
    for c in reversed(s):
        v = vals[c]
        total += -v if v < prev else v
        prev = max(prev, v)
    return total


def int_to_roman(n):
    out = ""
    for val, sym in _ROMAN:
        while n >= val:
            out += sym
            n -= val
    return out


# A single ion token: "Sym ROMAN" (charge state = roman - 1, electrons = Z - charge)
ION_RE = re.compile(r"^([A-Z][a-z]?)\s+([IVXLCDM]+)$")


def parse_ion(tok):
    """Return (sym, Z, spectrum_int, electrons) for 'Sym ROMAN', else None."""
    m = ION_RE.match(tok.strip())
    if not m:
        return None
    sym, roman = m.group(1), m.group(2)
    if sym not in SYM2Z:
        return None
    spec = roman_to_int(roman)
    if spec is None:
        return None
    Z = SYM2Z[sym]
    electrons = Z - (spec - 1)   # spectrum I = neutral (charge 0)
    return (sym, Z, spec, electrons)


def _seq_label(electrons):
    """Isoelectronic sequence label from electron count: 4 -> 'Be-like'."""
    sym = Z2SYM.get(electrons)
    return f"{sym}-like" if sym else None


def _ions_from_part(part):
    """Expand one ';'-separated part into a list of single ion tokens, if possible.
    Handles 'Sym ROMAN' and cross-element charge range 'SymA ROMAN-SymB ROMAN'.
    Returns list of parsed-ion tuples, or None if not cleanly an ion set."""
    part = part.strip()
    # cross-element charge range: "Ca XI-Cr XV"
    m = re.match(r"^([A-Z][a-z]?\s+[IVXLCDM]+)\s*-\s*([A-Z][a-z]?\s+[IVXLCDM]+)$", part)
    if m:
        a, b = parse_ion(m.group(1)), parse_ion(m.group(2))
        if a and b and a[3] == b[3] and a[1] <= b[1]:
            # enumerate every element from Za..Zb at the same electron count
            ions = []
            for Z in range(a[1], b[1] + 1):
                spec = Z - a[3] + 1
                if spec < 1:
                    return None
                ions.append((Z2SYM[Z], Z, spec, a[3]))
            return ions
        return None
    p = parse_ion(part)
    return [p] if p else None


def try_isoelectronic(species):
    """If the whole species string is an isoelectronic set of >=5 elements, return
    'ElMin-ElMax Seq-like'. Else None."""
    parts = [p.strip() for p in species.split(";") if p.strip()]
    all_ions = []
    for part in parts:
        ions = _ions_from_part(part)
        if ions is None:
            return None
        all_ions.extend(ions)
    if len(all_ions) < 5:
        return None
    electrons = {i[3] for i in all_ions}
    if len(electrons) != 1:
        return None
    e = electrons.pop()
    label = _seq_label(e)
    if not label:
        return None
    Zs = [i[1] for i in all_ions]
    lo, hi = Z2SYM[min(Zs)], Z2SYM[max(Zs)]
    if min(Zs) == max(Zs):
        return None
    return f"{lo}-{hi} {label}"


def merge_same_element_ranges(species):
    """T1: join '; '-separated parts that are the SAME element into comma form.
    'W XLV-XLVIII; W LXIII-LXVI' -> 'W XLV-XLVIII,LXIII-LXVI'."""
    parts = [p.strip() for p in species.split(";") if p.strip()]
    # group consecutive parts by leading element symbol
    out = []
    for part in parts:
        m = re.match(r"^([A-Z][a-z]?)\s+(.+)$", part)
        if not m:
            out.append(("", part))
            continue
        out.append((m.group(1), m.group(2)))
    # merge runs of identical symbol
    merged = []
    i = 0
    while i < len(out):
        sym, rest = out[i]
        if sym == "":
            merged.append(rest)
            i += 1
            continue
        specs = [rest]
        j = i + 1
        while j < len(out) and out[j][0] == sym:
            specs.append(out[j][1])
            j += 1
        if len(specs) > 1:
            merged.append(f"{sym} " + ",".join(specs))
        else:
            merged.append(f"{sym} {rest}")
        i = j
    return "; ".join(merged)


EXOTIC = {"Ps", "Ps I", "Mu", "Mu I", "Muonium", "Positronium"}


def reformat_species(species):
    """Apply transforms to a species string. Returns (new_species, note)."""
    s = species.strip()
    # T3 exotic -> H I
    if s in EXOTIC:
        return "H I", "T3:exotic->H I"
    # T2 isoelectronic compression (try before T1)
    iso = try_isoelectronic(s)
    if iso and iso != s:
        return iso, "T2:isoelectronic"
    # T1 same-element range merge
    merged = merge_same_element_ranges(s)
    if merged != s:
        return merged, "T1:range-merge"
    return s, ""


KW_LINE_RE = re.compile(r"^(.*?):\s*([A-Za-z]+):\s*([A-Za-z0-9.]+)\s*$")


def reformat_block(text):
    """Reformat the keywords_el={...} block in `text`. Returns (new_text, n_changes)."""
    m = re.search(r"(keywords_el=\{)(.*?)(\})", text, re.DOTALL)
    if not m:
        return text, 0
    inner = m.group(2)
    lines = inner.split("\n")
    new_lines = []
    n = 0
    for line in lines:
        raw = line.strip()
        if not raw:
            new_lines.append(line)
            continue
        km = KW_LINE_RE.match(raw)
        if not km:
            new_lines.append(line)
            continue
        species, code, mtype = km.group(1).strip(), km.group(2), km.group(3)
        new_species, note = reformat_species(species)
        if note:
            n += 1
            new_lines.append(f"{new_species}: {code}: {mtype}")
        else:
            new_lines.append(line)
    new_inner = "\n".join(new_lines)
    return text[:m.start(2)] + new_inner + text[m.end(2):], n


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ai-dir", required=True)
    ap.add_argument("--out-dir", required=True)
    ap.add_argument("--verbose", action="store_true")
    args = ap.parse_args()

    src, dst = Path(args.ai_dir), Path(args.out_dir)
    if dst.exists():
        shutil.rmtree(dst)
    total_changes = 0
    folders = 0
    for folder in sorted(src.iterdir()):
        f = folder / "bibtex_AI_Generated.txt"
        if not f.exists():
            continue
        folders += 1
        (dst / folder.name).mkdir(parents=True, exist_ok=True)
        text = f.read_text(encoding="utf-8")
        new_text, n = reformat_block(text)
        if n and args.verbose:
            print(f"{folder.name}: {n} line(s) reformatted")
        total_changes += n
        (dst / folder.name / "bibtex_AI_Generated.txt").write_text(new_text, encoding="utf-8")
    print(f"Reformatted {folders} folders, {total_changes} keyword lines changed -> {dst}")


if __name__ == "__main__":
    main()
