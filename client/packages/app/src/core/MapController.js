import { Store } from '../store/index.js';
import { VectorAPI } from '../api/vector.js';
import { SidebarComponent } from '../../../ui/src/components/Sidebar.js';
import { t } from '../i18n/index.js';

/** EnglishToolsEnglish */
function debounce(fn, delay) {
    let timer = null;
    return function (...args) {
        clearTimeout(timer);
        timer = setTimeout(() => fn.apply(this, args), delay);
    };
}

function mergeFeatureCollections(collections) {
    const features = [];
    const seen = new Set();

    for (const collection of collections) {
        for (const feature of collection?.features || []) {
            const id = feature?.id ?? feature?.properties?.id;
            const key = id !== undefined && id !== null
                ? `id:${id}`
                : `feature:${JSON.stringify(feature)}`;
            if (seen.has(key)) continue;
            seen.add(key);
            features.push(feature);
        }
    }

    return { type: 'FeatureCollection', features };
}

/**
 * MapController - English（Store/UI）English
 */
export class MapController {
    constructor(engine) {
        this.engine = engine;

        /**
         * AbortController English
         * Key: layerId, Value: AbortController
         * EnglishCancelEnglish
         */
        this._abortControllers = new Map();

        /**
         * English fetchViewportFeatures
         * moveend English 300ms English
         */
        this._debouncedFetch = debounce(() => this.fetchViewportFeatures(), 300);
        this._unsubscribeEngineViewChange = null;
        this._lastVisibleVectorOrderKey = null;
        this._lastVectorFetchStateKey = null;
        this._lastSelectedFeatureId = Symbol('uninitialized-selection');

        // English
        this._boundMoveEndHandler = async () => {
            if (Store.state.visibleVectorLayerIds.size > 0) {
                this._debouncedFetch();
            }
        };
        this.initVectorEvents();

        Store.onRastersChange = () => {
            this.applyLayerRenderOrder();
            this.updateUI();
        };

        Store.onVectorStateChange = (state) => {
            this.handleVectorStateChange(state);
            this.updateUI();
        };
    }


    /**
     * EnglishSidebar UI English
     */
    updateUI() {
        const container =
            document.getElementById('sidebar-content') ||
            document.getElementById('raster-list');

        if (container) {
            container.innerHTML = SidebarComponent.render({
                rasters:              Store.state.rasters,
                activeLayerIds:       Store.state.activeLayerIds,
                loadingIds:           Store.state.loadingIds,
                projects:             Store.state.projects,
                activeProject:        Store.state.activeProject,
                vectorLayers:         Store.state.vectorLayers,
                activeVectorLayerId:  Store.state.activeVectorLayerId,
                visibleVectorLayerIds: Store.state.visibleVectorLayerIds,
            });
        }

        const counter = document.getElementById('layer-counter');
        if (counter) {
            const totalActive =
                Store.state.activeLayerIds.size +
                (Store.state.activeVectorLayerId ? 1 : 0);
            counter.innerText = t('nav.layerCounter', { count: totalActive });
        }

        const emptyHint = document.getElementById('empty-hint');
        if (emptyHint) {
            const isAllEmpty =
                Store.state.rasters.length === 0 &&
                Store.state.projects.length === 0;
            emptyHint.classList.toggle('hidden', !isAllEmpty);
        }
    }

    applyLayerRenderOrder() {
        if (this.engine?.setRasterLayerOrder) {
            this.engine.setRasterLayerOrder(Store.getRasterRenderOrder());
        }
        if (this.engine?.setVectorLayerOrder) {
            this.engine.setVectorLayerOrder(Store.getVectorRenderOrder());
        }
    }


    /**
     * English
     */
    async toggleLayer(id) {
        const numericId = isNaN(id) ? id : Number(id);
        const raster = Store.state.rasters.find(r => r.id == numericId);

        if (!raster || !this.engine) return;
        if (Store.state.loadingIds.has(numericId)) return;

        if (Store.isLoaded(numericId)) {
            this.engine.removeLayer(raster.index_id || numericId);
            Store.removeActiveLayer(numericId);
            this.applyLayerRenderOrder();
        } else {
            Store.setLoading(numericId, true);
            this.updateUI();

            try {
                await this.engine.addGeoRasterLayer(raster);
                Store.addActiveLayer(numericId);
                this.applyLayerRenderOrder();
            } catch (err) {
                console.error('[MapController] Raster render failed:', err);
            } finally {
                // EnglishSucceededEnglish，English loading EnglishRefresh UI
                Store.setLoading(numericId, false);
                this.updateUI();
            }
        }

        this.updateUI();
    }

    /**
     * English
     */
    async focusLayer(id) {
        const numericId = isNaN(id) ? id : Number(id);
        const raster = Store.state.rasters.find(r => r.id == numericId);
        if (!raster) return;

        if (!Store.isLoaded(numericId)) {
            await this.toggleLayer(numericId);
        }

        if (this.engine) {
            this.engine.fitLayer(raster.index_id || numericId, raster.bounds || raster.extent);
        }
    }


    /**
     * EnglishVector LayerEnglish（English）English
     * @param {string} layerId
     */
    async toggleVectorLayer(layerId) {
        if (Store.state.activeVectorLayerId === layerId) {
            Store.setActiveVectorLayer(null);
            this.renderVectorData(layerId, { type: 'FeatureCollection', features: [] });
        } else {
            Store.setActiveVectorLayer(layerId);
            // English
            await this.fetchViewportFeatures();
        }
        this.updateUI();
    }

