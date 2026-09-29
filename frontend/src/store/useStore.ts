import { create } from 'zustand';
import { 
  FlowStage, 
  StepNumber, 
  ZoneProperties, 
  BoreholeProperties, 
  ActionStatus, 
  WhatIfParameters 
} from '@/types';
import { LAYER_REGISTRY, TIMELINE_MARKS } from '@/lib/layers';

export interface LayerStateItem {
  visible: boolean;
  opacity: number;
}

export interface ClimateTooltipData {
  layerLabel: string;
  value: number | string;
  unit: string;
  date: string;
  source: string;
  x: number;
  y: number;
}

interface AppStore {
  // 1. Flow State Machine
  flow: {
    stage: FlowStage;
    step: StepNumber;
    selectedZoneId: string | null;
  };
  hoveredZone: ZoneProperties | null;
  selectedBorehole: BoreholeProperties | null;
  selectedZoneData: ZoneProperties | null;

  // 2. Layer & Map Controls
  layers: {
    layers: Record<string, LayerStateItem>;
    timeIndex: number;
    isPlaying: boolean;
    panelOpen: boolean;
    terrainTransparent: boolean;
  };

  // 3. Corrective Actions State
  actions: Record<string, ActionStatus>;

  // 4. What-If Simulator Inputs
  whatIf: WhatIfParameters;

  // 5. Tooltip & UI Modals
  activeClimateTooltip: ClimateTooltipData | null;
  dataSourcesModalOpen: boolean;

  // Camera request tracking
  cameraRequest: {
    type: 'overview' | 'zone';
    target?: { lng: number; lat: number; height: number; heading?: number; pitch?: number };
    timestamp: number;
  } | null;

  // Actions
  setStage: (stage: FlowStage) => void;
  setStep: (step: StepNumber) => void;
  selectZone: (zoneId: string, zoneData?: ZoneProperties) => void;
  setHoveredZone: (zone: ZoneProperties | null) => void;
  selectBorehole: (borehole: BoreholeProperties | null) => void;
  backToOverview: () => void;
  openAnalysisPanel: () => void;
  closeAnalysisPanel: () => void;

  // Layer Actions
  setLayerVisibility: (layerId: string, visible: boolean) => void;
  setLayerOpacity: (layerId: string, opacity: number) => void;
  resetLayers: () => void;
  setTimeIndex: (index: number) => void;
  togglePlay: () => void;
  toggleTerrainTransparency: () => void;
  setTerrainTransparency: (val: boolean) => void;

  // Action Status Actions
  setActionStatus: (actionId: string, status: ActionStatus) => void;
  resetActionStatuses: () => void;

  // What-If Actions
  setWhatIf: (partial: Partial<WhatIfParameters>) => void;
  resetWhatIf: () => void;

  // Modals & Tooltips
  setClimateTooltip: (tooltip: ClimateTooltipData | null) => void;
  setDataSourcesModalOpen: (open: boolean) => void;
}

const initialLayers: Record<string, LayerStateItem> = {};
LAYER_REGISTRY.forEach(l => {
  initialLayers[l.id] = {
    visible: l.defaultVisible,
    opacity: l.defaultOpacity
  };
});

