import React from 'react';
import { useStore } from '@/store/useStore';
import { X, Layers, Activity } from 'lucide-react';
import { SourceBadge } from '@/components/ui/Badge';

export const BoreholeModal: React.FC = () => {
  const { selectedBorehole, selectBorehole } = useStore();

  if (!selectedBorehole) return null;

  return (
    <div className="fixed top-20 left-6 z-50 w-96 glass-panel rounded-xl p-4 text-slate-100 shadow-2xl border border-sky-500/30 animate-in fade-in zoom-in-95 duration-200">
      <div className="flex items-start justify-between pb-3 border-b border-white/10">
        <div>
          <div className="flex items-center gap-2">
            <h3 className="text-sm font-bold text-sky-400 font-mono">{selectedBorehole.id}</h3>
            <SourceBadge badge={selectedBorehole.source as any} />
          </div>
          <p className="text-xs text-slate-300 font-medium mt-0.5">{selectedBorehole.name}</p>
        </div>
        <button
          onClick={() => selectBorehole(null)}
          className="text-slate-400 hover:text-white p-1 rounded-md hover:bg-white/10 transition-colors"
        >
          <X className="w-4 h-4" />
        </button>
      </div>

      {/* Overview Stats */}
      <div className="grid grid-cols-2 gap-2 my-3 text-xs">
        <div className="bg-slate-900/60 p-2 rounded-lg border border-white/5">
          <span className="text-slate-400 text-[10px] block uppercase">Collar Elevation</span>
          <span className="font-semibold text-slate-100 font-mono">+{selectedBorehole.collarElevation} m RL</span>
        </div>
        <div className="bg-slate-900/60 p-2 rounded-lg border border-white/5">
          <span className="text-slate-400 text-[10px] block uppercase">Total Depth</span>
          <span className="font-semibold text-slate-100 font-mono">{selectedBorehole.totalDepthMeters} meters</span>
        </div>
        <div className="bg-slate-900/60 p-2 rounded-lg border border-white/5 col-span-2">
          <div className="flex justify-between items-center">
            <span className="text-slate-400 text-[10px] uppercase">Best Mn Intercept</span>
            <span className="text-xs font-bold text-emerald-400 font-mono">{selectedBorehole.interceptMnPercent}% Mn</span>
          </div>
          <span className="text-[11px] text-slate-300 block mt-0.5">{selectedBorehole.interceptInterval}</span>
        </div>
      </div>

      {/* Stratigraphic Core Column Log */}
      <div className="mt-3">
        <div className="flex items-center justify-between text-[11px] font-semibold text-slate-300 mb-1.5">
          <span className="flex items-center gap-1.5">
            <Layers className="w-3.5 h-3.5 text-sky-400" />
            Lithology & Grade vs. Depth
          </span>
          <span className="text-[10px] text-slate-400">0m - {selectedBorehole.totalDepthMeters}m</span>
        </div>

        <div className="space-y-1.5 max-h-52 overflow-y-auto pr-1">
          {selectedBorehole.logs.map((log, idx) => (
            <div
              key={idx}
              className="flex items-center gap-2 p-1.5 rounded bg-slate-900/40 border border-white/5 text-[11px]"
            >
              <div
                className="w-3 h-8 rounded shrink-0"
                style={{ backgroundColor: log.color }}
                title={`${log.grade}% Mn`}
              />
              <div className="flex-1 min-w-0">
                <div className="flex items-center justify-between">
                  <span className="font-medium text-slate-200 truncate">{log.rock}</span>
                  <span className={`font-mono text-[10px] font-bold ${log.grade > 35 ? 'text-red-400' : log.grade > 20 ? 'text-amber-400' : 'text-slate-400'}`}>
                    {log.grade}% Mn
                  </span>
                </div>
                <div className="text-[10px] text-slate-400 font-mono">
                  {log.from}m — {log.to}m (Δ {log.to - log.from}m)
                </div>
              </div>
            </div>
          ))}
        </div>
      </div>

      <div className="mt-3 pt-2 border-t border-white/10 flex items-center justify-between text-[10px] text-slate-400">
        <span className="flex items-center gap-1">
          <Activity className="w-3 h-3 text-emerald-400" />
          MOIL Central Assay Laboratory
        </span>
        <span className="font-mono">JORC 2012</span>
      </div>
    </div>
  );
};
