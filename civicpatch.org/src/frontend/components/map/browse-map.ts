import './map.css';
import { component, useEffect, useRef, useState } from 'haunted';
import { html } from 'lit-html';
import { ref } from 'lit-html/directives/ref.js';
import type * as maplibregl from 'maplibre-gl';
import { loadMapEngine, type MapEngine } from './map-engine.js';
import { fetchStateCoverageSummary } from '../../api.js';
import { getNeedsReviewCount } from '../../utils/coverage-utils.js';
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
  whenStyleReady,
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
  const containerRef = useRef<HTMLElement | null>(null);
  const mapRef = useRef<maplibregl.Map | null>(null);
  const engineRef = useRef<MapEngine | null>(null);
  const prevSelectedOcdidRef = useRef<string | null>(null);
  // The map exists only once the maplibre chunk has arrived, so the effects that load
  // sources are gated on this rather than running against a null map and never retrying.
  const [mapReady, setMapReady] = useState(false);
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
  // stateRef / selectedOcdidRef keep the context-restore handler in sync — registered once.
  const stateRef = useRef<string | undefined>(state);
  stateRef.current = state;
  const selectedOcdidRef = useRef<string | null>(selectedOcdid);
  selectedOcdidRef.current = selectedOcdid;
  // National-level hover tooltip: a single reused popup, the state it's currently showing,
  // and a per-state cache so we fetch each state's coverage summary at most once.
  const hoverPopupRef = useRef<maplibregl.Popup | null>(null);
  const hoverStateRef = useRef<string | null>(null);
  const summaryCacheRef = useRef<Map<string, any>>(new Map());

  // A backgrounded tab can lose its WebGL context; on restore MapLibre reloads
  // tiles into a fresh context but feature-state is gone, so coverage falls back
  // to the zero-coverage (red) color. Re-apply it from current props.
  const reapplyFeatureState = () => {
    const map = mapRef.current;
    if (!map) return;
    applyStateCoverage(map, coverageSummaryRef.current);
    const selectedState = stateRef.current;
    if (selectedState) {
      applyCountyCoverage(map, coverageSummaryRef.current[selectedState]?.counties ?? {});
      applyLocalStatus(map, localStatusRef.current);
    }
    if (selectedOcdidRef.current) {
      map.setFeatureState(
        { source: STATE_SOURCE_ID, sourceLayer: 'local', id: selectedOcdidRef.current },
        { selected: true },
      );
    }
  };

  const setContainer = (el: Element | undefined) => {
    containerRef.current = (el as HTMLElement) ?? null;
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

  const stateTooltipHtml = (code: string, s: any): string => {
    const header = `<strong>${code.toUpperCase()}</strong>`;
    if (!s) {
      return `<div class="map-tooltip">${header}<div class="map-tooltip__sub">Loading…</div></div>`;
    }
    const reach = Math.round((s.reach_fraction ?? 0) * 100);
    const toReview = getNeedsReviewCount(s);
    return `
      <div class="map-tooltip">
        ${header}
        <div>${reach}% covered (${s.covered ?? 0} / ${s.scrapeable ?? 0})</div>
        <div class="map-tooltip__sub">${toReview} to review</div>
      </div>`;
  };

  const handleStateHover = (e: maplibregl.MapLayerMouseEvent) => {
    const map = mapRef.current;
    if (!map || levelRef.current !== 'national') return;
    const code = (e.features?.[0]?.properties?.code as string | undefined)?.toLowerCase();
    if (!code) return;
    map.getCanvas().style.cursor = 'pointer';
    if (!hoverPopupRef.current) {
      hoverPopupRef.current = new engineRef.current.Popup({
        closeButton: false,
        closeOnClick: false,
        offset: 8,
        className: 'map-tooltip-popup',
      });
    }
    hoverPopupRef.current.setLngLat(e.lngLat).addTo(map);
    if (hoverStateRef.current === code) return; // same state — just reposition
    hoverStateRef.current = code;
    const cached = summaryCacheRef.current.get(code);
    hoverPopupRef.current.setHTML(stateTooltipHtml(code, cached));
    if (cached) return;
    fetchStateCoverageSummary(code)
      .then((d: any) => {
        summaryCacheRef.current.set(code, d.data);
        if (hoverStateRef.current === code) {
          hoverPopupRef.current?.setHTML(stateTooltipHtml(code, d.data));
        }
      })
      .catch(() => {});
  };

  const handleStateLeave = () => {
    const map = mapRef.current;
    if (map) map.getCanvas().style.cursor = '';
    hoverStateRef.current = null;
    hoverPopupRef.current?.remove();
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
      engineRef.current = engine;
      map = createMap(engine, el);
      map.addControl(new engine.NavigationControl(), 'bottom-right');
      map.on('load', () => map?.resize());
      map.on('click', handleClick);
      map.on('mousemove', 'states', handleStateHover);
      map.on('mouseleave', 'states', handleStateLeave);
      map.getCanvas().addEventListener('webglcontextrestored', reapplyFeatureState);
      // The map is otherwise trapped in this closure; expose it on the element
      // for debugging and for e2e assertions about layers/feature-state.
      (el as any)._map = map;
      mapRef.current = map;
      setMapReady(true);
    });

    return () => {
      disposed = true;
      hoverPopupRef.current?.remove();
      map?.remove();
      mapRef.current = null;
    };
  }, []);

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
    whenStyleReady(map, load);
    return () => map.off('sourcedata', onSourceData);
  }, [mapReady]);

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
    whenStyleReady(map, load);
    return () => map.off('sourcedata', onSourceData);
  }, [mapReady, state]);

  // Re-apply local status when localStatus changes; wait for style if needed.
  useEffect(() => {
    const map = mapRef.current;
    if (!map) return;
    const apply = () => applyLocalStatus(map, localStatus);
    whenStyleReady(map, apply);
  }, [localStatus]);

  // Re-apply state/county coverage when coverageSummary changes; wait for style if needed.
  useEffect(() => {
    const map = mapRef.current;
    if (!map) return;
    const apply = () => {
      applyStateCoverage(map, coverageSummary);
      if (state) applyCountyCoverage(map, coverageSummary[state]?.counties ?? {});
    };
    whenStyleReady(map, apply);
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

  return html`
    <div class="map-container" style="height:${height}">
      <div class="map-inner" style="height:100%" ${ref(setContainer)}></div>
      ${mapReady ? '' : html`<div class="map-loading">Loading map…</div>`}
      ${level !== 'national' ? html`<button class="map-reset-btn" title="Reset to national view" @click=${handleReset}>↩ Reset</button>` : ''}
      <div class="map-legend" aria-label="Map legend">
        <span class="map-legend__item"><span class="map-legend__swatch map-legend__swatch--fresh"></span>Fresh</span>
        <span class="map-legend__item"><span class="map-legend__swatch map-legend__swatch--stale"></span>Stale</span>
        <span class="map-legend__item"><span class="map-legend__swatch map-legend__swatch--gap"></span>No data</span>
        <span class="map-legend__item"><span class="map-legend__swatch map-legend__swatch--untracked"></span>Untracked</span>
        ${level === 'local' ? '' : html`<span class="map-legend__note">bolder = more covered</span>`}
      </div>
    </div>
  `;
}

customElements.define(
  'browse-map',
  component(BrowseMap as any, { useShadowDOM: false, observedAttributes: [] })
);
