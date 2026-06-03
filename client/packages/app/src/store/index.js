/**
 * Store - English
 * EnglishRaster ImageryEnglish、VectorAnnotation ProjectEnglish、English
 */
const sameLayerId = (left, right) => String(left) === String(right);

const getBundleKey = (raster) => String(raster?.bundle_id ?? 'unclassed');

const getLayerProjectKey = (layer, fallbackProjectId = null) =>
    String(layer?.project_id ?? layer?.projectId ?? fallbackProjectId ?? '');

function moveItem(items, fromIndex, toIndex, position = 'before') {
    const next = [...items];
    const [moved] = next.splice(fromIndex, 1);
    let insertIndex = toIndex + (position === 'after' ? 1 : 0);

    if (fromIndex < insertIndex) insertIndex -= 1;
    insertIndex = Math.max(0, Math.min(next.length, insertIndex));

    if (insertIndex === fromIndex) return items;
    next.splice(insertIndex, 0, moved);
    return next;
}

function orderedSetByItems(existingSet, orderedItems, getId) {
    const existingValues = Array.from(existingSet);
    const next = new Set();

    orderedItems.forEach((item) => {
        const itemId = getId(item);
        const existingValue = existingValues.find((value) => sameLayerId(value, itemId));
        if (existingValue !== undefined) next.add(existingValue);
    });

    existingValues.forEach((value) => {
        if (!Array.from(next).some((known) => sameLayerId(known, value))) {
            next.add(value);
        }
    });

    return next;
}

