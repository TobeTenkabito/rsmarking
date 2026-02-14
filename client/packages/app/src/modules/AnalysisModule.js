import { RasterAPI } from '../api/raster.js';
import { ModalComponent } from '../../../ui/src/components/Modal.js';
import { Store } from '../store/index.js';

/**
 * AnalysisModule - 负责光谱指数计算逻辑
 */
export class AnalysisModule {
    constructor(app) {
        this.app = app;
        this.currentType = null;
    }

    /**
     * 打开计算弹窗并动态生成波段选择器
     */
    openModal(type) {
        if (Store.state.rasters.length === 0) {
            alert("工作站暂无影像，请先上传数据");
            return;
        }

        this.currentType = type;
        const content = document.getElementById('index-content');
        const bar = document.getElementById('index-modal-bar');

        // 调用 UI 组件生成 HTML 内容
        content.innerHTML = ModalComponent.renderIndexConfig(type, Store.state.rasters);

        const themeColors = {
            'NDVI': '#10b981', // emerald
            'NDWI': '#3b82f6', // blue
            'NDBI': '#f59e0b', // amber
            'MNDWI': '#06b6d4' // cyan
        };

        if (bar) bar.style.backgroundColor = themeColors[type] || '#6366f1';
        document.getElementById('index-modal').classList.remove('hidden');
    }

    closeModal() {
        document.getElementById('index-modal').classList.add('hidden');
    }

    async execute() {
        const b1 = document.getElementById('index-b1-select').value;
        const b2 = document.getElementById('index-b2-select').value;
        const name = document.getElementById('index-name-input').value;

        if (!name) return alert("请输入结果图层名称");

        this.app.showGlobalLoader(true);
        try {
            let result;
            switch (this.currentType) {
                case 'NDVI': result = await RasterAPI.calculateNDVI(b1, b2, name); break;
                case 'NDWI': result = await RasterAPI.calculateNDWI(b1, b2, name); break;
                case 'NDBI': result = await RasterAPI.calculateNDBI(b1, b2, name); break;
                case 'MNDWI': result = await RasterAPI.calculateMNDWI(b1, b2, name); break;
            }
            this.closeModal();
            await this.app.refreshData(); // 刷新列表
        } catch (e) {
            alert(`空间运算失败: ${e.message}`);
        } finally {
            this.app.showGlobalLoader(false);
        }
    }
}
