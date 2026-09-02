// The only module that imports maplibre as a value, which makes it the whole lazy
// boundary: every other map function takes a Map as a parameter and needs maplibre
// for types alone, so those imports erase and stay static.
export type MapEngine = typeof import('maplibre-gl');

let engine: Promise<MapEngine> | null = null;

// Memoised because addProtocol registers globally — a second browse-map on the page
// must reuse this, not register the pmtiles protocol again.
export function loadMapEngine(): Promise<MapEngine> {
  if (!engine) {
    engine = importEngine();
  }
  return engine;
}

async function importEngine(): Promise<MapEngine> {
  const [maplibregl, pmtiles] = await Promise.all([
    import('maplibre-gl'),
    import('pmtiles'),
    import('maplibre-gl/dist/maplibre-gl.css'),
  ]);
  maplibregl.addProtocol('pmtiles', new pmtiles.Protocol().tile);
  return maplibregl;
}