export const Store = {
    state: {
        // --- English ---
        rasters: [],           // All uploaded/generated raster metadata
        activeLayerIds: new Set(), // Raster layer IDs currently visible on the map
        loadingIds: new Set(),    // Layer IDs currently loading or processing
        selectedMergeIds: [],  // Selected raster ID sequence for band stacking

        // --- VectorEnglish ---
        projects: [],          // All vector annotation projects
        activeProject: null,   // Currently selected project object
        vectorLayers: [],      // All vector layers in the current project
        activeVectorLayerId: null, // Vector layer ID currently being edited/viewed
        selectedVectorLayerId: null, // Selected vector layer ID
        visibleVectorLayerIds: new Set(), // Stores all layer IDs currently rendered on the map
        currentFeatures: {     // GeoJSON features loaded in the current map viewport
            type: "FeatureCollection",
            features: []
        },
        drawColor: '#4f46e5',
        selectedFeatureId: null, // Stores the currently selected feature ID

        // --- English ---
        spectrumMode: false,       // Whether spectrum picking mode is active
        spectrumResult: null,      // Most recent query result { bands, has_nodata, coordinate }
        spectrumRasterId: null,    // Current imagery index_id used for spectrum queries

        // --- Band ExtractionEnglish ---
        extractSourceId: null,       // Source file index_id for extraction actions
        selectedExtractIndices: [],  // Selected band index list [1, 3, ...]
    },

    // English
    onRastersChange: null,
    onVectorStateChange: null, // Vector state change callback

    /**
     * English UI RefreshVectorEnglish
     */
    notifyVectorChange() {
        if (this.onVectorStateChange) {
            this.onVectorStateChange({ ...this.state });
        }
    },


    setRasters(data) {
        this.state.rasters = data;
        this._syncActiveRasterOrder();
        if (this.onRastersChange) this.onRastersChange(data);
    },

    getRasters() {
        return this.state.rasters;
    },

    addActiveLayer(id) {
        if (this.state.activeLayerIds.has(id)) return;
        this.state.activeLayerIds.add(id);
    },

    removeActiveLayer(id) {
        this.state.activeLayerIds.delete(id);
    },

    isLoaded(id) {
        return this.state.activeLayerIds.has(id);
    },

    setLoading(id, isLoading) {
        if (isLoading) {
            this.state.loadingIds.add(id);
        } else {
            this.state.loadingIds.delete(id);
        }
    },

    setProjects(projects) {
        this.state.projects = projects;
        this.notifyVectorChange();
    },

    setActiveProject(project) {
        this.state.activeProject = project;
        // EnglishProjectEnglish
        this.state.vectorLayers = [];
        this.state.activeVectorLayerId = null;
        this.notifyVectorChange();
    },

    setVectorLayers(layers) {
        this.state.vectorLayers = layers;
        this._syncVisibleVectorLayerOrder();
        this.notifyVectorChange();
    },

    clearVectorState() {
        this.state.projects = [];
        this.state.activeProject = null;
        this.state.vectorLayers = [];
        this.state.activeVectorLayerId = null;
        this.state.selectedVectorLayerId = null;
        this.state.visibleVectorLayerIds = new Set();
        this.state.currentFeatures = { type: "FeatureCollection", features: [] };
        this.state.selectedFeatureId = null;
        this.notifyVectorChange();
    },

    clearRasterState() {
        this.state.rasters = [];
        this.state.activeLayerIds = new Set();
        this.state.loadingIds = new Set();
        this.state.selectedMergeIds = [];
        this.state.extractSourceId = null;
        this.state.selectedExtractIndices = [];
        this.state.spectrumMode = false;
        this.state.spectrumResult = null;
        this.state.spectrumRasterId = null;
        if (this.onRastersChange) this.onRastersChange(this.state.rasters);
    },

    reorderRasterLayer(sourceId, targetId, position = 'before') {
        const rasters = this.state.rasters;
        const sourceIndex = rasters.findIndex((raster) => sameLayerId(raster.id, sourceId));
        const targetIndex = rasters.findIndex((raster) => sameLayerId(raster.id, targetId));

        if (sourceIndex < 0 || targetIndex < 0 || sourceIndex === targetIndex) return false;
        if (getBundleKey(rasters[sourceIndex]) !== getBundleKey(rasters[targetIndex])) return false;

        const next = moveItem(rasters, sourceIndex, targetIndex, position);
        if (next === rasters) return false;

        this.state.rasters = next;
        this._syncActiveRasterOrder();
        if (this.onRastersChange) this.onRastersChange(next);
        return true;
    },

    reorderVectorLayer(sourceId, targetId, position = 'before') {
        const layers = this.state.vectorLayers;
        const activeProjectId = this.state.activeProject?.id ?? null;
        const sourceIndex = layers.findIndex((layer) => sameLayerId(layer.id, sourceId));
        const targetIndex = layers.findIndex((layer) => sameLayerId(layer.id, targetId));

        if (sourceIndex < 0 || targetIndex < 0 || sourceIndex === targetIndex) return false;
        if (
            getLayerProjectKey(layers[sourceIndex], activeProjectId) !==
            getLayerProjectKey(layers[targetIndex], activeProjectId)
        ) {
            return false;
        }

        const next = moveItem(layers, sourceIndex, targetIndex, position);
        if (next === layers) return false;

        this.state.vectorLayers = next;
        this._syncVisibleVectorLayerOrder();
        this.notifyVectorChange();
        return true;
    },

    _syncActiveRasterOrder() {
        this.state.activeLayerIds = orderedSetByItems(
            this.state.activeLayerIds,
            this.state.rasters,
            (raster) => raster.id
        );
    },

    _syncVisibleVectorLayerOrder() {
        this.state.visibleVectorLayerIds = orderedSetByItems(
            this.state.visibleVectorLayerIds,
            this.state.vectorLayers,
            (layer) => layer.id
        );
    },

    getRasterRenderOrder() {
        const activeIds = Array.from(this.state.activeLayerIds);
        const orderedIds = [];
        const matchedRasterIds = new Set();

        this.state.rasters.forEach((raster) => {
            if (activeIds.some((id) => sameLayerId(id, raster.id))) {
                orderedIds.push(raster.index_id ?? raster.id);
                matchedRasterIds.add(String(raster.id));
            }
        });

        activeIds.forEach((id) => {
            if (!matchedRasterIds.has(String(id))) {
                orderedIds.push(id);
            }
        });

        return orderedIds.map((id) => String(id));
    },

    getVectorRenderOrder() {
        const visibleIds = Array.from(this.state.visibleVectorLayerIds);
        const orderedIds = [];

        this.state.vectorLayers.forEach((layer) => {
            if (visibleIds.some((id) => sameLayerId(id, layer.id))) {
                orderedIds.push(layer.id);
            }
        });

        visibleIds.forEach((id) => {
            if (!orderedIds.some((known) => sameLayerId(known, id))) {
                orderedIds.push(id);
            }
        });

        return orderedIds.map((id) => String(id));
    },

    /**
     * EnglishActionsEnglishVector Layer
     * @param {string|null} layerId
     */
    // English
    setActiveVectorLayer(layerId) {
        this.state.activeVectorLayerId = layerId;
        // English：English
        if (layerId && !this.state.visibleVectorLayerIds.has(layerId)) {
            this.state.visibleVectorLayerIds.add(layerId);
        }
        this.state.currentFeatures = { type: "FeatureCollection", features: [] };
        this.notifyVectorChange();
    },

    setSelectedVectorLayerId(layerId) {
    this.state.selectedVectorLayerId = layerId;  // Write through to state
    this.notifyVectorChange();
    },

    removeVectorLayer(layerId) {
        this.state.vectorLayers = this.state.vectorLayers.filter(l => l.id !== layerId);
        this.state.visibleVectorLayerIds.delete(layerId);
        // such asEnglish，English
        if (this.state.activeVectorLayerId === layerId) {
            this.state.activeVectorLayerId = null;
        }
        this.notifyVectorChange();  // ✅ Trigger onVectorStateChange -> updateUI()
    },


    /**
     * English (English MapController English)
     */
    setCurrentFeatures(featureCollection) {
        this.state.currentFeatures = featureCollection;
        this.notifyVectorChange();
    },

    /**
     * English：English (EnglishRefresh)
     */
    addFeatureToState(feature) {
        this.state.currentFeatures.features.push(feature);
        this.notifyVectorChange();
    },

    toggleMergeSelection(id) {
        const index = this.state.selectedMergeIds.indexOf(id);
        if (index > -1) {
            this.state.selectedMergeIds.splice(index, 1);
        } else {
            this.state.selectedMergeIds.push(id);
        }
        return [...this.state.selectedMergeIds];
    },

    clearMergeSelection() {
        this.state.selectedMergeIds = [];
    },

    getMergeSelection() {
        return this.state.selectedMergeIds;
    },

    setDrawColor(color) {
        this.state.drawColor = color;
    },

    setSelectedFeatureId(id) {
        this.state.selectedFeatureId = id;
        this.notifyVectorChange();
    },

    // English
    toggleVectorVisibility(layerId) {
        if (this.state.visibleVectorLayerIds.has(layerId)) {
            this.state.visibleVectorLayerIds.delete(layerId);
            // English：such asEnglish，EnglishExitEnglish
            if (this.state.activeVectorLayerId === layerId) {
                this.state.activeVectorLayerId = null;
            }
        } else {
            this.state.visibleVectorLayerIds.add(layerId);
        }
        this.notifyVectorChange();
    },

    /**
    * English，English UI Refresh
    * @param {Function} fetchFn  English API English，returns raster English
    *                            English：() => RasterAPI.getList()
    */
    async refreshRasters(fetchFn) {
        try {
            const data = await fetchFn();
            this.setRasters(data);
        } catch (err) {
            console.error('[Store] refreshRasters Failed:', err);
        }
    },

    /**
    * EnglishVectorProjectEnglish，English UI Refresh
    * @param {Function} fetchFn  English API English，returns projects English
    *                            English：() => ProjectAPI.getList()
    */
    async refreshProjects(fetchFn) {
        try {
            const data = await fetchFn();
            this.setProjects(data);
        } catch (err) {
            console.error('[Store] refreshProjects Failed:', err);
        }
    },


    setSpectrumMode(enabled, rasterId = null) {
        this.state.spectrumMode = enabled;
        this.state.spectrumRasterId = rasterId;
        if (!enabled) this.state.spectrumResult = null;
        // English
        if (this.onRastersChange) this.onRastersChange(this.state.rasters);
    },

    setSpectrumResult(result) {
        this.state.spectrumResult = result;
    },


    getVectorLayers() {return this.state.vectorLayers;},
    getProjects() {return this.state.projects;},
    getActiveProject() {return this.state.activeProject;},

    setExtractSource(rasterId) {
        this.state.extractSourceId = rasterId;
        },

    getExtractSource() {
        return this.state.extractSourceId;
        },

    clearExtractSelection() {
        this.state.selectedExtractIndices = [];
        },

    toggleExtractSelection(bandIndex) {
        const index = this.state.selectedExtractIndices.indexOf(bandIndex);
        if (index > -1) {
            this.state.selectedExtractIndices.splice(index, 1);
        } else {
            this.state.selectedExtractIndices.push(bandIndex);
        }
        return [...this.state.selectedExtractIndices];
        },

    getExtractSelection() {
        return this.state.selectedExtractIndices;
        },
    };
