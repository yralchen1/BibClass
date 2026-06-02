# EL Prompt Changes Summary

Goal: maximize "complete match with no AI extras" rate (currently 19/98 = 19%).

Changes in `Prompt_EL_new.md` vs `Prompt_EL_old.md`:

| Change | Addresses failure pattern |
|---|---|
| Rule 1 extended: explicit list of "do NOT add X just because Y is present" | AT+TE reflexive co-assignment, QF/IP/ND over-assignment |
| Rule 5 extended: range over-compression warning + Cr-Fe vs Cr-Cu example | AI writing `H-Zr I` for `H I; C I; Ca I` (24084 Hall), `Cr-Cu I` for `Cr-Fe I` (24042) |
| Rule 7 (new): W never method type T | AI writing `W: T` (24121 Müller, 24122 Müller `CL: T`/`W: T`) |
| Rule 7 (cont.): Allowed Method Type column is STRICT | CL: T invalid combinations (24075 Peng) |
| Rule 7 (cont.): Method type (E/T/O) discipline + examples | IS: E vs IS: T flips (24081 Yu, 24136 Gakkhar) |
| Isotope rules: include ALL isotopes with data, not just base | AI dropping specific isotopes (24123 True dropped 87Rb) |
| Isotope rules: include isotope variants ONLY if distinct values | AI over-expanding isotopes (24095 Manti `Ne I; 20Ne I; 22Ne I`) |
| Isotope rules: negative ion dash MUST be preserved | 24079 Zhang `Se-: IS: E` → AI: `Se: IS: E` |
| 5 new real examples covering edge cases | AT+TE independence; QF-only; range vs list; negative ion |
| **ND** definition: explicit warning against routine quantum number labels | ND over-assignment (24046, 24055, 24107, 24135 extras) |
| **CL** warning: inference does NOT apply in reverse from EL | AI adding CL+W when original has only EL: E (24060 Mosnier, 24067 Ni) |
| **TA** definition: mutual exclusivity with CL, "never substitute" | 24109 Kologrivov (TA→CL+W substitution) |
| **W** definition: CRITICAL note about W never being T | Reinforces Rule 7 |
| **QF** constraint: test question "would a QED researcher find this useful?" | QF: T reflexive assignment (24051, 24057, 24069, 24073, 24085, 24111, 24120, 24124) |
| **IP** constraint: explicit list of situations where IP must NOT be assigned | IP: T reflexive assignment (24119, 24127 extras) |
| **TE** constraint: "do not assign when levels are intermediate tool" | TE: T added when paper only does corrections |
| **AT** definition: named methods (HF/DHF/MCDF/CI) + explicit exclusions (DFT, ECP, model potential) | AT over-assigned to non-HF papers |
| **AT/TE** independence note + example showing both-required-separately | Reflexive AT+TE co-assignment |
| **IS** definition: reinforced "base element only" + negative example | AI writing `229Th I: IS: T` |
| **Final pre-output checklist** with cost-of-extra-vs-cost-of-missing framing | Drives zero-extras discipline |
