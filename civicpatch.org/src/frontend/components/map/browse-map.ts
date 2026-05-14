import './map.css';
import { component, useEffect, useRef, useState } from 'haunted';
import { html } from 'lit-html';
import { ref } from 'lit-html/directives/ref.js';
import maplibregl from 'maplibre-gl';
import {
  DrillLevel,
  NATIONAL_SOURCE_ID,
  STATE_SOURCE_ID,
  STATE_BOUNDS,
  CoverageSummary,
  createMap,
  loadNationalSource,
  loadStateSource,
  addAllLayers,
  applyLevelVisibility,
  applyLocalStatus,
  applyCountyCoverage,
  applyStateCoverage,
  featureBounds,
} from './map-base.js';

interface BrowseMapProps {
  state?: string;
  selectedOcdid?: string | null;
  localStatus?: Record<string, string>;
  coverageSummary?: CoverageSummary;
  height?: string;
}

function BrowseMap(this: HTMLElement, {
  state,
  selectedOcdid = null,
  localStatus = {},
  coverageSummary = {},
  height = '25rem',
}: BrowseMapProps) {
  const mapRef = useRef<maplibregl.Map | null>(null);
  const prevSelectedOcdidRef = useRef<string | null>(null);
  const [level, setLevel] = useState<DrillLevel>('national');
  // levelRef keeps the click handler in sync — handleClick is registered once
  // and would otherwise capture a stale closure value of `level`.
  const levelRef = useRef<DrillLevel>('national');
  const setLevelBoth = (l: DrillLevel) => { levelRef.current = l; setLevel(l); };
  // localStatusRef / coverageSummaryRef keep the click handler in sync — registered once.
  const localStatusRef = useRef<Record<string, string>>(localStatus);
  localStatusRef.current = localStatus;
  const coverageSummaryRef = useRef<CoverageSummary>(coverageSummary);
  coverageSummaryRef.current = coverageSummary;

  const setupContainer = (el: Element | undefined) => {
    if (!el || mapRef.current) return;
    mapRef.current = createMap(el as HTMLElement);
    mapRef.current.addControl(new maplibregl.NavigationControl(), 'bottom-right');
    mapRef.current.on('load', () => mapRef.current?.resize());
    mapRef.current.on('click', handleClick);
  };

  const handleClick = (e: maplibregl.MapMouseEvent) => {
    const map = mapRef.current;
    if (!map) return;

    if (levelRef.current === 'national') {
      const pad = 6;
      const bbox: [maplibregl.PointLike, maplibregl.PointLike] = [
        [e.point.x - pad, e.point.y - pad],
        [e.point.x + pad, e.point.y + pad],
      ];
      const features = map.queryRenderedFeatures(bbox, { layers: ['states'] });
      if (!features.length) return;
      const code = features[0].properties?.code as string | undefined;
      if (!code) return;
      this.dispatchEvent(new CustomEvent('on-state-change', {
        detail: { state: code },
        bubbles: true,
        composed: true,
      }));
      return;
    }

    if (levelRef.current === 'counties') {
      const countyFeatures = map.queryRenderedFeatures(e.point, { layers: ['counties'] });
      if (!countyFeatures.length) {
        // Clicked outside any county — check if it's another state to switch to
        const stateFeatures = map.queryRenderedFeatures(e.point, { layers: ['states'] });
        const clickedStateCode = stateFeatures[0]?.properties?.code as string | undefined;
        if (clickedStateCode && clickedStateCode !== state) {
          this.dispatchEvent(new CustomEvent('on-state-change', {
            detail: { state: clickedStateCode },
            bubbles: true,
            composed: true,
          }));
        }
        return;
      }
      const ocdid = countyFeatures[0].properties?.jurisdiction_ocdid as string | undefined;
      if (!ocdid) return;
      setLevelBoth('local');
      applyLevelVisibility(map, 'local');
      applyLocalStatus(map, localStatusRef.current);
      this.dispatchEvent(new CustomEvent('on-county-change', {
        detail: { jurisdiction_ocdid: ocdid },
        bubbles: true,
        composed: true,
      }));
      if (countyFeatures[0].geometry) {
        const bounds = featureBounds(countyFeatures[0].geometry as GeoJSON.Geometry);
        if (bounds) map.fitBounds(bounds, { padding: 40, duration: 600 });
      }
      return;
    }

    if (levelRef.current === 'local') {
      const features = map.queryRenderedFeatures(e.point, { layers: ['local'] });
      if (!features.length) return;
      const ocdid = features[0].properties?.jurisdiction_ocdid as string | undefined;
      if (!ocdid) return;
      const name = features[0].properties?.name as string | undefined;
      this.dispatchEvent(new CustomEvent('on-jurisdiction-change', {
        detail: { jurisdiction_ocdid: ocdid, name },
        bubbles: true,
        composed: true,
      }));
    }
  };

  // Load national source when no state selected
  useEffect(() => {
    const map = mapRef.current;
    if (!map || state) return;
    const onSourceData = (e: any) => {
      if (e.sourceId === NATIONAL_SOURCE_ID && e.isSourceLoaded) {
        applyStateCoverage(map, coverageSummaryRef.current);
        map.off('sourcedata', onSourceData);
      }
    };
    const load = () => {
      loadNationalSource(map);
      addAllLayers(map);
      setLevelBoth('national');
      applyLevelVisibility(map, 'national');
      map.on('sourcedata', onSourceData);
    };
    if (map.isStyleLoaded()) load();
    else map.once('load', load);
    return () => map.off('sourcedata', onSourceData);
  }, []);

  // Load state source when state changes; reset to national when state is cleared
  useEffect(() => {
    const map = mapRef.current;
    if (!map) return;
    if (!state) {
      setLevelBoth('national');
      if (map.isStyleLoaded()) applyLevelVisibility(map, 'national');
      return;
    }
    const newLevel: DrillLevel = 'counties';
    const onSourceData = (e: any) => {
      if (e.sourceId === STATE_SOURCE_ID && e.isSourceLoaded) {
        applyLocalStatus(map, localStatusRef.current);
        applyCountyCoverage(map, coverageSummaryRef.current[state]?.counties ?? {});
        map.off('sourcedata', onSourceData);
      }
    };
    const load = () => {
      loadNationalSource(map);
      loadStateSource(map, state);
      addAllLayers(map);
      setLevelBoth(newLevel);
      applyLevelVisibility(map, newLevel);
      map.on('sourcedata', onSourceData);
      const bounds = STATE_BOUNDS[state];
      if (bounds) map.fitBounds(bounds, { padding: 40, duration: 600 });
    };
    if (map.isStyleLoaded()) load();
    else map.once('load', load);
    return () => map.off('sourcedata', onSourceData);
  }, [state]);

  // Re-apply local status when localStatus changes; wait for style if needed.
  useEffect(() => {
    const map = mapRef.current;
    if (!map) return;
    const apply = () => applyLocalStatus(map, localStatus);
    if (map.isStyleLoaded()) apply();
    else map.once('load', apply);
  }, [localStatus]);

  // Re-apply state/county coverage when coverageSummary changes; wait for style if needed.
  useEffect(() => {
    const map = mapRef.current;
    if (!map) return;
    const apply = () => {
      applyStateCoverage(map, coverageSummary);
      if (state) applyCountyCoverage(map, coverageSummary[state]?.counties ?? {});
    };
    if (map.isStyleLoaded()) apply();
    else map.once('load', apply);
  }, [coverageSummary]);

  // Apply level visibility when level changes
  useEffect(() => {
    if (!mapRef.current?.isStyleLoaded()) return;
    applyLevelVisibility(mapRef.current, level);
  }, [level]);

  // Highlight and zoom to selected jurisdiction
  useEffect(() => {
    const map = mapRef.current;
    if (!map?.isStyleLoaded()) return;
    if (prevSelectedOcdidRef.current) {
      map.setFeatureState(
        { source: STATE_SOURCE_ID, sourceLayer: 'local', id: prevSelectedOcdidRef.current },
        { selected: false }
      );
    }
    if (selectedOcdid) {
      setLevelBoth('local');
      applyLevelVisibility(map, 'local');
      applyLocalStatus(map, localStatusRef.current);
      map.setFeatureState(
        { source: STATE_SOURCE_ID, sourceLayer: 'local', id: selectedOcdid },
        { selected: true }
      );
      const features = map.querySourceFeatures(STATE_SOURCE_ID, {
        sourceLayer: 'local',
        filter: ['==', ['get', 'jurisdiction_ocdid'], selectedOcdid],
      });
      if (features.length && features[0].geometry) {
        const bounds = featureBounds(features[0].geometry as GeoJSON.Geometry);
        if (bounds) map.fitBounds(bounds, { padding: 80, maxZoom: 14, duration: 600 });
      }
    }
    prevSelectedOcdidRef.current = selectedOcdid;
  }, [selectedOcdid]);

  const handleReset = () => {
    const map = mapRef.current;
    if (!map) return;
    setLevelBoth('national');
    applyLevelVisibility(map, 'national');
    map.flyTo({ center: [-98.5, 39.5], zoom: 3.5 });
    this.dispatchEvent(new CustomEvent('on-state-change', {
      detail: { state: '' },
      bubbles: true,
      composed: true,
    }));
  };

  // Cleanup
  useEffect(() => {
    return () => {
      mapRef.current?.remove();
      mapRef.current = null;
    };
  }, []);

  return html`
    <div class="map-container" style="height:${height}">
      <div class="map-inner" style="height:100%" ${ref(setupContainer)}></div>
      ${level !== 'national' ? html`<button class="map-reset-btn" title="Reset to national view" @click=${handleReset}>↩ Reset</button>` : ''}
    </div>
  `;
}

customElements.define(
  'browse-map',
  component(BrowseMap as any, { useShadowDOM: false, observedAttributes: ['state', 'selected-ocdid'] })
);
