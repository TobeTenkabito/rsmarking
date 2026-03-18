import { Store } from '../store/index.js';
import { VectorAPI } from '../api/vector.js';
import { SidebarComponent } from '../../../ui/src/components/Sidebar.js';

/** 防抖工具函数 */
function debounce(fn, delay) {
    let timer = null;
    return function (...args) {
        clearTimeout(timer);
        timer = setTimeout(() => fn.apply(this, args), delay);
    };
}

/**
 * MapController - 负责地图引擎与业务状态（Store/UI）的深度联动
 */
export class MapController {
    constructor(engine) {
        this.engine = engine;

        /**
         * AbortController 注册表
         * Key: layerId, Value: AbortController
         * 用于在新请求发起时取消同一图层的上一次未完成请求
         */
        this._abortControllers = new Map();

        /**
         * 防抖版 fetchViewportFeatures
         * moveend 事件 300ms 内的连续触发只执行最后一次
         */
        this._debouncedFetch = debounce(() => this.fetchViewportFeatures(), 300);

        // 初始化地图事件监听
        this._boundMoveEndHandler = async () => {
            if (Store.state.visibleVectorLayerIds.size > 0) {
                this._debouncedFetch();
            }
        };
        this.initVectorEvents();

        Store.onRastersChange = () => {
            this.updateUI();
        };

        Store.onVectorStateChange = (state) => {
            this.handleVectorStateChange(state);
            this.updateUI();
        };
    }


    /**
     * 更新侧边栏 UI 与图层计数器
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
            counter.innerText = `已激活图层: ${totalActive}`;
        }

        const emptyHint = document.getElementById('empty-hint');
        if (emptyHint) {
            const isAllEmpty =
                Store.state.rasters.length === 0 &&
                Store.state.projects.length === 0;
            emptyHint.classList.toggle('hidden', !isAllEmpty);
        }
    }


    /**
     * 切换栅格图层显示状态
     */
    async toggleLayer(id) {
        const numericId = isNaN(id) ? id : Number(id);
        const raster = Store.state.rasters.find(r => r.id == numericId);

        if (!raster || !this.engine) return;
        if (Store.state.loadingIds.has(numericId)) return;

        if (Store.isLoaded(numericId)) {
            this.engine.removeLayer(raster.index_id || numericId);
            Store.removeActiveLayer(numericId);
        } else {
            Store.setLoading(numericId, true);
            this.updateUI();

            try {
                await this.engine.addGeoRasterLayer(raster);
                Store.addActiveLayer(numericId);
            } catch (err) {
                console.error('[MapController] 栅格渲染失败:', err);
            } finally {
                // 无论成功与否，都清除 loading 状态并刷新 UI
                Store.setLoading(numericId, false);
                this.updateUI();
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
     * 切换矢量图层的激活（编辑）状态
     * @param {string} layerId
     */
    async toggleVectorLayer(layerId) {
        if (Store.state.activeVectorLayerId === layerId) {
            Store.setActiveVectorLayer(null);
            this.renderVectorData(layerId, { type: 'FeatureCollection', features: [] });
        } else {
            Store.setActiveVectorLayer(layerId);
            // 激活后立即拉取当前视口数据
            await this.fetchViewportFeatures();
        }
        this.updateUI();
    }

    /**
     * 局部刷新特定矢量图层（标注保存或 AI 提取完成后调用）
     * @param {string} layerId
     */
    async refreshVectorLayer(layerId) {
        if (Store.state.visibleVectorLayerIds.has(layerId)) {
            await this.fetchViewportFeatures();
        }
    }


    /**
     * 初始化地图矢量相关的事件监听
     */
    initVectorEvents() {
        const map = this.engine.map || this.engine;
        if (!map?.on) return;

        map.on('moveend', this._boundMoveEndHandler);
    }

    /**
     * 销毁实例，清理所有事件监听与挂起请求（防止内存泄漏）
     * 在组件卸载或页面切换时调用
     */
    destroy() {
        const map = this.engine.map || this.engine;
        if (map?.off) {
            map.off('moveend', this._boundMoveEndHandler);
        }

        // 取消所有挂起的网络请求
        for (const controller of this._abortControllers.values()) {
            controller.abort();
        }
        this._abortControllers.clear();
    }


    /**
     * 获取当前视口的矢量要素并更新 Store 与地图
     * 核心优化：
     *   1. 每个 layerId 独立维护 AbortController，新请求自动取消旧请求
     *   2. 通过 signal 传递给 VectorAPI，避免过期响应污染状态
     */
    async fetchViewportFeatures() {
        const visibleIds = Array.from(Store.state.visibleVectorLayerIds);
        if (visibleIds.length === 0) return;

        const bbox = this._getMapBbox();
        if (!bbox) return;

        const fetchPromises = visibleIds.map(async (layerId) => {
            // 取消该图层上一次未完成的请求
            const prevController = this._abortControllers.get(layerId);
            if (prevController) prevController.abort();

            const controller = new AbortController();
            this._abortControllers.set(layerId, controller);

            try {
                const data = await VectorAPI.fetchFeaturesInBbox(
                    layerId,
                    bbox,
                    { signal: controller.signal }  // 传递取消信号
                );

                // 请求成功后清理注册表
                this._abortControllers.delete(layerId);

                // 仅将正在编辑的图层数据写回 Store
                if (layerId === Store.state.activeVectorLayerId) {
                    Store.setCurrentFeatures(data);
                }

                this.renderVectorData(layerId, data);
            } catch (err) {
                if (err.name === 'AbortError') {
                    // 请求被主动取消，属于正常流程，静默处理
                    return;
                }
                console.error(`[MapController] 图层 ${layerId} 视口加载失败:`, err);
            }
        });

        await Promise.all(fetchPromises);
    }


    /**
     * 处理 Store 中矢量状态的变化通知
     * 注意：此处不直接调用 fetchViewportFeatures，
     *       而是通过防抖调度，避免与 constructor 中的订阅回调产生重复请求
     */
    handleVectorStateChange(state) {
        // 通知底层引擎同步可见图层列表，清理已取消勾选的图层
        if (this.engine.syncVisibleLayers) {
            this.engine.syncVisibleLayers(Array.from(state.visibleVectorLayerIds));
        }

        // 联动编辑工具栏
        if (window.RS?.toggleEditMode) {
            window.RS.toggleEditMode(!!state.activeVectorLayerId);
        }

        // 使用防抖调度数据拉取，避免短时间内多次状态变更触发多次请求
        this._debouncedFetch();
    }


    /**
     * 从当前地图实例提取 BBox 数组 [west, south, east, north]
     * 兼容 Leaflet 与 OpenLayers
     * @returns {number[]|null}
     */
    _getMapBbox() {
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
     * 调用引擎接口将 GeoJSON 渲染到地图
     * @param {string} layerId
     * @param {Object} geojson
     */
    renderVectorData(layerId, geojson) {
        if (this.engine.updateVectorLayer) {
            this.engine.updateVectorLayer(layerId, geojson, Store.state.selectedFeatureId);
        }
    }
}