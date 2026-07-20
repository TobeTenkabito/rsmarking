import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { MapController } from '@app/core/MapController.js';
import { VectorAPI } from '@app/api/vector.js';
import { Store } from '@app/store/index.js';


function resetStore() {
    Store.state.rasters = [];
    Store.state.activeLayerIds = new Set();
    Store.state.loadingIds = new Set();
    Store.state.projects = [];
    Store.state.activeProject = null;
    Store.state.vectorLayers = [];
    Store.state.activeVectorLayerId = null;
    Store.state.selectedVectorLayerId = null;
    Store.state.visibleVectorLayerIds = new Set();
    Store.state.currentFeatures = { type: 'FeatureCollection', features: [] };
    Store.state.selectedFeatureId = null;
    Store.onRastersChange = null;
    Store.onVectorStateChange = null;
}


function createEngine() {
    return {
        map: {
            on: vi.fn(),
            off: vi.fn(),
        },
        setRasterLayerOrder: vi.fn(),
        setVectorLayerOrder: vi.fn(),
        syncVisibleLayers: vi.fn(),
        updateVectorLayer: vi.fn(),
        onViewChange: vi.fn(() => vi.fn()),
    };
}


describe('MapController', () => {
    let controller;
    let engine;

    beforeEach(() => {
        resetStore();
        engine = createEngine();
        controller = new MapController(engine);
    });

    afterEach(() => {
        controller.destroy();
        resetStore();
    });

    it('binds and removes the map move listener', () => {
        expect(engine.map.on).toHaveBeenCalledWith('moveend', expect.any(Function));
        expect(engine.onViewChange).toHaveBeenCalledWith(expect.any(Function));

        controller.destroy();

        expect(engine.map.off).toHaveBeenCalledWith('moveend', expect.any(Function));
    });

    it('fetches and merges both view envelopes when the globe crosses the dateline', async () => {
        engine.getViewBboxes = vi.fn(() => [
            [170, -20, 180, 20],
            [-180, -20, -170, 20],
        ]);
        Store.state.visibleVectorLayerIds = new Set(['vector-a']);
        const fetchSpy = vi.spyOn(VectorAPI, 'fetchFeaturesInBbox')
            .mockImplementation(async (_layerId, bbox) => ({
                type: 'FeatureCollection',
                features: [{
                    type: 'Feature',
                    id: bbox[0] > 0 ? 'east' : 'west',
                    geometry: { type: 'Point', coordinates: [bbox[0], 0] },
                    properties: {},
                }],
            }));

        await controller.fetchViewportFeatures();

        expect(fetchSpy).toHaveBeenCalledTimes(2);
        expect(engine.updateVectorLayer).toHaveBeenCalledWith(
            'vector-a',
            expect.objectContaining({
                features: expect.arrayContaining([
                    expect.objectContaining({ id: 'east' }),
                    expect.objectContaining({ id: 'west' }),
                ]),
            }),
            null
        );
        fetchSpy.mockRestore();
    });

    it('does not refetch or resync visibility when only current features change', () => {
        Store.state.vectorLayers = [{ id: 'vector-a' }];
        Store.state.visibleVectorLayerIds = new Set(['vector-a']);
        Store.state.activeVectorLayerId = 'vector-a';
        controller._debouncedFetch = vi.fn();

        controller.handleVectorStateChange({ ...Store.state });
        Store.state.currentFeatures = {
            type: 'FeatureCollection',
            features: [{
                type: 'Feature',
                id: 'feature-a',
                properties: {},
                geometry: { type: 'Point', coordinates: [10, 20] },
            }],
        };
        controller.handleVectorStateChange({ ...Store.state });

        expect(engine.syncVisibleLayers).toHaveBeenCalledOnce();
        expect(controller._debouncedFetch).toHaveBeenCalledOnce();
    });

    it('forwards store render order to the map engine', () => {
        Store.state.rasters = [
            { id: 1, index_id: 'raster-a' },
            { id: 2, index_id: 'raster-b' },
        ];
        Store.state.activeLayerIds = new Set([2, 1]);
        Store.state.vectorLayers = [
            { id: 'vector-a' },
            { id: 'vector-b' },
        ];
        Store.state.visibleVectorLayerIds = new Set(['vector-b', 'vector-a']);

        controller.applyLayerRenderOrder();

        expect(engine.setRasterLayerOrder).toHaveBeenCalledWith(['raster-a', 'raster-b']);
        expect(engine.setVectorLayerOrder).toHaveBeenCalledWith(['vector-a', 'vector-b']);
    });

    it('updates the loaded layer counter from active raster and vector state', () => {
        document.body.innerHTML = '<div id="layer-counter"></div>';
        Store.state.activeLayerIds = new Set([1, 2]);
        Store.state.activeVectorLayerId = 'vector-a';

        controller.updateUI();

        expect(document.getElementById('layer-counter').innerText).toContain('3');
    });
});
