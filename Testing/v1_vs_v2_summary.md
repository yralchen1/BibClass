# v1 vs v2 Comparison: Did the Prompt Update Help?

**v1** = old prompt (`Prompt_EL_old.md`), analyzed in `keywords_match_analysis.md` (data: `test/`)
**v2** = new prompt (`Prompt_EL_new.md`), analyzed in `keywords_match_analysis_v2.md` (data: `EL_test_set/`)

## Aggregate Stats (237 original keywords, 98 AI entries)

| Metric | v1 (old) | v2 (new) | Δ | Direction |
|---|---|---|---|---|
| Strict keyword matches | 160/237 (67%) | 148/237 (62%) | -12 (-5pp) | ↓ worse |
| Lenient keyword matches | 185/237 (78%) | 172/237 (72%) | -13 (-6pp) | ↓ worse |
| Total AI extras (hallucinations) | 171 | 154 | -17 (-10%) | ↑ better |
| At least 1 matched (strict) | 69/98 (70%) | 68/98 (69%) | -1 | ≈ flat |
| ALL matched (strict) | 51/98 (52%) | 44/98 (45%) | -7 (-7pp) | ↓ worse |
| ALL matched (lenient) | 57/98 (58%) | 50/98 (51%) | -7 (-7pp) | ↓ worse |
| Zero matches (strict) | 21/98 (21%) | 23/98 (23%) | +2 | ↓ worse |
| **Perfect+no extras (strict)** | **19/98 (19%)** | **19/98 (19%)** | **0** | **flat** |
| **Perfect+no extras (lenient)** | **20/98 (20%)** | **21/98 (21%)** | **+1** | **≈ flat** |

## Verdict

Error rate still high. Best-case metric (perfect match, zero extras) essentially unchanged: 19/98 → 19/98 (strict), 20/98 → 21/98 (lenient).

The prompt update made AI more conservative:
- **-17 fewer extras** (hallucinations dropped 10%) → conservatism rule worked
- **-12 fewer matches** (lost real keywords too) → over-conservatism

Net: AI dropped both noise AND signal at similar rates. Per-entry "perfect+clean" target did not move.

## Spot Checks (sample of 10 entries)

| ID | Issue v1 | Status v2 | Verdict |
|---|---|---|---|
| 24042 Kobayashi | AI wrote `Cr-Cu I` (should be `Cr-Fe I`) | Still `Cr-Cu I`, added GENINT/AT/TE/TP/LB extras | WORSE |
| 24050 Müller | Dropped `C V` base from CL/W | Still drops `C V` base | NO CHANGE |
| 24061 Drake | Dropped `He I` base, missed `IP: T` | Kept `He I; 4He I` base ✓ but added `EL: O` extra, still missed `IP: T` | PARTIAL |
| 24073 Maisenbacher | Dropped `1H I`, added 6 extras | Same drop, 8 extras | NO CHANGE |
| 24079 Zhang | Dropped `-` on `Se-` for IS | Kept `Se-` dash ✓ but over-expanded isotopes wildly | PARTIAL |
| 24084 Hall | Compressed to `H-Zr I` range | Listed elements individually ✓ but mixed scope | IMPROVED |
| 24095 Manti | Over-expanded `Ne I; 20Ne I; 22Ne I` on W/CL/TE | Fixed W/CL ✓ but still expanded TE | PARTIAL |
| 24097 Tupitsyn | Wrong range `U-Og I` | Dropped ALL element keywords, only GENINT | WORSE |
| 24109 Kologrivov | TA→CL+W substitution | Still TA→CL+W | NO CHANGE |
| 24123 True | Dropped `87Rb I` | Still drops `87Rb I`, missed `Hfs: E`, added TP+LB extras | NO CHANGE / WORSE |

## Why Did Some Fixes Not Land

- **TA→CL+W (24109)**: prompt did warn against this, AI ignored.
- **Range over-expansion (24042)**: prompt warned, AI ignored.
- **Isotope base-drop (24050, 24073, 24123)**: prompt rule clear, AI ignored.
- **`Cr-Cu` extension (24042)**: prompt example specifically targeted this, AI ignored.

Likely cause: prompt is too long; key constraints buried. AI follows new rules selectively. Some entries also got worse because rules introduced new failure modes (e.g., 24097 now drops everything to be "conservative").

## Files

- `keywords_comparison_v2.md` — side-by-side orig vs v2 AI keywords (100 rows)
- `keywords_match_analysis_v2.md` — per-entry match analysis + summary + entry-level stats
- `analyze_keywords_v2.py` — analysis script (clone of v1 pointing at `EL_test_set/`)
