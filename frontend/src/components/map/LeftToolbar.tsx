import React from 'react';
import { useStore } from '@/store/useStore';
import { 
  Plus, 
  Minus, 
  Search, 
  Layers as LayersIcon, 
  Compass, 
  RotateCw,
  Globe
} from 'lucide-react';

export const LeftToolbar: React.FC = () => {
  const { backToOverview, layers, setLayerVisibility } = useStore();

  const handleZoomIn = () => {
    const viewer = (window as any).cesiumViewer;
    if (viewer) {
      viewer.camera.zoomIn(viewer.camera.positionCartographic.height * 0.3);
    }
  };

  const handleZoomOut = () => {
    const viewer = (window as any).cesiumViewer;
    if (viewer) {
      viewer.camera.zoomOut(viewer.camera.positionCartographic.height * 0.3);
    }
  };

  const handleResetNorth = () => {
    const viewer = (window as any).cesiumViewer;
    if (viewer) {
      viewer.camera.setView({
        orientation: {
          heading: 0,
          pitch: viewer.camera.pitch,
          roll: 0
        }
      });
    }
  };

  return (
    <>
      {/* 1. Upper Left Icon Toolbar (matching screenshots 1 & 2) */}
      <aside className="fixed top-28 left-5 z-40 flex flex-col gap-2 pointer-events-auto">
        <div className="bg-[#0f172a]/90 backdrop-blur-md rounded-xl p-1 border border-white/10 shadow-2xl flex flex-col gap-1">
          <button
            onClick={handleZoomIn}
            title="Zoom In"
            className="w-8 h-8 rounded-lg flex items-center justify-center text-slate-300 hover:text-white hover:bg-white/10 transition-colors"
          >
            <Plus className="w-4 h-4" />
          </button>

          <button
            onClick={() => {}}
            title="Search Exploration Target"
            className="w-8 h-8 rounded-lg flex items-center justify-center text-slate-300 hover:text-white hover:bg-white/10 transition-colors"
          >
            <Search className="w-4 h-4" />
          </button>

          <button
            onClick={() => {
              // Toggle prospectivity visibility
              setLayerVisibility('prospectivity', !layers.layers.prospectivity?.visible);
            }}
            title="Toggle Mineral Prospectivity Layer"
            className="w-8 h-8 rounded-lg flex items-center justify-center text-slate-300 hover:text-white hover:bg-white/10 transition-colors"
          >
            <LayersIcon className="w-4 h-4" />
          </button>

          <button
            onClick={handleResetNorth}
            title="Reset North & Alignment"
            className="w-8 h-8 rounded-lg flex items-center justify-center text-slate-300 hover:text-white hover:bg-white/10 transition-colors"
          >
            <Compass className="w-4 h-4" />
          </button>
        </div>
      </aside>

      {/* 2. Lower Left Zoom (+ / -) Control Buttons (matching screenshot bottom left) */}
      <div className="fixed bottom-48 left-5 z-40 flex flex-col gap-1 pointer-events-auto">
        <div className="bg-[#0f172a]/90 backdrop-blur-md rounded-lg p-1 border border-white/10 shadow-xl flex flex-col gap-1">
          <button
            onClick={handleZoomIn}
            title="Zoom In"
            className="w-7 h-7 rounded flex items-center justify-center text-slate-300 hover:text-white hover:bg-white/10 transition-colors"
          >
            <Plus className="w-3.5 h-3.5" />
          </button>
          <div className="h-[1px] bg-white/10 w-full" />
          <button
            onClick={handleZoomOut}
            title="Zoom Out"
            className="w-7 h-7 rounded flex items-center justify-center text-slate-300 hover:text-white hover:bg-white/10 transition-colors"
          >
            <Minus className="w-3.5 h-3.5" />
          </button>
        </div>
      </div>
    </>
  );
};