    /**
     * EnglishRefreshEnglishVector Layer（English AI English）
     * @param {string} layerId
     */
    async refreshVectorLayer(layerId) {
        if (Store.state.visibleVectorLayerIds.has(layerId)) {
            await this.fetchViewportFeatures();
        }
    }


    /**
     * EnglishVectorEnglish
     */
    initVectorEvents() {
        const map = this.engine.map || this.engine;
        if (!map?.on) return;

        map.on('moveend', this._boundMoveEndHandler);
        if (typeof this.engine?.onViewChange === 'function') {
            this._unsubscribeEngineViewChange = this.engine.onViewChange(
                this._boundMoveEndHandler
            );
        }
    }

    /**
     * English，English（English）
     * English
     */
    destroy() {
        const map = this.engine.map || this.engine;
        if (map?.off) {
            map.off('moveend', this._boundMoveEndHandler);
        }
        this._unsubscribeEngineViewChange?.();
        this._unsubscribeEngineViewChange = null;

        // CancelEnglish
        for (const controller of this._abortControllers.values()) {
            controller.abort();
        }
        this._abortControllers.clear();
    }


    /**
     * EnglishVectorEnglish Store English
     * English：
     *   1. English layerId English AbortController，EnglishCancelEnglish
     *   2. English signal English VectorAPI，English
     */
    async fetchViewportFeatures() {
        const visibleIds = Store.getVectorRenderOrder();
        if (visibleIds.length === 0) return;

        const bboxes = typeof this.engine?.getViewBboxes === 'function'
            ? this.engine.getViewBboxes()
            : [this._getMapBbox()].filter(Boolean);
        if (bboxes.length === 0) return;

        const fetchPromises = visibleIds.map(async (layerId) => {
            // CancelEnglish
            const prevController = this._abortControllers.get(layerId);
            if (prevController) prevController.abort();

            const controller = new AbortController();
            this._abortControllers.set(layerId, controller);

            try {
                const responses = await Promise.all(
                    bboxes.map(bbox => VectorAPI.fetchFeaturesInBbox(
                        layerId,
                        bbox,
                        { signal: controller.signal }
                    ))
                );
                const data = mergeFeatureCollections(responses);

                // EnglishSucceededEnglish
                this._abortControllers.delete(layerId);

                // Render first so Store observers never see new attributes
                // paired with stale map geometry.
                this.renderVectorData(layerId, data);

                // English Store
                if (layerId === Store.state.activeVectorLayerId) {
                    Store.setCurrentFeatures(data);
                }
            } catch (err) {
                if (err.name === 'AbortError') {
                    // EnglishCancel，English，English
                    return;
                }
                console.error(`[MapController] Layer ${layerId} viewport load failed:`, err);
            }
        });

        await Promise.all(fetchPromises);
    }


    /**
     * English Store EnglishVectorEnglish
     * English：English fetchViewportFeatures，
     *       English，English constructor English
     */
    handleVectorStateChange(state) {
        // English，EnglishCancelEnglish
        const visibleOrder = Store.getVectorRenderOrder();
        const visibleOrderKey = JSON.stringify(visibleOrder);
        const fetchStateKey = JSON.stringify({
            activeLayerId: state.activeVectorLayerId ?? null,
            visibleLayerIds: [...visibleOrder].sort(),
        });

        if (
            visibleOrderKey !== this._lastVisibleVectorOrderKey &&
            this.engine.syncVisibleLayers
        ) {
            this._lastVisibleVectorOrderKey = visibleOrderKey;
            this.engine.syncVisibleLayers(visibleOrder);
        }

        // EnglishToolbar
        if (window.RS?.toggleEditMode) {
            window.RS.toggleEditMode(!!state.activeVectorLayerId);
        }

        // English，English
        if (fetchStateKey !== this._lastVectorFetchStateKey) {
            this._lastVectorFetchStateKey = fetchStateKey;
            if (visibleOrder.length > 0) this._debouncedFetch();
        }

        if (state.selectedFeatureId !== this._lastSelectedFeatureId) {
            this._lastSelectedFeatureId = state.selectedFeatureId;
            if (state.activeVectorLayerId && state.currentFeatures?.features) {
                this.renderVectorData(
                    state.activeVectorLayerId,
                    state.currentFeatures
                );
            }
        }
    }


    /**
     * English BBox English [west, south, east, north]
     * English Leaflet English OpenLayers
     * @returns {number[]|null}
     */
    _getMapBbox() {
        if (typeof this.engine?.getViewBbox === 'function') {
            return this.engine.getViewBbox();
        }

        const map = this.engine.map || this.engine;

        if (map.getBounds) {
            // Leaflet
            const bounds = map.getBounds();
            return [
                bounds.getWest(),
                bounds.getSouth(),
                bounds.getEast(),
                bounds.getNorth(),
            ];
        }

        if (map.getView?.().calculateExtent) {
            // OpenLayers
            return map.getView().calculateExtent(map.getSize());
        }

        return null;
    }

    /**
     * English GeoJSON English
     * @param {string} layerId
     * @param {Object} geojson
     */
    renderVectorData(layerId, geojson) {
        if (this.engine.updateVectorLayer) {
            this.engine.updateVectorLayer(layerId, geojson, Store.state.selectedFeatureId);
        }
    }
}
