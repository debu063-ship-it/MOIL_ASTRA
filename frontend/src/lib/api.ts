import {
  ZoneFeature,
  BoreholeFeature,
  OreVolumeData,
  ProductionData,
  CorrectiveAction,
  ShapData,
  DataSourceItem
} from '@/types';

/**
 * All data comes from the FastAPI backend (backend/app).
 * No static demo JSON is used anywhere in the app.
 */
export const API_BASE = import.meta.env.VITE_API_BASE || 'http://127.0.0.1:8600/api/v1';

export async function fetchJson<T>(url: string): Promise<T> {
  const res = await fetch(url);
  if (!res.ok) {
    throw new Error(`Failed to fetch ${url}: ${res.statusText}`);
  }
  return res.json() as Promise<T>;
}

const q = (params: Record<string, string | number | undefined>) => {
  const usp = new URLSearchParams();
  Object.entries(params).forEach(([k, v]) => {
    if (v !== undefined && v !== null && v !== '') usp.set(k, String(v));
  });
  const s = usp.toString();
  return s ? `?${s}` : '';
};

// ---------- map layers ----------

export async function fetchZones(): Promise<{ features: ZoneFeature[]; metadata: any }> {
  // top v3 prospectivity cells rendered as zone polygons (backend adapter)
  return fetchJson<{ features: ZoneFeature[]; metadata: any }>(`${API_BASE}/dashboard/zones`);
}

export async function fetchBoreholes(): Promise<{ features: BoreholeFeature[]; metadata: any }> {
  // 50 real NGDR collars with real assay core logs (12 fully assayed holes)
  return fetchJson<{ features: BoreholeFeature[]; metadata: any }>(`${API_BASE}/dashboard/boreholes`);
}

export async function fetchGeology(): Promise<{ features: any[]; metadata: any }> {
  return fetchJson<{ features: any[]; metadata: any }>(`${API_BASE}/layers/lithology_polygons`);
}

export async function fetchKnownOccurrences(): Promise<{ features: any[]; metadata: any }> {
  return fetchJson<{ features: any[]; metadata: any }>(`${API_BASE}/layers/moil_mines`);
}

export async function fetchBoreholeStructure(): Promise<{ structure: any[] }> {
  return fetchJson<{ structure: any[] }>(`${API_BASE}/layers/structure`);
}

export async function fetchGradeSummary(): Promise<any> {
  return fetchJson<any>(`${API_BASE}/grade/summary`);
}

export async function fetchVolumeSummary(): Promise<any> {
  return fetchJson<any>(`${API_BASE}/volume/summary`);
}

// ---------- zone analytics (5-step panel) ----------

export async function fetchOreVolume(zoneId: string): Promise<OreVolumeData> {
  // GSI cross-section resource blocks as 3D prism data (real tonnage/grade/SG)
  return fetchJson<OreVolumeData>(`${API_BASE}/dashboard/ore_volume${q({ zone_id: zoneId })}`);
}

export async function fetchProduction(mine: string): Promise<ProductionData> {
  // synthetic-calibrated ops (real annual MOIL anchors + real rainfall), labeled as such
  return fetchJson<ProductionData>(`${API_BASE}/dashboard/production${q({ mine })}`);
}

export async function fetchActions(mine?: string): Promise<{ actions: CorrectiveAction[]; metadata: any; mine?: string; context?: any }> {
  // deterministic rules engine over the mine's latest month
  return fetchJson<{ actions: CorrectiveAction[]; metadata: any; mine?: string; context?: any }>(
    `${API_BASE}/dashboard/actions${q({ mine })}`
  );
}

export async function fetchShap(mine?: string): Promise<ShapData> {
  // global v3 ensemble importances + evidence-only ablation narrative
  return fetchJson<ShapData>(`${API_BASE}/dashboard/shap${q({ mine })}`);
}

export async function fetchDataSources(): Promise<{ sources: DataSourceItem[] }> {
  return fetchJson<{ sources: DataSourceItem[] }>(`${API_BASE}/dashboard/data_sources`);
}

export async function fetchWeatherSummary(): Promise<any> {
  return fetchJson<any>(`${API_BASE}/dashboard/weather`);
}

export async function fetchGradeTonnage(): Promise<any> {
  return fetchJson<any>(`${API_BASE}/dashboard/grade_tonnage`);
}

export async function fetchClimateGrid(layerId: string, dateKey: string): Promise<any> {
  return fetchJson<any>(`${API_BASE}/dashboard/climate/${layerId}/${dateKey}`);
}

export async function fetchModelInfo(): Promise<any> {
  return fetchJson<any>(`${API_BASE}/models`);
}

export async function fetchShortfallHoldout(): Promise<any> {
  return fetchJson<any>(`${API_BASE}/shortfall/holdout`);
}

export async function fetchNextMonthForecast(mine: string): Promise<any> {
  return fetchJson<any>(`${API_BASE}/production/forecast${q({ mine })}`);
}

// ---------- what-if (runs the trained response model on the backend) ----------

export interface WhatIfBackendResult {
  mine: string;
  baseline_ratio: number;
  scenario_ratio: number;
  delta_ratio: number;
  planned_tonnes: number;
  baseline_shortfall_tonnes: number;
  scenario_shortfall_tonnes: number;
  provenance: string;
}

export async function runWhatIfSimulation(
  mine: string,
  equipmentAvailability: number,
  monthlyRainMm: number
): Promise<WhatIfBackendResult> {
  const res = await fetch(`${API_BASE}/whatif/simulate`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      mine,
      equipment_availability: equipmentAvailability,
      monthly_rain_mm: monthlyRainMm,
    }),
  });
  if (!res.ok) {
    const detail = await res.text();
    throw new Error(`what-if failed: ${detail}`);
  }
  return res.json() as Promise<WhatIfBackendResult>;
}
