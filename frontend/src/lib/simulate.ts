import { WhatIfParameters, WhatIfResult } from '@/types';
import { runWhatIfSimulation } from '@/lib/api';

/**
 * What-if simulation now runs the TRAINED response model (RandomForest v2)
 * on the FastAPI backend — no more hardcoded coefficients.
 * Params are mapped from the old slider semantics:
 *  - blastDelay (days)        -> blast_delay_days
 *  - equipmentCount (delta)   -> equipment_availability = mine latest + delta * 0.025 (clamped)
 *  - rainfallChange (%)       -> monthly_rain_mm = mine latest * (1 + pct/100) (clamped 0-800)
 * The production metadata supplies each mine's latest real observed drivers as the baseline.
 */
export function buildScenarioInputs(
  params: WhatIfParameters,
  production: { metadata?: { latestDrivers?: { equipment_availability: number; monthly_rain_mm: number } } } | null
) {
  const latest = production?.metadata?.latestDrivers;
  const baseEq = latest?.equipment_availability ?? 0.9;
  const baseRain = latest?.monthly_rain_mm ?? 50;
  const eq = Math.max(0.5, Math.min(1.0, baseEq + params.equipmentCount * 0.025));
  const rain = Math.max(0, Math.min(800, Math.max(0, baseRain * (1 + params.rainfallChange / 100))));
  return { equipmentAvailability: Number(eq.toFixed(3)), monthlyRainMm: Math.round(rain) };
}

export async function calculateSimulationAsync(
  params: WhatIfParameters,
  mine: string,
  production: { metadata?: { latestDrivers?: { equipment_availability: number; monthly_rain_mm: number } } } | null
): Promise<WhatIfResult> {
  const { equipmentAvailability, monthlyRainMm } = buildScenarioInputs(params, production);
  const r = await runWhatIfSimulation(mine, equipmentAvailability, monthlyRainMm);

  const plan = r.planned_tonnes || 40000;
  const baseForecast = plan * (1 - r.baseline_ratio);
  const netForecast = plan * (1 - r.scenario_ratio);
  const deltaMT = netForecast - baseForecast;
  const shortfallMT = Math.max(0, r.scenario_shortfall_tonnes);

  // risk score: map shortfall ratio to 0-100 (same semantics as production risk)
  const riskFromRatio = 30 + r.scenario_ratio * 160;
  const baseRiskFromRatio = 30 + r.baseline_ratio * 160;
  const adjustedRiskScore = Math.max(5, Math.min(99, Math.round(riskFromRatio)));
  const adjustedRiskColor =
    adjustedRiskScore >= 70 ? '#ef4444' : adjustedRiskScore >= 45 ? '#f97316' : '#22c55e';
  const adjustedRiskLevel: 'Red' | 'Amber' | 'Green' =
    adjustedRiskScore >= 70 ? 'Red' : adjustedRiskScore >= 45 ? 'Amber' : 'Green';

  return {
    deltaMT: Math.round(deltaMT),
    netProductionForecastMT: Math.round(netForecast),
    deltaRiskScore: Number((riskFromRatio - baseRiskFromRatio).toFixed(1)),
    adjustedRiskScore,
    adjustedRiskColor,
    adjustedRiskLevel,
    shortfallMT: Math.round(shortfallMT),
  };
}

/** Synchronous fallback while the async call is in flight (shows baseline). */
export function baselineSimulation(plan: number, baselineRatio: number): WhatIfResult {
  const baseForecast = plan * (1 - baselineRatio);
  const risk = Math.max(5, Math.min(99, Math.round(30 + baselineRatio * 160)));
  return {
    deltaMT: 0,
    netProductionForecastMT: Math.round(baseForecast),
    deltaRiskScore: 0,
    adjustedRiskScore: risk,
    adjustedRiskColor: risk >= 70 ? '#ef4444' : risk >= 45 ? '#f97316' : '#22c55e',
    adjustedRiskLevel: risk >= 70 ? 'Red' : risk >= 45 ? 'Amber' : 'Green',
    shortfallMT: Math.round(baselineRatio * plan),
  };
}
