#!/usr/bin/env python3
"""
analyze_keywords.py
Compare original keywords_el (test_set_bibtex.txt) with
AI-generated keywords_el (test/*/bibtex_AI_Generated.txt).
Output: keywords_match_analysis_v3.md
"""

import re
import os

# ── Element lookup tables ──────────────────────────────────────
ELEMENT_SYMBOLS = [
    'H','He','Li','Be','B','C','N','O','F','Ne',
    'Na','Mg','Al','Si','P','S','Cl','Ar','K','Ca',
    'Sc','Ti','V','Cr','Mn','Fe','Co','Ni','Cu','Zn',
    'Ga','Ge','As','Se','Br','Kr','Rb','Sr','Y','Zr',
    'Nb','Mo','Tc','Ru','Rh','Pd','Ag','Cd','In','Sn',
    'Sb','Te','I','Xe','Cs','Ba','La','Ce','Pr','Nd',
    'Pm','Sm','Eu','Gd','Tb','Dy','Ho','Er','Tm','Yb',
    'Lu','Hf','Ta','W','Re','Os','Ir','Pt','Au','Hg',
    'Tl','Pb','Bi','Po','At','Rn','Fr','Ra','Ac','Th',
    'Pa','U','Np','Pu','Am','Cm','Bk','Cf','Es','Fm',
    'Md','No','Lr','Rf','Db','Sg','Bh','Hs','Mt','Ds',
    'Rg','Cn','Nh','Fl','Mc','Lv','Ts','Og'
]
ELEMENT_Z  = {s: i+1 for i, s in enumerate(ELEMENT_SYMBOLS)}
Z_ELEMENT  = {i+1: s for i, s in enumerate(ELEMENT_SYMBOLS)}

ROMAN_VALS = [
    (1000,'M'),(900,'CM'),(500,'D'),(400,'CD'),
    (100,'C'),(90,'XC'),(50,'L'),(40,'XL'),
    (10,'X'),(9,'IX'),(5,'V'),(4,'IV'),(1,'I')
]

def to_roman(n):
    r = ''
    for val, sym in ROMAN_VALS:
        while n >= val:
            r += sym
            n -= val
    return r

# ── Species string utilities ───────────────────────────────────
def normalize_species(s):
    s = re.sub(r'\s+', ' ', s).strip()
    s = re.sub(r'\s*;\s*', '; ', s)
    return s

def tokenize(species_str):
    """Split species string on ';' → frozenset of stripped tokens."""
    return frozenset(t.strip() for t in normalize_species(species_str).split(';'))

def strip_mass(token):
    """Strip leading integer mass number: '13C V' → 'C V', '1H I' → 'H I'."""
    return re.sub(r'^\d+', '', token).strip()

def is_isotope_of(child_tok, parent_tok):
    """True if child_tok is an isotope variant of parent_tok (child has mass prefix)."""
    return child_tok != parent_tok and strip_mass(child_tok) == parent_tok

def base_form(tok):
    """Return the base form of a token (strip mass number if present)."""
    return strip_mass(tok)

# ── Isoelectronic expansion ────────────────────────────────────
def try_expand_isoelectronic(species_str):
    """
    Expand 'ELEM1-ELEM2 [RN1-RN2] SEQ-like' → frozenset of 'ELEM RN' tokens.
    Returns None if the pattern is not recognized.
    """
    s = normalize_species(species_str).strip()

    # Pattern 1: "ELEM1-ELEM2 SEQ-like"
    m = re.match(r'^([A-Z][a-z]?)-([A-Z][a-z]?)\s+([A-Z][a-z]?)-like$', s)
    if not m:
        # Pattern 2: "ELEM1-ELEM2 RN1-RN2 SEQ-like" (explicit Roman numeral range is redundant)
        m = re.match(
            r'^([A-Z][a-z]?)-([A-Z][a-z]?)\s+[IVXLCDM]+-[IVXLCDM]+\s+([A-Z][a-z]?)-like$', s
        )
    if not m:
        return None

    e1, e2, seq = m.group(1), m.group(2), m.group(3)
    if e1 not in ELEMENT_Z or e2 not in ELEMENT_Z or seq not in ELEMENT_Z:
        return None

    z1, z2   = ELEMENT_Z[e1], ELEMENT_Z[e2]
    n_elec   = ELEMENT_Z[seq]  # He-like → 2, Be-like → 4, etc.

    tokens = set()
    for z in range(z1, z2 + 1):
        if z not in Z_ELEMENT:
            continue
        charge = z - n_elec
        if charge < 0:
            continue
        tokens.add(f"{Z_ELEMENT[z]} {to_roman(charge + 1)}")

    return frozenset(tokens) if tokens else None

