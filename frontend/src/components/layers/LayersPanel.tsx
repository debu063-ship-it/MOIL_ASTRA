import React, { useEffect, useState } from 'react';
import { useStore } from '@/store/useStore';
import { LAYER_REGISTRY } from '@/lib/layers';
import { Switch } from '@/components/ui/Switch';
import { ChevronDown, ChevronUp, Database, Layers as LayersIcon } from 'lucide-react';

export const LayersPanel: React.FC = () => {
  const [layersCollapsed, setLayersCollapsed] = useState(false);
  const { 
    layers, 
    setLayerVisibility, 
    setLayerOpacity,
    setDataSourcesModalOpen,
    flow
  } = useStore();

  const isZoomed = flow.stage === 'zoomed' || flow.stage === 'step';
  const activeLayerCount = Object.values(layers.layers).filter(layer => layer.visible).length;

  useEffect(() => {
    if (layers.panelOpen) setLayersCollapsed(true);
  }, [layers.panelOpen]);

  const panelPosition = {
    right: layers.panelOpen ? 'calc(min(30vw, 430px) + 1rem)' : '1rem'
  };

  if (layers.panelOpen && layersCollapsed) {
    return (
      <div className="fixed top-[60px] z-40 pointer-events-auto" style={panelPosition}>
        <button
          onClick={() => setLayersCollapsed(false)}
          className="flex items-center gap-2 px-3 py-2 rounded-xl bg-[#0f172a]/95 text-slate-200 border border-white/10 shadow-xl text-xs font-semibold hover:border-sky-400/50 transition-colors"
          aria-label={`Show map layers, ${activeLayerCount} active`}
        >
          <LayersIcon className="w-3.5 h-3.5 text-sky-400" />
          Map layers
          <span className="font-mono text-sky-300">{activeLayerCount}</span>
        </button>
      </div>
    );
  }

  return (
    <div 
      className="fixed top-[60px] z-40 flex flex-col gap-2.5 transition-all duration-300 pointer-events-auto w-72 max-w-[90vw]"
      style={panelPosition}
    >
      {/* 1. Data Sources Summary Card (Matching Screenshot 1 top-right) */}
      <div 
        onClick={() => setDataSourcesModalOpen(true)}
        className="bg-[#0f172a]/90 backdrop-blur-md rounded-xl p-3 border border-white/10 shadow-2xl cursor-pointer hover:border-sky-400/40 transition-colors"
      >
        <div className="flex items-center justify-between text-xs font-semibold text-slate-200 mb-2">
          <span>Data Sources</span>
          <Database className="w-3.5 h-3.5 text-sky-400" />
        </div>

        <div className="space-y-1.5 text-[11px]">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <span className="w-2.5 h-2.5 rounded-full bg-emerald-400 shadow-sm shadow-emerald-400/50" />
              <span className="text-slate-300">Prospectivity</span>
            </div>
            <span className="px-1.5 py-0.2 rounded text-[9px] font-mono font-semibold bg-emerald-500/20 text-emerald-300 border border-emerald-500/30">
              [MODELED]
            </span>
          </div>

          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <span className="w-2.5 h-2.5 rounded-full bg-blue-400 shadow-sm shadow-blue-400/50" />
              <span className="text-slate-300">Minerals</span>
            </div>
            <span className="px-1.5 py-0.2 rounded text-[9px] font-mono font-semibold bg-blue-500/20 text-blue-300 border border-blue-500/30">
              [SYNTHETIC]
            </span>
          </div>
        </div>
      </div>

      {/* 2. Collapsible Layers Card (Matching Screenshot 1 top-right) */}
      <div className="bg-[#0f172a]/90 backdrop-blur-md rounded-xl border border-white/10 shadow-2xl overflow-hidden">
        {/* Accordion Header */}
        <button
          onClick={() => setLayersCollapsed(!layersCollapsed)}
          className="w-full px-3 py-2.5 flex items-center justify-between text-xs font-semibold text-slate-200 hover:bg-white/5 transition-colors border-b border-white/5"
        >
          <div className="flex items-center gap-1.5">
            {layersCollapsed ? <ChevronDown className="w-3.5 h-3.5 text-slate-400" /> : <ChevronUp className="w-3.5 h-3.5 text-slate-400" />}
            <span>Layers</span>
          </div>
          <span className="text-[10px] font-mono text-slate-400">
            {Object.values(layers.layers).filter(l => l.visible).length} Active
          </span>
        </button>

        {/* Layer Rows */}
        {!layersCollapsed && (
          <div className="p-2 space-y-2 max-h-[50vh] overflow-y-auto">
            {LAYER_REGISTRY.map((layer) => {
              const layerState = layers.layers[layer.id] || { visible: false, opacity: layer.defaultOpacity ?? 0.8 };
              const isSelected = layerState.visible;
              const opacityPercent = Math.round((layerState.opacity !== undefined ? layerState.opacity : (layer.defaultOpacity ?? 0.8)) * 100);

              return (
                <div 
                  key={layer.id}
                  className="flex flex-col gap-1.5 px-2 py-1.5 rounded-lg hover:bg-white/5 transition-colors border border-transparent hover:border-white/5"
                >
                  <div className="flex items-center justify-between gap-1.5">
                    <div className="flex items-center gap-2 min-w-0 pr-1">
                      {/* Radio Bullet Indicator */}
                      <span 
                        className={`w-2 h-2 rounded-full shrink-0 ${
                          isSelected ? 'bg-sky-400 ring-2 ring-sky-400/30' : 'bg-slate-600'
                        }`} 
                      />
                      <span className="text-[11px] font-medium text-slate-300 truncate">
                        {layer.label}
                      </span>
                      <span className={`px-1 py-0.2 rounded text-[8px] font-mono font-semibold shrink-0 ${
                        layer.badge === '[REAL]'
                          ? 'bg-blue-500/20 text-blue-300'
                          : layer.badge === '[MODELED]'
                          ? 'bg-emerald-500/20 text-emerald-300'
                          : 'bg-purple-500/20 text-purple-300'
                      }`}>
                        {layer.badge}
                      </span>
                    </div>

                    {/* Toggle Switch */}
                    <Switch
                      checked={layerState.visible}
                      onCheckedChange={(val) => setLayerVisibility(layer.id, val)}
                      id={`layer-toggle-${layer.id}`}
                    />
                  </div>

                  {/* Opacity Slider (0-100%) */}
                  <div className="flex items-center gap-2 pl-4 pr-1">
                    <input
                      type="range"
                      min={0}
                      max={100}
                      value={opacityPercent}
                      onChange={(e) => setLayerOpacity(layer.id, Number(e.target.value) / 100)}
                      className="flex-1 h-1 bg-slate-700 rounded-lg appearance-none cursor-pointer accent-sky-400"
                      id={`layer-opacity-${layer.id}`}
                      title={`${layer.label} Opacity: ${opacityPercent}%`}
                    />
                    <span className="text-[9px] text-slate-400 font-mono w-7 text-right">
                      {opacityPercent}%
                    </span>
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
};
