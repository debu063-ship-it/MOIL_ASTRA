"""Generate a separately labeled mine-wise production scenario, calibrated only to public company totals."""
from __future__ import annotations

import csv
import json
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
SAT = ROOT / "data/external/satellite"
OUT = ROOT / "data/synthetic"
SEED = 260929
METHOD = ("Synthetic mine allocation using documented scenario shares; monthly weather weights use observed "
          "Open-Meteo daily precipitation by nearest available station. Each synthetic fiscal-year aggregate "
          "is scaled to a public MOIL company production anchor when available, or linearly interpolated "
          "between anchors; mine targets are 5% above each scenario actual allocation. Monthly actuals "
          "include rain sensitivity, random noise, and injected disruption events, then are normalized to "
          "the annual mine allocation. No row is a real mine-wise production observation.")

# Scenario allocation assumptions (sum=1.0); only Balaghat/Ukwa/Tirodi etc. mine identities/types are sourced.
MINES = {
    "Balaghat": ("underground", .24, .15, "Balaghat"),
    "Ukwa": ("underground", .12, .15, "Ukwa"),
    "Tirodi": ("opencast", .10, .60, "Balaghat"),
    "Sitapatore": ("opencast", .05, .60, "Balaghat"),
    "Dongri Buzurg": ("opencast", .08, .60, "Bhandara"),
    "Chikla": ("underground", .06, .20, "Bhandara"),
    "Munsar": ("underground", .09, .20, "Nagpur"),
    "Gumgaon": ("underground", .08, .20, "Nagpur"),
    "Kandri": ("underground", .08, .20, "Nagpur"),
    "Beldongri": ("underground", .05, .20, "Nagpur"),
    "Parsoda": ("opencast", .05, .60, "Nagpur"),
}

# Fiscal-year end year -> tonnes. Amounts copied from documented public reports;
# FY23-24 is a calculation from MOIL's reported FY24-25 total and YoY growth.
ANCHORS = {
    2016: (1_032_000, "FY2015-16 MOIL production 10.32 lakh t", "docs/production_data_sources.md, real figures table, retrieved 2026-09-29"),
    2023: (1_302_000, "FY2022-23 MOIL production 13.02 lakh t", "MOIL Annual Report 2022-23, Production section; https://moil.nic.in/userfiles/file/InvRel/Financials/Annual_Report_2022-23.pdf; retrieved 2026-09-29"),
    2024: (1_803_000 / 1.0267, "FY2023-24 implied from FY2024-25 and reported 2.67% growth", "MOIL Annual Report 2024-25, Production section; https://moil.nic.in/userfiles/Annual_Report_2024_25.pdf; retrieved 2026-09-29"),
    2025: (1_803_000, "FY2024-25 MOIL production 18.03 lakh t", "MOIL Annual Report 2024-25, Production section; https://moil.nic.in/userfiles/Annual_Report_2024_25.pdf; retrieved 2026-09-29"),
    2026: (1_907_000, "FY2025-26 provisional MOIL production 19.07 lakh t", "MOIL provisional production disclosure for March 2026; https://moil.nic.in/userfiles/file/InvRel/Disclosure%20and%20events/Mar_2026.pdf; retrieved 2026-09-29"),
}


def read_daily_weather(station: str) -> pd.DataFrame:
    path = SAT / f"weather_daily_{station.lower()}_2015_2026.csv"
    lines = path.read_text(encoding="utf-8-sig").splitlines()
    header = next(i for i, line in enumerate(lines) if line.lower().startswith("time,precipitation_sum"))
    df = pd.read_csv(path, skiprows=header)
    df["time"] = pd.to_datetime(df["time"])
    df["fy_end"] = df.time.dt.year + (df.time.dt.month >= 4).astype(int)
    df["fy_month"] = ((df.time.dt.month - 4) % 12) + 1
    df["month"] = df.time.dt.strftime("%Y-%m")
    df["rain"] = pd.to_numeric(df["precipitation_sum (mm)"], errors="coerce").fillna(0)
    return df


