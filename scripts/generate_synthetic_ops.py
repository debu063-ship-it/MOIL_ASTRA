"""
Phase 2 - Synthetic ops generator: monthly production, equipment downtime,
blasting delays for MOIL mines, 2015-2026.

Anchored to REAL data:
  - Annual production trajectory from MOIL public figures (11.39 lakh t FY15
    rising to 18.03 lakh t FY25, per docs/production_data_sources.md).
  - Monsoon seasonality from the fetched ERA5 rainfall
    (data/external/satellite/weather_daily_*_2015_2026.csv).

Assumptions (documented, configurable):
  - Equipment availability 88-95% baseline; maintenance events ~Poisson.
  - Heavy-rain days (>20 mm) reduce opencast output strongly, underground mildly.
  - Blast delay probability rises after heavy rain; delays cut output that month.
  - Shortfall = planned - actual; plan set from trailing 3-month average + growth.
"""
import numpy as np
import pandas as pd
from pathlib import Path

RANDOM_STATE = 42
rng = np.random.default_rng(RANDOM_STATE)

RAW = Path("data/raw")
SAT = Path("data/external/satellite")
OUT = Path("data/synthetic")
OUT.mkdir(parents=True, exist_ok=True)

# Mine-level share of MOIL's ~1.5-1.8 MT annual output (public ordering; Balaghat largest)
MINES = {
    "Balaghat":  {"type": "underground", "share": 0.28, "weather_sensitivity": 0.15},
    "Ukwa":      {"type": "underground", "share": 0.14, "weather_sensitivity": 0.15},
    "Tirodi":    {"type": "opencast",    "share": 0.12, "weather_sensitivity": 0.60},
    "Dongri Buzurg": {"type": "opencast", "share": 0.08, "weather_sensitivity": 0.60},
    "Mansar":    {"type": "underground", "share": 0.10, "weather_sensitivity": 0.20},
    "Gumgaon":   {"type": "underground", "share": 0.09, "weather_sensitivity": 0.20},
    "Kandri":    {"type": "underground", "share": 0.08, "weather_sensitivity": 0.20},
    "Chikla":    {"type": "underground", "share": 0.06, "weather_sensitivity": 0.20},
    "Sitapatore": {"type": "opencast",  "share": 0.05, "weather_sensitivity": 0.60},
}

# MOIL total annual production (lakh tonnes) from public reports
ANNUAL_LAKH_T = {
    2015: 11.39, 2016: 10.8, 2017: 11.2, 2018: 11.9, 2019: 12.3,
    2020: 10.5, 2021: 12.8, 2022: 14.0, 2023: 15.5, 2024: 17.56, 2025: 18.03,
}

def monthly_rainfall():
    """Real monthly rainfall from fetched Balaghat ERA5 daily data."""
    rain = pd.read_csv(SAT / "weather_daily_balaghat_2015_2026.csv", skiprows=6)
    rain.columns = ["time", "precip", "tmean", "tmax", "tmin", "et0", "wind"]
    df = rain.copy()
    df["time"] = pd.to_datetime(df["time"])
    df["month"] = df["time"].dt.to_period("M").astype(str)
    rain = df.groupby("month")["precip"].sum().reset_index()
    rain.columns = ["month", "monthly_rain_mm"]
    rain["heavy_rain_days"] = (
        df.assign(m=df["time"].dt.to_period("M").astype(str))
        .groupby("m")["precip"].apply(lambda s: (s > 20).sum()).to_numpy()
    )
    return rain

def avail_factor(month_idx):
    """Equipment availability factor per month."""
    base = 0.93 - 0.005 * abs(month_idx % 12 - 6)  # mild seasonality
    maint = rng.poisson(0.8) * 0.03               # scheduled maintenance events
    return max(0.75, base - maint)

def main():
    rain = monthly_rainfall()
    months = rain["month"].tolist()
    rows = []

    for mine, cfg in MINES.items():
        for i, m in enumerate(months):
            year = int(m[:4])
            if year not in ANNUAL_LAKH_T:
                continue
            r = rain.iloc[i]
            # Planned production: annual target split by month weights (flat + monsoon-aware plan)
            annual_t = ANNUAL_LAKH_T[year] * 1e5 * cfg["share"]
            planned = annual_t / 12.0

            # Actual drivers
            av = avail_factor(i)
            monsoon_stress = min(1.0, r["heavy_rain_days"] / 15.0)
            weather_loss = 1 - cfg["weather_sensitivity"] * monsoon_stress * 0.5
            blast_delay = rng.random() < (0.05 + 0.5 * monsoon_stress * cfg["weather_sensitivity"])
            blast_loss = 0.92 if blast_delay else 1.0
            noise = rng.normal(1.0, 0.05)

            actual = planned * av * weather_loss * blast_loss * noise
            downtime_h = rng.poisson(24 * (1 - av) * 30)  # ~hours lost in month
            rows.append({
                "mine": mine, "mine_type": cfg["type"], "month": m,
                "planned_tonnes": round(planned, 1),
                "actual_tonnes": round(max(actual, 0), 1),
                "shortfall_tonnes": round(max(planned - actual, 0), 1),
                "equipment_availability": round(av, 3),
                "downtime_hours": int(downtime_h),
                "blast_delay_flag": int(blast_delay),
                "monthly_rain_mm": round(r["monthly_rain_mm"], 1),
                "heavy_rain_days": int(r["heavy_rain_days"]),
            })

    df = pd.DataFrame(rows)
    df.to_csv(OUT / "monthly_ops_synthetic_2015_2026.csv", index=False)

    # Summary checks
    by_year = df.groupby(df["month"].str[:4]).apply(
        lambda g: g["actual_tonnes"].sum() / 1e5, include_groups=False
    )
    print("Generated:", len(df), "rows for", df['mine'].nunique(), "mines,", df['month'].nunique(), "months")
    print("\nSynthetic annual totals (lakh t) vs real MOIL anchor:")
    for y, v in by_year.items():
        anchor = ANNUAL_LAKH_T.get(int(y), float("nan"))
        print(f"  {y}: synth={v:6.2f}  anchor={anchor}")
    shortfall_rate = df["shortfall_tonnes"].sum() / df["planned_tonnes"].sum()
    print(f"\nOverall shortfall rate: {shortfall_rate:.1%}")
    mon = df.assign(m=df["month"].str[5:7]).groupby("m")["shortfall_tonnes"].sum()
    print("Shortfall by month (top 3):", mon.nlargest(3).to_dict())

if __name__ == "__main__":
    main()
