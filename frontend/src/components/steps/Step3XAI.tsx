import React from 'react';
import ReactECharts from 'echarts-for-react';
import { ShapData } from '@/types';
import { SourceBadge } from '@/components/ui/Badge';
import { BrainCircuit, Info, Sparkles, CheckCircle2 } from 'lucide-react';

interface Step3Props {
  shap: ShapData | null;
  onNext: () => void;
}

export const Step3XAI: React.FC<Step3Props> = ({ shap, onNext }) => {
  if (!shap) {
    return <div className="text-slate-400 p-6 text-center">Loading Explainable AI model...</div>;
  }

  const { features, plainLanguageExplanation, metadata } = shap;

  // Horizontal Bar Chart Options (matching screenshot 3)
  const sortedFeatures = [...features].reverse(); // reverse so highest importance is on top
  const categories = sortedFeatures.map(f => f.name);
  const importances = sortedFeatures.map(f => f.importancePct);

  const chartOption = {
    backgroundColor: 'transparent',
    tooltip: {
      trigger: 'axis',
      axisPointer: { type: 'shadow' },
      backgroundColor: 'rgba(15, 23, 42, 0.95)',
      borderColor: 'rgba(255, 255, 255, 0.15)',
      textStyle: { color: '#f1f5f9', fontSize: 11 },
      formatter: (params: any[]) => {
        const item = params[0];
        const feat = features.find(f => f.name === item.name);
        return `<div style="font-weight: bold; margin-bottom: 2px;">${item.name}</div>
          <div style="font-size: 11px; color: #94a3b8;">Category: ${feat?.category || 'Feature'}</div>
          <div style="font-size: 12px; font-weight: bold; color: #38bdf8; margin-top: 4px;">
            Relative Weight: ${item.value}%
          </div>
          <div style="font-size: 10px; color: #a5f3fc;">SHAP Attribution: ${feat?.shapValue && feat.shapValue > 0 ? '+' : ''}${feat?.shapValue || 0}</div>`;
      }
    },
    grid: {
      top: 10,
      left: 140,
      right: 40,
      bottom: 25
    },
    xAxis: {
      type: 'value',
      max: 100,
      axisLine: { lineStyle: { color: 'rgba(15, 23, 42, 0.12)' } },
      splitLine: { lineStyle: { color: 'rgba(15, 23, 42, 0.07)' } },
      axisLabel: { color: '#64748b', fontSize: 10, formatter: '{value}%' }
    },
    yAxis: {
      type: 'category',
      data: categories,
      axisLine: { lineStyle: { color: 'rgba(15, 23, 42, 0.12)' } },
      axisLabel: { 
        color: '#334155',
        fontSize: 10.5,
        width: 130,
        overflow: 'truncate',
        interval: 0
      }
    },
    series: [
      {
        name: 'Feature Impact',
        type: 'bar',
        data: importances,
        barWidth: 12,
        itemStyle: {
          color: '#2563eb', // Rich deep blue as in screenshot 3
          borderRadius: [0, 4, 4, 0]
        },
        label: {
          show: true,
          position: 'right',
          color: '#475569',
          fontSize: 10,
          formatter: '{c}%'
        }
      }
    ]
  };

  return (
    <div className="space-y-4">
      {/* Header Info (matching screenshot 2) */}
      <div className="flex items-center justify-between">
        <div>
          <h3 className="text-sm font-bold text-slate-100 tracking-tight flex items-center gap-1.5">
            SHAP feature importance
          </h3>
          <p className="text-[11px] text-slate-400">Feature importance relative to current prediction</p>
        </div>
        <SourceBadge badge={metadata.source as any || '[MODELED]'} />
      </div>

      {/* Horizontal Bar Chart Card */}
      <div className="glass-card p-3 rounded-xl border border-white/10">
        <div className="h-64 w-full">
          <ReactECharts
            option={chartOption}
            style={{ height: '100%', width: '100%' }}
            opts={{ renderer: 'canvas' }}
          />
        </div>
        <div className="flex items-center justify-center gap-4 text-[10px] text-slate-400 pt-2 border-t border-white/5">
          <span className="flex items-center gap-1.5">
            <span className="w-2.5 h-2.5 rounded-sm bg-[#2563eb]" />
            Relative contribution
          </span>
        </div>
      </div>

      {/* Why This Prediction Plain-Language Card */}
      <div className="glass-card p-4 rounded-xl border border-sky-500/30 bg-sky-950/20">
        <div className="flex items-center gap-2 mb-2">
          <Info className="w-4 h-4 text-sky-400" />
          <h4 className="text-xs font-bold text-sky-200">Why this prediction</h4>
        </div>
        <p className="text-xs text-slate-300 leading-relaxed">
          {plainLanguageExplanation}
        </p>

        <div className="grid grid-cols-2 gap-2 mt-3 pt-3 border-t border-sky-500/20 text-[11px]">
          <div className="flex items-center gap-1.5 text-slate-300">
            <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400" />
            <span>High SWIR absorption match</span>
          </div>
          <div className="flex items-center gap-1.5 text-slate-300">
            <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400" />
            <span>Sausar Mansar formation lineament</span>
          </div>
        </div>
      </div>

      {/* CTA Button */}
      <div className="pt-2">
        <button
          onClick={onNext}
          className="w-full py-3 rounded-xl bg-sky-500 hover:bg-sky-400 text-slate-950 font-bold text-sm shadow-lg shadow-sky-500/25 flex items-center justify-center gap-2 transition-all hover:scale-[1.01] active:scale-[0.99]"
        >
          What-If Simulator &rarr;
        </button>
      </div>
    </div>
  );
};
