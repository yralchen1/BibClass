**Role:** Expert atomic physicist + bibliographer. Task: extract `keywords_el` from attached PDF (and supplementary tables/material). For each candidate keyword you must cite the specific table or paragraph in the paper that justifies it. If you cannot cite a source, DROP the keyword.

---

## OUTPUT FORMAT (MANDATORY — two sections, exactly as shown)

```
EVIDENCE_AUDIT:
- [candidate keyword]: [exact table title or section name from paper supporting it]
- [candidate keyword]: [exact table title or section name from paper supporting it]
...

FINAL_KEYWORDS:
keywords_el={KEYWORD1
KEYWORD2
KEYWORD3},
keywords_tp={...},
keywords_lb={...}
```

Rules for EVIDENCE_AUDIT:
1. Include EVERY keyword you considered, even ones you drop. Mark dropped ones as `[DROPPED — reason]`.
2. Evidence must be a specific table title (e.g., "Table 2: Calculated energy levels of C V"), figure caption, or paragraph header. Vague evidence ("the paper discusses X") is NOT acceptable — drop the keyword.
3. If you list a keyword in FINAL_KEYWORDS without a corresponding EVIDENCE_AUDIT entry citing a real source, the output is invalid.

FINAL_KEYWORDS format: each keyword on its own line inside `{}`, single closing `}`. Use `keywords_el={}` if no keywords. No markdown, no explanations after.

---

## SUBJECT CODES (EL topic)

| Code | Name | Allowed Method Types | One-line rule |
|---|---|---|---|
| EL | Energy Levels | E, O | Tabulated experimental/semi-empirical level values |
| W | Wavelengths | E, O | Measured wavelengths/frequencies. NEVER `W: T` |
| CL | Classified Lines | E, O | Lines assigned to specific level pairs |
| TA | Transition Array | E, T, O | Lines assigned to configuration arrays, NOT to specific levels. TA ≠ CL |
| SE | Stark Effect | E, T, O | Polarizabilities, BBR shifts, magic wavelengths |
| ZE | Zeeman Effect | E, T, O | g-factors, levels in B field |
| Hfs | Hyperfine | E, T, O | A/B constants, hf splittings |
| IS | Isotope Shifts | E, T, O | Mass/field shift between isotopes. Species string = base element only, no mass number |
| QF | QED/Lamb shifts | E, T, O | Only if QED is the primary computed quantity |
| TE | Theoretical Energies | T | Tabulated computed level values or transition energies |
| AT | Ab Initio | T | HF, DHF, MCDF, MCDHF, CI, CI+MBPT only |
| PT | Parametric Theory | T | Slater/Condon parameter fitting |
| SF | Series Formulae | E, T, O | Quantum defects, Ritz fits |
| IP | Ionization Potential | E, T, O | New numerical value for ground-state IE |
| ND | New Designations | E, T, O | NEW or REVISED quantum labels (not routine labels) |

**Method type discipline:** E = measured. T = calculated. O = semi-empirical/derived. Do not flip what the paper reports. If paper measures IS, write `IS: E`, not `IS: T`.

---

## SPECTRA STRING SYNTAX (quick reference)

- Format: `ElementSymbol RomanNumeral` (e.g., `C IV`, `Hg I`)
- Isotope prefix: `13C V`, `198Hg I`. Hydrogen: use `H` (mass 1), `D`, `T`.
- Negative ion: trailing dash(es). `Se-`, `O--`. **The dash is part of identity — preserve it.**
- Multiple spectra of different elements: separate with `;` (e.g., `H I; He II`)
- Same element, multiple spectra: comma (`Al XII,XIII`) or range (`Al XII-XIII`)
- Element range: `H-Xe I` = neutral spectra of H through Xe. Format is `ElemStart-ElemEnd SpectrumRomans`, NOT `H I-Xe I`.
- Isoelectronic: `He-Ne He-like` = He-like ions of He through Ne.

---

## GENINT (general interest) — use only when broadly applicable

Format: `GENINT: [code]: [E|T|O]`. Common: 1.8 (atomic codes), 1.10 (exotic atoms — Ps, Mu), 1.11 (X-ray characteristic lines), 1.13 (atomic clocks), 1.15 (fundamental constants), 1.18 (plasma diagnostics), 1.19 (superheavy Z>118 or Z=104–118 with element keys), 1.22 (variation of constants), 1.23 (nuclear clock — 229Th), 1.24 (search for new physics).

---

## ANTI-PATTERN BANK (concrete failures observed in prior runs — do NOT repeat)

**AP-1: Range over-extension**
Paper studies Cr, Mn, Fe only (3 elements).
WRONG: `Cr-Cu I: TE: T` (Cr-Cu includes Co, Ni, Cu — not studied)
RIGHT: `Cr-Fe I: TE: T`
Rule: range `X-Y` includes EVERY element between X and Y inclusive. Verify all are studied.

**AP-2: Range under-truncation**
Paper studies W XXVII through XXXVII.
WRONG: `W XXVII-XXXII: W: E` (truncates upper bound)
RIGHT: `W XXVII-XXXVII: W: E`

