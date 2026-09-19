// Types only — the value import lives in map-engine.ts, which loads lazily. Every
// function here takes the Map it operates on, so nothing in this file needs maplibre
// at runtime except createMap, which is handed the engine.
import type * as maplibregl from 'maplibre-gl';
import { config } from '../../assets/config.js';
import type { MapEngine } from './map-engine.js';
import type { ThemeMode } from '../../hooks/use-theme.js';

// config.storageHost comes from the backend's own FRIENDLY_STORAGE_HOST, so dev/staging
// map tiles come from the same bucket the map-generation pipeline uploaded them to —
// hardcoding cdn.civicpatch.org here would show prod's tiles in every environment.
const PMTILES_BASE = `${config.storageHost}/maps`;
export const NATIONAL_SOURCE_ID = 'national';
export const STATE_SOURCE_ID = 'state';

export type DrillLevel = 'national' | 'counties' | 'local';

export const LOCAL_STATUS = {
  FRESH: 'fresh',
  STALE: 'stale',
  GAP: 'gap',
  UNTRACKED: 'untracked',
} as const;
export type LocalStatus = typeof LOCAL_STATUS[keyof typeof LOCAL_STATUS];

function cssVar(name: string): string {
  if (typeof document === 'undefined') return '';
  return getComputedStyle(document.documentElement).getPropertyValue(name).trim();
}

interface MapColors {
  fresh: string;
  stale: string;
  gap: string;
  untracked: string;
  selected: string;
  outline: string;
}

function readMapColors(): MapColors {
  return {
    fresh:     cssVar('--status-fresh'),
    stale:     cssVar('--status-stale'),
    gap:       cssVar('--status-gap'),
    untracked: cssVar('--status-untracked'),
    selected:  cssVar('--status-selected'),
    outline:   cssVar('--border'),
  };
}

const BASEMAP_LAYER_ID = 'osm';

// OSM only publishes a light style, so dark palettes invert it (brightness min/max swapped).
const BASEMAP_PAINT: Record<ThemeMode, Record<string, number>> = {
  light: { 'raster-saturation': -1, 'raster-contrast': -0.2, 'raster-brightness-min': 0, 'raster-brightness-max': 1 },
  dark:  { 'raster-saturation': -1, 'raster-contrast': -0.3, 'raster-brightness-min': 1, 'raster-brightness-max': 0 },
};

export function getVisibleLayers(level: DrillLevel): string[] {
  if (level === 'national') return ['states'];
  if (level === 'counties') return ['states', 'counties'];
  return ['local'];
}

// Approximate bounding boxes [west, south, east, north] for all US states
export const STATE_BOUNDS: Record<string, [number, number, number, number]> = {
  al: [-88.47, 30.22, -84.89, 35.01], ak: [-179.15, 51.21, -129.99, 71.35],
  az: [-114.82, 31.33, -109.04, 37.00], ar: [-94.62, 33.00, -89.64, 36.50],
  ca: [-124.41, 32.53, -114.13, 42.01], co: [-109.06, 36.99, -102.04, 41.00],
  ct: [-73.73, 40.98, -71.79, 42.05], de: [-75.79, 38.45, -75.05, 39.84],
  fl: [-87.63, 24.52, -80.03, 31.00], ga: [-85.61, 30.36, -80.84, 35.00],
  hi: [-160.25, 18.91, -154.81, 22.24], id: [-117.24, 41.99, -111.04, 49.00],
  il: [-91.51, 36.97, -87.50, 42.51], in: [-88.10, 37.77, -84.78, 41.76],
  ia: [-96.64, 40.38, -90.14, 43.50], ks: [-102.05, 36.99, -94.59, 40.00],
  ky: [-89.57, 36.50, -81.96, 39.15], la: [-94.04, 28.93, -88.82, 33.02],
  me: [-71.08, 42.97, -66.95, 47.46], md: [-79.49, 37.91, -75.05, 39.72],
  ma: [-73.51, 41.24, -69.93, 42.89], mi: [-90.42, 41.70, -82.41, 48.31],
  mn: [-97.24, 43.50, -89.49, 49.38], ms: [-91.65, 30.17, -88.10, 35.01],
  mo: [-95.77, 35.99, -89.10, 40.61], mt: [-116.05, 44.36, -104.04, 49.00],
  ne: [-104.05, 39.99, -95.31, 43.00], nv: [-120.01, 35.00, -114.04, 42.00],
  nh: [-72.56, 42.70, -70.70, 45.31], nj: [-75.56, 38.93, -73.89, 41.36],
  nm: [-109.05, 31.33, -103.00, 37.00], ny: [-79.76, 40.50, -71.86, 45.02],
  nc: [-84.32, 33.84, -75.46, 36.59], nd: [-104.05, 45.94, -96.55, 49.00],
  oh: [-84.82, 38.40, -80.52, 41.98], ok: [-103.00, 33.62, -94.43, 37.00],
  or: [-124.57, 41.99, -116.46, 46.24], pa: [-80.52, 39.72, -74.69, 42.27],
  ri: [-71.91, 41.15, -71.13, 42.02], sc: [-83.35, 32.05, -78.54, 35.22],
  sd: [-104.06, 42.48, -96.44, 45.95], tn: [-90.31, 34.98, -81.65, 36.68],
  tx: [-106.65, 25.84, -93.51, 36.50], ut: [-114.05, 36.99, -109.04, 42.00],
  vt: [-73.44, 42.73, -71.50, 45.02], va: [-83.68, 36.54, -75.24, 39.47],
  wa: [-124.73, 45.54, -116.92, 49.00], wv: [-82.64, 37.20, -77.72, 40.64],
  wi: [-92.89, 42.49, -86.25, 47.08], wy: [-111.06, 40.99, -104.05, 45.01],
  dc: [-77.12, 38.79, -76.91, 38.99],
};

