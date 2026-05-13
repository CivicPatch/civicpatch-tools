import maplibregl from 'maplibre-gl';
import 'maplibre-gl/dist/maplibre-gl.css';
import { Protocol } from 'pmtiles';

const protocol = new Protocol();
maplibregl.addProtocol('pmtiles', protocol.tile);

export const PMTILES_BASE = 'https://cdn.civicpatch.org/maps';
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

// Read once at module load; theme toggles mid-session won't update paint expressions
// since they're baked when the layer is added. A reload re-reads the values.
const STATUS_COLORS = {
  fresh:     cssVar('--civ-status-fresh'),
  stale:     cssVar('--civ-status-stale'),
  gap:       cssVar('--civ-status-gap'),
  untracked: cssVar('--civ-status-untracked'),
  selected:  cssVar('--civ-status-selected'),
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

export function createMap(container: HTMLElement): maplibregl.Map {
  return new maplibregl.Map({
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
      layers: [{ id: 'osm', type: 'raster', source: 'osm' }],
      // TODO: replace with cdn.civicpatch.org/fonts once PBFs are uploaded to R2
      glyphs: 'https://demotiles.maplibre.org/font/{fontstack}/{range}.pbf',
    },
    center: [-98.5, 39.5],
    zoom: 3.5,
  });
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

const GRADIENT_PAINT = {
  'fill-color': [
    'interpolate', ['linear'],
    ['coalesce', ['feature-state', 'coverage'], 0],
    0,   STATUS_COLORS.gap,
    0.5, STATUS_COLORS.stale,
    1,   STATUS_COLORS.fresh,
  ] as any,
  'fill-opacity': 0.35,
};

const LOCAL_PAINT = {
  'fill-color': [
    'match', ['feature-state', 'status'],
    LOCAL_STATUS.FRESH, STATUS_COLORS.fresh,
    LOCAL_STATUS.STALE, STATUS_COLORS.stale,
    LOCAL_STATUS.GAP,   STATUS_COLORS.gap,
    STATUS_COLORS.untracked,
  ] as any,
  'fill-opacity': 0.35,
};

const LOCAL_STROKE_PAINT = {
  'line-color': [
    'case',
    ['boolean', ['feature-state', 'selected'], false], STATUS_COLORS.selected,
    '#6b7280',
  ] as any,
  'line-width': [
    'case',
    ['boolean', ['feature-state', 'selected'], false], 2.5,
    0.8,
  ] as any,
};

const DEFAULT_STROKE_PAINT = { 'line-color': '#6b7280', 'line-width': 0.8 };

export function addAllLayers(map: maplibregl.Map): void {
  const layers = [
    { id: 'states',   source: NATIONAL_SOURCE_ID, sourceLayer: 'states',   paint: GRADIENT_PAINT, strokePaint: DEFAULT_STROKE_PAINT },
    { id: 'counties', source: STATE_SOURCE_ID,    sourceLayer: 'counties', paint: GRADIENT_PAINT, strokePaint: DEFAULT_STROKE_PAINT },
    { id: 'local',    source: STATE_SOURCE_ID,    sourceLayer: 'local',    paint: LOCAL_PAINT,    strokePaint: LOCAL_STROKE_PAINT },
  ];

  for (const { id, source, sourceLayer, paint, strokePaint } of layers) {
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
  scraped: number;
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
  for (const [ocdid, { total, scraped }] of Object.entries(counties)) {
    map.setFeatureState(
      { source: STATE_SOURCE_ID, sourceLayer: 'counties', id: ocdid },
      { coverage: total > 0 ? scraped / total : 0 },
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
    const { ocdid, total, scraped } = summary.state;
    const coverage = total > 0 ? scraped / total : 0;
    map.setFeatureState(
      { source: NATIONAL_SOURCE_ID, sourceLayer: 'states', id: ocdid },
      { coverage },
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
