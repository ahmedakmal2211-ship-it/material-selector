# material-selector

A Python command-line tool that ranks engineering materials for a design goal using Ashby material indices (lightest stiff beam, cheapest strong tie, and so on) and plots Ashby charts (density vs modulus, density vs strength).

The dataset has 38 materials in `data/materials.csv`, with a source for every row (see `data/SOURCES.md`).

> **Cost caveat.** Rankings for the cost goals (`tie_strength_cost`, `beam_stiffness_cost`) are indicative only. Most costs in the dataset are estimates (32 of 38; only 6 come from a public price page), and even those are raw-material prices, not quotes. Use cost rankings to see which families deserve a closer look, not to pick a material.

## Quick start

```bash
git clone https://github.com/ahmedakmal2211-ship-it/material-selector.git
cd material-selector && pip install -e .[dev]
python -m material_selector rank --goal beam_stiffness --top 5
```

- The `material-selector` console script is also installed. Use it in place of `python -m material_selector` if your Python `Scripts` folder is on `PATH`.
- Use the editable install (`-e`) shown above. A normal (non-editable) install does not bundle the CSV. In that case point the tool at the data with `--data path/to/materials.csv` or the `MATERIAL_SELECTOR_DATA` environment variable.
- Commands: `goals` (list goals), `rank`, `show` (one material), `pareto` (two goals at once) and `chart`.

## Example output

All outputs below are real. The first line each command prints (`data: <path of the CSV in use>`) is left out.

`python -m material_selector rank --goal beam_stiffness --top 3 --isotropic-only --strength-basis yield`

```text
Goal: beam_stiffness - Light, stiff beam. Maximise E^(1/2)/rho [GPa^(1/2)/(Mg/m^3)]
rank  tie  material                    class  index  rho kg/m3  E GPa  sigma MPa  basis  USD/kg  aniso
----  ---  --------------------------  -----  -----  ---------  -----  ---------  -----  ------  -----
1          Magnesium AZ31B (extruded)  metal  3.79   1770       45     200        yield  5       no
2          Aluminium 6061-T6           metal  3.077  2700       69     270        yield  3       no
3     ~    Aluminium 2024-T3 (sheet)   metal  3.073  2780       73     275        yield  4       no

16 ranked, 22 excluded by limits, 0 skipped (missing data). '~' = within 5% of the material above (treat as a tie).
Screening aid only (single representative values, see docs/INDICES.md); not a design check.
```

## Reading a ranking

- **Tie mark `~`.** A row is marked `~` when its index is within 5% of the row above (change with `--tie-tol PCT`). Treat a run such as `2, ~3` as one group in arbitrary order. In the example above, 6061-T6 and 2024-T3 differ by about 0.1%.
- **Rank band (cost goals only).** For `tie_strength_cost` and `beam_stiffness_cost` the table adds a `rank band` column (best-worst rank) and a `cost` column (`sourced` or `estimated`). The band is a heuristic sensitivity range, not a statistical confidence interval. It is the range of ranks the material could take if each cost were off by a factor of 2 (estimated) or 1.5 (sourced). Change the factors with `--cost-factor-estimated` and `--cost-factor-sourced`. The method is in the Uncertainty section of [docs/INDICES.md](docs/INDICES.md).

`python -m material_selector rank --goal beam_stiffness_cost --top 8`

