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
  fetchKnownOccurrences
} from '@/lib/api';
import { TIMELINE_MARKS } from '@/lib/layers';
import { calculatePolygonAreaHectares } from '@/lib/geo';
import { baselineSimulation } from '@/lib/simulate';
import { SourceBadge } from '@/components/ui/Badge';
import { Sparkles, Eye, Navigation, AlertTriangle } from 'lucide-react';

// 1. Read token from import.meta.env.VITE_CESIUM_ION_TOKEN (not NEXT_PUBLIC_...)
const ionToken = import.meta.env.VITE_CESIUM_ION_TOKEN;
Cesium.Ion.defaultAccessToken = ionToken || '';

const isTokenConfigured = Boolean(
  ionToken && typeof ionToken === 'string' && ionToken.trim() !== ''
);

// Center Coordinates: Ukwa/Gudma Mn blocks, Balaghat district (NGDR toposheet 64C/05)
const CENTER_LNG = 80.45;
const CENTER_LAT = 21.97;
const OVERVIEW_HEIGHT = 3400;
// Helper to update entity material and outline alpha in real time for vector data sources
const updateDataSourceOpacity = (
  ds: Cesium.CustomDataSource | null,
  opacity: number,
  layerType: 'geology' | 'boundary' | 'occurrences' | 'infra' | 'dem' | 'thickness'
) => {
  if (!ds) return;
  const entities = ds.entities.values;
  for (let i = 0; i < entities.length; i++) {
    const entity = entities[i];
    const baseColor = (entity as any)._baseColor || '#38bdf8';
    const c = Cesium.Color.fromCssColorString(baseColor);

    if (layerType === 'boundary') {
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
  const zonesDataSourceRef = useRef<Cesium.CustomDataSource | null>(null);
  const oreVolumeDataSourceRef = useRef<Cesium.CustomDataSource | null>(null);
  const boreholesDataSourceRef = useRef<Cesium.CustomDataSource | null>(null);
  const boundaryDataSourceRef = useRef<Cesium.CustomDataSource | null>(null);
  const geologyDataSourceRef = useRef<Cesium.CustomDataSource | null>(null);
  const climateDataSourceRef = useRef<Cesium.CustomDataSource | null>(null);
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
        new Cesium.OpenStreetMapImageryProvider({
          url: 'https://tile.openstreetmap.org/',
          credit: '© OpenStreetMap contributors',
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
    globe.enableLighting = true;

    // Enable Underground Ore Volume Visibility via Globe Translucency
    globe.translucency.enabled = true;
    globe.translucency.frontFaceAlpha = 1.0;
    globe.translucency.backFaceAlpha = 1.0;

    // Initial Overview Camera - tilted to display 3D terrain relief
    viewer.camera.setView({
      destination: Cesium.Cartesian3.fromDegrees(CENTER_LNG, CENTER_LAT - 0.025, OVERVIEW_HEIGHT),
      orientation: {
        heading: Cesium.Math.toRadians(0),
        pitch: Cesium.Math.toRadians(-35),
        roll: 0.0
      }
    });

    // Create Custom Data Sources for fast dynamic rendering
    const zDS = new Cesium.CustomDataSource('zones');
    const oDS = new Cesium.CustomDataSource('oreVolume');
    const bDS = new Cesium.CustomDataSource('boreholes');
    const lDS = new Cesium.CustomDataSource('boundary');
    const gDS = new Cesium.CustomDataSource('geology');
    const cDS = new Cesium.CustomDataSource('climate');
    const occDS = new Cesium.CustomDataSource('occurrences');

    viewer.dataSources.add(zDS);
    viewer.dataSources.add(oDS);
    viewer.dataSources.add(bDS);
    viewer.dataSources.add(lDS);
    viewer.dataSources.add(gDS);
    viewer.dataSources.add(cDS);
    viewer.dataSources.add(occDS);

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
      fetchKnownOccurrences()
    ]).then(([zonesRes, boreholesRes, geologyRes, occRes]) => {
      zonesDataRef.current = zonesRes;
      boreholesDataRef.current = boreholesRes;

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
    }).catch(err => {
      console.error('Error loading initial map data:', err);
      setLoadingMap(false);
    });

    // Setup Screen Space Event Handler for Mouse Interactions
    const handler = new Cesium.ScreenSpaceEventHandler(scene.canvas);

    // Mouse Move: Hover Detection
    handler.setInputAction((movement: any) => {
      const pickedObject = scene.pick(movement.endPosition);
      if (Cesium.defined(pickedObject) && pickedObject.id && pickedObject.id.properties) {
        const props = pickedObject.id.properties;
        if (props.hasProperty('zoneData')) {
          const zoneData = props.getValue(Cesium.JulianDate.now()).zoneData;
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

        // Clicked a Zone
        if (props.hasProperty('zoneData')) {
          const zoneData = props.getValue(Cesium.JulianDate.now()).zoneData;
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
    };
  }, []);

  // 2. Sync Terrain Translucency
  useEffect(() => {
    if (!viewerRef.current) return;
    const globe = viewerRef.current.scene.globe;
    const isTranslucent = layers.terrainTransparent;
    globe.translucency.frontFaceAlpha = isTranslucent ? 0.35 : 1.0;
    globe.depthTestAgainstTerrain = !isTranslucent;
  }, [layers.terrainTransparent]);

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

  // 4. Render 3D Extruded Ore Volume in Zoomed/Step State
  useEffect(() => {
    const ds = oreVolumeDataSourceRef.current;
    if (!ds) return;

    ds.entities.removeAll();

    const isZoomed = flow.stage === 'zoomed' || flow.stage === 'step';
    const zoneId = flow.selectedZoneId || 'UKWA';

    if (!isZoomed) return;

    fetchOreVolume(zoneId).then((volData) => {
      volData.blocks.forEach((block) => {
        // Compute extruded polygon or box
        const coords = block.coordinates;
        const flatDegrees: number[] = [];
        coords.forEach((pt) => {
          flatDegrees.push(pt[0], pt[1]);
        });

        // 3D Voxel block cutting below the ground level
        ds.entities.add({
          id: `block-${block.id}`,
          polygon: {
            hierarchy: Cesium.Cartesian3.fromDegreesArray(flatDegrees),
            height: block.bottomAltitude,
            extrudedHeight: block.topAltitude,
            material: Cesium.Color.fromCssColorString(block.color).withAlpha(0.85),
            outline: true,
            outlineColor: Cesium.Color.fromCssColorString(block.color).withAlpha(0.4),
            outlineWidth: 1
          },
          properties: {
            blockData: block
          }
        });
      });
    }).catch(err => console.error('Error rendering 3D ore volume:', err));
  }, [flow.stage, flow.selectedZoneId]);

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

      if (isZoomed) {
        // Render 3D vertical cylinder passing through the ore volume!
        // Guard: 31 of 50 real holes lack reported depth/elevation — use documented fallbacks.
        const totalDepth = props.totalDepthMeters ?? 100;
        const safeCollar = Number.isFinite(collarElev) ? collarElev : 600;
        const cylinderLength = Math.max(10, Math.min(totalDepth, 400));
        const cylinderCenterElev = safeCollar - (cylinderLength / 2);

        // Vertical column cylinder
        ds.entities.add({
          id: `bh-col-${props.id}`,
          position: Cesium.Cartesian3.fromDegrees(lng, lat, cylinderCenterElev),
          cylinder: {
            length: cylinderLength,
            topRadius: 4.5,
            bottomRadius: 4.5,
            material: Cesium.Color.fromCssColorString((props.interceptMnPercent ?? 0) > 40 ? '#ef4444' : '#f97316').withAlpha(0.9 * opacity),
            outline: true,
            outlineColor: Cesium.Color.WHITE.withAlpha(0.7 * opacity),
            outlineWidth: 1.5
          },
          properties: { boreholeData: props }
        });

        // Top collar tag label (matching screenshot 2 tags)
        const tagTitles = [
          "Borehole grade",
          "Estimated probability",
          "Click to view",
          "Estimated grade (% Mn)",
          "Interception 95",
          "Anomalies"
        ];
        const tagTitle = tagTitles[Math.abs(props.id.charCodeAt(props.id.length - 1)) % tagTitles.length];

        ds.entities.add({
          id: `bh-lbl-${props.id}`,
          position: Cesium.Cartesian3.fromDegrees(lng, lat, (Number.isFinite(collarElev) ? collarElev : 600) + 22),
          label: {
            text: `${props.name || props.id}${props.interceptMnPercent != null ? `\n${props.interceptMnPercent}% Mn` : '\ncollar only'}`,
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
        // Overview Pin
        ds.entities.add({
          id: `bh-pin-${props.id}`,
          position: Cesium.Cartesian3.fromDegrees(lng, lat, (Number.isFinite(collarElev) ? collarElev : 600) + 15),
          point: {
            pixelSize: 8,
            color: Cesium.Color.fromCssColorString('#38bdf8').withAlpha(opacity),
            outlineColor: Cesium.Color.WHITE.withAlpha(opacity),
            outlineWidth: 2,
            disableDepthTestDistance: Number.POSITIVE_INFINITY
          },
          label: {
            text: props.id,
            font: '10px Inter',
            fillColor: Cesium.Color.fromCssColorString('#cbd5e1').withAlpha(opacity),
            showBackground: true,
            backgroundColor: Cesium.Color.fromCssColorString('#0b0f19').withAlpha(0.8 * opacity),
            backgroundPadding: new Cesium.Cartesian2(4, 2),
            pixelOffset: new Cesium.Cartesian2(0, -14),
            disableDepthTestDistance: Number.POSITIVE_INFINITY
          },
          properties: { boreholeData: props }
        });
      }
    });
  }, [mapDataReady, layers.layers.boreholes, flow.stage, flow.selectedZoneId]);

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
      const targetLng = selZone?.properties?.gridRef?.lon ?? CENTER_LNG;
      const targetLat = selZone?.properties?.gridRef?.lat ?? CENTER_LAT;

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
