import { describe, it, expect, vi } from 'vitest';
import { pmtilesUrl, stateFromOcdid, getVisibleLayers, whenStyleReady } from '../components/map/map-base.js';

function makeFakeMap() {
  const listeners: Record<string, Array<() => void>> = {};
  return {
    styleLoaded: false,
    isStyleLoaded() { return this.styleLoaded; },
    on(event: string, cb: () => void) { (listeners[event] ||= []).push(cb); },
    off(event: string, cb: () => void) {
      listeners[event] = (listeners[event] || []).filter((c) => c !== cb);
    },
    emit(event: string) { (listeners[event] || []).slice().forEach((c) => c()); },
    listenerCount(event: string) { return (listeners[event] || []).length; },
  };
}

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
