# Material indices: derivations, assumptions and screening limits

Method: Ashby-style performance indices (M. F. Ashby, *Materials Selection in Mechanical Design*, a public textbook method). For each design goal, write the objective (minimise mass `m` or cost `C`), the constraint (stiffness or strength), eliminate the free variable (section size), and read off the material group `M` to **maximise**.

This is a first-pass screening aid for study and early concept work. It does not replace a proper design check, a code or standard, or a competent engineer's sign-off.

## Symbols and units

| Symbol | Meaning | Unit used by the tool |
|---|---|---|
| ρ | density | Mg/m³ (= kg/m³ ÷ 1000) |
| E | Young's modulus | GPa |
| σ_f | strength (yield, tensile or flexural, see `strength_basis`) | MPa |
| C_m | cost per unit mass | USD/kg |
| m | mass | kg |
| L | length (fixed) | m |
| F | load (fixed) | N |
| A | cross-section area (free) | m² |
| S | required stiffness (fixed) | N/m |

## Assumptions (apply to every index)

1. Isotropic, linear-elastic material, small deflections.
2. Fixed geometry class: fixed length `L`, fixed load `F` or stiffness `S`; only the section size is free.
3. Beams and columns have a **square, solid section that scales in both directions** (shape factor 1). Panels have fixed width `b` and free thickness `t`.
4. Strength is a single representative value per material. Brittle materials fail at the strength shown, ductile ones at yield. Fatigue, creep, buckling of thin walls, temperature, corrosion, joining and manufacturability are **not** modelled.
5. Cost is per kg of stock material and is indicative only. Cost indices therefore rank *material* cost, not finished-part cost.
6. Load-case constants (C₁, C₂ and similar) depend on end conditions but do not change the ranking, so they are dropped.

## Derivations

### 1. Light, stiff tie (tension member)  — `tie_stiffness`

Objective: minimise m = A L ρ. Constraint: S = A E / L, so A = S L / E.
m = S L² (ρ / E). **Maximise M = E / ρ.**
Unit: GPa / (Mg/m³).

### 2. Light, strong tie  — `tie_strength`

Constraint: F ≤ A σ_f, so A = F / σ_f. m = F L (ρ / σ_f). **Maximise M = σ_f / ρ.**
Unit: MPa / (Mg/m³).

### 3. Cheapest strong tie  — `tie_strength_cost`

Cost C = C_m m = C_m ρ A L, with A = F / σ_f. C = F L (C_m ρ / σ_f). **Maximise M = σ_f / (C_m ρ).**
Unit in the tool: MPa / ((USD/kg) · (Mg/m³)). Only the ranking matters; the absolute scale is a convention.

### 4. Light, stiff beam (square section)  — `beam_stiffness`

Constraint: S = C₁ E I / L³ with I = A² / 12 (square section, b = h). So A = (12 S L³ / (C₁ E))^½.
m = A L ρ = (12 S / C₁)^½ L^{5/2} (ρ / E^½). **Maximise M = E^½ / ρ.**
Unit: GPa^½ / (Mg/m³).

### 5. Light, strong beam (square section)  — `beam_strength`

Constraint: the peak bending moment M_b = C₂ F L must not exceed Z σ_f, with Z = b³ / 6 = A^{3/2} / 6. So A = (6 C₂ F L / σ_f)^{2/3}.
m = A L ρ ∝ ρ / σ_f^{2/3}. **Maximise M = σ_f^{2/3} / ρ.**
Unit: MPa^{2/3} / (Mg/m³).

### 6. Light, stiff panel (fixed width, free thickness)  — `panel_stiffness`

I = b t³ / 12, S = C₁ E I / L³ ⇒ t = (12 S L³ / (C₁ E b))^{1/3}.
m = b t L ρ ∝ ρ / E^{1/3}. **Maximise M = E^{1/3} / ρ.**
Unit: GPa^{1/3} / (Mg/m³).

### 7. Light, strong panel  — `panel_strength`

Z = b t² / 6, M_f = Z σ_f ⇒ t ∝ σ_f^{-1/2}. m ∝ ρ / σ_f^{1/2}. **Maximise M = σ_f^{1/2} / ρ.**
Unit: MPa^{1/2} / (Mg/m³).

### 8. Cheapest stiff beam  — `beam_stiffness_cost`

Same as 4 but minimise C = C_m m. **Maximise M = E^½ / (C_m ρ).**

### 9. Light column against elastic buckling  — `column_buckling`

F_crit = π² E I / L², I = A² / 12 ⇒ A = (12 F L² / (π² E))^½. Same exponent as the stiff beam. **Maximise M = E^½ / ρ.** (Provided as an alias of `beam_stiffness`.)

## Hand-checked reference values (used by the tests)

Steel (ρ = 7.85 Mg/m³, E = 210 GPa, σ_f = 250 MPa):
- E/ρ = 210 / 7.85 = 26.75
- σ_f/ρ = 250 / 7.85 = 31.85
- E^½/ρ = 14.491 / 7.85 = 1.846
- E^{1/3}/ρ = 5.943 / 7.85 = 0.757

Aluminium (ρ = 2.70 Mg/m³, E = 70 GPa, σ_f = 275 MPa):
- E/ρ = 25.93
- E^½/ρ = 8.367 / 2.70 = 3.099
- σ_f^{2/3}/ρ = 42.29 / 2.70 = 15.66

Note that steel and aluminium are almost equal on E/ρ (ties) but aluminium is ~1.7x better on E^½/ρ (beams). That is the textbook result that explains why bicycle frames and aircraft skins use light alloys even though specific modulus is the same.

## Screening limits

Indices rank; limits remove. A material is **excluded** before ranking if any enabled limit fails:

| Limit | Meaning |
|---|---|
| `min_modulus_gpa` | minimum stiffness |
| `min_strength_mpa` | minimum strength |
| `max_density_kg_m3` | maximum density |
| `max_cost_usd_per_kg` | maximum stock cost |
| `classes` | allowed families (metal, polymer, composite, ceramic, wood) |

Limits are inclusive (`>=` for minimums, `<=` for maximums). Missing values never pass a limit that uses them.

## Limits of this tool

- One value per property; real properties have wide ranges (alloy, temper, grade, fibre fraction, direction).
- Composites and wood are anisotropic; the dataset uses an along-fibre or quasi-isotropic figure as stated per row.
- Ceramics are brittle: flexural strength is not a safe design stress without a statistical (Weibull) approach.
- Cost data are indicative, dated, and volatile.
