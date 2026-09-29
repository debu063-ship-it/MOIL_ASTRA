import React, { useEffect, useState } from 'react';
import ReactECharts from 'echarts-for-react';
import { useStore } from '@/store/useStore';
import { ProductionData, WhatIfResult } from '@/types';
import { calculateSimulationAsync, baselineSimulation } from '@/lib/simulate';
import { SourceBadge } from '@/components/ui/Badge';
import { Sliders, RotateCcw, Loader2 } from 'lucide-react';

interface Step4Props {
  production: ProductionData | null;
  mine: string;
  onNext: () => void;
}

export const Step4WhatIf: React.FC<Step4Props> = ({ production, mine, onNext }) => {
  const { whatIf, setWhatIf, resetWhatIf } = useStore();
  const [result, setResult] = useState<WhatIfResult | null>(null);
  const [running, setRunning] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const targetMT = production?.metadata.monthlyTargetMT ?? 40000;
  const baselineRatio = production?.metadata.shortfallPercent ?? 0.12;
  const baseForecastMT = Math.round(targetMT * (1 - baselineRatio));

  // Baseline result while the model call is in flight
  useEffect(() => {
    setResult(baselineSimulation(targetMT, baselineRatio));
  }, [targetMT, baselineRatio]);

  // Run the TRAINED backend model whenever sliders change (debounced)
  useEffect(() => {
    let cancelled = false;
    setRunning(true);
    setError(null);
    const t = setTimeout(() => {
      calculateSimulationAsync(whatIf, mine, production)
        .then((r) => { if (!cancelled) setResult(r); })
        .catch((e) => { if (!cancelled) setError(String(e)); })
        .finally(() => { if (!cancelled) setRunning(false); });
    }, 350);
    return () => { cancelled = true; clearTimeout(t); };
  }, [whatIf, mine, production]);

  const simulationResult: WhatIfResult = result ?? baselineSimulation(targetMT, baselineRatio);

  const chartOption = {
    backgroundColor: 'transparent',
    tooltip: {
      trigger: 'axis',
      backgroundColor: 'rgba(15, 23, 42, 0.95)',
      borderColor: 'rgba(255, 255, 255, 0.15)',
      textStyle: { color: '#f1f5f9', fontSize: 11 }
    },
    legend: {
      data: ['Target', 'Baseline Forecast', 'Simulated Output'],
      textStyle: { color: '#64748b', fontSize: 10 },
      top: 0,
      right: 0
    },
    grid: {
      top: 25,
      left: 45,
      right: 15,
      bottom: 25
    },
    xAxis: {
      type: 'category',
      data: ['M1 (Baseline)', 'M2 (Target)', 'M3 (Simulated)'],
      axisLine: { lineStyle: { color: 'rgba(15, 23, 42, 0.12)' } },
      axisLabel: { color: '#64748b', fontSize: 10 }
    },
    yAxis: {
      type: 'value',
      name: 'MT',
      min: Math.round(Math.min(baseForecastMT, simulationResult.netProductionForecastMT) * 0.85),
      axisLine: { lineStyle: { color: 'rgba(15, 23, 42, 0.12)' } },
      splitLine: { lineStyle: { color: 'rgba(15, 23, 42, 0.07)' } },
      axisLabel: { color: '#64748b', fontSize: 10, formatter: (val: number) => `${val / 1000}k` }
    },
    series: [
      {
        name: 'Target',
        type: 'line',
        data: [targetMT, targetMT, targetMT],
        lineStyle: { color: '#64748b', type: 'dotted', width: 2 },
        symbol: 'none'
      },
      {
        name: 'Baseline Forecast',
        type: 'bar',
        data: [baseForecastMT, 0, 0],
        itemStyle: { color: '#f97316', borderRadius: [4, 4, 0, 0] },
        barWidth: '32%'
      },
      {
        name: 'Simulated Output',
        type: 'bar',
        data: [0, 0, simulationResult.netProductionForecastMT],
        itemStyle: { 
          color: simulationResult.adjustedRiskColor,
          borderRadius: [4, 4, 0, 0]
        },
        barWidth: '32%'
      }
    ]
  };

  return (
    <div className="space-y-4">
      {/* Header and Reset Button */}
      <div className="flex items-center justify-between">
        <div>
          <h3 className="text-xs font-bold text-slate-100 uppercase tracking-wider flex items-center gap-1.5">
            <Sliders className="w-4 h-4 text-sky-400" />
            Operational Sensitivity Simulator
          </h3>
          <p className="text-[11px] text-slate-400">
            Trained response model ({mine} baseline) · {running ? 'running…' : 'live'}
          </p>
        </div>
        <div className="flex items-center gap-2">
          <SourceBadge badge="[MODELED]" />
          <button
            onClick={resetWhatIf}
            className="p-1 rounded text-slate-400 hover:text-sky-300 hover:bg-white/5 transition-colors"
            title="Reset Simulator Sliders"
          >
            <RotateCcw className="w-3.5 h-3.5" />
          </button>
        </div>
      </div>

      {/* Why this prediction summary card (matching screenshot 4) */}
      <div className="bg-[#0f172a]/70 p-3.5 rounded-xl border border-sky-500/30 text-xs">
        <span className="font-bold text-sky-200 block mb-1">Why this prediction:</span>
        <p className="text-slate-300 text-[11px] leading-relaxed">
          The RandomForest response model was trained on mine-month operations
          (synthetic-calibrated to real MOIL annual anchors + real rainfall). Sliders set
          equipment availability, rainfall and blast delays for the next month; the backend
          returns the predicted shortfall ratio.
        </p>
        {error && <p className="text-red-400 text-[10px] mt-1">{error}</p>}
      </div>

      {/* Mini Comparison Chart (matching screenshot 4) */}
      <div className="glass-card p-3 rounded-xl border border-white/10">
        <div className="h-36 w-full">
          <ReactECharts
            option={chartOption}
            style={{ height: '100%', width: '100%' }}
            opts={{ renderer: 'canvas' }}
          />
        </div>

        {/* Live Metrics Row */}
        <div className="grid grid-cols-3 gap-2 mt-2 pt-2 border-t border-white/5 text-center">
          <div className="bg-slate-900/60 p-2 rounded-lg border border-white/5">
            <span className="text-[10px] text-slate-400 block uppercase">Simulated Output</span>
            <span className="font-mono text-xs font-bold text-slate-100">
              {running && <Loader2 className="inline w-3 h-3 animate-spin mr-1" />}
              {simulationResult.netProductionForecastMT.toLocaleString()} MT
            </span>
          </div>
          <div className="bg-slate-900/60 p-2 rounded-lg border border-white/5">
            <span className="text-[10px] text-slate-400 block uppercase">Net Delta</span>
            <span className={`font-mono text-xs font-bold ${simulationResult.deltaMT >= 0 ? 'text-emerald-400' : 'text-red-400'}`}>
              {simulationResult.deltaMT >= 0 ? '+' : ''}{simulationResult.deltaMT.toLocaleString()} MT
            </span>
          </div>
          <div className="bg-slate-900/60 p-2 rounded-lg border border-white/5">
            <span className="text-[10px] text-slate-400 block uppercase">Adjusted Risk</span>
            <span className="font-mono text-xs font-bold" style={{ color: simulationResult.adjustedRiskColor }}>
              {simulationResult.adjustedRiskScore} / 100
            </span>
          </div>
        </div>
      </div>

      {/* Interactive Controls (matching user screenshot 4) */}
      <div className="space-y-3.5 glass-card p-4 rounded-xl border border-white/10">
        {/* Slider 1: Blast Delay */}
        <div className="space-y-1.5">
          <div className="flex items-center justify-between text-xs">
            <label htmlFor="blast-delay-slider" className="font-medium text-slate-200">
              Blast delay (days)
            </label>
            <div className="flex items-center gap-1.5">
              <input
                type="number"
                min={0}
                max={14}
                value={whatIf.blastDelay}
                onChange={(e) => setWhatIf({ blastDelay: Math.max(0, Math.min(14, Number(e.target.value))) })}
                className="w-14 px-2 py-0.5 rounded bg-slate-900 text-center font-mono text-xs text-sky-400 border border-white/10 focus:outline-none focus:border-sky-400"
              />
            </div>
          </div>
          <input
            id="blast-delay-slider"
            type="range"
            min={0}
            max={14}
            step={1}
            value={whatIf.blastDelay}
            onChange={(e) => setWhatIf({ blastDelay: Number(e.target.value) })}
            className="w-full h-1.5 bg-slate-700 rounded-lg appearance-none cursor-pointer accent-sky-400"
          />
        </div>

        {/* Slider 2: Equipment Count */}
        <div className="space-y-1.5 pt-2 border-t border-white/5">
          <div className="flex items-center justify-between text-xs">
            <label htmlFor="equipment-count-slider" className="font-medium text-slate-200">
              Equipment availability shift (±2.5%/unit)
            </label>
            <div className="flex items-center gap-1.5">
              <input
                type="number"
                min={-4}
                max={6}
                value={whatIf.equipmentCount}
                onChange={(e) => setWhatIf({ equipmentCount: Math.max(-4, Math.min(6, Number(e.target.value))) })}
                className="w-14 px-2 py-0.5 rounded bg-slate-900 text-center font-mono text-xs text-sky-400 border border-white/10 focus:outline-none focus:border-sky-400"
              />
            </div>
          </div>
          <input
            id="equipment-count-slider"
            type="range"
            min={-4}
            max={6}
            step={1}
            value={whatIf.equipmentCount}
            onChange={(e) => setWhatIf({ equipmentCount: Number(e.target.value) })}
            className="w-full h-1.5 bg-slate-700 rounded-lg appearance-none cursor-pointer accent-sky-400"
          />
        </div>

        {/* Slider 3: Rainfall Change */}
        <div className="space-y-1.5 pt-2 border-t border-white/5">
          <div className="flex items-center justify-between text-xs">
            <label htmlFor="rainfall-change-slider" className="font-medium text-slate-200">
              Rainfall change (%)
            </label>
            <div className="flex items-center gap-1.5">
              <input
                type="number"
                min={-50}
                max={100}
                value={whatIf.rainfallChange}
                onChange={(e) => setWhatIf({ rainfallChange: Math.max(-50, Math.min(100, Number(e.target.value))) })}
                className="w-14 px-2 py-0.5 rounded bg-slate-900 text-center font-mono text-xs text-sky-400 border border-white/10 focus:outline-none focus:border-sky-400"
              />
            </div>
          </div>
          <input
            id="rainfall-change-slider"
            type="range"
            min={-50}
            max={100}
            step={5}
            value={whatIf.rainfallChange}
            onChange={(e) => setWhatIf({ rainfallChange: Number(e.target.value) })}
            className="w-full h-1.5 bg-slate-700 rounded-lg appearance-none cursor-pointer accent-sky-400"
          />
        </div>
      </div>

      {/* CTA Button */}
      <div className="pt-2">
        <button
          onClick={onNext}
          className="w-full py-3 rounded-xl bg-sky-500 hover:bg-sky-400 text-slate-950 font-bold text-sm shadow-lg shadow-sky-500/25 flex items-center justify-center gap-2 transition-all hover:scale-[1.01] active:scale-[0.99]"
        >
          Export Report &rarr;
        </button>
      </div>
    </div>
  );
};
