import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { MapController } from '@app/core/MapController.js';
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

        controller.destroy();

        expect(engine.map.off).toHaveBeenCalledWith('moveend', expect.any(Function));
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
