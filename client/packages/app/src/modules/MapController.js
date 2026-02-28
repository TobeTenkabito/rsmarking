import { Store } from '../store/index.js';
import { VectorAPI } from '../api/vector.js';
import { SidebarComponent } from '../../../ui/src/components/Sidebar.js';

/**
 * MapController - 负责地图引擎与业务状态（Store/UI）的深度联动
 */
export class MapController {
    constructor(engine) {
        this.engine = engine;

        // 初始化地图事件监听 (如视口移动)
        this.initVectorEvents();

        // 1. 订阅栅格变化 (原有)
        Store.onRastersChange = () => {
            this.updateUI();
        };

        // 2. 订阅矢量状态变化 (新增)，实现数据驱动视图
        Store.onVectorStateChange = (state) => {
            this.handleVectorStateChange(state);
            this.updateUI(); // 矢量状态变化时同步更新侧边栏
        };
    }

    /**
     * 更新侧边栏 UI 与图层计数器
     */
    updateUI() {
        // 关键修改：传递整个 Store.state 对象给 SidebarComponent
        const container = document.getElementById('sidebar-content') || document.getElementById('raster-list');
        if (container) {
            container.innerHTML = SidebarComponent.render({
                rasters: Store.state.rasters,
                activeLayerIds: Store.state.activeLayerIds,
                loadingIds: Store.state.loadingIds,

                // 传入矢量相关状态
                projects: Store.state.projects,
                activeProject: Store.state.activeProject,
                vectorLayers: Store.state.vectorLayers,
                activeVectorLayerId: Store.state.activeVectorLayerId
            });
        }

        const counter = document.getElementById('layer-counter');
        if (counter) {
            // 统计总活跃图层 (栅格 Set 长度 + 矢量是否激活)
            const totalActive = Store.state.activeLayerIds.size + (Store.state.activeVectorLayerId ? 1 : 0);
            counter.innerText = `已激活图层: ${totalActive}`;
        }

        // 处理空状态显示 (当栅格和矢量项目都为空时显示提示)
        const emptyHint = document.getElementById('empty-hint');
        if (emptyHint) {
            const isAllEmpty = Store.state.rasters.length === 0 && Store.state.projects.length === 0;
            isAllEmpty ? emptyHint.classList.remove('hidden') : emptyHint.classList.add('hidden');
        }
    }
    /**
     * 切换图层显示状态
     */
    async toggleLayer(id) {
        const numericId = isNaN(id) ? id : Number(id);
        const raster = Store.state.rasters.find(r => r.id == numericId);

        if (!raster || !this.engine) return;
        if (Store.state.loadingIds.has(numericId)) return;

        if (Store.isLoaded(numericId)) {
            // 移除图层
            this.engine.removeLayer(raster.index_id || numericId);
            Store.removeActiveLayer(numericId);
        } else {
            // 添加图层
            Store.setLoading(numericId, true);
            this.updateUI();

            try {
                await this.engine.addGeoRasterLayer(raster);
                Store.addActiveLayer(numericId);
            } catch (err) {
                console.error("[MapController] 栅格渲染失败:", err);
            } finally {
                Store.setLoading(numericId, false);
            }
        }
        this.updateUI();
    }

    /**
     * 聚焦并缩放到指定图层
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
     * 切换矢量图层的激活状态
     * @param {string} layerId 矢量图层 ID
     */
    async toggleVectorLayer(layerId) {
        if (Store.state.activeVectorLayerId === layerId) {
            // 取消激活：清空 Store 和 地图上的渲染
            Store.setActiveVectorLayer(null);
            this.renderVectorData({ type: "FeatureCollection", features: [] });
        } else {
            // 激活新图层：通过 Store 更新 ID
            Store.setActiveVectorLayer(layerId);
            // 立即尝试加载当前视野内的要素
            await this.fetchViewportFeatures();
        }
        // UI 更新由 Store 的监听器 handleVectorStateChange 触发，此处调用 updateUI 以确保复选框状态同步
        this.updateUI();
    }

    /**
     * 初始化地图矢量相关的事件监听
     */
    initVectorEvents() {
        const map = this.engine.map || this.engine;
        if (!map || !map.on) return;

        // 监听地图移动结束事件，动态加载当前视口的矢量标注
        map.on('moveend', async () => {
            if (Store.state.activeVectorLayerId) {
                await this.fetchViewportFeatures();
            }
        });
    }

    /**
     * 核心逻辑：获取当前视口的矢量要素并更新 Store 与地图
     */
    async fetchViewportFeatures() {
        const layerId = Store.state.activeVectorLayerId;
        if (!layerId) return;

        const map = this.engine.map || this.engine;
        let bbox = [];

        // 兼容不同地图引擎的边界获取方式
        if (map.getBounds) {
            const bounds = map.getBounds();
            bbox = [bounds.getWest(), bounds.getSouth(), bounds.getEast(), bounds.getNorth()];
        } else if (map.getView && map.getView().calculateExtent) {
            bbox = map.getView().calculateExtent(map.getSize());
        }

        if (bbox.length === 4) {
            try {
                // 调用 API 获取 GeoJSON 数据
                const data = await VectorAPI.fetchFeaturesInBbox(layerId, bbox);

                // 更新 Store 状态，自动触发通知
                Store.setCurrentFeatures(data);

                // 将数据同步推送到地图引擎
                this.renderVectorData(data);
            } catch (error) {
                console.error("[MapController] 视口矢量加载失败:", error);
            }
        }
    }

    /**
     * 处理 Store 中矢量状态的变化通知
     */
    handleVectorStateChange(state) {
        // 如果当前没有任何激活的矢量图层，确保地图清除旧的残留
        if (!state.activeVectorLayerId) {
            this.renderVectorData({ type: "FeatureCollection", features: [] });
        }
    }

    /**
     * 负责调用核心引擎接口，将 GeoJSON 渲染到地图上
     */
    renderVectorData(geojson) {
        if (this.engine.updateVectorLayer) {
            this.engine.updateVectorLayer('annotation-layer', geojson);
            return;
        }

        // 降级处理
        const map = this.engine.map || this.engine;
        if (map && map.getSource && map.getSource('annotation-source')) {
            map.getSource('annotation-source').setData(geojson);
        }
    }

    /**
    * 局部刷新特定的矢量图层数据（通常在标注保存后调用）
    * @param {string} layerId
    */
    async refreshVectorLayer(layerId) {
        // 只有当刷新的图层是当前激活图层时才执行
        if (Store.state.activeVectorLayerId === layerId) {
            await this.fetchViewportFeatures();
        }
    }
}
