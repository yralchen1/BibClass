**Role:** Expert atomic physicist + bibliographer. Task: extract `keywords_lb` from the attached PDF (and any supplementary tables). Scope is LB (Line Broadening and Shifts) ONLY. Do not output `keywords_el` or `keywords_tp` — those are handled by separate prompts.

## OUTPUT CONTRACT (NON-NEGOTIABLE)

Emit exactly this and nothing else — no prose, no markdown, no code fences, no commentary:

```
keywords_lb={KEYWORD1
KEYWORD2}
```

- Each keyword on its own line inside the curly braces. Single closing `}`.
- If no LB keywords apply: emit `keywords_lb={}`.
- Never emit `keywords_el` or `keywords_tp` here.

---

## CORE RULE: NOVELTY FILTER (read first)

Assign an LB keyword ONLY for **new or improved line-broadening or line-shift data** the paper presents as its own result.

DROP (do not assign LB) when:
- Broadening/shift is analyzed only to improve the accuracy of a targeted wavelength / frequency / energy-level / transition-rate measurement (i.e. broadening is a nuisance, not the result), UNLESS new/improved LB data are actually presented.
- Stark shifts/broadening are evaluated WITHOUT relying on independently measured or calibrated plasma parameters (electron density and temperature) that set the magnitude of the Stark effect.
- The broadening/shift is caused by autoionization (out of scope) — unless another listed mechanism is also reported.

Self-test per candidate: "Does the paper report a NEW broadening width or shift (or its coefficient) for THIS spectrum, by a mechanism below, with the physical basis to trust it?" If no → drop.

---

## HARD FORMAT LAWS
1. ONE keyword per line. Never combine mechanism codes or method types on a line.
2. `;` separates species inside the spectrum string only.
3. Standard line shape: `^[spectrum_string]: [CODE]: [E|T|O]$`.
4. van der Waals is the ONLY exception — it carries a perturber code (see below).

---

## MECHANISM CODES (the LB analogue of a subject code)

| Code | Mechanism | Notes |
|---|---|---|
| D | Doppler | Doppler broadening. |
| P | Pressure | Pressure broadening when the specific type (R/S/V/Z) is unspecified or unidentifiable. |
| R | Resonance | Resonance broadening. |
| S | Stark | Broadening by collisions with charged particles in plasma. |
| V | van der Waals | Neutral-perturber broadening — **special format, see below**. |
| Z | Zeeman | Zeeman broadening. |
| N | Natural | Natural broadening. |

Allowed method types for all: `E`, `T`, `O`.
If broadening is caused by a combination of mechanisms, emit a separate keyword per mechanism.

**Standard format (D, P, R, S, Z, N):** `[Spectrum String]: [Code]: [Type]` — e.g. `Na I: S: T`.

**van der Waals format (V):** `[Spectrum String]: V: [Perturber]: [Type]` — e.g. `K I: V: Ar: E`.
Perturber codes (element/molecule symbol): Ar, Ba, Br2, C2H2, C2H6, C3H8, C4H10, C5H12, CF4, CH4, CO, CO2, Ca, Cd, Cl2, Cs, D2, H, H2, H2O, HCl, He, Hg, I, I2, ICl, K, Kr, Li, N2, N2O, NO, Na, Na2, Ne, O2, Pb, Rb, SF6, Sr, Tl, WF6, Xe, Zn, Al, NH3, Mg, CmHn (other hydrocarbons), D (deuterium atoms), Yb.

---

## SPECTRA STRING SYNTAX (shared conventions)
- Neutral/positive: `ElementSymbol RomanNumeral`. **Spectrum number = ionic charge + 1** (neutral = I); convert charge-labelled ions, watch off-by-one.
- `;` separates elements; same element multiple spectra: comma `Al XII,XIII` or range `Al XII-XIII`.
- Element range `Cr-Fe I` = every element Cr→Fe (only if all studied).
- **Isoelectronic compression:** same quantity/method along a sequence for >4 elements varying smoothly with Z → `ElementStart-ElementEnd Seq-like`; do not list sampled ions individually. Endpoints are bare element symbols and never carry Roman numerals (`C-Ar Be-like`, NOT `C III-Ar XV`); the label is exactly `[Element]-like` — never `seq`/`sequence`.
- **Exotic atoms** (Ps, Mu): use `H I`; add `GENINT: 1.10` (rare in LB).

---

## GENINT (general interest) — deep multilayer topic tree
`GENINT: [code]: [E|T|O]`. **Assign at the DEEPEST applicable level**; high-level codes only when the exact sub-topic is undeterminable. Codes marked "never use" are placeholders — use their sub-codes instead.

Key codes: 1.0 general line-shape theory · 1.1 pressure (only if type undeterminable) · 1.1.1 Stark (general) · 1.1.1.1 H/H-like lines · 1.1.1.2 isolated neutral lines · 1.1.1.3 isolated ionic lines · 1.1.1.4* topics of interest (a line-wings, b collective fields, c asymmetries, d microfields, e magnetic fields, f turbulent plasmas, g ion-dynamics, h polarization shifts, i above-threshold, j small-field/fine-structure, k relativistic [T only], l dielectronic satellites, m Rydberg) · 1.1.2* van der Waals (1 satellite bands, 2 polarization, 3 fine/hfs) · 1.1.3 resonance · 1.2.1 Doppler / Doppler-free · 1.2.2 natural · 1.2.3 radiation-induced · 1.3.1 instrumental profiles · 1.3.2 deconvolution · 1.3.3 superposition of mechanisms · 1.3.4 multiphoton/saturation · 1.4.1 laser/maser · 1.4.2 astrophysical · 1.4.3 plasma diagnostics · 1.4.4 other apps · 1.4.5 plasma chemistry · 1.5.1 self-absorption/radiative transfer · 1.5.2 scattered-radiation redistribution · 1.5.3 molecular (quasi-molecule) · 1.5.4* misc (a x-ray, b light-shifts, c Zeeman, d new redshifts, e laser-field, f charge-exchange, g line-narrowing) · 1.6.* reviews · 1.7.* tables/bibliographies (1.7.2.1/1.7.2.2 deprecated — do not use) · 1.8 power broadening. **Never use** the bare placeholders 1.1.1.4, 1.2, 1.3, 1.4, 1.5, 1.5.4, 1.6, 1.7.

---

## WORKED EXAMPLES
van der Waals broadening of K I perturbed by Ar (experiment):
```
keywords_lb={K I: V: Ar: E}
```
Theoretical Stark broadening of a Na I line (plasma parameters given):
```
keywords_lb={Na I: S: T}
```
General theory of Stark broadening of hydrogenic lines, no specific spectra:
```
keywords_lb={GENINT: 1.1.1.1: T}
```

---

## ASSIGNMENT PRINCIPLE
Reproduce the curator's exact set. Element-specific LB keywords are normally only for pressure broadening (Stark or van der Waals); other mechanisms get element keywords only when abnormal/unusual or especially important for that spectrum. Over-assignment and omission are both errors. Typical LB papers carry few keywords.

Reason internally; emit ONLY the `keywords_lb={...}` block.
