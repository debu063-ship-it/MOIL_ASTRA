import React from 'react';

export const Legend: React.FC = () => {
  return (
    <div className="fixed bottom-6 left-5 z-40 flex flex-col gap-2 pointer-events-auto">
      {/* 1. Categorical Probability Scale Card (matching screenshot) */}
      <div className="bg-[#0f172a]/90 backdrop-blur-md rounded-xl p-2.5 w-44 border border-white/10 shadow-2xl text-slate-200">
        <span className="text-[10px] text-slate-400 font-semibold block mb-1.5 uppercase tracking-wide">
          Prospectivity probability
        </span>

        <div className="space-y-1 text-[11px]">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <span className="w-2.5 h-2.5 rounded-sm bg-[#ef4444]" />
              <span className="text-slate-200">Very high</span>
            </div>
            <span className="font-mono text-slate-300">&gt;80%</span>
          </div>

          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <span className="w-2.5 h-2.5 rounded-sm bg-[#f97316]" />
              <span className="text-slate-200">High</span>
            </div>
            <span className="font-mono text-slate-300">60–80%</span>
          </div>

          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <span className="w-2.5 h-2.5 rounded-sm bg-[#eab308]" />
              <span className="text-slate-200">Medium</span>
            </div>
            <span className="font-mono text-slate-300">40–60%</span>
          </div>

          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <span className="w-2.5 h-2.5 rounded-sm bg-[#3b82f6]" />
              <span className="text-slate-200">Low</span>
            </div>
            <span className="font-mono text-slate-300">&lt;40%</span>
          </div>
        </div>
      </div>

      {/* 2. Monthly Grade Continuous Color Ramp (matching screenshot) */}
      <div className="bg-[#0f172a]/90 backdrop-blur-md rounded-xl p-2.5 w-44 border border-white/10 shadow-2xl text-slate-200">
        <span className="text-[10px] text-slate-400 font-semibold block mb-1 uppercase tracking-wide">
          Manganese ore grade · % Mn
        </span>

        {/* Gradient Bar */}
        <div 
          className="h-2 w-full rounded-sm"
          style={{
            background: 'linear-gradient(to right, #3b82f6, #06b6d4, #22c55e, #eab308, #f97316, #ef4444)'
          }}
        />

        <div className="flex justify-between items-center text-[9px] font-mono text-slate-400 mt-1">
          <span>18%</span>
          <span>28%</span>
          <span>36%</span>
          <span>45%+</span>
        </div>
      </div>
    </div>
  );
};
