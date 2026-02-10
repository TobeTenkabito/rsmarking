export const Store = {
    state: {
        rasters: [],
        activeLayerIds: new Set(),
        loadingIds: new Set()
    },


    onToggle: null,

    setRasters(data) {
        this.state.rasters = data;
    },

    addActiveLayer(id) {
        if (this.state.activeLayerIds.has(id)) return;
        this.state.activeLayerIds.add(id);
        console.log(`[Store] 图层 ${id} 已激活`);
    },

    removeActiveLayer(id) {
        this.state.activeLayerIds.delete(id);
        console.log(`[Store] 图层 ${id} 已卸载`);
    },

    setLoading(id, isLoading) {
        if (isLoading) {
            this.state.loadingIds.add(id);
        } else {
            this.state.loadingIds.delete(id);
        }
    },

    isLoaded(id) {
        return this.state.activeLayerIds.has(id);
    },

    isLoading(id) {
        return this.state.loadingIds.has(id);
    }
};