# ── Per-keyword classification ─────────────────────────────────
def classify_species(orig_sp, ai_sp):
    """
    Compare two species strings.
    Returns (strict_label, lenient_label, method_note).
    """
    # 1. Exact string match after normalization
    if normalize_species(orig_sp) == normalize_species(ai_sp):
        return 'MATCH', 'MATCH', 'exact'

    orig_tok = tokenize(orig_sp)
    ai_tok   = tokenize(ai_sp)

    # 2. Token sets are equal (order differs)
    if orig_tok == ai_tok:
        return 'MATCH', 'MATCH', 'normalized'

    # 3. AI is a proper superset of orig
    if orig_tok < ai_tok:
        extra = ai_tok - orig_tok
        # Are all extra tokens isotope variants of existing orig tokens?
        if all(any(is_isotope_of(e, o) for o in orig_tok) for e in extra):
            return 'PARTIAL', 'PARTIAL', 'AI_isotope_expansion'
        # Extra tokens are genuinely different species (e.g. Ps I added alongside H I)
        return 'MATCH', 'MATCH', 'AI_added_species'

    # 4. AI is a proper subset of orig
    if ai_tok < orig_tok:
        missing = orig_tok - ai_tok

        def base_covered(m_tok):
            base = strip_mass(m_tok)
            if base == m_tok:
                # m_tok has no mass prefix → AI must have an isotope variant of it
                return any(is_isotope_of(a, m_tok) for a in ai_tok)
            else:
                # m_tok has mass prefix (e.g. '1H I') → base ('H I') must be in AI
                return base in ai_tok or any(strip_mass(a) == base for a in ai_tok)

        if all(base_covered(m) for m in missing):
            return 'PARTIAL', 'MATCH', 'AI_dropped_base'
        return 'NO MATCH', 'NO MATCH', 'subset_mismatch'

    # 5. Partial overlap → try isoelectronic expansion
    orig_exp = try_expand_isoelectronic(orig_sp)
    ai_exp   = try_expand_isoelectronic(ai_sp)

    cmp_orig = orig_exp if orig_exp is not None else orig_tok
    cmp_ai   = ai_exp   if ai_exp   is not None else ai_tok

    if cmp_orig == cmp_ai:
        return 'MATCH', 'MATCH', 'isoelectronic'

    return 'NO MATCH', 'NO MATCH', 'mismatch'


def match_one(orig_kw, ai_kws, used_indices):
    """
    Find best AI match for a single original keyword.
    orig_kw: (species, type, source)
    ai_kws:  list of (species, type, source)
    used_indices: set of AI indices already consumed
    Returns (strict, lenient, method, matched_ai_str, ai_index_consumed)
    """
    o_sp, o_type, o_src = orig_kw
    candidates = [
        (i, kw) for i, kw in enumerate(ai_kws)
        if i not in used_indices and kw[1] == o_type and kw[2] == o_src
    ]

    if not candidates:
        return 'NO MATCH', 'NO MATCH', 'no_type_match', '—', None

    PRIO = {'MATCH': 0, 'PARTIAL': 1, 'NO MATCH': 2}
    best = None
    best_idx = None

    for ai_idx, ai_kw in candidates:
        s, l, method = classify_species(o_sp, ai_kw[0])
        if best is None or PRIO[s] < PRIO[best[0]]:
            best = (s, l, method, f"{ai_kw[0]}: {ai_kw[1]}: {ai_kw[2]}")
            best_idx = ai_idx

    s, l, method, ai_str = best
    consumed = best_idx if s != 'NO MATCH' else None
    return s, l, method, ai_str, consumed

