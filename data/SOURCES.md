# Data sources

Access date: 2026-11-08. All data are public/textbook-grade. Values are single representative numbers; see the `notes` column of `materials.csv` for ranges, conditions and anything marked unverified.

| Domain | Used for |
|---|---|
| en.wikipedia.org | Alloy pages (6061, 7075, Ti-6Al-4V, SAE 304, 4340, PEEK, soda-lime glass, zirconium dioxide); "Young's modulus" and "Ultimate tensile strength" typical-value tables; "Prices of chemical elements" (metal price context) |
| www.azom.com | Datasheet-style pages for AISI 4340, Mg AZ31B, HAYNES 718, 304 stainless and Y-TZP zirconia (article 22376) |
| www.engineeringtoolbox.com | Young's modulus table, engineering materials properties (polymers, composites), densities of solids |
| www.wood-database.com | White oak and Douglas-fir along-grain density, MOE, MOR |
| www.atimaterials.com | 304 stainless density and annealed ASTM A240 minimum yield |
| www.continentaltrade.com.pl | Soda-lime glass density, modulus, modulus of rupture |
| www.imarcgroup.com | Resin and carbon fibre price context (HDPE, PP, PC, carbon fibre; market-research site, indicative) |
| accuratus.com | Public ceramic datasheets: 99.5% alumina, silicon carbide, silicon nitride |

## Not accessible or not used
- matweb.com returned HTTP 403 to automated fetches, so no value is cited from MatWeb.
- Manufacturer PDF datasheets (Morgan, Pilkington) returned binary that could not be read, so they are not cited; makeitfrom.com returned 403.
- 304 yield is the ASTM A240 minimum (205 MPa), not a typical value.
- Costs are order-of-magnitude estimates. Metal prices are anchored on Wikipedia Prices_of_chemical_elements (2019-2020); HDPE, PP, PC and carbon fibre on IMARC pages (2025-2026). All other polymer, composite, wood and ceramic costs are reasoned and marked unverified in the notes.
