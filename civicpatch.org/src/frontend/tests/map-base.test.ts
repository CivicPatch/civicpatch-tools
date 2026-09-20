import { describe, it, expect, vi } from 'vitest';
import {
  pmtilesUrl,
  stateFromOcdid,
  getVisibleLayers,
  whenStyleReady,
  applyStateCoverage,
  applyCountyCoverage,
  applyLocalStatus,
} from '../components/map/map-base.js';

function makeFakeMap() {
  const listeners: Record<string, Array<() => void>> = {};
  const sources = new Set<string>();
  const written: Array<{ source: string; id: string }> = [];
  return {
    styleLoaded: false,
    written,
    isStyleLoaded() { return this.styleLoaded; },
    addFakeSource(id: string) { sources.add(id); },
    getSource(id: string) { return sources.has(id) ? {} : undefined; },
    setFeatureState(target: { source: string; id: string }) {
      if (!sources.has(target.source)) {
        throw new Error(`The source '${target.source}' does not exist in the map's style.`);
      }
      written.push({ source: target.source, id: target.id });
    },
    on(event: string, cb: () => void) { (listeners[event] ||= []).push(cb); },
    off(event: string, cb: () => void) {
      listeners[event] = (listeners[event] || []).filter((c) => c !== cb);
    },
    emit(event: string) { (listeners[event] || []).slice().forEach((c) => c()); },
    listenerCount(event: string) { return (listeners[event] || []).length; },
  };
}

const COVERAGE = {
  wa: { state: { ocdid: 'ocd-division/country:us/state:wa', total: 4, covered: 2, covered_fresh: 1 }, counties: {} },
};
const COUNTIES = {
  'ocd-division/country:us/state:wa/county:king': { total: 4, covered: 2, covered_fresh: 1 },
};

describe('pmtilesUrl', () => {
  it('returns pmtiles URL for a state', () => {
    expect(pmtilesUrl('co')).toBe('pmtiles://https://cdn.civicpatch.org/maps/co.pmtiles');
  });
});

describe('stateFromOcdid', () => {
  it('extracts state code from ocdid', () => {
    expect(stateFromOcdid('ocd-division/country:us/state:co/place:denver')).toBe('co');
  });

  it('returns null for ocdid without state', () => {
    expect(stateFromOcdid('ocd-division/country:us')).toBeNull();
  });
});

describe('getVisibleLayers', () => {
  it('national level shows only states', () => {
    expect(getVisibleLayers('national')).toEqual(['states']);
  });

  it('counties level shows states and counties', () => {
    expect(getVisibleLayers('counties')).toEqual(['states', 'counties']);
  });

  it('local level shows only local', () => {
    expect(getVisibleLayers('local')).toEqual(['local']);
  });
});

describe('whenStyleReady', () => {
  it('runs immediately and subscribes to nothing when the style is already loaded', () => {
    const map = makeFakeMap();
    map.styleLoaded = true;
    const fn = vi.fn();

    whenStyleReady(map as any, fn);

    expect(fn).toHaveBeenCalledTimes(1);
    expect(map.listenerCount('idle')).toBe(0);
  });

  it('defers until idle fires with the style loaded, then runs once and unsubscribes', () => {
    const map = makeFakeMap();
    const fn = vi.fn();

    whenStyleReady(map as any, fn);
    expect(fn).not.toHaveBeenCalled();
    expect(map.listenerCount('idle')).toBe(1);

    map.styleLoaded = true;
    map.emit('idle');

    expect(fn).toHaveBeenCalledTimes(1);
    expect(map.listenerCount('idle')).toBe(0);
  });

  // Regression for the load-timing races: `map.once('load')` ate the single
  // load event then hung; subscribing to a one-shot event can also miss the
  // false->true transition. whenStyleReady must keep waiting through a
  // not-yet-ready idle and fire on a later one.
  it('keeps waiting when idle fires before the style is loaded', () => {
    const map = makeFakeMap();
    const fn = vi.fn();

    whenStyleReady(map as any, fn);
    map.emit('idle'); // style still loading
    expect(fn).not.toHaveBeenCalled();
    expect(map.listenerCount('idle')).toBe(1);

    map.styleLoaded = true;
    map.emit('idle');
    expect(fn).toHaveBeenCalledTimes(1);
  });
});

// Regression: coverage and local status arrive from their own fetches, which can land
// after the style is ready but before the source is added. A style-ready check is not a
// source-ready check, and writing feature state to a missing source throws once per entry.
describe('feature-state writes against a missing source', () => {
  it('applyStateCoverage writes nothing until the national source exists', () => {
    const map = makeFakeMap();
    map.styleLoaded = true;

    expect(() => applyStateCoverage(map as any, COVERAGE)).not.toThrow();
    expect(map.written).toHaveLength(0);

    map.addFakeSource('national');
    applyStateCoverage(map as any, COVERAGE);
    expect(map.written).toEqual([{ source: 'national', id: 'ocd-division/country:us/state:wa' }]);
  });

  it('applyCountyCoverage writes nothing until the state source exists', () => {
    const map = makeFakeMap();
    map.styleLoaded = true;

    expect(() => applyCountyCoverage(map as any, COUNTIES)).not.toThrow();
    expect(map.written).toHaveLength(0);

    map.addFakeSource('state');
    applyCountyCoverage(map as any, COUNTIES);
    expect(map.written).toHaveLength(1);
  });

  it('applyLocalStatus writes nothing until the state source exists', () => {
    const map = makeFakeMap();
    map.styleLoaded = true;
    const status = { 'ocd-division/country:us/state:wa/place:seattle': 'fresh' };

    expect(() => applyLocalStatus(map as any, status)).not.toThrow();
    expect(map.written).toHaveLength(0);

    map.addFakeSource('state');
    applyLocalStatus(map as any, status);
    expect(map.written).toHaveLength(1);
  });
});
