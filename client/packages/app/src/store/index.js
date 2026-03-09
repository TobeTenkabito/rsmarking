<<<<<<< HEAD
/**
 * Store - 核心状态管理中心
 * 负责维护栅格影像元数据、矢量标注项目及图层、以及全局交互状态
 */
export const Store = {
    state: {
        // --- 栅格数据状态 ---
        rasters: [],           // 所有已上传/生成的影像元数据
        activeLayerIds: new Set(), // 当前地图上加载显示的栅格图层 ID
        loadingIds: new Set(),    // 正在处理/加载中的图层 ID
        selectedMergeIds: [],  // 波段合成功能中选中的影像 ID 序列

        // --- 矢量标注状态 ---
        projects: [],          // 所有矢量标注项目列表
        activeProject: null,   // 当前选中的项目对象
        vectorLayers: [],      // 当前项目下的所有矢量图层
        activeVectorLayerId: null, // 当前正在编辑/查看的矢量图层 ID
        currentFeatures: {     // 当前地图视口内加载的 GeoJSON 要素
            type: "FeatureCollection",
            features: []
        },
        drawColor: '#4f46e5',
        selectedFeatureId: null, // 存储当前被选中的要素 ID
    },

    // 监听回调
    onRastersChange: null,
    onVectorStateChange: null, // 矢量状态变化回调

    /**
     * 通知 UI 刷新矢量相关组件
     */
    notifyVectorChange() {
        if (this.onVectorStateChange) {
            this.onVectorStateChange({ ...this.state });
        }
    },


    setRasters(data) {
        this.state.rasters = data;
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
        // 切换项目时通常需要清空当前的图层列表和选中项
        this.state.vectorLayers = [];
        this.state.activeVectorLayerId = null;
        this.notifyVectorChange();
    },

    setVectorLayers(layers) {
        this.state.vectorLayers = layers;
        this.notifyVectorChange();
    },

    /**
     * 设置当前正在操作的矢量图层
     * @param {string|null} layerId
     */
    setActiveVectorLayer(layerId) {
        this.state.activeVectorLayerId = layerId;
        // 切换图层时重置要素缓存，等待 MapController 触发 BBox 加载
        this.state.currentFeatures = { type: "FeatureCollection", features: [] };
        this.notifyVectorChange();
    },


    /**
     * 更新当前视口的要素集合 (由 MapController 移动结束后调用)
     */
    setCurrentFeatures(featureCollection) {
        this.state.currentFeatures = featureCollection;
        this.notifyVectorChange();
    },

    /**
     * 局部更新：向当前集合添加单个新要素 (无需全量刷新)
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
    }
};
=======
/**
 * Store - 核心状态管理中心
 * 负责维护栅格影像元数据、矢量标注项目及图层、以及全局交互状态
 */
export const Store = {
    state: {
        // --- 栅格数据状态 ---
        rasters: [],           // 所有已上传/生成的影像元数据
        activeLayerIds: new Set(), // 当前地图上加载显示的栅格图层 ID
        loadingIds: new Set(),    // 正在处理/加载中的图层 ID
        selectedMergeIds: [],  // 波段合成功能中选中的影像 ID 序列

        // --- 矢量标注状态 ---
        projects: [],          // 所有矢量标注项目列表
        activeProject: null,   // 当前选中的项目对象
        vectorLayers: [],      // 当前项目下的所有矢量图层
        activeVectorLayerId: null, // 当前正在编辑/查看的矢量图层 ID
        currentFeatures: {     // 当前地图视口内加载的 GeoJSON 要素
            type: "FeatureCollection",
            features: []
        },
        drawColor: '#4f46e5',
        selectedFeatureId: null, // 存储当前被选中的要素 ID
    },

    // 监听回调
    onRastersChange: null,
    onVectorStateChange: null, // 矢量状态变化回调

    /**
     * 通知 UI 刷新矢量相关组件
     */
    notifyVectorChange() {
        if (this.onVectorStateChange) {
            this.onVectorStateChange({ ...this.state });
        }
    },


    setRasters(data) {
        this.state.rasters = data;
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
        // 切换项目时通常需要清空当前的图层列表和选中项
        this.state.vectorLayers = [];
        this.state.activeVectorLayerId = null;
        this.notifyVectorChange();
    },

    setVectorLayers(layers) {
        this.state.vectorLayers = layers;
        this.notifyVectorChange();
    },

    /**
     * 设置当前正在操作的矢量图层
     * @param {string|null} layerId
     */
    setActiveVectorLayer(layerId) {
        this.state.activeVectorLayerId = layerId;
        // 切换图层时重置要素缓存，等待 MapController 触发 BBox 加载
        this.state.currentFeatures = { type: "FeatureCollection", features: [] };
        this.notifyVectorChange();
    },


    /**
     * 更新当前视口的要素集合 (由 MapController 移动结束后调用)
     */
    setCurrentFeatures(featureCollection) {
        this.state.currentFeatures = featureCollection;
        this.notifyVectorChange();
    },

    /**
     * 局部更新：向当前集合添加单个新要素 (无需全量刷新)
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
    }
};
>>>>>>> bd05e13daabf3cba3f74fa7d9fbf6191d3065cfd
