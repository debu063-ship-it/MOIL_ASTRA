import React from 'react';
import { useStore } from '@/store/useStore';
import { SourceBadge } from '@/components/ui/Badge';
import { X, CloudRain, Thermometer, Leaf, Droplets } from 'lucide-react';

export const ClimateTooltip: React.FC = () => {
  const { activeClimateTooltip, setClimateTooltip } = useStore();

  if (!activeClimateTooltip) return null;

  const { layerLabel, value, unit, date, source, x, y } = activeClimateTooltip;

  const getIcon = () => {
    switch (layerLabel.toLowerCase()) {
      case 'ndvi':
        return <Leaf className="w-4 h-4 text-emerald-400" />;
      case 'rainfall':
        return <CloudRain className="w-4 h-4 text-blue-400" />;
      case 'soil_moisture':
        return <Droplets className="w-4 h-4 text-teal-400" />;
      case 'lst':
        return <Thermometer className="w-4 h-4 text-orange-400" />;
      default:
        return <Droplets className="w-4 h-4 text-sky-400" />;
    }
  };

  return (
    <div
      className="fixed z-50 glass-panel rounded-xl p-3 shadow-2xl border border-sky-400/40 text-slate-100 w-56 animate-in fade-in zoom-in-95 duration-150 pointer-events-none"
      style={{
        left: `${Math.min(window.innerWidth - 240, Math.max(20, x + 16))}px`,
        top: `${Math.min(window.innerHeight - 150, Math.max(20, y - 50))}px`
      }}
    >
      <div className="flex items-center justify-between pb-1.5 border-b border-white/10">
        <div className="flex items-center gap-1.5 font-bold text-xs text-sky-300">
          {getIcon()}
          <span>{layerLabel}</span>
        </div>
        <button
          onClick={() => setClimateTooltip(null)}
          className="p-0.5 text-slate-400 hover:text-white rounded hover:bg-white/10"
        >
          <X className="w-3.5 h-3.5" />
        </button>
      </div>

      <div className="my-2">
        <span className="text-[10px] text-slate-400 uppercase tracking-wider block">Observed Value</span>
        <div className="text-lg font-mono font-bold text-slate-100 flex items-baseline gap-1">
          <span>{value}</span>
          <span className="text-xs text-sky-400 font-normal">{unit}</span>
        </div>
      </div>

      <div className="pt-1.5 border-t border-white/5 flex items-center justify-between text-[10px] text-slate-400">
        <span className="font-mono">{date}</span>
        <SourceBadge badge={source as any} />
      </div>
    </div>
  );
};
