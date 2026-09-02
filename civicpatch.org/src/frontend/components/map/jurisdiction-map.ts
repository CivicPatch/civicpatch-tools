import "./map.css";
import { component, useEffect, useRef, useState } from "haunted";
import { html } from "lit-html";
import { ref } from "lit-html/directives/ref.js";
import type * as maplibregl from "maplibre-gl";
import { loadMapEngine } from "./map-engine.js";
import {
  STATE_SOURCE_ID,
  createMap,
  loadStateSource,
  addAllLayers,
  applyLevelVisibility,
  stateFromOcdid,
  featureBounds,
} from "./map-base.js";

interface JurisdictionMapProps {
  jurisdictionOcdid?: string;
}

function JurisdictionMap(
  this: HTMLElement,
  { jurisdictionOcdid }: JurisdictionMapProps,
) {
  const containerRef = useRef<HTMLElement | null>(null);
  const mapRef = useRef<maplibregl.Map | null>(null);
  const [mapReady, setMapReady] = useState(false);

  const setContainer = (el: Element | undefined) => {
    containerRef.current = (el as HTMLElement) ?? null;
  };

  // maplibre arrives as its own chunk, so the map is built here rather than during the
  // render commit: an effect can be cancelled if the element goes before the chunk lands.
  useEffect(() => {
    const el = containerRef.current;
    if (!el) return;
    let map: maplibregl.Map | null = null;
    let disposed = false;

    loadMapEngine().then((engine) => {
      if (disposed) return;
      map = createMap(engine, el);
      mapRef.current = map;
      setMapReady(true);
    });

    return () => {
      disposed = true;
      map?.remove();
      mapRef.current = null;
    };
  }, []);

  useEffect(() => {
    if (!mapRef.current || !jurisdictionOcdid) return;
    const map = mapRef.current;
    const state = stateFromOcdid(jurisdictionOcdid);
    if (!state) return;

    const tryFit = () => {
      const features = map.querySourceFeatures(STATE_SOURCE_ID, {
        sourceLayer: "local",
        filter: ["==", ["get", "jurisdiction_ocdid"], jurisdictionOcdid],
      });
      if (!features.length) return;
      const feature = features[0];
      if (!feature.geometry) return;
      map.fitBounds(featureBounds(feature.geometry), {
        padding: 40,
        maxZoom: 14,
      });
      map.off("sourcedata", tryFit);
    };

    const load = () => {
      loadStateSource(map, state);
      addAllLayers(map);
      applyLevelVisibility(map, "local");

      map.setFeatureState(
        {
          source: STATE_SOURCE_ID,
          sourceLayer: "local",
          id: jurisdictionOcdid,
        },
        { selected: true },
      );

      map.on("sourcedata", tryFit);
      tryFit();
    };

    if (map.isStyleLoaded()) {
      load();
    } else {
      map.once("load", load);
    }
    return () => map.off("sourcedata", tryFit);
  }, [jurisdictionOcdid, mapReady]);

  return html`
    <div class="map-container">
      <div class="map-inner" style="height:100%" ${ref(setContainer)}></div>
      ${mapReady ? "" : html`<div class="map-loading">Loading map</div>`}
    </div>
  `;
}

customElements.define(
  "jurisdiction-map",
  component(JurisdictionMap as any, {
    useShadowDOM: false,
    observedAttributes: ["jurisdiction-ocdid"],
  }),
);
