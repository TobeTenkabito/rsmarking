import { Store } from '../store/index.js';
import { VectorAPI } from '../api/vector.js';
import { SidebarComponent } from '../../../ui/src/components/Sidebar.js';

/**
 * MapController - 负责地图引擎与业务状态（Store/UI）的深度联动
 */
export class MapController {
    constructor(engine) {
        this.engine = engine;

        // 初始化地图事件监听
        this.initVectorEvents();

        // 1. 订阅栅格变化
        Store.onRastersChange = () => {
            this.updateUI();
        };

        // 2. 订阅矢量状态变化，实现数据驱动视图
        Store.onVectorStateChange = (state) => {
            this.handleVectorStateChange(state);
            this.updateUI(); // 矢量状态变化时同步更新侧边栏
        };
    }

    /**
     * 更新侧边栏 UI 与图层计数器
     */
    updateUI() {
        // 传递整个 Store.state 对象给 SidebarComponent
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
                activeVectorLayerId: Store.state.activeVectorLayerId,
                // 将图层可见性集合作为参数下发
                visibleVectorLayerIds: Store.state.visibleVectorLayerIds
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
        // UI 更新由 Store 的监听器触发，此处手动刷新确保即时性
        this.updateUI();
    }

    /**
     * 初始化地图矢量相关的事件监听
     */
    initVectorEvents() {
        const map = this.engine.map || this.engine;
        if (!map || !map.on) return;

        // 监听地图移动结束事件，动态加载当前视口的矢量标注 (BBox 加载策略)
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
        const visibleIds = Array.from(Store.state.visibleVectorLayerIds);
        if (visibleIds.length === 0) return;

        const map = this.engine.map || this.engine;
        let bbox = [];

        if (map.getBounds) {
            const bounds = map.getBounds();
            bbox = [bounds.getWest(), bounds.getSouth(), bounds.getEast(), bounds.getNorth()];
        } else if (map.getView && map.getView().calculateExtent) {
            bbox = map.getView().calculateExtent(map.getSize());
        }

        if (bbox.length === 4) {
            // 🆕 发起并发请求，拉取所有当前可见的图层数据
            const fetchPromises = visibleIds.map(async (layerId) => {
                try {
                    const data = await VectorAPI.fetchFeaturesInBbox(layerId, bbox);

                    // 仅将正在编辑的图层数据写回 Store 供其他业务(如高亮选中)使用
                    if (layerId === Store.state.activeVectorLayerId) {
                        Store.setCurrentFeatures(data);
                    }

                    // 传入真实的图层 ID 进行多实例渲染
                    this.renderVectorData(layerId, data);
                } catch (error) {
                    console.error(`[MapController] 图层 ${layerId} 视口加载失败:`, error);
                }
            });

            await Promise.all(fetchPromises);
        }
    }

    /**
     * 处理 Store 中矢量状态的变化通知
     * 适配 main.js 中暴露的 RS 全局变量
     */
    handleVectorStateChange(state) {
        // 核心逻辑：通知底层引擎同步当前的可见图层列表，清理掉被取消勾选的图层
        if (this.engine.syncVisibleLayers) {
            this.engine.syncVisibleLayers(Array.from(state.visibleVectorLayerIds));
        }
        // 联动 UI：如果没有激活的编辑图层，强制关闭编辑工具栏
        if (window.RS && window.RS.toggleEditMode) {
            window.RS.toggleEditMode(!!state.activeVectorLayerId);
        }
        // 触发并发数据拉取
        this.fetchViewportFeatures();
    }

    /**
     * 负责调用核心引擎接口，将 GeoJSON 渲染到地图上
     */
    renderVectorData(layerId, geojson) {
        if (this.engine.updateVectorLayer) {
            this.engine.updateVectorLayer(layerId, geojson, Store.state.selectedFeatureId);
        }
    }

    /**
    * 局部刷新特定的矢量图层数据（通常在标注保存或 AI 提取完成后调用）
    * @param {string} layerId
    */
    async refreshVectorLayer(layerId) {
        // 只要这个图层在地图上可见，发生数据变动时就刷新视口
        if (Store.state.visibleVectorLayerIds.has(layerId)) {
            await this.fetchViewportFeatures();
        }
    }
}
