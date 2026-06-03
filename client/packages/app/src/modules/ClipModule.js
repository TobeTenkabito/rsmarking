import { Store } from '../store/index.js';
import { RasterAPI } from '../api/raster.js';
import { VectorAPI } from '../api/vector.js';
import { boundsToGeometry } from '../utils/geometry.js';

const CLIP_MODE = {
    NONE:   null,
    RASTER: 'raster',
    VECTOR: 'vector',
};

export class ClipModule {
    constructor(app) {
        this.app = app;
        this._clipMode             = CLIP_MODE.NONE;
        this._pendingVectorLayerId = null;
        this._initDrawListener();
    }

    /** English A：EnglishPolygonEnglish */
    startClipRasterByDraw() {
        if (!this._getActiveRasterId()) {
            this.app.ui.showToast('Load a raster image on the map first.', 'warning');
            return;
        }
        this._enterClipMode(CLIP_MODE.RASTER);
    }

    /** English B-1：English bounds EnglishVector */
    async clipVectorByActiveBounds(targetLayerId) {
        const layerId = targetLayerId ?? Store.state.activeVectorLayerId;
        if (!layerId) {
            this.app.ui.showToast('Select a vector layer first.', 'warning');
            return;
        }
        const raster = this._getActiveRasterMeta();
        if (!raster) {
            this.app.ui.showToast('Load a raster image on the map first.', 'warning');
            return;
        }
        if (!raster.bounds_wgs84) {
            this.app.ui.showToast('Current imagery is missing spatial extent information (bounds_wgs84).', 'error');
            return;
        }
        await this._executeClipVector(layerId, boundsToGeometry(raster.bounds_wgs84));
    }

    /** English B-2：EnglishPolygonEnglishVector */
    startClipVectorByDraw(targetLayerId) {
        const layerId = targetLayerId ?? Store.state.activeVectorLayerId;
        if (!layerId) {
            this.app.ui.showToast('Select a vector layer first.', 'warning');
            return;
        }
        this._pendingVectorLayerId = layerId;
        this._enterClipMode(CLIP_MODE.VECTOR);
    }

    /**
     * English C：EnglishVector LayerEnglishVector Layer
     * @param {string} clipLayerId   English id
     * @param {string} targetLayerId English id
     */
    async clipVectorByLayer(clipLayerId, targetLayerId) {
        if (!clipLayerId || !targetLayerId) {
            this.app.ui.showToast('Select both a clip layer and a target layer.', 'warning');
            return;
        }
        if (clipLayerId === targetLayerId) {
            this.app.ui.showToast('The clip layer and target layer cannot be the same.', 'warning');
            return;
        }

        this.app.ui.showGlobalLoading('Getting the clip layer extent...');
        try {
            const clipFeatures = await this._fetchAllFeatures(clipLayerId);
            if (!clipFeatures.length) {
                this.app.ui.showToast('The clip layer has no features.', 'warning');
                return;
            }
            const clipGeometry = this._mergeFeaturesToGeometry(clipFeatures);
            this.app.ui.hideGlobalLoading();
            await this._executeClipVector(targetLayerId, clipGeometry);
        } catch (err) {
            console.error('[ClipModule] Layer ClipFailed:', err);
            this.app.ui.showToast(`Layer ClipFailed：${err.message}`, 'error');
            this.app.ui.hideGlobalLoading();
        }
    }

    /** CancelEnglishActions */
    cancel() {
        if (this._clipMode === CLIP_MODE.NONE) return;
        this._exitClipMode();
        this.app.ui.showToast('Clip action canceled.', 'info');
    }

    async _executeClipRaster(clipGeometry) {
        const rasterId = this._getActiveRasterId();
        const raster   = this._getActiveRasterMeta();
        if (!rasterId || !raster) return;
        const newName = `${raster.name ?? rasterId}_clip_${Date.now()}`;
        this.app.ui.showGlobalLoading('Clipping raster imagery...');
        try {
            const result = await RasterAPI.clipRasterByVector(
                rasterId, newName, [clipGeometry], 'EPSG:4326', true, null, false,
                );
            await this.app.raster?.refreshData();
        if (result?.id && this.app.mapController) {
            await this.app.mapController.toggleLayer(result.id);
        }

        this.app.ui.showToast('Raster clipping complete. New imagery has been loaded.', 'success');
    } catch (err) {
        console.error('[ClipModule] Raster clipping failed:', err);
        this.app.ui.showToast(`Raster clipping failed：${err.message}`, 'error');
    } finally {
        this.app.ui.hideGlobalLoading();
    }
}

