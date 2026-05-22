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
        Store.state.selectedFeatureId = null;
        Store.state.selectedMergeIds = [];
        Store.state.extractSourceId = null;
        Store.state.selectedExtractIndices = [];
        Store.state.spectrumMode = false;
        Store.state.spectrumResult = null;
        Store.state.spectrumRasterId = null;
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

    it('clears vector state without leaving selected or visible layers behind', () => {
        Store.state.projects = [{ id: 'project-a' }];
        Store.state.activeProject = { id: 'project-a' };
        Store.state.vectorLayers = [{ id: 'layer-a' }];
        Store.state.activeVectorLayerId = 'layer-a';
        Store.state.selectedVectorLayerId = 'layer-a';
        Store.state.visibleVectorLayerIds = new Set(['layer-a']);
        Store.state.currentFeatures = {
            type: 'FeatureCollection',
            features: [{ id: 'feature-a' }],
        };
        Store.state.selectedFeatureId = 'feature-a';

        Store.clearVectorState();

        expect(Store.state.projects).toEqual([]);
        expect(Store.state.activeProject).toBe(null);
        expect(Store.state.vectorLayers).toEqual([]);
        expect(Store.state.activeVectorLayerId).toBe(null);
        expect(Store.state.selectedVectorLayerId).toBe(null);
        expect(Store.state.visibleVectorLayerIds.size).toBe(0);
        expect(Store.state.currentFeatures.features).toEqual([]);
        expect(Store.state.selectedFeatureId).toBe(null);
    });

    it('clears raster state and calculator selections together', () => {
        Store.state.rasters = [{ id: 1 }];
        Store.state.activeLayerIds = new Set([1]);
        Store.state.loadingIds = new Set([1]);
        Store.state.selectedMergeIds = [1, 2];
        Store.state.extractSourceId = 1;
        Store.state.selectedExtractIndices = [2];
        Store.state.spectrumMode = true;
        Store.state.spectrumResult = { bands: [] };
        Store.state.spectrumRasterId = 1;

        Store.clearRasterState();

        expect(Store.state.rasters).toEqual([]);
        expect(Store.state.activeLayerIds.size).toBe(0);
        expect(Store.state.loadingIds.size).toBe(0);
        expect(Store.state.selectedMergeIds).toEqual([]);
        expect(Store.state.extractSourceId).toBe(null);
        expect(Store.state.selectedExtractIndices).toEqual([]);
        expect(Store.state.spectrumMode).toBe(false);
        expect(Store.state.spectrumResult).toBe(null);
        expect(Store.state.spectrumRasterId).toBe(null);
    });
});
