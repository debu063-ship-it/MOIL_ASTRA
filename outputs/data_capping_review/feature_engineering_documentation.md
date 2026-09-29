# MOIL SIH26009 — Reviewed Feature Engineering Catalog

> [!NOTE]
> All derived features have been recomputed from the reviewed base data.
> Aspect angles are transformed into orthogonal sine and cosine components.
> `deposit_probability` is strictly isolated as a model diagnostic and NEVER used as a predictor.

| Feature Name | Domain | Formula | Source Columns | Physical Units | Description / Purpose |
|---|---|---|---|---|---|
| `iron_oxide_index` | Spectral | `B4 / B2` | B4, B2 | ratio | Sensitivity to Fe-bearing alteration minerals |
| `swir_nir_ratio` | Spectral | `B11 / B8` | B11, B8 | ratio | Shortwave IR to Near IR ratio |
| `clay_alteration_idx` | Spectral | `B11 / B12` | B11, B12 | ratio | Clay/phyllosilicate hydroxyl absorption proxy |
| `ferrous_iron_idx` | Spectral | `B12 / B8` | B12, B8 | ratio | Ferrous iron bearing silicate index |
| `ndvi` | Vegetation | `(B8 - B4) / (B8 + B4)` | B8, B4 | [-1, 1] | Normalized Difference Vegetation Index |
| `spectral_mean` | Spectral | `mean(B2, B3, B4, B8, B11, B12)` | B2..B12 | reflectance | Broadband albedo proxy |
| `spectral_range` | Spectral | `max(B) - min(B)` | B2..B12 | reflectance | Spectral dynamic contrast |
| `aspect_sin` | Topography | `sin(aspect * pi / 180)` | aspect | [-1, 1] | East-West illumination component |
| `aspect_cos` | Topography | `cos(aspect * pi / 180)` | aspect | [-1, 1] | North-South illumination component |
| `topo_ruggedness` | Topography | `slope * elevation / 1000` | slope, elevation | km-deg | Terrain roughness index |
| `sausar_proximity_class` | Geology | `binned(dist_to_sausar_km)` | dist_to_sausar_km | category | Categorical Sausar proximity bands |
| `in_sausar` | Geology | `1 if gsi_group == 'SAUSAR GROUP' else 0` | gsi_group | binary | Host rock indicator |
| `dist_to_gondite_km` | Geology | `Spatial distance to Gondite formation boundary` | vector geology | km | Primary ore formation proximity |
| `deposit_probability` | Model Diagnostic | `Existing model output probability` | prior model | [0, 1] | DIAGNOSTIC ONLY; NOT A PREDICTOR |
| `shortfall_pct` | Operations | `(shortfall_tonnes / planned_tonnes) * 100` | shortfall_tonnes, planned_tonnes | % | Normalized production shortfall rate |
| `production_efficiency` | Operations | `(actual_tonnes / planned_tonnes) * 100` | actual_tonnes, planned_tonnes | % | Plan realization percentage |
| `rain_intensity` | Weather | `monthly_rain_mm / heavy_rain_days` | monthly_rain_mm, heavy_rain_days | mm/day | Rainfall volume per heavy rain day |
| `downtime_rate` | Operations | `downtime_hours / 720` | downtime_hours | fraction | Fraction of monthly hours lost to downtime |
| `blast_delay_flag` | Operations | `1 if downtime_hours > 80 else 0` | downtime_hours | binary | Flag for severe blasting / logistics suspension |
| `monsoon_flag` | Weather | `1 if month in [6,7,8,9] else 0` | month | binary | Southwest monsoon season indicator |
| `quarter` | Calendar | `month.quarter` | month | integer 1-4 | Quarterly operational cycle |
| `actual_lag1` | Operations | `shift(actual_tonnes, 1)` | actual_tonnes | tonnes | Previous month actual production |
| `actual_lag3` | Operations | `shift(actual_tonnes, 3)` | actual_tonnes | tonnes | Three-month lagged production |
| `actual_tonnes_ma3` | Operations | `rolling_mean(actual_tonnes, 3)` | actual_tonnes | tonnes | 3-month smoothed production baseline |
| `actual_tonnes_ma6` | Operations | `rolling_mean(actual_tonnes, 6)` | actual_tonnes | tonnes | 6-month smoothed production baseline |
| `shortfall_ma3` | Operations | `rolling_mean(shortfall_pct, 3)` | shortfall_pct | % | 3-month smoothed shortfall percentage |
| `shortfall_ma6` | Operations | `rolling_mean(shortfall_pct, 6)` | shortfall_pct | % | 6-month smoothed shortfall percentage |
| `total_precip_mm` | Weather | `sum(daily_precip)` | precipitation_sum | mm | Monthly cumulative rainfall |
| `temp_range_c` | Weather | `max(temp_max) - min(temp_min)` | temperature_2m_max, min | °C | Monthly extreme thermal range |
| `heavy_rain_days` | Weather | `count(daily_precip >= 35mm)` | precipitation_sum | days | Monthly heavy rainfall frequency |
| `had_extreme_rain_day` | Weather | `1 if any daily_precip > 100mm else 0` | precipitation_sum | binary | Catastrophic precipitation event indicator |
