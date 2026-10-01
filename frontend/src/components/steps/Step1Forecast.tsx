import React, { useState, useEffect } from 'react';
import ReactECharts from 'echarts-for-react';
import { ProductionData } from '@/types';
import { fetchGradeTonnage, fetchWeatherSummary } from '@/lib/api';
import { SourceBadge, StatusBadge } from '@/components/ui/Badge';
import { 
  TrendingUp, 
  AlertTriangle, 
  Calendar, 
  Layers, 
  ShieldAlert, 
  CloudRain, 
  Scale, 
  Droplets,
  Wind,
  CheckCircle2
} from 'lucide-react';

interface Step1Props {
  production: ProductionData | null;
  mine: string;
  onNext: () => void;
}

export const Step1Forecast: React.FC<Step1Props> = ({ production, mine, onNext }) => {
  const [activeTab, setActiveTab] = useState<'forecast' | 'grade_tonnage' | 'weather'>('forecast');
  const [viewMode, setViewMode] = useState<'monthly' | 'quarterly'>('monthly');

  const [gradeTonnage, setGradeTonnage] = useState<any>(null);
  const [weather, setWeather] = useState<any>(null);

  useEffect(() => {
    fetchGradeTonnage().then(setGradeTonnage).catch(console.error);
    fetchWeatherSummary().then(setWeather).catch(console.error);
  }, []);

  if (!production) {
    return <div className="text-slate-400 p-6 text-center">Loading production data...</div>;
  }

  const { metadata, monthly, quarterly, shortfallDrivers } = production;

  // Monthly Line Chart Options with Confidence Band
  const months = monthly.map(m => m.month);
  const actuals = monthly.map(m => m.actual);
  const forecasts = monthly.map(m => m.forecast);
  const lowerCI = monthly.map(m => m.lowerCI);
  const upperDiff = monthly.map(m => m.upperCI - m.lowerCI);
  const targets = monthly.map(m => m.target);
  // Data-driven y-axis floor: a hardcoded min pushed every line below the
  // visible axis area for low-tonnage mines (chart rendered "empty").
  const seriesVals = [...targets, ...actuals, ...forecasts, ...lowerCI]
    .filter((v): v is number => v != null && isFinite(v));
  const yMin = seriesVals.length
    ? Math.max(0, Math.floor((Math.min(...seriesVals) * 0.92) / 1000) * 1000)
    : 0;

  const monthlyOption = {
    backgroundColor: 'transparent',
    tooltip: {
      trigger: 'axis',
      backgroundColor: 'rgba(15, 23, 42, 0.95)',
      borderColor: 'rgba(255, 255, 255, 0.15)',
      textStyle: { color: '#f1f5f9', fontSize: 11 },
      formatter: (params: any[]) => {
        let title = `<div style="font-weight: bold; margin-bottom: 4px;">${params[0].name} 2024</div>`;
        let lines = '';
        params.forEach(p => {
          if (p.seriesName !== 'lowerCI' && p.value !== undefined && p.value !== null) {
            lines += `<div style="display: flex; justify-content: space-between; gap: 12px; font-size: 11px;">
              <span>${p.marker} ${p.seriesName}:</span>
              <span style="font-family: monospace; font-weight: bold;">${Number(p.value).toLocaleString()} MT</span>
            </div>`;
          }
        });
        return title + lines;
      }
    },
    legend: {
      data: ['Target', 'Actual', 'AI Forecast'],
      textStyle: { color: '#64748b', fontSize: 10 },
      top: 0,
      right: 0
    },
    grid: {
      top: 30,
      left: 45,
      right: 15,
      bottom: 25
    },
    xAxis: {
      type: 'category',
      data: months,
      axisLine: { lineStyle: { color: 'rgba(15, 23, 42, 0.12)' } },
      axisLabel: { color: '#64748b', fontSize: 10 }
    },
    yAxis: {
      type: 'value',
      name: 'MT',
      min: yMin,
      axisLine: { lineStyle: { color: 'rgba(15, 23, 42, 0.12)' } },
      splitLine: { lineStyle: { color: 'rgba(15, 23, 42, 0.07)' } },
      axisLabel: { color: '#64748b', fontSize: 10, formatter: (val: number) => `${val / 1000}k` }
    },
    series: [
      {
        name: 'lowerCI',
        type: 'line',
        data: lowerCI,
        lineStyle: { opacity: 0 },
        stack: 'confidence-band',
        symbol: 'none'
      },
      {
        name: '95% Confidence Band',
        type: 'line',
        data: upperDiff,
        lineStyle: { opacity: 0 },
        areaStyle: { color: 'rgba(56, 189, 248, 0.15)' },
        stack: 'confidence-band',
        symbol: 'none'
      },
      {
        name: 'Target',
        type: 'line',
        data: targets,
        lineStyle: { color: '#64748b', type: 'dotted', width: 2 },
        symbol: 'none'
      },
      {
        name: 'Actual',
        type: 'line',
        data: actuals,
        lineStyle: { color: '#38bdf8', width: 2.5 },
        itemStyle: { color: '#38bdf8' },
        symbolSize: 6
      },
      {
        name: 'AI Forecast',
        type: 'line',
        data: forecasts,
        lineStyle: { color: '#f97316', width: 2.5, type: 'dashed' },
        itemStyle: { color: '#f97316' },
        symbolSize: 6
      }
    ]
  };

  // Quarterly Bar Chart Options
  const qLabels = quarterly.map(q => q.quarter);
  const qTargets = quarterly.map(q => q.target);
  const qActualForecast = quarterly.map(q => q.actual !== null ? q.actual : q.forecast);

  const quarterlyOption = {
    backgroundColor: 'transparent',
    tooltip: {
      trigger: 'axis',
      backgroundColor: 'rgba(15, 23, 42, 0.95)',
      borderColor: 'rgba(255, 255, 255, 0.15)',
      textStyle: { color: '#f1f5f9', fontSize: 11 }
    },
    legend: {
      data: ['Target', 'Actual / Projected'],
      textStyle: { color: '#64748b', fontSize: 10 },
      top: 0,
      right: 0
    },
    grid: {
      top: 30,
      left: 45,
      right: 15,
      bottom: 25
    },
    xAxis: {
      type: 'category',
      data: qLabels,
      axisLine: { lineStyle: { color: 'rgba(15, 23, 42, 0.12)' } },
      axisLabel: { color: '#64748b', fontSize: 10 }
    },
    yAxis: {
      type: 'value',
      name: 'MT',
      axisLine: { lineStyle: { color: 'rgba(15, 23, 42, 0.12)' } },
      splitLine: { lineStyle: { color: 'rgba(15, 23, 42, 0.07)' } },
      axisLabel: { color: '#64748b', fontSize: 10, formatter: (val: number) => `${val / 1000}k` }
    },
    series: [
      {
        name: 'Target',
        type: 'bar',
        data: qTargets,
        itemStyle: { color: '#475569', borderRadius: [4, 4, 0, 0] },
        barWidth: '24%'
      },
      {
        name: 'Actual / Projected',
        type: 'bar',
        data: qActualForecast,
        itemStyle: { 
          color: (param: any) => param.dataIndex === 2 ? '#ef4444' : '#38bdf8',
          borderRadius: [4, 4, 0, 0]
        },
        barWidth: '24%'
      }
    ]
  };

  // Risk Gauge Option
  const gaugeOption = {
    backgroundColor: 'transparent',
    series: [
      {
        type: 'gauge',
        startAngle: 180,
        endAngle: 0,
        min: 0,
        max: 100,
        radius: '100%',
        center: ['50%', '75%'],
        splitNumber: 5,
        axisLine: {
          lineStyle: {
            width: 8,
            color: [
              [0.4, '#22c55e'],
              [0.7, '#f59e0b'],
              [1, '#ef4444']
            ]
          }
        },
        pointer: {
          icon: 'triangle',
          length: '50%',
          width: 6,
          offsetCenter: [0, '-10%'],
          itemStyle: { color: '#f8fafc' }
        },
        axisTick: { length: 4, lineStyle: { color: 'auto', width: 1 } },
        splitLine: { length: 8, lineStyle: { color: 'auto', width: 2 } },
        axisLabel: { color: '#64748b', fontSize: 9, distance: -24 },
        title: { offsetCenter: [0, '-35%'], fontSize: 11, color: '#64748b' },
        detail: {
          fontSize: 16,
          offsetCenter: [0, '0%'],
          valueAnimation: true,
          formatter: (value: number) => `${Math.round(value)}`,
          color: '#0f172a',
          fontFamily: 'monospace',
          fontWeight: 'bold'
        },
        data: [{ value: metadata.riskScore, name: 'Risk Score' }]
      }
    ]
  };

  // Grade-Tonnage Chart Options
  const cutoffs = gradeTonnage?.cutoffCurve?.map((c: any) => `${c.cutoffMnPct}%`) || [];
  const tonnages = gradeTonnage?.cutoffCurve?.map((c: any) => (c.tonnageMT / 1000000).toFixed(2)) || [];
  const avgGrades = gradeTonnage?.cutoffCurve?.map((c: any) => c.avgGradeMnPct) || [];

  const gradeTonnageOption = {
    backgroundColor: 'transparent',
    tooltip: {
      trigger: 'axis',
      backgroundColor: 'rgba(15, 23, 42, 0.95)',
      borderColor: 'rgba(255, 255, 255, 0.15)',
      textStyle: { color: '#f1f5f9', fontSize: 11 }
    },
    legend: {
      data: ['Ore Tonnage (M MT)', 'Mean Grade (% Mn)'],
      textStyle: { color: '#64748b', fontSize: 10 },
      top: 0
    },
    grid: { top: 30, left: 40, right: 40, bottom: 25 },
    xAxis: {
      type: 'category',
      data: cutoffs,
      name: 'Cutoff %',
      axisLine: { lineStyle: { color: 'rgba(15, 23, 42, 0.12)' } },
      axisLabel: { color: '#64748b', fontSize: 10 }
    },
    yAxis: [
      {
        type: 'value',
        name: 'M MT',
        axisLine: { lineStyle: { color: 'rgba(15, 23, 42, 0.12)' } },
        splitLine: { lineStyle: { color: 'rgba(15, 23, 42, 0.07)' } },
        axisLabel: { color: '#38bdf8', fontSize: 10 }
      },
      {
        type: 'value',
        name: '% Mn',
        min: 30,
        max: 55,
        axisLine: { lineStyle: { color: 'rgba(15, 23, 42, 0.12)' } },
        splitLine: { show: false },
        axisLabel: { color: '#f97316', fontSize: 10 }
      }
    ],
    series: [
      {
        name: 'Ore Tonnage (M MT)',
        type: 'bar',
        data: tonnages,
        itemStyle: { color: '#0284c7', borderRadius: [4, 4, 0, 0] },
        barWidth: '35%'
      },
      {
        name: 'Mean Grade (% Mn)',
        type: 'line',
        yAxisIndex: 1,
        data: avgGrades,
        lineStyle: { color: '#f97316', width: 2.5 },
        itemStyle: { color: '#f97316' },
        symbolSize: 6
      }
    ]
  };

  // Weather Rainfall Forecast Chart
  const forecastDays = weather?.outlook7d?.days || [];
  const forecastRain = weather?.outlook7d?.expected_mm_per_day || [];

  const weatherForecastOption = {
    backgroundColor: 'transparent',
    tooltip: {
      trigger: 'axis',
      backgroundColor: 'rgba(15, 23, 42, 0.95)',
      borderColor: 'rgba(255, 255, 255, 0.15)',
      textStyle: { color: '#f1f5f9', fontSize: 11 }
    },
    grid: { top: 25, left: 35, right: 15, bottom: 25 },
    xAxis: {
      type: 'category',
      data: forecastDays,
      axisLine: { lineStyle: { color: 'rgba(15, 23, 42, 0.12)' } },
      axisLabel: { color: '#64748b', fontSize: 10 }
    },
    yAxis: {
      type: 'value',
      name: 'mm',
      axisLine: { lineStyle: { color: 'rgba(15, 23, 42, 0.12)' } },
      splitLine: { lineStyle: { color: 'rgba(15, 23, 42, 0.07)' } },
      axisLabel: { color: '#38bdf8', fontSize: 10 }
    },
    series: [
      {
        name: 'Rainfall (mm)',
        type: 'bar',
        data: forecastRain,
        itemStyle: {
          color: (param: any) => param.value > 30 ? '#ef4444' : param.value > 15 ? '#0284c7' : '#38bdf8',
          borderRadius: [4, 4, 0, 0]
        },
        barWidth: '40%'
      }
    ]
  };

  return (
    <div className="space-y-4">
      {/* Tab Switcher for All 14 Integrated Datasets */}
      <div className="flex items-center p-1 bg-slate-900/80 rounded-xl border border-white/10 text-xs">
        <button
          onClick={() => setActiveTab('forecast')}
          className={`flex-1 py-1.5 rounded-lg font-semibold flex items-center justify-center gap-1.5 transition-all ${
            activeTab === 'forecast'
              ? 'bg-sky-500 text-slate-950 shadow-md shadow-sky-500/20'
              : 'text-slate-400 hover:text-slate-200'
          }`}
        >
          <TrendingUp className="w-3.5 h-3.5" />
          Production & Shortfall
        </button>

        <button
          onClick={() => setActiveTab('grade_tonnage')}
          className={`flex-1 py-1.5 rounded-lg font-semibold flex items-center justify-center gap-1.5 transition-all ${
            activeTab === 'grade_tonnage'
              ? 'bg-sky-500 text-slate-950 shadow-md shadow-sky-500/20'
              : 'text-slate-400 hover:text-slate-200'
          }`}
        >
          <Scale className="w-3.5 h-3.5" />
          Grade & Tonnage
        </button>

        <button
          onClick={() => setActiveTab('weather')}
          className={`flex-1 py-1.5 rounded-lg font-semibold flex items-center justify-center gap-1.5 transition-all ${
            activeTab === 'weather'
              ? 'bg-sky-500 text-slate-950 shadow-md shadow-sky-500/20'
              : 'text-slate-400 hover:text-slate-200'
          }`}
        >
          <CloudRain className="w-3.5 h-3.5" />
          Weather Telemetry
        </button>
      </div>

      {/* VIEW 1: PRODUCTION & SHORTFALL */}
      {activeTab === 'forecast' && (
        <>
          {/* Target vs Shortfall KPI Strip */}
          <div className="grid grid-cols-2 gap-2.5">
            <div className="glass-card p-3 rounded-xl border border-white/5">
              <div className="flex items-center justify-between">
                <span className="text-[11px] text-slate-400 font-medium">Monthly Target</span>
                <SourceBadge badge="[REAL]" />
              </div>
              <div className="text-lg font-bold font-mono text-slate-100 mt-1">
                {metadata.monthlyTargetMT.toLocaleString()} <span className="text-xs font-normal text-slate-400">MT</span>
              </div>
              <span className="text-[10px] text-slate-400">Annual: {(metadata.targetAnnualMT / 100000).toFixed(1)} Lakh MT</span>
            </div>

            <div className="glass-card p-3 rounded-xl border border-red-500/20 bg-red-950/20">
              <div className="flex items-center justify-between">
                <span className="text-[11px] text-red-300 font-medium">Predicted Shortfall</span>
                <StatusBadge status={metadata.riskLevel} />
              </div>
              <div className="text-lg font-bold font-mono text-red-400 mt-1">
                -{metadata.shortfallMT.toLocaleString()} <span className="text-xs font-normal text-red-300/80">MT</span>
              </div>
              <span className="text-[10px] text-red-400/80">Shortfall Impact: ~{metadata.shortfallPercent}% of target</span>
            </div>
          </div>

          {/* Production Forecast Chart Card */}
          <div className="glass-card p-3.5 rounded-xl border border-white/10">
            <div className="flex items-center justify-between mb-1">
              <div className="flex items-center gap-2">
                <TrendingUp className="w-4 h-4 text-sky-400" />
                <span className="text-xs font-bold text-slate-100 uppercase tracking-wider">Production Forecast</span>
                <SourceBadge badge="[MODELED]" />
              </div>

              {/* Monthly / Quarterly Toggle */}
              <div className="flex items-center bg-slate-900/80 p-0.5 rounded-lg border border-white/5 text-[11px]">
                <button
                  onClick={() => setViewMode('monthly')}
                  className={`px-2 py-0.5 rounded-md font-medium transition-colors ${
                    viewMode === 'monthly' ? 'bg-sky-500 text-slate-900 font-bold' : 'text-slate-400 hover:text-slate-200'
                  }`}
                >
                  Monthly
                </button>
                <button
                  onClick={() => setViewMode('quarterly')}
                  className={`px-2 py-0.5 rounded-md font-medium transition-colors ${
                    viewMode === 'quarterly' ? 'bg-sky-500 text-slate-900 font-bold' : 'text-slate-400 hover:text-slate-200'
                  }`}
                >
                  Quarterly
                </button>
              </div>
            </div>

            <div className="h-44 w-full mt-2">
              <ReactECharts
                option={viewMode === 'monthly' ? monthlyOption : quarterlyOption}
                style={{ height: '100%', width: '100%' }}
                opts={{ renderer: 'canvas' }}
              />
            </div>
          </div>

          {/* Operational Risk Gauge & Shortfall Drivers */}
          <div className="grid grid-cols-5 gap-2.5">
            <div className="col-span-2 glass-card p-2.5 rounded-xl border border-white/10 flex flex-col justify-between">
              <div className="flex items-center justify-between text-[11px] font-semibold text-slate-200">
                <span className="flex items-center gap-1">
                  <ShieldAlert className="w-3.5 h-3.5 text-amber-400" />
                  Risk Index
                </span>
                <SourceBadge badge="[MODELED]" />
              </div>
              <div className="h-24 w-full">
                <ReactECharts
                  option={gaugeOption}
                  style={{ height: '100%', width: '100%' }}
                  opts={{ renderer: 'canvas' }}
                />
              </div>
              <div className="text-center text-[10px] text-slate-400">
                {metadata.riskScore >= 70 ? 'High Slippage Alert' : 'Normal Operating Variance'}
              </div>
            </div>

            <div className="col-span-3 glass-card p-3 rounded-xl border border-white/10 flex flex-col justify-between">
              <div className="flex items-center justify-between text-[11px] font-semibold text-slate-200 mb-1.5">
                <span className="flex items-center gap-1">
                  <AlertTriangle className="w-3.5 h-3.5 text-red-400" />
                  Shortfall Root Causes
                </span>
              </div>

              <div className="space-y-1.5 flex-1">
                {shortfallDrivers.map((driver, idx) => (
                  <div
                    key={idx}
                    className="p-1.5 rounded bg-slate-900/50 border border-white/5 flex items-center justify-between text-[11px]"
                  >
                    <span className="text-slate-300 truncate max-w-[140px]">{driver.driver}</span>
                    <span className="font-mono text-red-400 font-bold shrink-0">-{driver.impactMT} MT</span>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </>
      )}

      {/* VIEW 2: GRADE & TONNAGE (UNFC / JORC) */}
      {activeTab === 'grade_tonnage' && (
        <div className="space-y-3">
          <div className="glass-card p-3.5 rounded-xl border border-white/10">
            <div className="flex items-center justify-between mb-2">
              <span className="text-xs font-bold text-slate-100 uppercase tracking-wider flex items-center gap-1.5">
                <Scale className="w-4 h-4 text-sky-400" />
                Cutoff Grade vs Tonnage Curve
              </span>
              <SourceBadge badge="[REAL]" />
            </div>
            <div className="h-44 w-full">
              <ReactECharts
                option={gradeTonnageOption}
                style={{ height: '100%', width: '100%' }}
                opts={{ renderer: 'canvas' }}
              />
            </div>
          </div>

          {/* UNFC Classification Cards */}
          <div className="space-y-2">
            <span className="text-[11px] text-slate-400 uppercase font-semibold tracking-wider block px-1">
              UNFC-1997 / JORC Mineral Inventory
            </span>
            {gradeTonnage?.unfcClassification?.map((cat: any, i: number) => (
              <div key={i} className="p-2.5 rounded-xl bg-slate-900/60 border border-white/5 flex items-center justify-between text-xs">
                <div>
                  <span className="font-semibold text-slate-200 block">{cat.category}</span>
                  <span className="text-[10px] text-slate-400">{cat.status}</span>
                </div>
                <div className="text-right shrink-0 ml-2">
                  <span className="font-mono font-bold text-sky-300 block">
                    {(cat.tonnageMT / 100000).toFixed(1)} Lakh MT
                  </span>
                  <span className="text-[10px] font-mono text-emerald-400 font-semibold">{cat.avgGrade}</span>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* VIEW 3: WEATHER & PIT HYDROLOGY */}
      {activeTab === 'weather' && (
        <div className="space-y-3">
          {/* Station KPI strip */}
          <div className="grid grid-cols-3 gap-2 text-xs">
            <div className="glass-card p-2.5 rounded-xl border border-white/5">
              <span className="text-[10px] text-slate-400 uppercase block">24h Rainfall</span>
              <span className="text-base font-bold font-mono text-sky-400 mt-0.5 block">
                {weather?.currentConditions?.rainfallLast24hMm ?? '—'} mm
              </span>
              <span className="text-[9px] text-slate-400">Month: {weather?.currentConditions?.rainfallMonthlyTotalMm ?? '—'} mm</span>
            </div>

            <div className="glass-card p-2.5 rounded-xl border border-white/5">
              <span className="text-[10px] text-slate-400 uppercase block">Sump Pumping</span>
              <span className="text-base font-bold font-mono text-amber-400 mt-0.5 block">
                {weather?.pitDewatering?.activePumpingCapacityM3Hr ?? 450} m³/h
              </span>
              <span className="text-[9px] text-red-400">Req: {weather?.pitDewatering?.requiredPumpingCapacityM3Hr ?? 580} m³/h</span>
            </div>

            <div className="glass-card p-2.5 rounded-xl border border-amber-500/20 bg-amber-950/20">
              <span className="text-[10px] text-amber-300 uppercase block">Flood Risk</span>
              <span className="text-sm font-bold text-amber-400 mt-1 block">
                {weather?.floodRisk || '—'}
              </span>
              <span className="text-[9px] text-amber-300/80">Pit Haul Road Warning</span>
            </div>
          </div>

          {/* 7-Day Rainfall Forecast */}
          <div className="glass-card p-3.5 rounded-xl border border-white/10">
            <div className="flex items-center justify-between mb-2">
              <span className="text-xs font-bold text-slate-100 uppercase tracking-wider flex items-center gap-1.5">
                <CloudRain className="w-4 h-4 text-sky-400" />
                7-Day Rainfall Outlook (climatological, real obs.)
              </span>
              <SourceBadge badge="[MODELED]" />
            </div>
            <div className="h-40 w-full">
              <ReactECharts
                option={weatherForecastOption}
                style={{ height: '100%', width: '100%' }}
                opts={{ renderer: 'canvas' }}
              />
            </div>
          </div>
        </div>
      )}

      {/* CTA Button */}
      <div className="pt-2">
        <button
          onClick={onNext}
          className="w-full py-3 rounded-xl bg-sky-500 hover:bg-sky-400 text-slate-950 font-bold text-sm shadow-lg shadow-sky-500/25 flex items-center justify-center gap-2 transition-all hover:scale-[1.01] active:scale-[0.99]"
        >
          Corrective Actions &rarr;
        </button>
      </div>
    </div>
  );
};
