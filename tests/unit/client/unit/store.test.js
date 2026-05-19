import { describe, it, expect, beforeEach } from 'vitest';
import { Store } from '@app/store/index.js';

describe('Store layer state', () => {
    beforeEach(() => {
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
        Store.onRastersChange = null;
        Store.onVectorStateChange = null;
    });

    it('toggles vector layer visibility', () => {
        const layerId = 'layer-123';
        Store.toggleVectorVisibility(layerId);
        expect(Store.state.visibleVectorLayerIds.has(layerId)).toBe(true);

        Store.toggleVectorVisibility(layerId);
        expect(Store.state.visibleVectorLayerIds.has(layerId)).toBe(false);
    });

    it('makes an active vector layer visible automatically', () => {
        const layerId = 'layer-456';
        Store.setActiveVectorLayer(layerId);

        expect(Store.state.activeVectorLayerId).toBe(layerId);
        expect(Store.state.visibleVectorLayerIds.has(layerId)).toBe(true);
    });

    it('leaves visibility on when vector editing exits', () => {
        Store.setActiveVectorLayer('layer-1');
        Store.setActiveVectorLayer(null);

        expect(Store.state.activeVectorLayerId).toBe(null);
        expect(Store.state.visibleVectorLayerIds.has('layer-1')).toBe(true);
    });

    it('reorders raster layers only inside the same bundle', () => {
        Store.setRasters([
            { id: 1, index_id: 'idx-1', bundle_id: 'bundle-a' },
            { id: 2, index_id: 'idx-2', bundle_id: 'bundle-a' },
            { id: 3, index_id: 'idx-3', bundle_id: 'bundle-b' },
        ]);
        Store.addActiveLayer(1);
        Store.addActiveLayer(2);

        expect(Store.reorderRasterLayer(2, 1, 'before')).toBe(true);
        expect(Store.state.rasters.map((raster) => raster.id)).toEqual([2, 1, 3]);
        expect(Store.getRasterRenderOrder()).toEqual(['idx-2', 'idx-1']);

        expect(Store.reorderRasterLayer(2, 3, 'after')).toBe(false);
        expect(Store.state.rasters.map((raster) => raster.id)).toEqual([2, 1, 3]);
    });

    it('reorders vector layers only inside the same project', () => {
        Store.setActiveProject({ id: 'project-a', name: 'Project A' });
        Store.setVectorLayers([
            { id: 'layer-1', name: 'One', project_id: 'project-a' },
            { id: 'layer-2', name: 'Two', project_id: 'project-a' },
            { id: 'layer-3', name: 'Three', project_id: 'project-b' },
        ]);
        Store.toggleVectorVisibility('layer-1');
        Store.toggleVectorVisibility('layer-2');

        expect(Store.reorderVectorLayer('layer-2', 'layer-1', 'before')).toBe(true);
        expect(Store.state.vectorLayers.map((layer) => layer.id)).toEqual(['layer-2', 'layer-1', 'layer-3']);
        expect(Store.getVectorRenderOrder()).toEqual(['layer-2', 'layer-1']);

        expect(Store.reorderVectorLayer('layer-2', 'layer-3', 'after')).toBe(false);
        expect(Store.state.vectorLayers.map((layer) => layer.id)).toEqual(['layer-2', 'layer-1', 'layer-3']);
    });
});
