# Data sources

Access date: 2026-11-08. All data are public/textbook-grade. Values are single representative numbers; see the `notes` column of `materials.csv` for ranges, conditions and anything marked unverified.

| Domain | Used for |
|---|---|
| en.wikipedia.org | Alloy and polymer pages (6061, 2024 aluminium alloy, 7075, Ti-6Al-4V, SAE 304, 4340, PEEK, PTFE, PET, polystyrene, soda-lime glass, zirconium dioxide); "Young's modulus" and "Ultimate tensile strength" typical-value tables; "Prices of chemical elements" (metal price context) |
| www.azom.com | Datasheet-style pages for AISI 4340, Mg AZ31B, HAYNES 718, 304 and 316L stainless, grade 2 titanium and Y-TZP zirconia |
| www.engineeringtoolbox.com | Young's modulus table, engineering materials properties (polymers, composites), densities of solids |
| www.wood-database.com | White oak, Douglas-fir and balsa along-grain density, MOE, MOR |
| www.atimaterials.com | 304 stainless density and annealed ASTM A240 minimum yield |
| www.continentaltrade.com.pl | Soda-lime glass density, modulus, modulus of rupture |
| www.imarcgroup.com | Public price pages (Sep 2026 unless stated): copper, stainless steel (grade unspecified), titanium, nickel, magnesium, aluminium, hot rolled coil, HDPE, PP, PC, ABS, PMMA, epoxy, PET, polystyrene, polyamide, carbon fibre (market-research site, indicative) |
| www.zoro.com | 304 stainless plate listing: typical annealed yield 31,200 psi (retailer listing, not a mill datasheet) |
| accuratus.com | Public ceramic datasheets: 99.5% alumina, silicon carbide, silicon nitride |

## Not accessible or not used
- matweb.com returned HTTP 403 to automated fetches, so no value is cited from MatWeb.
- Manufacturer PDF datasheets (Morgan, Pilkington) returned binary that could not be read, so they are not cited; makeitfrom.com returned 403.
- 304 yield (215 MPa) is a retailer-listed typical value; 316L yield (170 MPa) is the ASTM A240 minimum because no typical value was found (named in the row).
- Borosilicate glass, nylon 6, tungsten carbide and bronze were not added because no opened page gave a full set of values.

## Cost confidence
- `cost_confidence = sourced` (6 rows): an opened public price page for the same commodity shows a price with unit and date; the page is in `cost_source_url` and the USD/kg working is in `notes`. These are copper, HDPE, PP, PC, ABS and polystyrene, from IMARC (market-research) pages, Sep 2026. Sourced prices are regional commodity (resin or metal) prices with a regional spread (regional min-to-max up to about 1.6x on these pages), not stock or delivered prices; the number used is a representative single value.
- `cost_confidence = estimated` (32 rows): no price page for that exact material, or the page was only a grade/product proxy or had a wide regional spread (A36 via hot rolled coil, 304 via generic stainless, nylon 6/6 via generic polyamide, PMMA, epoxy, PET). `cost_source_url` is blank; any anchor page is named in `notes`.
- All costs are single indicative USD/kg numbers for 2026, order-of-magnitude only.

Demotion rule used: a cost stays `sourced` only if the opened page is for the same commodity (not a grade or product proxy) and its regional min-to-max spread is at most about 1.6x; anything wider, or any proxy page, is `estimated` (copper, HDPE, PP, PC, ABS and polystyrene pass; A36, 304, nylon 6/6, PMMA, epoxy and PET were demoted).
