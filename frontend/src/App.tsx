import React from 'react';
import { CesiumMap } from '@/components/map/CesiumMap';
import { TopHeader } from '@/components/map/TopHeader';
import { LeftToolbar } from '@/components/map/LeftToolbar';
import { LayersPanel } from '@/components/layers/LayersPanel';
import { Legend } from '@/components/map/Legend';
import { TimeSlider } from '@/components/map/TimeSlider';
import { ZoneDetailModal } from '@/components/map/ZoneDetailModal';
import { BoreholeModal } from '@/components/map/BoreholeModal';
import { ClimateTooltip } from '@/components/map/ClimateTooltip';
import { DataSourcesModal } from '@/components/map/DataSourcesModal';
import { AnalysisPanel } from '@/components/panel/AnalysisPanel';

export const App: React.FC = () => {
  return (
    <main className="relative w-screen h-screen overflow-hidden bg-[#0b0f19]">
      {/* 1. Full-Screen 3D Cesium Map Canvas */}
      <CesiumMap />

      {/* 2. Top Navigation Bar & Floating Title Chip */}
      <TopHeader />

      {/* 3. Left Side Icon Toolbar & Zoom Controls */}
      <LeftToolbar />

      {/* 4. Top-Right Floating Data Sources & Layers Cards */}
      <LayersPanel />

      {/* 5. Bottom-Left Two-Box Legend (Percent Sources & Monthly Grade) */}
      <Legend />

      {/* 6. Bottom-Center Monthly Time Slider with Player Controls */}
      <TimeSlider />

      {/* 7. Floating Zone Detail Inspector Card (Upon Zone Click) */}
      <ZoneDetailModal />

      {/* 8. Stratigraphic Borehole Core Log Modal */}
      <BoreholeModal />

      {/* 9. Climate Layer Click Tooltip */}
      <ClimateTooltip />

      {/* 10. Data Sources Provenance Catalog Modal */}
      <DataSourcesModal />

      {/* 11. Right Slide-In Analysis & What-If Panel */}
      <AnalysisPanel />
    </main>
  );
};

export default App;