export const useStore = create<AppStore>((set) => ({
  flow: {
    stage: 'overview',
    step: 1,
    selectedZoneId: null
  },
  hoveredZone: null,
  selectedBorehole: null,
  selectedZoneData: null,

  layers: {
    layers: initialLayers,
    timeIndex: 0,
    isPlaying: false,
    panelOpen: false,
    terrainTransparent: false
  },

  actions: {
    'act-01': 'pending',
    'act-02': 'pending',
    'act-03': 'pending',
    'act-04': 'pending'
  },

  whatIf: {
    blastDelay: 0,
    equipmentCount: 0,
    rainfallChange: 0
  },

  activeClimateTooltip: null,
  dataSourcesModalOpen: false,
  cameraRequest: null,

  setStage: (stage) => set((state) => ({ flow: { ...state.flow, stage } })),

  setStep: (step) => set((state) => ({ 
    flow: {
      ...state.flow,
      step,
      stage: state.flow.selectedZoneId ? 'step' : state.flow.stage
    },
    layers: { ...state.layers, panelOpen: true }
  })),

  selectZone: (zoneId, zoneData) => set((state) => ({
    flow: {
      stage: 'zoomed',
      step: 1,
      selectedZoneId: zoneId
    },
    selectedZoneData: zoneData || state.selectedZoneData,
    layers: {
      ...state.layers,
      terrainTransparent: true // Automatically enable underground ore visibility in close-up
    },
    cameraRequest: {
      type: 'zone',
      timestamp: Date.now()
    }
  })),

  setHoveredZone: (zone) => set({ hoveredZone: zone }),

  selectBorehole: (borehole) => set({ selectedBorehole: borehole }),

  backToOverview: () => set((state) => ({
    flow: {
      stage: 'overview',
      step: 1,
      selectedZoneId: null
    },
    selectedZoneData: null,
    selectedBorehole: null,
    layers: {
      ...state.layers,
      panelOpen: false,
      terrainTransparent: false
    },
    cameraRequest: {
      type: 'overview',
      timestamp: Date.now()
    }
  })),

  openAnalysisPanel: () => set((state) => ({
    layers: { ...state.layers, panelOpen: true },
    flow: {
      ...state.flow,
      stage: state.flow.selectedZoneId ? 'step' : state.flow.stage
    }
  })),

  closeAnalysisPanel: () => set((state) => ({
    layers: { ...state.layers, panelOpen: false },
    flow: { ...state.flow, stage: state.flow.selectedZoneId ? 'zoomed' : 'overview' }
  })),

  setLayerVisibility: (layerId, visible) => set((state) => ({
    layers: {
      ...state.layers,
      layers: {
        ...state.layers.layers,
        [layerId]: {
          ...state.layers.layers[layerId],
          visible
        }
      }
    }
  })),

  setLayerOpacity: (layerId, opacity) => set((state) => ({
    layers: {
      ...state.layers,
      layers: {
        ...state.layers.layers,
        [layerId]: {
          ...state.layers.layers[layerId],
          opacity
        }
      }
    }
  })),

  resetLayers: () => {
    const reset: Record<string, LayerStateItem> = {};
    LAYER_REGISTRY.forEach(l => {
      reset[l.id] = {
        visible: l.defaultVisible,
        opacity: l.defaultOpacity
      };
    });
    set((state) => ({
      layers: {
        ...state.layers,
        layers: reset,
        timeIndex: 0,
        isPlaying: false,
        terrainTransparent: state.flow.stage === 'zoomed' || state.flow.stage === 'step'
      }
    }));
  },

  setTimeIndex: (index) => set((state) => ({
    layers: { ...state.layers, timeIndex: Math.max(0, Math.min(TIMELINE_MARKS.length - 1, index)) }
  })),

  togglePlay: () => set((state) => ({
    layers: { ...state.layers, isPlaying: !state.layers.isPlaying }
  })),

  toggleTerrainTransparency: () => set((state) => ({
    layers: { ...state.layers, terrainTransparent: !state.layers.terrainTransparent }
  })),

  setTerrainTransparency: (val) => set((state) => ({
    layers: { ...state.layers, terrainTransparent: val }
  })),

  setActionStatus: (actionId, status) => set((state) => ({
    actions: {
      ...state.actions,
      [actionId]: status
    }
  })),

  resetActionStatuses: () => set({
    actions: {
      'act-01': 'pending',
      'act-02': 'pending',
      'act-03': 'pending',
      'act-04': 'pending'
    }
  }),

  setWhatIf: (partial) => set((state) => ({
    whatIf: { ...state.whatIf, ...partial }
  })),

  resetWhatIf: () => set({
    whatIf: {
      blastDelay: 0,
      equipmentCount: 0,
      rainfallChange: 0
    }
  }),

  setClimateTooltip: (tooltip) => set({ activeClimateTooltip: tooltip }),

  setDataSourcesModalOpen: (open) => set({ dataSourcesModalOpen: open })
}));

// dev/test hook: allows browser-console or E2E to drive the store
if (typeof window !== 'undefined') {
  (window as any).__store = useStore;
}
