import React, { useEffect, useRef, useState, useCallback } from 'react';
import * as Cesium from 'cesium';
import 'cesium/Build/Cesium/Widgets/widgets.css';
import { useStore } from '@/store/useStore';
import { 
  fetchZones, 
  fetchBoreholes, 
  fetchGeology, 
  fetchOreVolume, 
  fetchClimateGrid,
  fetchKnownOccurrences,
  fetchGridScores
} from '@/lib/api';
import { TIMELINE_MARKS } from '@/lib/layers';
import { calculatePolygonAreaHectares } from '@/lib/geo';
import { baselineSimulation } from '@/lib/simulate';
import { SourceBadge } from '@/components/ui/Badge';
import { Sparkles, Eye, Navigation, AlertTriangle, Box } from 'lucide-react';

// 1. Read token from import.meta.env.VITE_CESIUM_ION_TOKEN (not NEXT_PUBLIC_...)
const ionToken = import.meta.env.VITE_CESIUM_ION_TOKEN;
Cesium.Ion.defaultAccessToken = ionToken || '';

const isTokenConfigured = Boolean(
  ionToken && typeof ionToken === 'string' && ionToken.trim() !== ''
);

// Center Coordinates: Ukwa/Gudma Mn blocks, Balaghat district (NGDR toposheet 64C/05)
const CENTER_LNG = 80.45;
const CENTER_LAT = 21.97;
const OVERVIEW_HEIGHT = 6500;
// Helper to update entity material and outline alpha in real time for vector data sources
const updateDataSourceOpacity = (
  ds: Cesium.CustomDataSource | null,
  opacity: number,
  layerType: 'geology' | 'boundary' | 'occurrences' | 'infra' | 'dem' | 'thickness' | 'voxels'
) => {
  if (!ds) return;
  const entities = ds.entities.values;
  for (let i = 0; i < entities.length; i++) {
    const entity = entities[i];
    const baseColor = (entity as any)._baseColor || '#38bdf8';
    const c = Cesium.Color.fromCssColorString(baseColor);

    if (layerType === 'voxels') {
      if (entity.polygon) {
        entity.polygon.material = new Cesium.ColorMaterialProperty(c.withAlpha(0.85 * opacity));
      }
    } else if (layerType === 'boundary') {
      if (entity.polygon) {
        entity.polygon.material = new Cesium.ColorMaterialProperty(c.withAlpha(0.12 * opacity));
        entity.polygon.outlineColor = new Cesium.ConstantProperty(c.withAlpha(opacity));
      }
    } else if (layerType === 'geology') {
      if (entity.polygon) {
        entity.polygon.material = new Cesium.ColorMaterialProperty(c.withAlpha(0.55 * opacity));
        entity.polygon.outlineColor = new Cesium.ConstantProperty(c.withAlpha(0.9 * opacity));
      }
    } else if (layerType === 'occurrences') {
      if (entity.point) {
        entity.point.color = new Cesium.ConstantProperty(c.withAlpha(opacity));
        entity.point.outlineColor = new Cesium.ConstantProperty(Cesium.Color.WHITE.withAlpha(opacity));
      }
      if (entity.label) {
        entity.label.fillColor = new Cesium.ConstantProperty(Cesium.Color.WHITE.withAlpha(opacity));
        entity.label.backgroundColor = new Cesium.ConstantProperty(Cesium.Color.fromCssColorString('#0b0f19').withAlpha(0.85 * opacity));
      }
    } else if (layerType === 'infra') {
      if (entity.polygon) {
        entity.polygon.material = new Cesium.ColorMaterialProperty(c.withAlpha(0.5 * opacity));
        entity.polygon.outlineColor = new Cesium.ConstantProperty(c.withAlpha(0.9 * opacity));
      }
      if (entity.polyline) {
        entity.polyline.material = new Cesium.ColorMaterialProperty(c.withAlpha(0.95 * opacity));
      }
    } else if (layerType === 'dem') {
      if (entity.polyline) {
        entity.polyline.material = new Cesium.ColorMaterialProperty(c.withAlpha(0.85 * opacity));
      }
    } else if (layerType === 'thickness') {
      if (entity.polygon) {
        entity.polygon.material = new Cesium.ColorMaterialProperty(c.withAlpha(0.5 * opacity));
        entity.polygon.outlineColor = new Cesium.ConstantProperty(c.withAlpha(0.85 * opacity));
      }
    }
  }
};