    async _executeClipVector(layerId, clipGeometry) {
        this.app.ui.showGlobalLoading('Clipping vector features...');
        try {
            const allFeatures = await this._fetchAllFeatures(layerId);
            if (!allFeatures.length) {
                this.app.ui.showToast('The current layer has no features to clip.', 'warning');
                return;
            }
            const result = await VectorAPI.clipVectorByGeometry(
                clipGeometry, allFeatures, 'EPSG:4326', 'clip',
            );
            if (!result?.features?.length) {
                this.app.ui.showToast('No features were found inside the clip extent.', 'warning');
                return;
            }
            await this._saveClipResultToNewLayer(layerId, result.features);
        } catch (err) {
            console.error('[ClipModule] Vector clipping failed:', err);
            this.app.ui.showToast(`Vector clipping failed：${err.message}`, 'error');
        } finally {
            this.app.ui.hideGlobalLoading();
        }
    }

    async _saveClipResultToNewLayer(sourceLayerId, features) {
        const activeProject = Store.state.activeProject;
        if (!activeProject) {
            this.app.ui.showToast('Select a vector project first.', 'warning');
            return;
        }
        const sourceLayer  = Store.state.vectorLayers.find(l => l.id === sourceLayerId);
        const newLayerName = `${sourceLayer?.name ?? sourceLayerId}_clip_${Date.now()}`;

        const newLayer = await VectorAPI.createLayer(activeProject.id, newLayerName, null);
        const payload  = features.map(f => ({
            geometry:   f.geometry,
            properties: {
                ...f.properties,
                clip_source_layer: sourceLayerId,
                clipped_at:        new Date().toISOString(),
            },
        }));
        await VectorAPI.bulkCreateFeatures(newLayer.id, payload);

        await this.app.project?.handleSelectProject(activeProject.id);
        if (this.app.mapController?.toggleVectorLayer) {
            this.app.mapController.toggleVectorLayer(newLayer.id);
        }
        this.app.ui.showToast(`Clipping complete. A new layer has been created「${newLayerName}」`, 'success');
    }

    _initDrawListener() {
        const map = this.app.mapEngine?.map;
        if (!map) return;

        map.on('draw:created', async (e) => {
            if (this._clipMode === CLIP_MODE.NONE) return;

            const mode           = this._clipMode;
            const pendingLayerId = this._pendingVectorLayerId;
            this._exitClipMode();

            const geometry = e.layer.toGeoJSON().geometry;
            this.app.mapEngine.map.removeLayer(e.layer);

            if (mode === CLIP_MODE.RASTER) {
                await this._executeClipRaster(geometry);
            } else if (mode === CLIP_MODE.VECTOR) {
                await this._executeClipVector(pendingLayerId, geometry);
            }
        });
    }

    _enterClipMode(mode) {
        this._clipMode = mode;
        const map = this.app.mapEngine?.map;
        if (!map) return;

        const color   = '#f59e0b';
        const handler = new L.Draw.Polygon(map, {
            shapeOptions: {
                color, fillColor: color,
                fillOpacity: 0.15, weight: 2, dashArray: '6 4',
            },
        });
        const annotation = this.app.annotation;
        if (annotation) {
            annotation.currentHandler = handler;
            annotation.currentType    = 'polygon';
        }
        handler.enable();

        const label = mode === CLIP_MODE.RASTER ? 'Raster Clip' : 'Vector Clip';
        this.app.ui.showToast(`${label} mode: draw a clip extent on the map (Esc to cancel).`, 'info');
    }

    _exitClipMode() {
        this._clipMode             = CLIP_MODE.NONE;
        this._pendingVectorLayerId = null;
        this.app.annotation?.stopDrawing();
    }

    _getActiveRasterId() {
        const ids = Store.state.activeLayerIds;
        if (!ids.size) return null;
        const activeId = ids.values().next().value;
        const match = Store.state.rasters.find(r => r.id == activeId);
        return match?.index_id ?? null;  // ← returns index_id
    }

    _getActiveRasterMeta() {
        const ids = Store.state.activeLayerIds;
        if (!ids.size) return null;
        const activeId = ids.values().next().value;
        return Store.state.rasters.find(r => r.id == activeId) ?? null;
    }

    async _fetchAllFeatures(layerId) {
        const fc = await VectorAPI.fetchFeaturesInBbox(layerId, [-180, -90, 180, 90]);
        return fc?.features ?? [];
    }

    /**
     * English Feature English MultiPolygon
     * English Polygon/MultiPolygon TypeEnglish
     */
    _mergeFeaturesToGeometry(features) {
        const polygons = features
            .map(f => f.geometry)
            .filter(g => g?.type === 'Polygon' || g?.type === 'MultiPolygon');

        if (!polygons.length) {
            throw new Error('The clip layer has no usable polygon features (Polygon/MultiPolygon).');
        }
        if (polygons.length === 1) return polygons[0];

        const allCoords = polygons.flatMap(g =>
            g.type === 'MultiPolygon' ? g.coordinates : [g.coordinates]
        );
        return { type: 'MultiPolygon', coordinates: allCoords };
    }
}
