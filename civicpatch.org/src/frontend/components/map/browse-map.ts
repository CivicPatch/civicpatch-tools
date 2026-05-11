import './map.css';
import { component, useEffect, useRef } from 'haunted';
import { html } from 'lit-html';
import { ref } from 'lit-html/directives/ref.js';
import maplibregl from 'maplibre-gl';
import {
  SOURCE_ID,
  DEFAULT_LAYERS,
  createMap,
  loadStateSource,
  addJurisdictionLayers,
} from './map-base.js';

interface BrowseMapProps {
  state?: string;
  selectedOcdid?: string | null;
  coverageMap?: Record<string, number>;
  height?: string;
}

function BrowseMap(this: HTMLElement, {
  state,
  selectedOcdid = null,
  coverageMap = {},
  height = '25rem',
}: BrowseMapProps) {
  const mapRef = useRef<maplibregl.Map | null>(null);
  const prevSelectedOcdidRef = useRef<string | null>(null);

  const setupContainer = (el: Element | undefined) => {
    if (!el || mapRef.current) return;
    mapRef.current = createMap(el as HTMLElement);
    mapRef.current.addControl(new maplibregl.NavigationControl(), 'bottom-right');
    mapRef.current.on('load', () => mapRef.current?.resize());
    mapRef.current.on('click', handleClick);
  };

  const handleClick = (e: maplibregl.MapMouseEvent) => {
    if (!mapRef.current) return;
    const clickableLayers = DEFAULT_LAYERS.filter(l => l.clickable).map(l => l.id);
    const features = mapRef.current.queryRenderedFeatures(e.point, { layers: clickableLayers });
    if (!features.length) return;
    const ocdid = features[0].properties?.jurisdiction_ocdid as string | undefined;
    if (!ocdid) return;
    const name = features[0].properties?.name as string | undefined;
    this.dispatchEvent(new CustomEvent('on-jurisdiction-change', {
      detail: { jurisdiction_ocdid: ocdid, name },
      bubbles: true,
      composed: true,
    }));
  };

  const handleLocate = () => {
    navigator.geolocation.getCurrentPosition(
      (pos) => {
        if (!mapRef.current) return;
        const { longitude, latitude } = pos.coords;
        mapRef.current.flyTo({ center: [longitude, latitude], zoom: 10 });
        mapRef.current.once('moveend', () => {
          if (!mapRef.current) return;
          const point = mapRef.current.project([longitude, latitude]);
          const clickableLayers = DEFAULT_LAYERS.filter(l => l.clickable).map(l => l.id);
          const features = mapRef.current.queryRenderedFeatures(point, { layers: clickableLayers });
          if (!features.length) return;
          const ocdid = features[0].properties?.jurisdiction_ocdid as string | undefined;
          if (!ocdid) return;
          this.dispatchEvent(new CustomEvent('on-jurisdiction-change', {
            detail: { jurisdiction_ocdid: ocdid },
            bubbles: true,
            composed: true,
          }));
        });
      },
      () => { /* denied or unavailable — silently no-op */ }
    );
  };

  // Load state source + layers once the map is ready; re-apply coverage when tiles arrive
  useEffect(() => {
    if (!mapRef.current || !state) return;
    const map = mapRef.current;
    const onSourceData = (e: any) => {
      if (e.sourceId === SOURCE_ID && e.isSourceLoaded) {
        applyCoverage(map, coverageMap);
      }
    };
    const load = () => {
      loadStateSource(map, state);
      if (!map.getLayer('jurisdictions')) addJurisdictionLayers(map, DEFAULT_LAYERS);
      applyCoverage(map, coverageMap);
      map.on('sourcedata', onSourceData);
    };
    if (map.isStyleLoaded()) {
      load();
    } else {
      map.once('load', load);
    }
    return () => map.off('sourcedata', onSourceData);
  }, [state]);

  // Apply coverage when coverageMap changes
  useEffect(() => {
    if (!mapRef.current?.isStyleLoaded()) return;
    applyCoverage(mapRef.current, coverageMap);
  }, [coverageMap]);

  // Update selected feature highlight
  useEffect(() => {
    const map = mapRef.current;
    if (!map) return;
    if (prevSelectedOcdidRef.current) {
      map.setFeatureState(
        { source: SOURCE_ID, sourceLayer: 'jurisdictions', id: prevSelectedOcdidRef.current },
        { selected: false }
      );
    }
    if (selectedOcdid) {
      map.setFeatureState(
        { source: SOURCE_ID, sourceLayer: 'jurisdictions', id: selectedOcdid },
        { selected: true }
      );
    }
    prevSelectedOcdidRef.current = selectedOcdid;
  }, [selectedOcdid]);

  // Cleanup map on disconnect
  useEffect(() => {
    return () => {
      mapRef.current?.remove();
      mapRef.current = null;
    };
  }, []);

  return html`
    <div class="map-container" style="height:${height}">
      <div class="map-inner" style="height:100%" ${ref(setupContainer)}></div>
      ${navigator.geolocation ? html`<button class="map-locate-btn" title="Find my location" @click=${handleLocate}>Locate</button>` : ''}
    </div>
  `;
}

function applyCoverage(map: maplibregl.Map, coverageMap: Record<string, number>): void {
  for (const [ocdid, coverage] of Object.entries(coverageMap)) {
    map.setFeatureState(
      { source: SOURCE_ID, sourceLayer: 'jurisdictions', id: ocdid },
      { scraped: coverage > 0 }
    );
  }
}

customElements.define(
  'browse-map',
  component(BrowseMap as any, { useShadowDOM: false, observedAttributes: ['state', 'selected-ocdid'] })
);