def main() -> dict:
    OUT.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(SEED)
    weights = np.array([v[1] for v in MINES.values()], dtype=float)
    if not np.isclose(weights.sum(), 1.0):
        raise ValueError(f"mine allocation shares must sum to 1, got {weights.sum()}")
    weather = {s: read_daily_weather(s) for s in ["balaghat", "bhandara", "nagpur", "ukwa"]}
    station_months = {}
    for station, daily in weather.items():
        grouped = daily.groupby(["fy_end", "fy_month"], as_index=False).agg(
            month=("month", "first"), monthly_rain_mm=("rain", "sum"),
            heavy_rain_days=("rain", lambda s: int((s > 20).sum())))
        station_months[station.title()] = {
            int(y): grp.sort_values("fy_month").copy()
            for y, grp in grouped.groupby("fy_end") if len(grp) == 12}
    # Use only complete fiscal years available for every required weather station.
    complete_fys = set.intersection(*(set(s.keys()) for s in station_months.values()))
    anchor_years = sorted(ANCHORS)
    anchor_values = np.array([ANCHORS[y][0] for y in anchor_years], dtype=float)
    fiscal_totals = {fy: float(np.interp(fy, anchor_years, anchor_values)) for fy in complete_fys
                     if min(anchor_years) <= fy <= max(anchor_years)}

    rows = []
    for fy_end in sorted(complete_fys):
        if fy_end not in fiscal_totals:
            continue
        annual_t = fiscal_totals[fy_end]
        if fy_end in ANCHORS:
            calibrated_to, source_ref = ANCHORS[fy_end][1], ANCHORS[fy_end][2]
        else:
            lower = max(y for y in anchor_years if y < fy_end)
            upper = min(y for y in anchor_years if y > fy_end)
            calibrated_to = f"Linear interpolation between FY{lower-1}-{str(lower)[-2:]} and FY{upper-1}-{str(upper)[-2:]} MOIL published totals"
            source_ref = ANCHORS[lower][2] + " | " + ANCHORS[upper][2]
        # Fixed set of injected disruptions each fiscal year, reproducible with SEED.
        disruption_ix = set(rng.choice(np.arange(12), size=2, replace=False).tolist())
        for (mine, (mine_type, share, sensitivity, station)), idx in zip(MINES.items(), range(len(MINES))):
            months = station_months[station][fy_end]
            rain = months.monthly_rain_mm.to_numpy(dtype=float)
            rain_norm = rain / max(1.0, float(rain.max()))
            # Actual seasonal weights lean away from very wet months; weights normalized within FY.
            actual_weights = np.maximum(0.25, 1.0 - 0.22 * rain_norm)
            actual_weights = actual_weights / actual_weights.sum()
            plan_weights = np.maximum(0.35, 1.0 - 0.14 * rain_norm)
            plan_weights = plan_weights / plan_weights.sum()
            mine_annual = annual_t * share
            planned_annual = mine_annual * 1.05
            wet_days = months.heavy_rain_days.to_numpy(dtype=int)
            stress = np.clip(wet_days / 15.0, 0, 1)
            avail = np.clip(0.94 - 0.12 * stress * sensitivity - rng.uniform(0.0, .045, 12), .72, .98)
            event_multiplier = np.ones(12)
            for m_idx in disruption_ix:
                if rng.random() < 0.55:
                    event_multiplier[m_idx] = rng.uniform(.72, .88)
            random_month = rng.lognormal(mean=0.0, sigma=.08, size=12)
            actual_shape = actual_weights * (1 - sensitivity * .35 * stress) * avail * event_multiplier * random_month
            actual_shape = actual_shape / actual_shape.sum()
            actual_t = mine_annual * actual_shape
            planned_t = planned_annual * plan_weights
            for j, (_, m) in enumerate(months.iterrows()):
                event = "planned_disruption" if j in disruption_ix and event_multiplier[j] < 1 else "none"
                method = METHOD + f" Mine allocation share assumption={share:.4f}; rainfall station={station}."
                rows.append({"mine": mine, "mine_type": mine_type, "month": m.month,
                    "fiscal_year": f"FY{fy_end-1}-{str(fy_end)[-2:]}",
                    "planned_tonnes": round(float(planned_t[j]), 2),
                    "actual_tonnes": round(float(actual_t[j]), 2),
                    "shortfall_tonnes": round(max(0.0, float(planned_t[j]-actual_t[j])), 2),
                    "equipment_availability": round(float(avail[j]), 4),
                    "disruption_event": event,
                    "monthly_rain_mm": round(float(m.monthly_rain_mm), 2),
                    "heavy_rain_days": int(m.heavy_rain_days), "provenance": "SYNTHETIC",
                    "method": method, "random_seed": SEED, "calibrated_to": calibrated_to,
                    "source_ref": source_ref + f" | Open-Meteo daily weather file for {station}; retrieved 2026-09-29"})
    df = pd.DataFrame(rows)
    path = OUT / "production_scenario.csv"
    df.to_csv(path, index=False)
    annual_summary = (df.groupby("fiscal_year", as_index=False)
        .agg(scenario_actual_tonnes=("actual_tonnes", "sum"), scenario_plan_tonnes=("planned_tonnes", "sum")))
    summary = []
    for r in annual_summary.to_dict("records"):
        fy_end = int(r["fiscal_year"].split("-")[0][2:]) + 1
        expected = fiscal_totals.get(fy_end)
        summary.append({**r, "company_total_anchor_tonnes": expected,
                        "actual_vs_anchor_pct": (r["scenario_actual_tonnes"]-expected)/expected*100 if expected else None,
                        "calibrated_to": ANCHORS.get(fy_end, (None, "interpolated", None))[1]})
    result = {"gap": 5, "status": "COMPLETE_SYNTHETIC_SCENARIO", "rows": len(df),
        "mines": int(df.mine.nunique()), "months": int(df.month.nunique()),
        "fiscal_years": sorted(df.fiscal_year.unique().tolist()), "random_seed": SEED,
        "all_rows_provenance": "SYNTHETIC", "annual_validation": summary,
        "source_anchors": {str(y): {"tonnes": v[0], "label": v[1], "source_ref": v[2]} for y,v in ANCHORS.items()},
        "method": METHOD, "output": str(path.relative_to(ROOT))}
    (ROOT / "data/processed/production_scenario_validation.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    return result


if __name__ == "__main__":
    print(json.dumps(main(), indent=2))
