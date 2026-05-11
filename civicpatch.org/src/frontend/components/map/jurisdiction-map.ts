import './map.css';
import { component, useEffect, useRef } from 'haunted';
import { html } from 'lit-html';
import { ref } from 'lit-html/directives/ref.js';
import maplibregl from 'maplibre-gl';
import {
  STATE_SOURCE_ID,
  createMap,
  loadStateSource,
  addAllLayers,
  applyLevelVisibility,
  stateFromOcdid,
  featureBounds,
} from './map-base.js';

interface JurisdictionMapProps {
  jurisdictionOcdid?: string;
}

function JurisdictionMap(this: HTMLElement, {
  jurisdictionOcdid,
}: JurisdictionMapProps) {
  const mapRef = useRef<maplibregl.Map | null>(null);

  const setupContainer = (el: Element | undefined) => {
    if (!el || mapRef.current) return;
    mapRef.current = createMap(el as HTMLElement);
  };

  useEffect(() => {
    if (!mapRef.current || !jurisdictionOcdid) return;
    const map = mapRef.current;
    const state = stateFromOcdid(jurisdictionOcdid);
    if (!state) return;

    const tryFit = () => {
      const features = map.querySourceFeatures(STATE_SOURCE_ID, {
        sourceLayer: 'local',
        filter: ['==', ['get', 'jurisdiction_ocdid'], jurisdictionOcdid],
      });
      if (!features.length) return;
      const feature = features[0];
      if (!feature.geometry) return;
      map.fitBounds(featureBounds(feature.geometry), { padding: 40, maxZoom: 14 });
      map.off('sourcedata', tryFit);
    };

    const load = () => {
      loadStateSource(map, state);
      addAllLayers(map);
      applyLevelVisibility(map, 'local');

      map.setFeatureState(
        { source: STATE_SOURCE_ID, sourceLayer: 'local', id: jurisdictionOcdid },
        { selected: true }
      );

      map.on('sourcedata', tryFit);
      tryFit();
    };

    if (map.isStyleLoaded()) {
      load();
    } else {
      map.once('load', load);
    }
    return () => map.off('sourcedata', tryFit);
  }, [jurisdictionOcdid, mapRef.current]);

  useEffect(() => {
    return () => {
      mapRef.current?.remove();
      mapRef.current = null;
    };
  }, []);

  return html`
    <div class="map-container">
      <div class="map-inner" style="height:100%" ${ref(setupContainer)}></div>
    </div>
  `;
}

customElements.define(
  'jurisdiction-map',
  component(JurisdictionMap as any, { useShadowDOM: false, observedAttributes: ['jurisdiction-ocdid'] })
);