# ── Parsing ────────────────────────────────────────────────────
def parse_kw_line(line):
    """Parse 'SPECIES: TYPE: SOURCE' → (species, type, source) or None."""
    line = line.strip()
    if not line:
        return None
    parts = line.rsplit(':', 2)
    if len(parts) != 3:
        return None
    species = parts[0].strip()
    kw_type = parts[1].strip()
    source  = parts[2].strip()
    if not species or not kw_type or not source:
        return None
    return (species, kw_type, source)

def parse_kw_block(text):
    """Parse a keywords block text → list of (species, type, source)."""
    kws = []
    for line in text.strip().splitlines():
        kw = parse_kw_line(line)
        if kw:
            kws.append(kw)
    return kws

def filter_genint(kw_list):
    return [kw for kw in kw_list if not kw[0].upper().startswith('GENINT')]

def parse_bibtex(path):
    """Parse test_set_bibtex.txt → {id: {author, year, kws}}."""
    with open(path) as f:
        content = f.read()
    result = {}
    pattern = re.compile(
        r'@\w+\{(\d+)EL,.*?author=\{(.*?)\}.*?year=\{(\d+)\}.*?keywords_el=\{(.*?)\}',
        re.DOTALL
    )
    for m in pattern.finditer(content):
        eid = m.group(1)
        raw_author = m.group(2).strip()
        first = raw_author.split(' and ')[0].strip()
        last  = first.split(',')[0].strip() if ',' in first else first.split()[-1].strip()
        year  = m.group(3)
        kws   = filter_genint(parse_kw_block(m.group(4)))
        result[eid] = {'author': last, 'year': year, 'kws': kws}
    return result

def parse_ai_folders(test_dir):
    """Parse test/*/bibtex_AI_Generated.txt → {id: [(species, type, source)]}."""
    result = {}
    for folder in os.listdir(test_dir):
        eid = folder.split('_')[-1]
        fpath = os.path.join(test_dir, folder, 'bibtex_AI_Generated.txt')
        if not os.path.exists(fpath):
            continue
        with open(fpath) as f:
            text = f.read()
        m = re.search(r'keywords_el=\{(.*?)\}', text, re.DOTALL)
        if m:
            result[eid] = filter_genint(parse_kw_block(m.group(1)))
    return result

# ── Analysis ───────────────────────────────────────────────────
def analyze(orig_entries, ai_entries):
    results = {}
    for eid in sorted(orig_entries.keys(), key=int):
        info    = orig_entries[eid]
        orig_kws = info['kws']
        ai_kws  = ai_entries.get(eid, [])

        matched      = []  # (orig_str, strict, lenient, method, matched_ai_str)
        used_indices = set()

        for ok in orig_kws:
            s, l, method, ai_str, consumed = match_one(ok, ai_kws, used_indices)
            if consumed is not None:
                used_indices.add(consumed)
            orig_str = f"{ok[0]}: {ok[1]}: {ok[2]}"
            matched.append((orig_str, s, l, method, ai_str))

        extras = [
            f"{kw[0]}: {kw[1]}: {kw[2]}"
            for i, kw in enumerate(ai_kws)
            if i not in used_indices
        ]

        results[eid] = {
            'author':  info['author'],
            'year':    info['year'],
            'matched': matched,
            'extras':  extras,
        }
    return results

# ── Report writing ─────────────────────────────────────────────
METHOD_LABELS = {
    'exact':                '',
    'normalized':           '',
    'AI_isotope_expansion': ' (AI expanded isotopes)',
    'AI_added_species':     ' (AI added species)',
    'AI_dropped_base':      ' (AI dropped base)',
    'isoelectronic':        ' (isoelectronic equiv.)',
    'subset_mismatch':      '',
    'mismatch':             '',
    'no_type_match':        '',
}

