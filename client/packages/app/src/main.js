import { MapEngine } from '../../core/src/map.js';
import { RasterAPI } from './api/raster.js';
import { Store } from './store/index.js';
import { ModalComponent } from '../../ui/src/components/Modal.js';
import { ModalTemplates } from '../../ui/src/templates/Modals.js';

// 导入业务逻辑模块
import { MapController } from './modules/MapController.js';
import { AnalysisModule } from './modules/AnalysisModule.js';
import { ExtractionModule } from './modules/ExtractionModule.js';

/**
 * App Class - 系统调度中心
 */
class App {
    constructor() {
        this.mapController = null;
        this.analysis = null;
        this.extraction = null;
    }

    /**
     * 启动流程
     */
    async init() {
        try {
            // 1. 动态注入 HTML 骨架 (解耦 index.html)
            this.injectModals();

            // 2. 初始化核心引擎 (Leaflet)
            const engine = new MapEngine('map');

            // 3. 实例化子模块
            this.mapController = new MapController(engine);
            this.analysis = new AnalysisModule(this);
            this.extraction = new ExtractionModule(this);

            // 4. 建立桥梁并绑定事件
            this.mountGlobalBridge();
            this.bindEvents();

            // 5. 首次加载数据
            await this.refreshData();

            console.log("%c[RSMarking] 🟢 系统初始化成功", "color: #6366f1; font-weight: bold;");
        } catch (error) {
            console.error("[App] 初始化流程中断:", error);
        }
    }

    /**
     * 注入弹窗骨架，保持 index.html 简洁
     */
    injectModals() {
        const container = document.getElementById('modals-container');
        if (container) {
            container.innerHTML =
                ModalTemplates.indexModal +
                ModalTemplates.extractionModal +
                ModalTemplates.mergeModal;
        }
        // 详情面板注入
        const detailContainer = document.getElementById('detail-panel-container') || document.body;
        const detailDiv = document.createElement('div');
        detailDiv.innerHTML = ModalTemplates.detailPanel;
        detailContainer.appendChild(detailDiv);
    }

    /**
     * 暴露 RS 全局命名空间，解决模块化下的 HTML onclick 识别问题
     */
    mountGlobalBridge() {
        window.RS = {
            // 基础操作
            fetchRasters: () => this.refreshData(),
            clearDatabase: () => this.handleClearDatabase(),

            // 指数分析
            openIndexModal: (type) => this.analysis.openModal(type),
            closeIndexModal: () => this.analysis.closeModal(),
            executeIndexCalculation: () => this.analysis.execute(),

            // 要素提取
            openExtractionModal: (type) => this.extraction.openModal(type),
            closeExtractionModal: () => this.extraction.closeModal(),
            runExtraction: () => this.extraction.run(),

            // 波段合成
            openMergeModal: () => this.handleOpenMergeModal(),
            closeMergeModal: () => document.getElementById('merge-modal').classList.add('hidden'),
            executeMerge: () => this.handleExecuteMerge(),
            toggleMergeItem: (id) => this.handleToggleMergeSelection(id),

            // UI 辅助
            hideDetail: () => document.getElementById('detail-panel').classList.add('hidden')
        };
    }

    /**
     * 统一绑定 DOM 事件（使用委托机制）
     */
    bindEvents() {
        // 影像列表委托点击
        const listContainer = document.getElementById('raster-list');
        listContainer?.addEventListener('click', async (e) => {
            const item = e.target.closest('[data-id]');
            if (!item) return;
            const id = item.dataset.id;

            if (e.target.classList.contains('layer-checkbox')) {
                await this.mapController.toggleLayer(id);
            } else if (e.target.closest('.btn-delete')) {
                await this.handleDelete(id);
            } else if (e.target.closest('.item-info')) {
                const raster = Store.state.rasters.find(r => r.id == id);
                this.showDetail(raster);
                await this.mapController.focusLayer(id);
            }
        });

        // 文件上传
        document.getElementById('raster-upload-input')?.addEventListener('change', async (e) => {
            const file = e.target.files?.[0];
            if (!file) return;
            this.showGlobalLoader(true);
            try {
                await RasterAPI.upload(file);
                await this.refreshData();
            } finally {
                this.showGlobalLoader(false);
                e.target.value = "";
            }
        });
    }

    async refreshData() {
        try {
            const data = await RasterAPI.fetchAll();
            Store.setRasters(data);
            this.mapController.updateUI();
        } catch (err) {
            console.error("[App] 数据更新失败:", err);
        }
    }

    async handleDelete(id) {
        if (!confirm("确定从工作站移除此影像？该操作不可恢复。")) return;
        await RasterAPI.delete(id);
        this.mapController.engine.removeLayer(id);
        Store.removeActiveLayer(id);
        await this.refreshData();
    }

    handleClearDatabase() {
        if (confirm("🚨 注意：这将清空所有存储的遥感数据，确定吗？")) {
            RasterAPI.clearDB().then(() => window.location.reload());
        }
    }

    // 波段合成专有逻辑
    handleOpenMergeModal() {
        Store.clearMergeSelection();
        const list = document.getElementById('merge-selection-list');
        if (list) {
            list.innerHTML = ModalComponent.renderMergeList(Store.state.rasters, []);
        }
        document.getElementById('confirm-merge-btn').disabled = true;
        document.getElementById('merge-modal').classList.remove('hidden');
    }

    handleToggleMergeSelection(id) {
        Store.toggleMergeSelection(id);
        const selectedIds = Store.getMergeSelection();
        // 刷新列表显示
        const list = document.getElementById('merge-selection-list');
        if (list) list.innerHTML = ModalComponent.renderMergeList(Store.state.rasters, selectedIds);

        const btn = document.getElementById('confirm-merge-btn');
        if (btn) btn.disabled = selectedIds.length < 2;
    }

    async handleExecuteMerge() {
        const ids = Store.getMergeSelection();
        const name = prompt("请输入合成影像名称", `Stacked_Image_${Date.now()}`);
        if (!name) return;

        this.showGlobalLoader(true);
        try {
            await RasterAPI.mergeBands(ids.join(','), name);
            document.getElementById('merge-modal').classList.add('hidden');
            await this.refreshData();
        } catch (e) {
            alert("合成失败，请检查波段兼容性");
        } finally {
            this.showGlobalLoader(false);
        }
    }

    showDetail(raster) {
        const panel = document.getElementById('detail-panel');
        if (!panel) return;
        document.getElementById('detail-title').innerText = raster.file_name;
        document.getElementById('detail-content').innerHTML = ModalComponent.renderDetail(raster);
        panel.classList.remove('hidden');
    }

    showGlobalLoader(show) {
        const loader = document.getElementById('global-loader');
        if (loader) {
            show ? loader.classList.remove('hidden') : loader.classList.add('hidden');
        }
    }
}

// 实例化应用
const app = new App();
window.addEventListener('load', () => app.init());
