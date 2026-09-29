import React from 'react';
import { useStore } from '@/store/useStore';
import { 
  X, 
  Layers, 
  Compass, 
  TrendingUp, 
  Sparkles, 
  ArrowRight,
  Database,
  BarChart3
} from 'lucide-react';
import { SourceBadge } from '@/components/ui/Badge';

export const ZoneDetailModal: React.FC = () => {
  const { 
    flow, 
    layers,
    selectedZoneData, 
    openAnalysisPanel,
    backToOverview 
  } = useStore();

  // Show floating zone inspector in zoomed state when right panel is not open yet
  if (flow.stage !== 'zoomed' || !selectedZoneData || layers.panelOpen) return null;

  return (
    <div className="fixed top-20 left-20 z-40 w-80 bg-[#0f172a]/95 backdrop-blur-md rounded-2xl p-4 border border-sky-500/40 shadow-2xl text-slate-100 animate-in fade-in zoom-in-95 duration-200">
      {/* Header */}
      <div className="flex items-start justify-between pb-2 border-b border-white/10">
        <div>
          <div className="flex items-center gap-2">
            <h3 className="text-sm font-bold text-sky-400 font-mono">{selectedZoneData.id}</h3>
            <SourceBadge badge={selectedZoneData.source as any} />
          </div>
          <p className="text-xs text-slate-200 font-semibold mt-0.5">{selectedZoneData.name}</p>
        </div>
        <button
          onClick={backToOverview}
          className="text-slate-400 hover:text-white p-1 rounded-lg hover:bg-white/10"
        >
          <X className="w-4 h-4" />
        </button>
      </div>

      {/* Primary Metrics Grid */}
      <div className="grid grid-cols-2 gap-2 my-3 text-xs">
        {/* Manganese Potential Score */}
        <div className="bg-slate-900/80 p-2 rounded-xl border border-white/5">
          <span className="text-[10px] text-slate-400 block uppercase">Mn Potential</span>
          <span className="font-mono text-sm font-bold text-emerald-400">
            {(selectedZoneData.probability * 100).toFixed(0)}%
          </span>
          <span className="text-[9px] text-slate-400 block">Category: {selectedZoneData.riskCategory}</span>
        </div>

        {/* Estimated Mineral Volume */}
        <div className="bg-slate-900/80 p-2 rounded-xl border border-white/5">
          <span className="text-[10px] text-slate-400 block uppercase">Est. Ore Volume</span>
          <span className="font-mono text-sm font-bold text-sky-400">
            {(selectedZoneData.estimatedReserveTons / 3.4 / 1000).toFixed(0)}k m³
          </span>
          <span className="text-[9px] text-slate-400 block">{(selectedZoneData.estimatedReserveTons / 100000).toFixed(1)} Lakh MT</span>
        </div>

        {/* Depth Range & Overburden */}
        <div className="bg-slate-900/80 p-2 rounded-xl border border-white/5">
          <span className="text-[10px] text-slate-400 block uppercase">Subsurface Depth</span>
          <span className="font-mono text-xs font-bold text-slate-200">
            {selectedZoneData.overburdenThickness} to 160m
          </span>
          <span className="text-[9px] text-slate-400 block">5 Bench Levels</span>
        </div>

        {/* Average Grade */}
        <div className="bg-slate-900/80 p-2 rounded-xl border border-white/5">
          <span className="text-[10px] text-slate-400 block uppercase">Average Grade</span>
          <span className="font-mono text-xs font-bold text-amber-400">
            {selectedZoneData.avgGrade}
          </span>
          <span className="text-[9px] text-slate-400 block">Strike: {selectedZoneData.strikeLengthMeters}m</span>
        </div>

        <div className="bg-slate-900/80 p-2 rounded-xl border border-white/5">
          <span className="text-[10px] text-slate-400 block uppercase">Mapped Area</span>
          <span className="font-mono text-xs font-bold text-slate-100">
            {selectedZoneData.areaHectares?.toLocaleString('en-IN', { maximumFractionDigits: 1 }) ?? '—'} ha
          </span>
          <span className="text-[9px] text-slate-400 block">Prospectivity footprint</span>
        </div>
      </div>

      {/* Geological Formation Details */}
      <div className="bg-slate-900/50 p-2.5 rounded-xl border border-white/5 text-[11px] space-y-1">
        <span className="font-semibold text-slate-300 block flex items-center gap-1.5">
          <Layers className="w-3.5 h-3.5 text-sky-400" />
          Geological Structure:
        </span>
        <p className="text-[10px] text-slate-400 leading-relaxed">
          {selectedZoneData.description}
        </p>
      </div>

      {/* Launch Analysis CTA */}
      <div className="mt-3 pt-2 border-t border-white/10">
        <button
          onClick={openAnalysisPanel}
          className="w-full py-2.5 rounded-xl bg-sky-500 hover:bg-sky-400 text-slate-950 font-bold text-xs shadow-lg shadow-sky-500/25 flex items-center justify-center gap-2 transition-all hover:scale-[1.02] active:scale-[0.98]"
        >
          <BarChart3 className="w-4 h-4" />
          View Full AI Analysis & What-If &rarr;
        </button>
      </div>
    </div>
  );
};