def write_report(results, out_path):
    lines = []
    lines.append('# Keyword Match Analysis: Original vs AI-Generated\n\n')
    lines.append('GENINT lines excluded from all comparisons.\n\n')
    lines.append('**Strict**: `AI_dropped_base` = PARTIAL. '
                 '**Lenient**: `AI_dropped_base` = MATCH.\n\n')
    lines.append('---\n\n')

    summary = []

    for eid in sorted(results.keys(), key=int):
        r = results[eid]
        matched = r['matched']
        extras  = r['extras']

        n_orig    = len(matched)
        n_strict  = sum(1 for m in matched if m[1] == 'MATCH')
        n_lenient = sum(1 for m in matched if m[2] == 'MATCH')
        n_extras  = len(extras)

        pct_s = f"{100*n_strict//n_orig}%"  if n_orig else '—'
        pct_l = f"{100*n_lenient//n_orig}%" if n_orig else '—'

        label = f"{r['year']} {r['author']}"
        lines.append(f"## {eid} — {label}\n\n")
        lines.append('| Original keyword | Strict | Lenient | Matched AI keyword |\n')
        lines.append('|---|---|---|---|\n')

        for orig_str, strict, lenient, method, ai_str in matched:
            note = METHOD_LABELS.get(method, f' ({method})')
            strict_cell  = f"{strict}{note}"
            lenient_cell = lenient
            lines.append(f'| `{orig_str}` | {strict_cell} | {lenient_cell} | `{ai_str}` |\n')

        lines.append('\n')
        if extras:
            extras_str = '<br>'.join(f'`{e}`' for e in extras)
            lines.append(f'**AI EXTRAS ({n_extras})**:<br>{extras_str}\n\n')
        else:
            lines.append('**AI EXTRAS**: (none)\n\n')

        lines.append(
            f'**Stats** — Strict: {n_strict}/{n_orig} ({pct_s}) | '
            f'Lenient: {n_lenient}/{n_orig} ({pct_l}) | '
            f'AI extras: {n_extras}\n\n'
        )
        lines.append('---\n\n')

        summary.append((eid, label, n_orig, n_strict, pct_s, n_lenient, pct_l, n_extras))

    # Summary table
    lines.append('## Summary\n\n')
    lines.append('| ID | Reference | Orig | Strict # | Strict % | Lenient # | Lenient % | AI Extras |\n')
    lines.append('|---|---|---|---|---|---|---|---|\n')

    tot_orig = tot_strict = tot_lenient = tot_extras = 0
    for eid, label, n_orig, n_strict, pct_s, n_lenient, pct_l, n_extras in summary:
        lines.append(
            f'| {eid} | {label} | {n_orig} | {n_strict} | {pct_s} | '
            f'{n_lenient} | {pct_l} | {n_extras} |\n'
        )
        tot_orig    += n_orig
        tot_strict  += n_strict
        tot_lenient += n_lenient
        tot_extras  += n_extras

    tp_s = f"{100*tot_strict//tot_orig}%"  if tot_orig else '—'
    tp_l = f"{100*tot_lenient//tot_orig}%" if tot_orig else '—'
    lines.append(
        f'| **TOTAL** | — | **{tot_orig}** | **{tot_strict}** | **{tp_s}** | '
        f'**{tot_lenient}** | **{tp_l}** | **{tot_extras}** |\n'
    )

    with open(out_path, 'w') as f:
        f.writelines(lines)

    print(f"Written: {out_path}")
    print(f"Total original keywords : {tot_orig}")
    print(f"Strict  matches         : {tot_strict}/{tot_orig} ({tp_s})")
    print(f"Lenient matches         : {tot_lenient}/{tot_orig} ({tp_l})")
    print(f"AI extras (non-GENINT)  : {tot_extras}")

# ── Entry point ────────────────────────────────────────────────
if __name__ == '__main__':
    BIBTEX   = '/Users/themanaspandey/stuff/test_set_bibtex.txt'
    TEST_DIR = '/Users/themanaspandey/stuff/EL_test_set 2'
    OUT      = '/Users/themanaspandey/stuff/keywords_match_analysis_v3.md'

    orig    = parse_bibtex(BIBTEX)
    ai      = parse_ai_folders(TEST_DIR)
    results = analyze(orig, ai)
    write_report(results, OUT)
