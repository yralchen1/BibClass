# v1 vs v2 vs v3 — Full Comparison

| Metric | v1 (old) | v2 (new) | v3 (anti-pattern+audit) | Best |
|---|---|---|---|---|
| Strict matches | 160/237 (67%) | 148/237 (62%) | **61/237 (25%)** | v1 |
| Lenient matches | 185/237 (78%) | 172/237 (72%) | **89/237 (37%)** | v1 |
| AI extras | 171 | 154 | 154 | v2/v3 tie |
| ≥1 matched (strict) | 69/98 (70%) | 68/98 (69%) | **32/98 (33%)** | v1 |
| ALL matched (strict) | 51/98 (52%) | 44/98 (45%) | **13/98 (13%)** | v1 |
| ALL matched (lenient) | 57/98 (58%) | 50/98 (51%) | **19/98 (19%)** | v1 |
| Zero matches (strict) | 21/98 (21%) | 23/98 (23%) | **59/98 (60%)** | v1 |
| **Perfect+no extras (strict)** | 19/98 (19%) | 19/98 (19%) | **6/98 (6%)** | v1/v2 tie |
| **Perfect+no extras (lenient)** | 20/98 (20%) | 21/98 (21%) | **9/98 (9%)** | v2 |

## Verdict

**v3 catastrophic regression.** Almost every metric collapsed.

## Why v3 Failed

Sampled v3 outputs reveal AI invented new failure modes that v3 prompt's structure encouraged:

**1. Format violations (combined codes/types)**
```
v3 output:  Cr-Cu I: EL: O; PT: T          ← two codes one line (illegal)
v3 output:  H I: SE: E, T, O               ← three method types one line (illegal)
v3 output:  H I: QF: E, T, O               ← three method types one line (illegal)
v3 output:  H I; C I; ... Cs I: W, CL, EL: E  ← three codes one line (illegal)
```
AI tried to "be concise" because evidence audit forced grouping by evidence source. Parser cannot recognize these as valid keywords → match count crashed.

**2. Species hallucination**
```
v3 output:  Kaonic Ne: W: E      ← entirely invented species (paper is Ne I!)
```
Evidence audit did not catch this — AI cited "exotic atom" GENINT rule loosely.

**3. Anti-pattern bank still ignored**
- AP-1 (Cr-Cu over-extension): 24042 STILL `Cr-Cu I`
- AP-5 (base form drop): 24050 STILL `13C V` alone
- AP-7 (isotope over-expansion): 24079 STILL `76Se-; 77Se-; 78Se-; ...`
- AP-10 (TA→CL+W): 24109 STILL `CL: E; W: E`
- AP-6 (isotope drop): 24123 STILL drops `87Rb I`

AI reads anti-patterns, ignores them, follows training-time biases.

**4. Over-conservative drops**
24123 True: v2 had `EL, CL, W, SF` (4 hits). v3 dropped `CL, W, Hfs` (kept only `EL, SF, SE`). Evidence audit drove false-negative drops.

## What Worked in v3

- **AP-9 (1H I redundancy)**: 24073 correctly collapsed `1H I` → `H I` ✓
- **Evidence audit ran**: AI did produce audit sections, did drop some keywords with cited "no evidence" reasons
- AI extras stayed flat at 154 (not worse than v2)

## Recommendation: v4 design

Roll back v3 entirely. Start v4 from v2 base. Add:

1. **STRICT format enforcement** at top of prompt:
   ```
   EACH LINE = ONE species_string : ONE subject_code : ONE method_type
   NEVER combine codes (no `EL: E; PT: T`)
   NEVER combine method types (no `SE: E, T, O`)
   NEVER combine codes within colon (no `W, CL, EL: E`)
   Multiple codes/types → multiple lines.
   ```

2. **Keep anti-pattern bank from v3** (it didn't hurt, just didn't help much)

3. **Drop evidence audit** — caused species hallucination and grouped format violations. Replace with simpler self-check:
   ```
   Before emitting, scan each keyword line: is it in `species : code : type` format with single code and single type? If not, fix.
   ```

4. **Add format validation example** showing 5-6 valid lines vs 5-6 invalid lines.

5. **Consider running validation script as post-process** to reject malformed lines before submission. Mechanical filter beats prompt instruction.

## Files

- `keywords_comparison_v3.md` — side-by-side orig vs v3 AI
- `keywords_match_analysis_v3.md` — full match analysis
- `analyze_keywords_v3.py` — analysis script