export function pmtilesUrl(state: string): string {
  return `pmtiles://${PMTILES_BASE}/${state}.pmtiles`;
}

export function stateFromOcdid(ocdid: string): string | null {
  const part = ocdid.split('/').find(p => p.startsWith('state:'));
  return part ? part.split(':')[1] : null;
}

// Run fn once the style is ready to mutate. `load` fires only once and may
// have already passed (and `styledata` can settle without re-firing once
// glyphs/sprite resolve), so a deferred map.once(...) can hang forever. `idle`
// fires after the map settles AND re-fires on later changes, so we re-check
// until the style has loaded.
export function whenStyleReady(map: maplibregl.Map, fn: () => void): void {
  if (map.isStyleLoaded()) {
    fn();
    return;
  }
  const onIdle = () => {
    if (!map.isStyleLoaded()) return;
    map.off('idle', onIdle);
    fn();
  };
  map.on('idle', onIdle);
}

export function createMap(engine: MapEngine, container: HTMLElement, mode: ThemeMode): maplibregl.Map {
  const m = new engine.Map({
    container,
    style: {
      version: 8,
      sources: {
        osm: {
          type: 'raster',
          tiles: ['https://tile.openstreetmap.org/{z}/{x}/{y}.png'],
          tileSize: 256,
          attribution: '© OpenStreetMap contributors',
        },
      },
      layers: [{ id: BASEMAP_LAYER_ID, type: 'raster', source: 'osm', paint: BASEMAP_PAINT[mode] }],
      // TODO: replace with cdn.civicpatch.org/fonts once PBFs are uploaded to R2
      glyphs: 'https://demotiles.maplibre.org/font/{fontstack}/{range}.pbf',
    },
    center: [-98.5, 39.5],
    zoom: 3,
  });
  return m;
}

export function applyMapTheme(map: maplibregl.Map, mode: ThemeMode): void {
  setPaint(map, BASEMAP_LAYER_ID, BASEMAP_PAINT[mode]);
  for (const [id, { fill, stroke }] of Object.entries(layerPaints(readMapColors()))) {
    if (map.getLayer(id)) setPaint(map, id, fill);
    if (map.getLayer(`${id}-stroke`)) setPaint(map, `${id}-stroke`, stroke);
  }
}

function setPaint(map: maplibregl.Map, layerId: string, paint: Record<string, unknown>): void {
  for (const [property, value] of Object.entries(paint)) {
    map.setPaintProperty(layerId, property, value);
  }
}

export function loadNationalSource(map: maplibregl.Map): void {
  if (map.getSource(NATIONAL_SOURCE_ID)) return;
  map.addSource(NATIONAL_SOURCE_ID, {
    type: 'vector',
    url: `pmtiles://${PMTILES_BASE}/states.pmtiles`,
    promoteId: { states: 'jurisdiction_ocdid' },
  });
}

export function loadStateSource(map: maplibregl.Map, state: string): void {
  const url = pmtilesUrl(state);
  if (map.getSource(STATE_SOURCE_ID)) {
    (map.getSource(STATE_SOURCE_ID) as any).setUrl(url);
  } else {
    map.addSource(STATE_SOURCE_ID, {
      type: 'vector',
      url,
      promoteId: {
        states: 'jurisdiction_ocdid',
        counties: 'jurisdiction_ocdid',
        local: 'jurisdiction_ocdid',
      },
    });
  }
}

// Two axes, two channels: color = freshness (covered_fresh / covered), so all-stale reads
// amber and all-fresh reads green; opacity = coverage (covered / total), so faint = little
// data and bold = mostly covered. No coverage at all → grey (gap).
function gradientPaint(colors: MapColors) {
  return {
    'fill-color': [
      'case',
      ['==', ['coalesce', ['feature-state', 'coverage'], 0], 0], colors.gap,
      [
        'interpolate', ['linear'],
        ['coalesce', ['feature-state', 'freshness'], 0],
        0, colors.stale,
        1, colors.fresh,
      ],
    ] as any,
    'fill-opacity': [
      'interpolate', ['linear'],
      ['coalesce', ['feature-state', 'coverage'], 0],
      0, 0.15,
      1, 0.5,
    ] as any,
  };
}

