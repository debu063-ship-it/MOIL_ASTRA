export type FlowStage = 'overview' | 'zoomed' | 'step';
export type StepNumber = 1 | 2 | 3 | 4 | 5;

export interface ZoneProperties {
  id: string;
  name: string;
  probability: number;
  riskCategory: 'Very High' | 'High' | 'Medium' | 'Low';
  color: string;
  estimatedReserveTons: number;
  areaHectares?: number;
  avgGrade: string;
  strikeLengthMeters: number;
  overburdenThickness: string;
  shortfallRisk: number;
  confidence: number;
  source: string;
  description: string;
  zoneId?: string;
  gridRef?: { lat: number; lon: number };
}

export interface ZoneFeature {
  type: 'Feature';
  properties: ZoneProperties;
  geometry: {
    type: 'Polygon';
    coordinates: number[][][];
  };
}

export interface BoreholeLog {
  from: number;
  to: number;
  rock: string;
  grade: number;
  color: string;
}

export interface BoreholeProperties {
  id: string;
  zoneId: string;
  name: string;
  collarElevation: number;
  totalDepthMeters: number;
  interceptMnPercent: number;
  interceptInterval: string;
  collarCoordinates: [number, number];
  source: string;
  status: string;
  logs: BoreholeLog[];
}

export interface BoreholeFeature {
  type: 'Feature';
  properties: BoreholeProperties;
  geometry: {
    type: 'Point';
    coordinates: [number, number, number];
  };
}

export interface OreBlock {
  id: string;
  coordinates: number[][];
  center: [number, number];
  topAltitude: number;
  bottomAltitude: number;
  height: number;
  gradePercent: number;
  probability: number;
  gradeCategory: string;
  color: string;
  benchLevel: string;
  tonnageEst: number;
}

export interface OreVolumeData {
  metadata: {
    zoneId: string;
    source: string;
    krigingMethod: string;
    gridSpacingMeters: number[];
    totalBlocks: number;
    datum: string;
  };
  blocks: OreBlock[];
}

export type LayerSourceBadge = '[REAL]' | '[MODELED]' | '[SYNTHETIC]';

export interface LayerLegendItem {
  label: string;
  color: string;
}

export interface LayerDefinition {
  id: string;
  label: string;
  type: 'geojson' | 'climate_grid' | 'tile';
  url?: string;
  folder?: string;
  source: string;
  badge: LayerSourceBadge;
  timeVarying: boolean;
  defaultVisible: boolean;
  defaultOpacity: number;
  unit?: string;
  legend: LayerLegendItem[];
}

export interface MonthlyProduction {
  month: string;
  target: number;
  actual: number | null;
  forecast: number;
  lowerCI: number;
  upperCI: number;
}

export interface QuarterlyProduction {
  quarter: string;
  target: number;
  actual: number | null;
  forecast: number;
}

export interface ShortfallDriver {
  driver: string;
  impactMT: number;
  severity: 'High' | 'Medium' | 'Low';
}

export interface ProductionData {
  metadata: {
    zoneId: string;
    zoneName: string;
    source: string;
    targetAnnualMT: number;
    monthlyTargetMT: number;
    riskLevel: 'Red' | 'Amber' | 'Green';
    shortfallMT: number;
    shortfallPercent: number;
    riskScore: number;
    latestDrivers?: {
      equipment_availability: number;
      monthly_rain_mm: number;
      downtime_hours: number;
      blast_delay_flag: number;
      heavy_rain_days: number;
    };
  };
  monthly: MonthlyProduction[];
  quarterly: QuarterlyProduction[];
  shortfallDrivers: ShortfallDriver[];
}

export type ActionStatus = 'pending' | 'accepted' | 'ignored';

export interface CorrectiveAction {
  id: string;
  title: string;
  category: string;
  priority: number;
  expectedImpactMT: number;
  riskReductionPct: number;
  costEstimateINR: string;
  leadTimeDays: number;
  confidence: number;
  source: string;
  description: string;
  status: ActionStatus;
}

export interface ShapFeature {
  name: string;
  importancePct: number;
  shapValue: number;
  direction: 'positive' | 'negative' | 'neutral';
  category: string;
}

export interface ShapData {
  metadata: {
    zoneId: string;
    source: string;
    targetMetric: string;
    modelType?: string;
    baselineProbability?: number;
    predictedProbability: number;
  };
  features: ShapFeature[];
  plainLanguageExplanation: string;
}

export interface BoreholeLogInterval {
  from: number | null;
  to: number | null;
  rock: string;
  grade: number;
  color: string;
}

export interface WhatIfParameters {
  blastDelay: number; // days (0 - 14)
  equipmentCount: number; // equipment-availability delta units (-4 to +6), 1 unit = +2.5% availability
  rainfallChange: number; // percentage (-50% to +100%)
}

export interface WhatIfResult {
  deltaMT: number;
  netProductionForecastMT: number;
  deltaRiskScore: number;
  adjustedRiskScore: number;
  adjustedRiskColor: string;
  adjustedRiskLevel: 'Red' | 'Amber' | 'Green';
  shortfallMT: number;
}

export interface DataSourceItem {
  id: string;
  title: string;
  badge: LayerSourceBadge;
  badgeColor?: string;
  organization: string;
  description: string;
  resolution: string;
  cadence: string;
  license: string;
}
