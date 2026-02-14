/**
 * Store - 核心状态管理中心
 */
export const Store = {
    state: {
        rasters: [], 
        activeLayerIds: new Set(),
        loadingIds: new Set(),
        selectedMergeIds: [],
    },

    // 监听回调 
    onRastersChange: null,

    // --- 影像数据管理 ---
    setRasters(data) {
        this.state.rasters = data;
        if (this.onRastersChange) this.onRastersChange(data);
    },

    getRasters() {
        return this.state.rasters;
    },

    // --- 地图图层状态控制 ---
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

    // --- 加载/进度状态 ---
    setLoading(id, isLoading) {
        if (isLoading) {
            this.state.loadingIds.add(id);
        } else {
            this.state.loadingIds.delete(id);
        }
    },

    isLoading(id) {
        return this.state.loadingIds.has(id);
    },

    // --- 工具箱专有状态 ---
    toggleMergeSelection(id) {
        const index = this.state.selectedMergeIds.indexOf(id);
        if (index > -1) {
            // 已选中则移除
            this.state.selectedMergeIds.splice(index, 1);
        } else {
            // 未选中则按顺序添加
            this.state.selectedMergeIds.push(id);
        }
        return [...this.state.selectedMergeIds];
    },

    clearMergeSelection() {
        this.state.selectedMergeIds = [];
    },

    getMergeSelection() {
        return this.state.selectedMergeIds;
    }
};
