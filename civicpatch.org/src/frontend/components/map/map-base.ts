import maplibregl from 'maplibre-gl';
import 'maplibre-gl/dist/maplibre-gl.css';
import { Protocol } from 'pmtiles';

// Register PMTiles protocol once, globally
const protocol = new Protocol();
maplibregl.addProtocol('pmtiles', protocol.tile);

export const PMTILES_BASE = 'cdn.civicpatch.org/maps';
export const SOURCE_ID = 'jurisdictions';

export type DrillLevel = 'national' | 'counties' | 'local';

export function getVisibleLayers(level: DrillLevel): string[] {
  if (level === 'national') return ['states'];
  if (level === 'counties') return ['states', 'counties'];
  return ['local'];
}


export interface LayerConfig {
  id: string;
  sourceLayer: string;
  scrapedColor: string;
  unscrapedColor: string;
  selectedColor: string;
  fillOpacity: number;
  strokeColor: string;
  strokeWidth: number;
  clickable: boolean;
}

export const DEFAULT_LAYERS: LayerConfig[] = [
  {
    id: 'jurisdictions',
    sourceLayer: 'jurisdictions',
    scrapedColor: '#10b981',
    unscrapedColor: '#ef4444',
    selectedColor: '#6366f1',
    fillOpacity: 0.3,
    strokeColor: '#6b7280',
    strokeWidth: 0.8,
    clickable: true,
  },
];

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
      glyphs: 'https://demotiles.maplibre.org/font/{fontstack}/{range}.pbf',
    },
    center: [-98.5, 39.5],
    zoom: 3.5,
  });
}

export function loadStateSource(map: maplibregl.Map, state: string): void {
  const url = pmtilesUrl(state);
  if (map.getSource(SOURCE_ID)) {
    (map.getSource(SOURCE_ID) as any).setUrl(url);
  } else {
    map.addSource(SOURCE_ID, {
      type: 'vector',
      url,
      promoteId: 'jurisdiction_ocdid',
    });
  }
}

export function addJurisdictionLayers(map: maplibregl.Map, layers: LayerConfig[]): void {
  for (const layer of layers) {
    if (!map.getLayer(layer.id)) {
      map.addLayer({
        id: layer.id,
        type: 'fill',
        source: SOURCE_ID,
        'source-layer': layer.sourceLayer,
        paint: {
          'fill-color': [
            'case',
            ['boolean', ['feature-state', 'selected'], false], layer.selectedColor,
            ['==', ['feature-state', 'scraped'], false], layer.unscrapedColor,
            layer.scrapedColor,
          ],
          'fill-opacity': layer.fillOpacity,
        },
      });
    }
    if (!map.getLayer(`${layer.id}-stroke`)) {
      map.addLayer({
        id: `${layer.id}-stroke`,
        type: 'line',
        source: SOURCE_ID,
        'source-layer': layer.sourceLayer,
        paint: {
          'line-color': layer.strokeColor,
          'line-width': layer.strokeWidth,
        },
      });
    }
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