export const CesiumMap: React.FC = () => {
  const containerRef = useRef<HTMLDivElement>(null);
  const viewerRef = useRef<Cesium.Viewer | null>(null);

  // Warning banner state for missing or empty Cesium Ion token
  const [tokenMissing] = useState(!isTokenConfigured);

  // Store bindings
  const { 
    flow, 
    selectZone, 
    setHoveredZone, 
    hoveredZone, 
    selectBorehole, 
    layers, 
    whatIf,
    setClimateTooltip,
    cameraRequest 
  } = useStore();

  const [loadingMap, setLoadingMap] = useState(true);
  const [mapDataReady, setMapDataReady] = useState(false);
  const [tooltipPos, setTooltipPos] = useState<{ x: number; y: number } | null>(null);

  // Cache data sources
  const voxelDataSourceRef = useRef<Cesium.CustomDataSource | null>(null);
  const gridScoresRef = useRef<any>(null);
  const zonesDataSourceRef = useRef<Cesium.CustomDataSource | null>(null);
  const oreVolumeDataSourceRef = useRef<Cesium.CustomDataSource | null>(null);
  const boreholesDataSourceRef = useRef<Cesium.CustomDataSource | null>(null);
  const boundaryDataSourceRef = useRef<Cesium.CustomDataSource | null>(null);
  const geologyDataSourceRef = useRef<Cesium.CustomDataSource | null>(null);
  const climateDataSourceRef = useRef<Cesium.CustomDataSource | null>(null);
  const undergroundFlyDoneRef = useRef(false);
  const occurrencesDataSourceRef = useRef<Cesium.CustomDataSource | null>(null);

  // Raw data storage
  const zonesDataRef = useRef<any>(null);
  const boreholesDataRef = useRef<any>(null);

  // 1. Initialize Cesium Viewer
  useEffect(() => {
    if (!containerRef.current) return;

    const hasToken = Boolean(
      Cesium.Ion.defaultAccessToken && Cesium.Ion.defaultAccessToken.trim() !== ''
    );

    // Create viewer with clean UI (disable default widgets for pitch-ready UI)
    // Requirement 4: Uses Cesium World Terrain and satellite imagery
    const viewer = new Cesium.Viewer(containerRef.current, {
      animation: false,
      baseLayerPicker: false,
      fullscreenButton: false,
      geocoder: false,
      homeButton: false,
      infoBox: false,
      sceneModePicker: false,
      selectionIndicator: false,
      timeline: false,
      navigationHelpButton: false,
      scene3DOnly: true,
      shouldAnimate: true,
      shadows: false,
      requestRenderMode: false,
      terrain: hasToken
        ? Cesium.Terrain.fromWorldTerrain({
            requestWaterMask: true,
            requestVertexNormals: true,
          })
        : undefined,
      baseLayer: new Cesium.ImageryLayer(
        new Cesium.UrlTemplateImageryProvider({
          url: 'https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}',
          credit: 'Imagery © Esri, Maxar, Earthstar Geographics',
          maximumLevel: 18,
        })
      ),
    });

    viewerRef.current = viewer;
    (window as any).cesiumViewer = viewer;

    // Configure Scene & Atmosphere
    const scene = viewer.scene;
    const globe = scene.globe;
    if (scene.skyAtmosphere) {
      scene.skyAtmosphere.show = true;
    }
    scene.fog.enabled = true;
    scene.fog.density = 0.00015;

    // Enable 3D depth test against terrain so 3D relief is visible
    globe.depthTestAgainstTerrain = true;
    // Keep the scene fully lit regardless of real sun position (demo may run at
    // any hour — day/night shading would black out the satellite imagery).
    globe.enableLighting = false;

    // Enable Underground Ore Volume Visibility via Globe Translucency
    globe.translucency.enabled = true;
    globe.translucency.frontFaceAlpha = 1.0;
    globe.translucency.backFaceAlpha = 1.0;

    // Initial Overview Camera - tilted to display 3D terrain relief
    // Tilted hero view: camera sits south of the Ukwa cluster and looks north
    // onto the high-probability voxel field (ground center ≈ CENTER_LAT).
    viewer.camera.setView({
      destination: Cesium.Cartesian3.fromDegrees(CENTER_LNG, CENTER_LAT - 0.045, OVERVIEW_HEIGHT),
      orientation: {
        heading: Cesium.Math.toRadians(0),
        pitch: Cesium.Math.toRadians(-55),
        roll: 0.0
      }
    });

    // Create Custom Data Sources for fast dynamic rendering
    const vDS = new Cesium.CustomDataSource('voxels');
    const zDS = new Cesium.CustomDataSource('zones');
    const oDS = new Cesium.CustomDataSource('oreVolume');
    const bDS = new Cesium.CustomDataSource('boreholes');
    const lDS = new Cesium.CustomDataSource('boundary');
    const gDS = new Cesium.CustomDataSource('geology');
    const cDS = new Cesium.CustomDataSource('climate');
    const occDS = new Cesium.CustomDataSource('occurrences');

    viewer.dataSources.add(vDS);
    viewer.dataSources.add(zDS);
    viewer.dataSources.add(oDS);
    viewer.dataSources.add(bDS);
    viewer.dataSources.add(lDS);
    viewer.dataSources.add(gDS);
    viewer.dataSources.add(cDS);
    viewer.dataSources.add(occDS);

    voxelDataSourceRef.current = vDS;
    zonesDataSourceRef.current = zDS;
    oreVolumeDataSourceRef.current = oDS;
    boreholesDataSourceRef.current = bDS;
    boundaryDataSourceRef.current = lDS;
    geologyDataSourceRef.current = gDS;
    climateDataSourceRef.current = cDS;
    occurrencesDataSourceRef.current = occDS;

    // Load initial static layers
    Promise.all([
      fetchZones(),
      fetchBoreholes(),
      fetchGeology(),
      fetchKnownOccurrences(),
      fetchGridScores({ minLat: 21.55, minLon: 80.0, maxLat: 22.06, maxLon: 80.5 })
    ]).then(([zonesRes, boreholesRes, geologyRes, occRes, gridRes]) => {
      zonesDataRef.current = zonesRes;
      boreholesDataRef.current = boreholesRes;
      gridScoresRef.current = gridRes;

      // 1. Geology outlines (blue boundary rendering of the real mapped polygons)
      geologyRes.features.forEach((feat: any, bgi: number) => {
        const poly = feat.geometry.type === 'MultiPolygon'
          ? feat.geometry.coordinates[0][0] : feat.geometry.coordinates[0];
        const flatDegrees: number[] = [];
        poly.forEach((pt: number[]) => {
          flatDegrees.push(pt[0], pt[1]);
        });
        const ent = lDS.entities.add({
          id: `boundary-${bgi}`,
          polygon: {
            hierarchy: Cesium.Cartesian3.fromDegreesArray(flatDegrees),
            height: 0,
            heightReference: Cesium.HeightReference.CLAMP_TO_GROUND,
            material: Cesium.Color.fromCssColorString('#38bdf8').withAlpha(0.06),
            outline: true,
            outlineColor: Cesium.Color.fromCssColorString('#38bdf8').withAlpha(0.9),
            outlineWidth: 3
          }
        });
        (ent as any)._baseColor = '#38bdf8';
      });

      // 2. Geology (real mapped lithology polygons; colored by group)
      const GEO_COLORS: Record<string, string> = {
        'SAUSAR': '#be123c', 'TIRODI GNEISSIC COMPLEX': '#334155',
        'AMGAON GNEISSIC COMPLEX': '#b45309', 'SAKOLI': '#7c2d12',
        'NANDGAON': '#94a3b8', 'KHAIRAGARH': '#64748b'
      };
      geologyRes.features.forEach((feat: any, gi: number) => {
        const poly = feat.geometry.type === 'MultiPolygon'
          ? feat.geometry.coordinates[0][0] : feat.geometry.coordinates[0];
        const flatDegrees: number[] = [];
        poly.forEach((pt: number[]) => {
          flatDegrees.push(pt[0], pt[1]);
        });
        const group = String(feat.properties.supergroup || feat.properties.group || 'OTHER').toUpperCase();
        const color = GEO_COLORS[Object.keys(GEO_COLORS).find(k => group.includes(k)) || ''] || '#64748b';
        const props = { ...feat.properties, color, opacity: 0.45, id: feat.properties.unit || `geo-${gi}` };
        const ent = gDS.entities.add({
          id: `geology-${gi}`,
          polygon: {
            hierarchy: Cesium.Cartesian3.fromDegreesArray(flatDegrees),
            height: 0,
            heightReference: Cesium.HeightReference.CLAMP_TO_GROUND,
            material: Cesium.Color.fromCssColorString(color).withAlpha(0.35),
            outline: true,
            outlineColor: Cesium.Color.fromCssColorString(color).withAlpha(0.8),
            outlineWidth: 1.5
          },
          properties: { geologyData: props }
        });
        (ent as any)._baseColor = color;
      });

      // 3. Populate Known Manganese Occurrences (real MOIL mines as points)
      const MINE_COLORS: Record<string, string> = {
        'Underground': '#ef4444', 'Opencast': '#f97316', 'Both': '#eab308'
      };
      occRes.features.forEach((feat: any, oi: number) => {
        const lng = feat.geometry.coordinates[0] ?? feat.properties.lon;
        const lat = feat.geometry.coordinates[1] ?? feat.properties.lat;
        const color = MINE_COLORS[feat.properties.type] || '#ef4444';
        const props = {
          ...feat.properties, color,
          avgGrade: `${feat.properties.formation || 'Sausar Group'} Mn`,
          id: feat.properties.name || `mine-${oi}`
        };
        const ent = occDS.entities.add({
          id: `occurrence-${oi}`,
          position: Cesium.Cartesian3.fromDegrees(lng, lat, 620),
          point: {
            pixelSize: 10,
            color: Cesium.Color.fromCssColorString(color),
            outlineColor: Cesium.Color.WHITE,
            outlineWidth: 2,
            disableDepthTestDistance: Number.POSITIVE_INFINITY
          },
          label: {
            text: `⛏️ ${props.name}\n${props.avgGrade}`,
            font: '10px Inter',
            fillColor: Cesium.Color.WHITE,
            showBackground: true,
            backgroundColor: Cesium.Color.fromCssColorString('#0b0f19').withAlpha(0.85),
            backgroundPadding: new Cesium.Cartesian2(4, 2),
            pixelOffset: new Cesium.Cartesian2(0, -18),
            disableDepthTestDistance: Number.POSITIVE_INFINITY
          },
          properties: {
            occurrenceData: props
          }
        });
        (ent as any)._baseColor = color;
      });

      setLoadingMap(false);
      setMapDataReady(true);

      // Apply initial opacities from store
      const curLayers = useStore.getState().layers.layers;
      updateDataSourceOpacity(lDS, curLayers.geology?.opacity ?? 0.5, 'boundary');
      updateDataSourceOpacity(gDS, curLayers.geology?.opacity ?? 0.5, 'geology');
      updateDataSourceOpacity(occDS, curLayers.known_occurrences?.opacity ?? 1.0, 'occurrences');

      // Force re-render of voxel + borehole effects now that raw data is ready
      setMapDataReady(true);
    }).catch(err => {
      console.error('Error loading initial map data:', err);
      setLoadingMap(false);
    });

    // Setup Screen Space Event Handler for Mouse Interactions
    const handler = new Cesium.ScreenSpaceEventHandler(scene.canvas);

    // Resolve a grid-cell pseudo-zone to the nearest named zone (Z-xxx) so the
    // 5-step analysis panel opens with real zone data on voxel click/hover.
    const resolveZoneForCell = (cellData: any) => {
      const feats = zonesDataRef.current?.features || [];
      let best: any = null;
      let bestD = Infinity;
      feats.forEach((f: any) => {
        const ring = f.geometry.coordinates[0];
        let sx = 0, sy = 0;
        ring.forEach((p: number[]) => { sx += p[0]; sy += p[1]; });
        const cx = sx / ring.length, cy = sy / ring.length;
        const d = (cx - cellData.gridRef.lon) ** 2 + (cy - cellData.gridRef.lat) ** 2;
        if (d < bestD) { bestD = d; best = f; }
      });
      if (!best) return cellData;
      return {
        ...best.properties,
        areaHectares: calculatePolygonAreaHectares(best.geometry.coordinates),
      };
    };

    // Mouse Move: Hover Detection
    handler.setInputAction((movement: any) => {
      const pickedObject = scene.pick(movement.endPosition);
      if (Cesium.defined(pickedObject) && pickedObject.id && pickedObject.id.properties) {
        const props = pickedObject.id.properties;
        if (props.hasProperty('zoneData')) {
          const raw = props.getValue(Cesium.JulianDate.now()).zoneData;
          const zoneData = raw?.id?.startsWith('CELL-') ? resolveZoneForCell(raw) : raw;
          setHoveredZone(zoneData);
          setTooltipPos({ x: movement.endPosition.x, y: movement.endPosition.y });
          setClimateTooltip(null);
          return;
        }
        if (props.hasProperty('climateData')) {
          const cData = props.getValue(Cesium.JulianDate.now()).climateData;
          setClimateTooltip({
            layerLabel: cData.layer.toUpperCase(),
            value: cData.value,
            unit: cData.unit,
            date: cData.date,
            source: cData.source,
            x: movement.endPosition.x,
            y: movement.endPosition.y
          });
          setHoveredZone(null);
          setTooltipPos(null);
          return;
        }
      }
      setHoveredZone(null);
      setTooltipPos(null);
      setClimateTooltip(null);
    }, Cesium.ScreenSpaceEventType.MOUSE_MOVE);

    // Canvas mouseleave hides hover tooltips
    const onCanvasMouseLeave = () => {
      setHoveredZone(null);
      setTooltipPos(null);
      setClimateTooltip(null);
    };
    scene.canvas.addEventListener('mouseleave', onCanvasMouseLeave);

    // Left Click: Select Zone or Borehole
    handler.setInputAction((click: any) => {
      const pickedObject = scene.pick(click.position);
      if (Cesium.defined(pickedObject) && pickedObject.id && pickedObject.id.properties) {
        const props = pickedObject.id.properties;

        // Clicked a Zone (or a voxel cell — resolved to its nearest named zone)
        if (props.hasProperty('zoneData')) {
          const raw = props.getValue(Cesium.JulianDate.now()).zoneData;
          const zoneData = raw?.id?.startsWith('CELL-') ? resolveZoneForCell(raw) : raw;
          selectZone(zoneData.id, zoneData);
          return;
        }

        // Clicked a Borehole
        if (props.hasProperty('boreholeData')) {
          const bhData = props.getValue(Cesium.JulianDate.now()).boreholeData;
          selectBorehole(bhData);
          return;
        }
      }
    }, Cesium.ScreenSpaceEventType.LEFT_CLICK);

    return () => {
      scene.canvas.removeEventListener('mouseleave', onCanvasMouseLeave);
      handler.destroy();
      viewer.destroy();
      viewerRef.current = null;
      undergroundFlyDoneRef.current = false;
    };
  }, []);

  // 1b. 3D Voxel Prospectivity Terrain — stepped probability blocks draped on satellite imagery
  useEffect(() => {
    const ds = voxelDataSourceRef.current;
    if (!ds) return;

    ds.entities.removeAll();
    const visible = layers.layers.prospectivity?.visible ?? true;
    if (!visible || !gridScoresRef.current) return;

    const PROB_COLORS: [number, string][] = [
      [0.8, '#ef4444'], [0.6, '#f97316'], [0.4, '#eab308'], [0.0, '#3b82f6']
    ];
    const probColor = (p: number) =>
      PROB_COLORS.find(([t]) => p >= t)?.[1] ?? '#3b82f6';

    const feats = gridScoresRef.current.features || [];
    // Voxel footprint ~ half the cell spacing (~0.005° ≈ 550 m → ~270 m squares)
    const HALF = 0.0025;
    feats.forEach((feat: any, vi: number) => {
      const lon = feat.geometry.coordinates[0];
      const lat = feat.geometry.coordinates[1];
      const prob = feat.properties.prob_v3;
      const color = probColor(prob);
      // Exaggerated relief: probability drives block height (50–450 m)
      const blockH = 50 + prob * 400;

      const ent = ds.entities.add({
        id: `voxel-${vi}`,
        polygon: {
          hierarchy: Cesium.Cartesian3.fromDegreesArray([
            lon - HALF, lat - HALF,
            lon + HALF, lat - HALF,
            lon + HALF, lat + HALF,
            lon - HALF, lat + HALF
          ]),
          // Terrain-clamped extrusion: base follows World Terrain automatically
          heightReference: Cesium.HeightReference.CLAMP_TO_GROUND,
          extrudedHeight: blockH,
          material: Cesium.Color.fromCssColorString(color).withAlpha(0.85),
          outline: true,
          outlineColor: Cesium.Color.fromCssColorString(color).withAlpha(0.35),
          outlineWidth: 1
        },
        properties: {
          zoneData: {
            id: `CELL-${vi}`,
            name: `Grid cell ${feat.properties.risk_category_v3} risk`,
            probability: prob,
            riskCategory: feat.properties.risk_category_v3,
            color,
            source: 'MODELED',
            avgGrade: '—',
            estimatedReserveTons: 0,
            gridRef: { lat, lon }
          }
        }
      });
      (ent as any)._baseColor = color;
    });

    const curOpacity = useStore.getState().layers.layers.prospectivity?.opacity ?? 0.85;
    updateDataSourceOpacity(ds, curOpacity, 'voxels');
  }, [mapDataReady, layers.layers.prospectivity?.visible]);

  // 1c. Voxel opacity follows the prospectivity layer slider
  useEffect(() => {
    if (!voxelDataSourceRef.current) return;
    updateDataSourceOpacity(
      voxelDataSourceRef.current,
      layers.layers.prospectivity?.opacity ?? 0.85,
      'voxels'
    );
  }, [layers.layers.prospectivity?.opacity, mapDataReady]);

  // 2. Sync Terrain Translucency + underground X-ray mode
  useEffect(() => {
    if (!viewerRef.current) return;
    const globe = viewerRef.current.scene.globe;
    const isTranslucent = layers.terrainTransparent || layers.undergroundMode;
    // Softer X-ray: imagery stays readable behind the subsurface instead of
    // ghosting to black space (hard 0.25 alpha made the whole view go dark).
    globe.translucency.frontFaceAlpha = layers.undergroundMode ? 0.55 : (isTranslucent ? 0.35 : 1.0);
    globe.translucency.backFaceAlpha = layers.undergroundMode ? 0.65 : (isTranslucent ? 0.45 : 1.0);
    globe.depthTestAgainstTerrain = !isTranslucent;
    // In underground mode the voxel field hides so the subsurface reads clearly
    if (voxelDataSourceRef.current) {
      voxelDataSourceRef.current.show = !layers.undergroundMode;
    }
  }, [layers.terrainTransparent, layers.undergroundMode]);

  // 3. Render / Update Zones
  useEffect(() => {
    const ds = zonesDataSourceRef.current;
    if (!mapDataReady || !ds || !zonesDataRef.current) return;

    ds.entities.removeAll();
    const visible = layers.layers.prospectivity?.visible ?? true;
    const opacity = layers.layers.prospectivity?.opacity ?? 0.85;

    if (!visible) return;

    zonesDataRef.current.features.forEach((feat: any) => {
      const props = {
        ...feat.properties,
        areaHectares: calculatePolygonAreaHectares(feat.geometry.coordinates),
      };
      const isSelected = flow.selectedZoneId === props.id;
      const isOverview = flow.stage === 'overview';

      // When in zoomed/step stage, non-selected zones fade out to subtle wireframe
      let zoneAlpha = opacity;
      if (!isOverview && !isSelected) {
        zoneAlpha = 0.12;
      }

      // Color from What-If simulation if selected
      let zoneColor = props.color;
      if (isSelected && (whatIf.blastDelay !== 0 || whatIf.equipmentCount !== 0 || whatIf.rainfallChange !== 0)) {
        const sim = baselineSimulation(props.estimatedReserveTons > 0 ? 40000 : 40000, 0.12);
        zoneColor = sim.adjustedRiskColor;
      }

      const coords = feat.geometry.coordinates[0];
      const flatDegrees: number[] = [];
      coords.forEach((pt: number[]) => {
        flatDegrees.push(pt[0], pt[1]);
      });

      ds.entities.add({
        id: `zone-${props.id}`,
        polygon: {
          hierarchy: Cesium.Cartesian3.fromDegreesArray(flatDegrees),
          height: 0,
          heightReference: Cesium.HeightReference.CLAMP_TO_GROUND,
          material: Cesium.Color.fromCssColorString(zoneColor).withAlpha(zoneAlpha),
          outline: true,
          outlineColor: Cesium.Color.fromCssColorString(zoneColor).withAlpha(0.9),
          outlineWidth: isSelected ? 3 : 1.5
        },
        properties: {
          zoneData: props
        }
      });
    });
  }, [mapDataReady, layers.layers.prospectivity, flow.stage, flow.selectedZoneId, whatIf]);

  // 4. Render 3D Extruded Ore Volume — all GSI blocks in underground mode, zone blocks in zoomed mode
  useEffect(() => {
    const ds = oreVolumeDataSourceRef.current;
    if (!ds) return;

    ds.entities.removeAll();

    const isZoomed = flow.stage === 'zoomed' || flow.stage === 'step';
    const underground = layers.undergroundMode;
    if (underground) undergroundFlyDoneRef.current = true;
    if (!isZoomed && !underground) return;

    const loadZone = (zoneId: string, ghost: boolean) =>
      fetchOreVolume(zoneId).then((volData) => {
        volData.blocks.forEach((block) => {
          const coords = block.coordinates;
          const flatDegrees: number[] = [];
          coords.forEach((pt) => {
            flatDegrees.push(pt[0], pt[1]);
          });

          ds.entities.add({
            id: `block-${block.id}${ghost ? '-ghost' : ''}`,
            polygon: {
              hierarchy: Cesium.Cartesian3.fromDegreesArray(flatDegrees),
              height: block.bottomAltitude,
              extrudedHeight: block.topAltitude,
              material: Cesium.Color.fromCssColorString(block.color).withAlpha(ghost ? 0.4 : 0.85),
              outline: true,
              outlineColor: Cesium.Color.fromCssColorString(block.color).withAlpha(ghost ? 0.35 : 0.55),
              outlineWidth: 1.5
            },
            properties: {
              blockData: block
            }
          });
        });
      }).catch(err => console.error(`Error rendering 3D ore volume (${zoneId}):`, err));

    if (underground) {
      // Underground mapping: every GSI resource block for both explored deposits,
      // then auto-fit the camera to the blocks — they span ~1.8 km across two
      // clusters, so a fixed camera position leaves them off-screen (black view).
      Promise.all([loadZone('UKWA', false), loadZone('GUDMA', false)]).then(() => {
        const viewer = viewerRef.current;
        if (!viewer || viewer.isDestroyed() || !undergroundFlyDoneRef.current) return;
        undergroundFlyDoneRef.current = false;
        viewer.flyTo(ds.entities.values, {
          duration: 2.2,
          offset: new Cesium.HeadingPitchRange(
            Cesium.Math.toRadians(0),
            Cesium.Math.toRadians(-35),
            2400
          )
        });
      }).catch(() => { /* blocks already render; fly is cosmetic */ });
    } else if (isZoomed) {
      loadZone(flow.selectedZoneId || 'UKWA', false);
    }
  }, [flow.stage, flow.selectedZoneId, layers.undergroundMode]);

  // 5. Render Boreholes (Pins in Overview, Vertical Stratigraphic Columns in Close-Up)
  useEffect(() => {
    const ds = boreholesDataSourceRef.current;
    if (!mapDataReady || !ds || !boreholesDataRef.current) return;

    ds.entities.removeAll();
    const visible = layers.layers.boreholes?.visible ?? true;
    const opacity = layers.layers.boreholes?.opacity ?? 1.0;
    if (!visible) return;

    const isZoomed = flow.stage === 'zoomed' || flow.stage === 'step';
    const selectedZoneId = flow.selectedZoneId;

    boreholesDataRef.current.features.forEach((feat: any) => {
      const props = feat.properties;
      const [lng, lat, collarElev] = feat.geometry.coordinates;

      // In zoomed state, prioritize boreholes inside the selected zone
      if (isZoomed && selectedZoneId && props.zoneId !== selectedZoneId) {
        return;
      }

      const safeCollar = Number.isFinite(collarElev) ? collarElev : 600;
      const gradeColor = (g: number | null | undefined) =>
        g == null ? '#78716c' : g > 40 ? '#dc2626' : g > 30 ? '#ea580c' : g > 20 ? '#d97706' : '#a8a29e';
      const coreColor = gradeColor(props.interceptMnPercent);

      if (isZoomed || layers.undergroundMode) {
        // Stratigraphic column at REAL depth: top = collar, bottom = collar − totalDepth
        const totalDepth = props.totalDepthMeters ?? 100;
        const cylinderLength = Math.max(10, Math.min(totalDepth, 400));
        const cylinderCenterElev = safeCollar - (cylinderLength / 2);

        const colR = layers.undergroundMode ? 9 : 4.5;
        ds.entities.add({
          id: `bh-col-${props.id}`,
          position: Cesium.Cartesian3.fromDegrees(lng, lat, cylinderCenterElev),
          cylinder: {
            length: cylinderLength,
            topRadius: colR,
            bottomRadius: colR,
            material: Cesium.Color.fromCssColorString(coreColor).withAlpha(0.9 * opacity),
            outline: true,
            outlineColor: Cesium.Color.WHITE.withAlpha(0.7 * opacity),
            outlineWidth: 1.5
          },
          properties: { boreholeData: props }
        });

        ds.entities.add({
          id: `bh-lbl-${props.id}`,
          position: Cesium.Cartesian3.fromDegrees(lng, lat, safeCollar + 22),
          label: {
            text: `${props.name || props.id}${props.interceptMnPercent != null ? `\n${props.interceptMnPercent}% Mn` : props.totalDepthMeters ? `\n${Math.round(props.totalDepthMeters)} m deep` : '\ncollar only'}`,
            font: 'bold 11px Inter, monospace',
            fillColor: Cesium.Color.WHITE.withAlpha(opacity),
            showBackground: true,
            backgroundColor: Cesium.Color.fromCssColorString('#0f172a').withAlpha(0.9 * opacity),
            backgroundPadding: new Cesium.Cartesian2(8, 5),
            verticalOrigin: Cesium.VerticalOrigin.BOTTOM,
            disableDepthTestDistance: Number.POSITIVE_INFINITY
          },
          properties: { boreholeData: props }
        });
      } else {
        // Overview: grade-colored cores standing above the voxel field (reference-video look)
        const standH = 280;
        const hasLog = Array.isArray(props.logs) && props.logs.length > 0;

        ds.entities.add({
          id: `bh-col-${props.id}`,
          position: Cesium.Cartesian3.fromDegrees(lng, lat, safeCollar + standH / 2),
          cylinder: {
            length: standH,
            topRadius: 12,
            bottomRadius: 12,
            material: Cesium.Color.fromCssColorString(coreColor).withAlpha(0.95 * opacity),
            outline: true,
            outlineColor: Cesium.Color.WHITE.withAlpha(0.55 * opacity),
            outlineWidth: 1.2
          },
          properties: { boreholeData: props }
        });

        ds.entities.add({
          id: `bh-lbl-${props.id}`,
          position: Cesium.Cartesian3.fromDegrees(lng, lat, safeCollar + standH + 30),
          label: {
            text: `${props.name || props.id}${props.interceptMnPercent != null ? `\n${props.interceptMnPercent.toFixed(1)}% Mn` : hasLog ? '\ncored' : '\ncollar only'}`,
            font: 'bold 10px Inter, monospace',
            fillColor: Cesium.Color.WHITE.withAlpha(0.95 * opacity),
            showBackground: true,
            backgroundColor: Cesium.Color.fromCssColorString('#0f172a').withAlpha(0.9 * opacity),
            backgroundPadding: new Cesium.Cartesian2(7, 4),
            verticalOrigin: Cesium.VerticalOrigin.BOTTOM,
            disableDepthTestDistance: Number.POSITIVE_INFINITY
          },
          properties: { boreholeData: props }
        });
      }
    });
  }, [mapDataReady, layers.layers.boreholes, flow.stage, flow.selectedZoneId, layers.undergroundMode]);

  // 6. Render Climate Layers (Driven by TimeSlider)
  useEffect(() => {
    const ds = climateDataSourceRef.current;
    if (!ds) return;

    ds.entities.removeAll();

    const activeClimateLayerId = (['rainfall'] as const).find(
      id => layers.layers[id]?.visible
    );

    if (!activeClimateLayerId) return;

    const dateKey = TIMELINE_MARKS[layers.timeIndex]?.key || '2025-07';
    const opacity = layers.layers[activeClimateLayerId]?.opacity || 0.6;

    fetchClimateGrid(activeClimateLayerId, dateKey).then((geo) => {
      geo.features.forEach((feat: any, idx: number) => {
        const props = feat.properties;
        const coords = feat.geometry.coordinates[0];
        const flatDegrees: number[] = [];
        coords.forEach((pt: number[]) => flatDegrees.push(pt[0], pt[1]));

        ds.entities.add({
          id: `climate-${activeClimateLayerId}-${idx}`,
          polygon: {
            hierarchy: Cesium.Cartesian3.fromDegreesArray(flatDegrees),
            material: Cesium.Color.fromCssColorString(props.color).withAlpha(opacity),
            outline: true,
            outlineColor: Cesium.Color.fromCssColorString(props.color).withAlpha(opacity + 0.2),
            outlineWidth: 1,
            height: 2,
            heightReference: Cesium.HeightReference.CLAMP_TO_GROUND
          },
          properties: {
            climateData: props
          }
        });
      });
    }).catch(err => console.error('Error fetching climate grid:', err));
  }, [layers.timeIndex, layers.layers.rainfall]);

  // 7. Sync Geology, Boundary (geology outlines) and Occurrences Visibility & Opacity
  useEffect(() => {
    if (geologyDataSourceRef.current) {
      const layer = layers.layers.geology;
      geologyDataSourceRef.current.show = layer?.visible ?? false;
      updateDataSourceOpacity(geologyDataSourceRef.current, layer?.opacity ?? 0.5, 'geology');
    }
    if (boundaryDataSourceRef.current) {
      const layer = layers.layers.geology;
      boundaryDataSourceRef.current.show = layer?.visible ?? true;
      updateDataSourceOpacity(boundaryDataSourceRef.current, layer?.opacity ?? 0.9, 'boundary');
    }
    if (occurrencesDataSourceRef.current) {
      const layer = layers.layers.known_occurrences;
      occurrencesDataSourceRef.current.show = layer?.visible ?? true;
      updateDataSourceOpacity(occurrencesDataSourceRef.current, layer?.opacity ?? 1.0, 'occurrences');
    }
  }, [
    layers.layers.geology,
    layers.layers.known_occurrences
  ]);

  // 8. Handle Camera Fly Requests
  useEffect(() => {
    if (!viewerRef.current || !cameraRequest) return;
    const camera = viewerRef.current.camera;

    if (cameraRequest.type === 'zone') {
      // Zoomed 3D Close-Up View
      const zoneId = flow.selectedZoneId || 'Z-001';
      // Center on the selected zone's real grid reference when available
      const selZone = zonesDataRef.current?.features?.find(
        (f: any) => f.properties.id === zoneId);
      const liveZone = useStore.getState().selectedZoneData;
      const targetLng = selZone?.properties?.gridRef?.lon
        ?? liveZone?.gridRef?.lon ?? CENTER_LNG;
      const targetLat = selZone?.properties?.gridRef?.lat
        ?? liveZone?.gridRef?.lat ?? CENTER_LAT;

      camera.flyTo({
        destination: Cesium.Cartesian3.fromDegrees(
          targetLng + (layers.panelOpen ? 0.002 : 0),
          targetLat - 0.006,
          850
        ),
        orientation: {
          heading: Cesium.Math.toRadians(-25),
          pitch: Cesium.Math.toRadians(-32),
          roll: 0.0
        },
        duration: 2.0
      });
    } else if (cameraRequest.type === 'overview') {
      // Back to Overview
      camera.flyTo({
        destination: Cesium.Cartesian3.fromDegrees(CENTER_LNG, CENTER_LAT - 0.022, OVERVIEW_HEIGHT),
        orientation: {
          heading: Cesium.Math.toRadians(0),
          pitch: Cesium.Math.toRadians(-52),
          roll: 0.0
        },
        duration: 1.8
      });
    }
  }, [cameraRequest, layers.panelOpen]);

  return (
    <div className="relative w-full h-full overflow-hidden select-none bg-[#0b0f19]">
      {/* Cesium Canvas Container */}
      <div ref={containerRef} className="w-full h-full" />

      {/* Underground Mapping HUD badge */}
      {layers.undergroundMode && (
        <div className="fixed top-14 left-1/2 -translate-x-1/2 z-40 flex items-center gap-2 px-3.5 py-2 bg-[#0f172a]/90 backdrop-blur-md rounded-xl border border-sky-400/50 shadow-2xl pointer-events-none">
          <Box className="w-4 h-4 text-sky-400" />
          <span className="text-xs font-bold text-sky-200 tracking-wide">UNDERGROUND MAPPING</span>
          <span className="text-[10px] font-mono text-slate-400">GSI blocks · real borehole depth</span>
        </div>
      )}

      {/* Warning Banner for missing Cesium Ion Token */}
      {tokenMissing && (
        <div 
          id="cesium-token-warning"
          className="fixed top-14 left-1/2 -translate-x-1/2 z-50 flex items-center gap-2.5 px-4 py-2.5 bg-amber-950/95 border border-amber-500/80 rounded-lg shadow-2xl backdrop-blur-md text-amber-200 text-xs font-semibold tracking-wide animate-pulse pointer-events-auto"
        >
          <AlertTriangle className="w-4 h-4 text-amber-400 shrink-0" />
          <span>Cesium Ion token missing. Add VITE_CESIUM_ION_TOKEN to .env.local and restart the dev server.</span>
        </div>
      )}

      {/* Loading Overlay */}
      {loadingMap && (
        <div className="absolute inset-0 z-50 flex flex-col items-center justify-center bg-slate-950/80 backdrop-blur-md">
          <div className="w-12 h-12 rounded-xl bg-sky-500/20 border border-sky-500/40 flex items-center justify-center animate-pulse">
            <Sparkles className="w-6 h-6 text-sky-400" />
          </div>
          <span className="text-sm font-bold text-slate-100 mt-3 tracking-wide">
            Initializing 3D Geospatial Engine...
          </span>
          <span className="text-xs text-slate-400 font-mono mt-1">
            Loading Balaghat ML-04 Ore Body & Satellite Layers
          </span>
        </div>
      )}

      {/* Hover Tooltip over Zone */}
      {hoveredZone && tooltipPos && (
        <div
          className="fixed pointer-events-none z-50 glass-panel rounded-xl p-3 shadow-2xl border border-sky-400/40 text-slate-100 w-64 animate-in fade-in zoom-in-95 duration-150"
          style={{
            left: `${tooltipPos.x + 16}px`,
            top: `${tooltipPos.y - 40}px`
          }}
        >
          <div className="flex items-center justify-between pb-1.5 border-b border-white/10">
            <span className="font-mono text-xs font-bold text-sky-400">{hoveredZone.id}</span>
            <SourceBadge badge={hoveredZone.source as any} />
          </div>
          <h4 className="text-xs font-semibold text-slate-100 mt-1">{hoveredZone.name}</h4>
          
          <div className="grid grid-cols-2 gap-1.5 mt-2 text-[11px]">
            <div>
              <span className="text-slate-400 block text-[10px]">Probability</span>
              <span className="font-bold text-emerald-400 font-mono">
                {(hoveredZone.probability * 100).toFixed(0)}%
              </span>
            </div>
            <div>
              <span className="text-slate-400 block text-[10px]">Avg Grade</span>
              <span className="font-bold text-slate-200 font-mono">{hoveredZone.avgGrade}</span>
            </div>
            <div className="col-span-2">
              <span className="text-slate-400 block text-[10px]">Reserves Est.</span>
              <span className="font-bold text-sky-300 font-mono">
                {hoveredZone.estimatedReserveTons.toLocaleString()} MT
              </span>
            </div>
            <div className="col-span-2">
              <span className="text-slate-400 block text-[10px]">Mapped zone area</span>
              <span className="font-bold text-slate-200 font-mono">
                {hoveredZone.areaHectares?.toLocaleString('en-IN', { maximumFractionDigits: 1 }) ?? '—'} ha
              </span>
            </div>
          </div>

          <div className="mt-2 pt-1.5 border-t border-white/5 text-[10px] text-sky-400/90 font-medium">
            Click to inspect 3D ore volume & AI forecast &rarr;
          </div>
        </div>
      )}
    </div>
  );
};