```text
Goal: beam_stiffness_cost - Cheapest stiff beam. Maximise E^(1/2)/(C_m*rho) [GPa^(1/2)/((USD/kg)*(Mg/m^3))]
rank  tie  rank band  material                                     class    index  rho kg/m3  E GPa  sigma MPa  basis     USD/kg  cost       aniso
----  ---  ---------  -------------------------------------------  -------  -----  ---------  -----  ---------  --------  ------  ---------  -----
1          1-4        Douglas-fir, along grain (averaged regions)  wood     11.4   510        12.17  86.2       flexural  0.6     estimated  yes
2          1-6        White oak, along grain (12% MC)              wood     5.771  755        12.15  102.3      flexural  0.8     estimated  yes
3          1-6        Balsa, along grain (12% MC)                  wood     4.28   150        3.71   19.6       flexural  3       estimated  yes
4     ~    1-6        Soda-lime glass (flat/float, annealed)       ceramic  4.243  2500       72     41         flexural  0.8     estimated  no
5          2-19       Grey cast iron (generic)                     metal    1.584  7200       130    200        tensile   1       estimated  no
6     ~    2-20       Structural steel ASTM A36 (hot rolled)       metal    1.507  7820       200    250        yield     1.2     estimated  no
7          5-19       Polystyrene (general purpose)                polymer  1.205  1005       3.3    53         tensile   1.5     sourced    no
8          5-25       Aluminium 6061-T6                            metal    1.026  2700       69     270        yield     3       estimated  no

38 ranked, 0 excluded by limits, 0 skipped (missing data). '~' = within 5% of the material above (treat as a tie).
Rank band = best-worst rank if each cost is off by x/÷ 2 (estimated) or 1.5 (sourced). See docs/INDICES.md, Uncertainty.
Note: strength values mix bases (flexural, tensile, yield); yield, tensile and flexural strengths are not directly comparable.
Note: anisotropic rows use one along-fibre/grain value; use --isotropic-only to drop them.
Screening aid only (single representative values, see docs/INDICES.md); not a design check.
```

The bands are wide. Aluminium 6061-T6 sits at rank 8 but could be anywhere from 5 to 25, and even rank 1 could be 4th. Cost rankings are indicative only. Most costs are estimates, and the few sourced ones are raw-material prices that differ by about 1.6x between regions on the pages used, and by more across suppliers and product forms, so the factor of 1.5 on sourced costs is a floor, not a typical value. These rank material cost per kg, not finished-part cost. Get a quote before relying on any result.

## Goals

Each goal maximises one index M. Units are as printed by the tool (density in Mg/m^3, E in GPa, strength in MPa, cost in USD/kg).

| Goal | What it ranks | Index (maximise) | Units |
|---|---|---|---|
| `tie_stiffness` | Light, stiff tie (tension member) | E / rho | GPa/(Mg/m^3) |
| `tie_strength` | Light, strong tie | sigma_f / rho | MPa/(Mg/m^3) |
| `tie_strength_cost` | Cheapest strong tie | sigma_f / (C_m rho) | MPa/((USD/kg)(Mg/m^3)) |
| `beam_stiffness` | Light, stiff beam (square section) | E^(1/2) / rho | GPa^(1/2)/(Mg/m^3) |
| `beam_strength` | Light, strong beam (square section) | sigma_f^(2/3) / rho | MPa^(2/3)/(Mg/m^3) |
| `beam_stiffness_cost` | Cheapest stiff beam | E^(1/2) / (C_m rho) | GPa^(1/2)/((USD/kg)(Mg/m^3)) |
| `panel_stiffness` | Light, stiff panel (fixed width, free thickness) | E^(1/3) / rho | GPa^(1/3)/(Mg/m^3) |
| `panel_strength` | Light, strong panel | sigma_f^(1/2) / rho | MPa^(1/2)/(Mg/m^3) |
| `column_buckling` | Light column against elastic buckling (alias of `beam_stiffness`) | E^(1/2) / rho | GPa^(1/2)/(Mg/m^3) |

## Screening limits and filters

Limits and filters remove materials before ranking. They work with `rank`, `pareto` and `chart`. Limits are inclusive, and a material with a missing value never passes a limit that uses it.

| Option | Meaning |
|---|---|
| `--min-modulus GPA` | minimum Young's modulus |
| `--min-strength MPA` | minimum strength |
| `--max-density KG_M3` | maximum density |
| `--max-cost USD_KG` | maximum cost |
| `--class CLASS [CLASS ...]` | allowed classes: metal, polymer, composite, ceramic, wood |
| `--strength-basis BASIS [BASIS ...]` | keep only these strength bases: yield, tensile, flexural (repeatable) |
| `--isotropic-only` | drop rows flagged anisotropic (composites and wood) |
| `--sourced-cost-only` | for cost goals, drop rows whose cost is only estimated |
| `-v`, `--verbose` | list excluded and skipped materials with reasons |

Example: the cheapest strong tie among metals and polymers that are at least 200 MPa and cost no more than 5 USD/kg:

```bash
python -m material_selector rank --goal tie_strength_cost --min-strength 200 --max-cost 5 --class metal polymer --top 5
```