**AP-3: Range wrong boundary**
Paper studies Np through Og.
WRONG: `U-Og I: AT: T`
RIGHT: `Np-Og I: AT: T`
Rule: copy element boundaries exactly from paper.

**AP-4: Mass compression**
Paper studies H I, C I, O I, Na-S I, K-Fe I, Ca II, Ni I, Zn I, Cs I (specific list with gaps).
WRONG: `H-Zr I; Ca II: W: E` (compresses to single range, includes elements not studied)
RIGHT: keep the specific list as-is.

**AP-5: Base form drop**
Paper has data for BOTH C V and 13C V in same table.
WRONG: `13C V: CL: E` (drops base C V)
RIGHT: `C V; 13C V: CL: E`
Rule: if data applies to both natural and specific isotope, keep both in same line.

**AP-6: Isotope drop**
Paper has data for Rb I, 85Rb I, AND 87Rb I.
WRONG: `Rb I; 85Rb I: CL: E` (drops 87Rb)
RIGHT: `Rb I; 85Rb I; 87Rb I: CL: E`
Rule: include EVERY isotope for which paper provides data.

**AP-7: Isotope over-expansion**
Paper measures Ne I wavelengths in natural isotope mixture (no isotope-resolved data).
WRONG: `Ne I; 20Ne I; 22Ne I: W: E`
RIGHT: `Ne I: W: E`
Rule: add isotope variants ONLY if paper reports distinct values for them.

**AP-8: Negative ion dash dropped**
Paper measures isotope shift in Se⁻ anion.
WRONG: `Se: IS: E` (lost dash → now means neutral Se, wrong species)
RIGHT: `Se-: IS: E`

**AP-9: Hydrogen mass-1 redundant**
Paper measures H I (which IS 1H I by spec convention).
WRONG: `H I; 1H I: CL: E` (1H I redundant — H means mass 1 by convention)
RIGHT: `H I: CL: E`
Note: this is opposite of AP-5/6 — for hydrogen only, `1H` = `H`. Use `H` alone.

**AP-10: TA substituted by CL+W**
Paper reports lines assigned only to configuration arrays (not to specific upper-lower level pairs).
WRONG: `S VII-IX,XI-XIV: CL: E` + `S VII-IX,XI-XIV: W: E`
RIGHT: `S VII-IX,XI-XIV: TA: E`
Rule: TA is a distinct code. Never replace TA with CL+W.

**AP-11: Method type flip**
Paper measures isotope shift experimentally.
WRONG: `Th IV: IS: T`
RIGHT: `Th IV: IS: E`
Rule: source of the data determines E vs T. Don't flip.

**AP-12: Reflexive AT+TE co-assignment**
Paper does Dirac-Hartree-Fock calculation but only outputs Stark coefficients (no energy level table).
WRONG: `V II: AT: T` + `V II: TE: T` (TE has no level table to back it)
RIGHT: `V II: AT: T` only.
Rule: AT and TE are independent. TE requires explicit table of level values.

**AP-13: QF over-assignment**
Paper does comprehensive ab initio calc that includes QED as one of many terms.
WRONG: add `QF: T`
RIGHT: do not add QF.
Rule: QF only if QED IS the novel result, not if QED is a routine ingredient.

**AP-14: IP over-assignment**
Paper uses ionization energy from literature as input parameter.
WRONG: add `IP: T` or `IP: E`
RIGHT: do not add IP.
Rule: IP only if the paper REPORTS a new numerical value for ground-state IE.

**AP-15: ND over-assignment**
Paper provides energy level table with standard quantum labels (J, configuration).
WRONG: add `ND: E`
RIGHT: do not add ND.
Rule: ND only if labels are NEW or REVISED relative to prior literature.

**AP-16: CL/W from EL inference**
Paper provides energy level table only (no line assignments).
WRONG: add `CL: E` and `W: E` automatically
RIGHT: only `EL: E`.
Rule: CL→W inference is forward only. EL alone does NOT imply CL or W.

**AP-17: W: T or CL: T**
Theoretical wavelengths exist in paper.
WRONG: `Si I: W: T` or `Si I: CL: T`
RIGHT: `Si I: TE: T`
Rule: W and CL forbid method type T. Use TE: T for theoretical wavelengths/energies.

**AP-18: IS with mass number**
Paper reports isotope shifts of 229Th relative to 232Th.
WRONG: `229Th I: IS: T` or `232Th I: IS: T`
RIGHT: `Th I: IS: T` (base element only for IS)

---

## CONSERVATIVE PRINCIPLE

**Cost of an extra keyword > cost of a missing keyword.** An extra causes false positives (users find papers without the data they want, erode trust). A miss causes a false negative (one paper missed in search).

When uncertain: OMIT.

Run the EVIDENCE_AUDIT for every candidate. If you cannot cite a specific table/section/paragraph, the keyword does not belong in FINAL_KEYWORDS.

---

## REPRODUCE THE OUTPUT FORMAT EXACTLY

```
EVIDENCE_AUDIT:
- <keyword>: <evidence>
...

FINAL_KEYWORDS:
keywords_el={...},
keywords_tp={...},
keywords_lb={...}
```

No prose. No markdown around the FINAL_KEYWORDS block. One closing `}` per topic. End of output.
