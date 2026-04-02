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
        selectedVectorLayerId: null, // 选中的矢量图层 ID
        visibleVectorLayerIds: new Set(), // 存储当前所有需要在地图上渲染的图层 ID
        currentFeatures: {     // 当前地图视口内加载的 GeoJSON 要素
            type: "FeatureCollection",
            features: []
        },
        drawColor: '#4f46e5',
        selectedFeatureId: null, // 存储当前被选中的要素 ID

        // --- 光譜查詢狀態 ---
        spectrumMode: false,       // 是否處於光譜拾取模式
        spectrumResult: null,      // 最近一次查詢結果 { bands, has_nodata, coordinate }
        spectrumRasterId: null,    // 當前綁定查詢的影像 index_id

        // --- 波段提取狀態 ---
        extractSourceId: null,       // 提取操作的源文件 index_id
        selectedExtractIndices: [],  // 已選中的波段索引列表 [1, 3, ...]
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
    // 独立设置编辑激活状态
    setActiveVectorLayer(layerId) {
        this.state.activeVectorLayerId = layerId;
        // 联动：激活编辑的图层必须保证是可见的
        if (layerId && !this.state.visibleVectorLayerIds.has(layerId)) {
            this.state.visibleVectorLayerIds.add(layerId);
        }
        this.state.currentFeatures = { type: "FeatureCollection", features: [] };
        this.notifyVectorChange();
    },

    setSelectedVectorLayerId(layerId) {
    this.state.selectedVectorLayerId = layerId;  // 正确写入 state
    this.notifyVectorChange();
    },

    removeVectorLayer(layerId) {
        this.state.vectorLayers = this.state.vectorLayers.filter(l => l.id !== layerId);
        this.state.visibleVectorLayerIds.delete(layerId);
        // 如果删的正好是当前激活图层，清空激活状态
        if (this.state.activeVectorLayerId === layerId) {
            this.state.activeVectorLayerId = null;
        }
        this.notifyVectorChange();  // ✅ 触发 onVectorStateChange → updateUI()
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
    },

    // 切换单个图层的地图可见性
    toggleVectorVisibility(layerId) {
        if (this.state.visibleVectorLayerIds.has(layerId)) {
            this.state.visibleVectorLayerIds.delete(layerId);
            // 容错：如果关闭显示的图层正好是正在编辑的图层，强制退出编辑模式
            if (this.state.activeVectorLayerId === layerId) {
                this.state.activeVectorLayerId = null;
            }
        } else {
            this.state.visibleVectorLayerIds.add(layerId);
        }
        this.notifyVectorChange();
    },

    /**
    * 重新从后端拉取最新栅格列表，并通知 UI 刷新
    * @param {Function} fetchFn  外部传入的 API 请求函数，返回 raster 数组
    *                            例：() => RasterAPI.getList()
    */
    async refreshRasters(fetchFn) {
        try {
            const data = await fetchFn();
            this.setRasters(data);
        } catch (err) {
            console.error('[Store] refreshRasters 失败:', err);
        }
    },

    /**
    * 重新从后端拉取最新矢量项目列表，并通知 UI 刷新
    * @param {Function} fetchFn  外部传入的 API 请求函数，返回 projects 数组
    *                            例：() => ProjectAPI.getList()
    */
    async refreshProjects(fetchFn) {
        try {
            const data = await fetchFn();
            this.setProjects(data);
        } catch (err) {
            console.error('[Store] refreshProjects 失败:', err);
        }
    },


    setSpectrumMode(enabled, rasterId = null) {
        this.state.spectrumMode = enabled;
        this.state.spectrumRasterId = rasterId;
        if (!enabled) this.state.spectrumResult = null;
        // 復用現有通知機制
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