Add `--strength-basis yield` to compare like with like, `--isotropic-only` to leave out wood and composites, or `--sourced-cost-only` to use only the rows whose cost came from a public price page (6 rows, so the list is short). If the goal does not use cost, the flag does nothing and the tool prints a note on stderr saying so.

## Output formats

`rank --format` accepts `table` (default), `markdown`, `csv` and `json`. With `csv` and `json`, stdout carries only the data; the data path, notes and the screening-aid line go to stderr, so the output can be piped straight into other tools. The `markdown` format also prints the goal line and the notes on stdout. CSV and JSON include the source, cost confidence and notes fields.

`python -m material_selector rank --goal tie_strength --top 3 --format markdown`

```text
Goal: tie_strength - Light, strong tie. Maximise sigma_f/rho [MPa/(Mg/m^3)]
| rank | tie | material | class | index | rho kg/m3 | E GPa | sigma MPa | basis | USD/kg | aniso |
|---|---|---|---|---|---|---|---|---|---|---|
| 1 |  | CFRP unidirectional, epoxy, 61% fibre (0 deg) | composite | 1081 | 1600 | 142 | 1730 | tensile | 60 | yes |
| 2 |  | Kevlar/epoxy unidirectional, 53% fibre (0 deg) | composite | 814.8 | 1350 | 63.6 | 1100 | tensile | 50 | yes |
| 3 |  | S-glass/epoxy unidirectional, 45% fibre (GFRP, 0 deg) | composite | 483.3 | 1800 | 39.5 | 870 | tensile | 20 | yes |

38 ranked, 0 excluded by limits, 0 skipped (missing data). '~' = within 5% of the material above (treat as a tie).
Note: strength values mix bases (flexural, tensile, yield); yield, tensile and flexural strengths are not directly comparable.
Note: anisotropic rows use one along-fibre/grain value; use --isotropic-only to drop them.
Screening aid only (single representative values, see docs/INDICES.md); not a design check.
```

## Show one material

`show` prints every property of one material (case-insensitive; part of the name is enough if it matches only one) and its value for every goal.

`python -m material_selector show 6061`

```text
name              Aluminium 6061-T6
class             metal
density (kg/m^3)  2700
modulus E (GPa)   69
strength (MPa)    270
strength_basis    yield
cost (USD/kg)     3
cost_confidence   estimated
cost_source_url   -
anisotropic       no
source_name       Wikipedia (6061 aluminium alloy)
source_url        https://en.wikipedia.org/wiki/6061_aluminium_alloy
notes             Page gives typical yield 270 MPa (min 240), UTS 310 MPa, E 68-69 GPa (page inconsistent). Cost estimated (indicative, 2026, order-of-magnitude): anchored on IMARC primary aluminium 2.76 USD/kg global Dec 2025 (https://www.imarcgroup.com/aluminum-pricing-report); alloy stock higher, no 6061 price page opened.
Caution: cost is an estimate (no price source); treat it as order-of-magnitude.

goal                 value  units
-------------------  -----  -----------------------------
tie_stiffness        25.56  GPa/(Mg/m^3)
tie_strength         100    MPa/(Mg/m^3)
tie_strength_cost    33.33  MPa/((USD/kg)*(Mg/m^3))
beam_stiffness       3.077  GPa^(1/2)/(Mg/m^3)
beam_strength        15.47  MPa^(2/3)/(Mg/m^3)
beam_stiffness_cost  1.026  GPa^(1/2)/((USD/kg)*(Mg/m^3))
panel_stiffness      1.519  GPa^(1/3)/(Mg/m^3)
panel_strength       6.086  MPa^(1/2)/(Mg/m^3)
column_buckling      3.077  GPa^(1/2)/(Mg/m^3)
Screening aid only (single representative values, see docs/INDICES.md); not a design check.
```

## Pareto front

When two goals pull in different directions, `pareto` lists the materials that no other material beats on both.

`python -m material_selector pareto --goals beam_stiffness tie_strength_cost`

