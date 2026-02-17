import { Store } from '../store/index.js';
import { SidebarComponent } from '../../../ui/src/components/Sidebar.js';

/**
 * MapController - 负责地图引擎与业务状态（Store/UI）的深度联动
 */
export class MapController {
    constructor(engine) {
        this.engine = engine;
    }

    /**
     * 更新侧边栏 UI 与图层计数器
     */
    updateUI() {
        const container = document.getElementById('raster-list');
        if (container) {
            // 使用 SidebarComponent 渲染列表
            container.innerHTML = SidebarComponent.render(
                Store.state.rasters,
                Store.state.activeLayerIds,
                Store.state.loadingIds
            );
        }

        const counter = document.getElementById('layer-counter');
        if (counter) {
            counter.innerText = `已载入图层: ${Store.state.activeLayerIds.size}`;
        }

        // 处理空状态显示
        const emptyHint = document.getElementById('empty-hint');
        if (emptyHint) {
            Store.state.rasters.length === 0 ?
                emptyHint.classList.remove('hidden') :
                emptyHint.classList.add('hidden');
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
                console.error("[MapController] 渲染失败:", err);
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
}
