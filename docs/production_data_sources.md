# MOIL Production Data — Verified Real Sources (as of Sep 2026)

## Real production figures already found (public, official)
| Year | Production (lakh tonnes) | Source |
|------|--------------------------|--------|
| 2014-15 | 11.39 | MOIL MOU doc, steel.gov.in |
| 2015-16 | 10.32 | MOIL MOU doc, steel.gov.in |
| FY2023-24 | ~17.56 (implied: 18.03/1.0267) | MOIL Directors Report |
| FY2024-25 | 18.03 (record) | MOIL Directors Report / sustainabilityreports.com |
| FY2024-25 revenue | ₹1,584.94 crore | MOIL AR 2024-25 |
| Q3 FY2025-26 | record; 9-month cum. 14.21 lakh t (+6.8% yoy) | PIB press release Jan 2026 |
| Q1 FY2026-27 sales | 3.68 lakh t | PIB / SteelMin |
| Nov 2025 (month) | 165,000 t (+1% yoy) | SteelOrbis |
| Reserves (one mine) | ~9.5 Mt proved (MECL exploration) | BSE filing 2022 |

## Where to download full PDFs (free, no login)
1. **MOIL official**: https://www.moil.nic.in → Investors → Annual Reports (all years, mine-wise production & reserves tables inside).
2. **BSE India filings**: https://www.bseindia.com → search MOIL (scrip 533221) → "Financials" → "Annual Reports" — direct PDFs like the 2022 filing above.
3. **PIB press releases**: https://pib.gov.in — search "MOIL production" → monthly/quarterly production figures, fully citable.
4. **IBM Indian Minerals Yearbook** (state-wise Mn production): https://ibm.gov.in → Publications → Indian Minerals Yearbook → "Manganese Ore" chapter (free PDF, has state-wise and mine-wise tables).
5. **India Data Portal**: https://indiadataportal.com — machine-readable CSVs of mineral production (search "manganese ore").
6. **sustainabilityreports.com/moil** — aggregated AR PDFs, quick access.

## Suggested manual step (30 min)
Download 5–8 annual report PDFs from (1) or (2) into `data/external/production/`,
then use `pdfplumber`/`camelot` (see ndvi_and_geology_sources.md) to pull the
"Production of Manganese Ore (mine-wise)" table into:
`data/external/production/production_history.csv` → columns:
`fiscal_year, mine, ore_raised_tonnes, mn_grade_pct, source_page`.

Until that's done, the table above (real, cited numbers) can seed the Phase-2
synthetic generator so monthly patterns are anchored to true annual totals.