function localPaint(colors: MapColors) {
  return {
    'fill-color': [
      'match', ['feature-state', 'status'],
      LOCAL_STATUS.FRESH, colors.fresh,
      LOCAL_STATUS.STALE, colors.stale,
      LOCAL_STATUS.GAP,   colors.gap,
      colors.untracked,
    ] as any,
    'fill-opacity': 0.35,
  };
}

function localStrokePaint(colors: MapColors) {
  return {
    'line-color': [
      'case',
      ['boolean', ['feature-state', 'selected'], false], colors.selected,
      colors.outline,
    ] as any,
    'line-width': [
      'case',
      ['boolean', ['feature-state', 'selected'], false], 2.5,
      0.8,
    ] as any,
  };
}

function defaultStrokePaint(colors: MapColors) {
  return { 'line-color': colors.outline, 'line-width': 0.8 };
}

function layerPaints(colors: MapColors) {
  return {
    states:   { fill: gradientPaint(colors), stroke: defaultStrokePaint(colors) },
    counties: { fill: gradientPaint(colors), stroke: defaultStrokePaint(colors) },
    local:    { fill: localPaint(colors),    stroke: localStrokePaint(colors) },
  };
}

export function addAllLayers(map: maplibregl.Map): void {
  const paints = layerPaints(readMapColors());
  const layers = [
    { id: 'states',   source: NATIONAL_SOURCE_ID, sourceLayer: 'states',   paint: paints.states.fill,   strokePaint: paints.states.stroke },
    { id: 'counties', source: STATE_SOURCE_ID,    sourceLayer: 'counties', paint: paints.counties.fill, strokePaint: paints.counties.stroke },
    { id: 'local',    source: STATE_SOURCE_ID,    sourceLayer: 'local',    paint: paints.local.fill,    strokePaint: paints.local.stroke },
  ];

  for (const { id, source, sourceLayer, paint, strokePaint } of layers) {
    if (!map.getSource(source)) continue;
    if (!map.getLayer(id)) {
      map.addLayer({
        id,
        type: 'fill',
        source,
        'source-layer': sourceLayer,
        layout: { visibility: 'none' },
        paint,
      });
    }
    if (!map.getLayer(`${id}-stroke`)) {
      map.addLayer({
        id: `${id}-stroke`,
        type: 'line',
        source,
        'source-layer': sourceLayer,
        layout: { visibility: 'none' },
        paint: strokePaint,
      });
    }
  }
}

export function applyLevelVisibility(map: maplibregl.Map, level: DrillLevel): void {
  const visible = new Set(getVisibleLayers(level));
  for (const id of ['states', 'counties', 'local']) {
    const v = visible.has(id) ? 'visible' : 'none';
    if (map.getLayer(id)) map.setLayoutProperty(id, 'visibility', v);
    if (map.getLayer(`${id}-stroke`)) map.setLayoutProperty(`${id}-stroke`, 'visibility', v);
  }
}

export function applyLocalStatus(
  map: maplibregl.Map,
  localStatus: Record<string, string>,
): void {
  for (const [ocdid, status] of Object.entries(localStatus)) {
    map.setFeatureState(
      { source: STATE_SOURCE_ID, sourceLayer: 'local', id: ocdid },
      { status },
    );
  }
}

export interface CoverageEntry {
  ocdid?: string;
  total: number;
  covered: number;
  covered_fresh: number;
}

export interface CoverageSummary {
  [state: string]: {
    state: CoverageEntry | null;
    counties: Record<string, CoverageEntry>;
  };
}

export function applyCountyCoverage(
  map: maplibregl.Map,
  counties: Record<string, CoverageEntry>,
): void {
  for (const [ocdid, { total, covered, covered_fresh }] of Object.entries(counties)) {
    map.setFeatureState(
      { source: STATE_SOURCE_ID, sourceLayer: 'counties', id: ocdid },
      {
        coverage: total > 0 ? covered / total : 0,
        freshness: covered > 0 ? covered_fresh / covered : 0,
      },
    );
  }
}

export function applyStateCoverage(
  map: maplibregl.Map,
  coverageSummary: CoverageSummary,
): void {
  for (const summary of Object.values(coverageSummary)) {
    if (!summary.state?.ocdid) {
      continue;
    }
    const { ocdid, total, covered, covered_fresh } = summary.state;
    map.setFeatureState(
      { source: NATIONAL_SOURCE_ID, sourceLayer: 'states', id: ocdid },
      {
        coverage: total > 0 ? covered / total : 0,
        freshness: covered > 0 ? covered_fresh / covered : 0,
      },
    );
  }
}

export function featureBounds(geometry: GeoJSON.Geometry): maplibregl.LngLatBoundsLike {
  const coords: number[][] = [];
  const collect = (c: unknown): void => {
    if (typeof (c as number[])[0] === 'number') {
      coords.push(c as number[]);
    } else {
      (c as unknown[]).forEach(collect);
    }
  };
  collect((geometry as GeoJSON.Polygon | GeoJSON.MultiPolygon).coordinates);
  const lngs = coords.map(c => c[0]);
  const lats = coords.map(c => c[1]);
  return [
    [Math.min(...lngs), Math.min(...lats)],
    [Math.max(...lngs), Math.max(...lats)],
  ];
}