```text
Pareto front: maximise beam_stiffness (E^(1/2)/rho) and tie_strength_cost (sigma_f/(C_m*rho))
material                                     class  beam_stiffness  tie_strength_cost
-------------------------------------------  -----  --------------  -----------------
Balsa, along grain (12% MC)                  wood   12.84           43.56
Douglas-fir, along grain (averaged regions)  wood   6.84            281.7

2 non-dominated of 38 with both values (0 excluded by limits, 0 skipped).
No other material is at least as good on both goals and better on one.
Screening aid only (single representative values, see docs/INDICES.md); not a design check.
```

The Pareto front uses nominal costs and applies no rank band; the tool prints `Note: cost goals in pareto use nominal costs; no rank band applied.` on stderr. Both materials on this front are anisotropic wood rows using along-grain figures. Add `--isotropic-only` to see the front without them.

## Ashby charts

Each chart draws every material as a point, a shaded envelope around each class, lines of constant index for the chosen goal, and a ring around the top materials. Hollow points are anisotropic rows (a single along-fibre or along-grain value). The envelopes are padded hulls around this dataset's points, not the full property fields of each class.

Density vs modulus, top 5 for `beam_stiffness`:

```bash
python -m material_selector chart --kind modulus --goal beam_stiffness --out docs/ashby_density_modulus.png
```

![Ashby chart of density vs Young's modulus with class envelopes, hollow markers for anisotropic rows, and the top 5 materials for a light, stiff beam circled](docs/ashby_density_modulus.png)

Density vs strength, top 5 for `tie_strength`:

```bash
python -m material_selector chart --kind strength --goal tie_strength --out docs/ashby_density_strength.png
```

![Ashby chart of density vs strength with class envelopes, hollow markers for anisotropic rows, and the top 5 materials for a light, strong tie circled](docs/ashby_density_strength.png)

## How it works

For each goal the tool uses an Ashby-style performance index: write the objective (minimise mass or cost) and the constraint (stiffness or strength), eliminate the free section size, and read off the material group M to maximise. It assumes isotropic, linear-elastic material, fixed length and load, and a solid square section for beams and columns (a panel has fixed width and free thickness). Strength is one value per material. Fatigue, creep, thin-wall buckling, temperature, corrosion, joining and manufacturability are not modelled, and cost indices rank material cost, not finished-part cost. Derivations, assumptions, hand-checked reference values and the tie and rank-band method are in [docs/INDICES.md](docs/INDICES.md).

## Data and its limits

- **Single values.** Each property is one representative number. Real properties vary widely with alloy, temper, grade, fibre fraction and direction. Several values are midpoints of the ranges given by their source. The weakest is polypropylene, with a yield of 30 MPa.
- **Costs.** Only 6 of the 38 costs are sourced from public IMARC market-research pages (copper, HDPE, PP, PC, ABS, polystyrene). These are resin or commodity prices, not stock or delivered prices, and regional prices for the same material differ by about 1.6x on these pages, and by more across suppliers and product forms. The other 32 costs are estimates and are flagged `estimated`. Materials whose price pages were grade-generic or had a wide regional spread (A36 steel, 304 stainless, nylon 6/6, PMMA, epoxy, PET) are counted as estimated. All costs are indicative, order-of-magnitude figures, not quotes, so cost-goal rankings are indicative only. The `cost_confidence` column says which is which.
- **Strength basis.** Rows use yield, tensile or flexural strength, which are not directly comparable. The tool warns when a ranking mixes them, and `--strength-basis` restricts it.
- **Stainless steels.** 304 uses a typical yield value from a retailer listing (215 MPa), not a mill datasheet. 316L uses the specification minimum (170 MPa), because no typical value was found.
- **Anisotropic rows.** Composites and wood use an along-fibre or along-grain value and are marked anisotropic. Across the fibre or grain they are much weaker and less stiff. Use `--isotropic-only` to drop them.
- **Ceramics.** Flexural strength is not a safe design stress without a statistical (Weibull) approach.

Near-tied ranks are within the uncertainty of the data. Sources for every row are listed in [data/SOURCES.md](data/SOURCES.md).

## Disclaimer

This is a screening aid for study and concept work. It is not a design check and not certification. Use proper standards, tested material data and a competent engineer's sign-off for any real design.

## Tests

```bash
python -m pytest -q
```

Expected result with the current code: `154 passed`.

## Licence

MIT. See [LICENSE](LICENSE).

Copyright (c) 2026 Akmal Azeem
