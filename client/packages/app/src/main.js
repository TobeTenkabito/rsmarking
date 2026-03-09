import { MapEngine } from '../../core/src/map.js';
import { RasterAPI } from './api/raster.js';
import { VectorAPI } from './api/vector.js';
import { Store } from './store/index.js';
import { ModalComponent } from '../../ui/src/components/Modal.js';
import { ModalTemplates } from '../../ui/src/templates/Modals.js';

// 导入业务逻辑模块
import { MapController } from './modules/MapController.js';
import { AnalysisModule } from './modules/AnalysisModule.js';
import { ExtractionModule } from './modules/ExtractionModule.js';
import { AnnotationModule } from './modules/AnnotationModule.js';

/**
 * App Class - 系统调度中心
 */
class App {
    constructor() {
        this.mapEngine = null;
        this.mapController = null;
        this.analysis = null;
        this.extraction = null;
        this.annotation = null;
    }

    /**
     * 启动流程
     */
    async init() {
        try {
            // 1. 动态注入 HTML 骨架
            this.injectModals();

            // 2. 初始化核心引擎 (Leaflet)
            this.mapEngine = new MapEngine('map');

            // 3. 实例化子模块
            this.mapController = new MapController(this.mapEngine);
            this.analysis = new AnalysisModule(this);
            this.extraction = new ExtractionModule(this);

            // 🆕 整合 AnnotationModule
            this.annotation = new AnnotationModule(this);

            // 4. 建立桥梁并绑定事件 (关键：解决 ES6 Module 作用域隔离问题)
            this.mountGlobalBridge();
            this.bindEvents();

            // 5. 首次加载数据
            await this.refreshData();             // 加载栅格影像数据
            await this.refreshVectorProjects();   // 加载矢量项目数据

            console.log("%c[RSMarking] 🟢 系统初始化成功", "color: #6366f1; font-weight: bold;");
        } catch (error) {
            console.error("[App] ❌ 初始化流程中断:", error);
        }
    }

    /**
     * 注入弹窗骨架
     */
    injectModals() {
        const container = document.getElementById('modals-container');
        if (container) {
            container.innerHTML =
                ModalTemplates.indexModal +
                ModalTemplates.extractionModal +
                ModalTemplates.mergeModal;
        }
        const detailContainer = document.getElementById('detail-panel-container') || document.body;
        const detailDiv = document.createElement('div');
        detailDiv.innerHTML = ModalTemplates.detailPanel;
        detailContainer.appendChild(detailDiv);
    }

    /**
     * 暴露 RS 全局命名空间
     * 解决 HTML 中内联事件 (如 onclick="RS.xxx()") 无法访问 Module 内部方法的问题
     */
    mountGlobalBridge() {
        window.RS = {
            // --- 基础操作 ---
            fetchRasters: () => this.refreshData(),
            clearDatabase: () => this.handleClearDatabase(),

            // --- 指数分析 (使用可选链 ?. 增强健壮性) ---
            openIndexModal: (type) => this.analysis?.openModal(type),
            closeIndexModal: () => this.analysis?.closeModal(),
            executeIndexCalculation: () => this.analysis?.execute(),

            // --- 要素提取 ---
            openExtractionModal: (type) => this.extraction?.openModal(type),
            closeExtractionModal: () => this.extraction?.closeModal(),
            runExtraction: () => this.extraction?.run(),

            // --- 波段合成 ---
            openMergeModal: () => this.handleOpenMergeModal(),
            closeMergeModal: () => document.getElementById('merge-modal')?.classList.add('hidden'),
            executeMerge: () => this.handleExecuteMerge(),
            toggleMergeItem: (id) => this.handleToggleMergeSelection(id),

            // --- UI 辅助 ---
            hideDetail: () => document.getElementById('detail-panel')?.classList.add('hidden'),

            //  矢量标注系统接口
            createProject: () => this.handleCreateProject(),
            // 兼容 HTML <select onchange> 传递过来的字符串
            selectProject: (id) => this.handleSelectProject(id),
            createLayer: () => this.handleCreateLayer(),
            toggleVectorLayer: (id) => this.handleToggleVectorLayer(id),

            //  标注工具指令整合
            toggleEditMode: (enabled) => {
                if(this.annotation?.toggleEditMode) this.annotation.toggleEditMode(enabled);
            },
            setDrawMode: (mode) => this.handleSetDrawMode(mode),
            cancelDraw: () => this.handleCancelDraw(),
            setDrawColor: (color) => Store.setDrawColor(color),
            // 删除
            deleteSelectedFeature: () => this.handleDeleteSelectedFeature(),

            // 基础刷新
            refreshData: () => this.refreshData(),
        };
        // 监听要素选中事件并触发地图重绘以显示高亮
            window.addEventListener('inspect-feature', (e) => {
                const featureId = e.detail.id;
                if (!featureId) return;
                Store.setSelectedFeatureId(featureId);
                // 显示删除按钮
                const delBtn = document.getElementById('btn-delete-feature');
                if (delBtn) delBtn.classList.remove('hidden');
                // 触发地图重绘以显示高亮红框
                if (this.mapController) {
                    this.mapController.renderVectorData(Store.state.currentFeatures);
            }
        });
            // 监听地图空白处点击，取消选中状态
        if (this.mapEngine && this.mapEngine.map) {
            this.mapEngine.map.on('click', () => {
                if (Store.state.selectedFeatureId) {
                    Store.setSelectedFeatureId(null);
                    // 隐藏删除按钮
                    const delBtn = document.getElementById('btn-delete-feature');
                    if (delBtn) delBtn.classList.add('hidden');
                    // 撤销高亮红框
                    if (this.mapController) {
                        this.mapController.renderVectorData(Store.state.currentFeatures);
                    }
                }
            });
        }

    // 监听键盘 Delete / Backspace 键触发删除操作
    document.addEventListener('keydown', async (e) => {
        if ((e.key === 'Delete' || e.key === 'Backspace') && Store.state.selectedFeatureId) {
            const targetId = Store.state.selectedFeatureId;
            if (confirm('确认删除该标注？')) {
                try {
                    await VectorAPI.deleteFeature(targetId);
                    Store.setSelectedFeatureId(null);
                    await this.mapController.refreshVectorLayer(Store.state.activeVectorLayerId);
                } catch (err) {
                    console.error('删除失败', err);
                }
            }
        }
    });
    }

    /**
     * 统一绑定 DOM 事件
     */
    bindEvents() {
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

        document.getElementById('raster-upload-input')?.addEventListener('change', async (e) => {
            const file = e.target.files?.[0];
            if (!file) return;
            this.showGlobalLoader(true);
            try {
                await RasterAPI.upload(file);
                await this.refreshData();
            } catch (err) {
                alert(`上传失败: ${err.message}`);
            } finally {
                this.showGlobalLoader(false);
                e.target.value = ""; // 重置 input 允许重复上传同名文件
            }
        });
    }

    // 栅格影像业务逻辑
    async refreshData() {
        try {
            const data = await RasterAPI.fetchAll();
            Store.setRasters(data);
            this.mapController?.updateUI();
        } catch (err) {
            console.error("[App] 栅格数据更新失败:", err);
        }
    }

    async handleDelete(id) {
        if (!confirm("确定从工作站移除此影像？该操作不可恢复。")) return;
        await RasterAPI.delete(id);
        this.mapEngine?.removeLayer(id);
        Store.removeActiveLayer(id);
        await this.refreshData();
    }

    handleClearDatabase() {
        if (confirm("🚨 注意：这将清空所有存储的遥感数据，确定吗？")) {
            RasterAPI.clearDB().then(() => window.location.reload());
        }
    }

    handleOpenMergeModal() {
        Store.clearMergeSelection();
        const list = document.getElementById('merge-selection-list');
        if (list) {
            list.innerHTML = ModalComponent.renderMergeList(Store.state.rasters, []);
        }
        const btn = document.getElementById('confirm-merge-btn');
        if(btn) btn.disabled = true;
        document.getElementById('merge-modal')?.classList.remove('hidden');
    }

    handleToggleMergeSelection(id) {
        Store.toggleMergeSelection(id);
        const selectedIds = Store.getMergeSelection();
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
            document.getElementById('merge-modal')?.classList.add('hidden');
            await this.refreshData();
        } catch (e) {
            alert("合成失败，请检查波段兼容性");
        } finally {
            this.showGlobalLoader(false);
        }
    }

    showDetail(raster) {
        const panel = document.getElementById('detail-panel');
        if (!panel || !raster) return;
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

    // 矢量标注业务逻辑整合
    async refreshVectorProjects() {
        try {
            const projects = await VectorAPI.fetchProjects();
            Store.setProjects(projects);
        } catch (err) {
            console.error("[App] 矢量项目加载失败:", err);
        }
    }

    async handleCreateProject() {
        const name = prompt("请输入新矢量项目名称：", "默认标注项目");
        if (!name) return;

        this.showGlobalLoader(true);
        try {
            await VectorAPI.createProject(name);
            await this.refreshVectorProjects();
        } catch (e) {
            alert(`创建项目失败: ${e.message}`);
        } finally {
            this.showGlobalLoader(false);
        }
    }

    async handleSelectProject(projectId) {
        if (!projectId) {
            Store.setActiveProject(null);
            return;
        }
        // 注意：HTML select 下拉框传来的 projectId 可能是 string，使用 == 进行弱类型比对
        const proj = Store.state.projects.find(p => p.id == projectId);
        if (!proj) return;

        Store.setActiveProject(proj);
        this.showGlobalLoader(true);
        try {
            const layers = await VectorAPI.fetchLayers(proj.id);
            Store.setVectorLayers(layers);
        } catch (e) {
            console.error("[App] 加载矢量图层失败:", e);
            alert(`加载矢量图层失败: ${e.message}`);
        } finally {
            this.showGlobalLoader(false);
        }
    }

    async handleCreateLayer() {
        const activeProj = Store.state.activeProject;
        if (!activeProj) {
            alert("请先选择或创建一个矢量项目！");
            return;
        }

        const name = prompt("请输入新标注图层名称：", "建筑物标注");
        if (!name) return;

        // 尝试自动关联当前正在查看的栅格底图
        const activeRasters = Array.from(Store.state.activeLayerIds);
        const sourceRasterId = activeRasters.length > 0 ? activeRasters[0] : null;

        this.showGlobalLoader(true);
        try {
            await VectorAPI.createLayer(activeProj.id, name, sourceRasterId);
            // 创建成功后重新拉取该项目的图层列表
            await this.handleSelectProject(activeProj.id);
        } catch (e) {
            alert(`创建图层失败: ${e.message}`);
        } finally {
            this.showGlobalLoader(false);
        }
    }

    handleToggleVectorLayer(layerId) {
        if (this.mapController && typeof this.mapController.toggleVectorLayer === 'function') {
            this.mapController.toggleVectorLayer(layerId);
        } else {
            console.warn("[App] MapController.toggleVectorLayer 方法未找到，请确认是否已在 MapController 中实现。");
        }
    }

    /**
     * 🆕 设置绘图模式业务处理
     */
    handleSetDrawMode(mode) {
        // 校验：必须选中一个图层才能开始绘图
        if (!Store.state.activeVectorLayerId) {
            alert("请先在左侧选择或创建一个目标标注图层");
            return;
        }

        // 容错处理：确保 AnnotationModule 存在此方法
        if (this.annotation && typeof this.annotation.startDrawing === 'function') {
            this.annotation.startDrawing(mode);
        } else {
            console.warn("[App] 无法启动绘图: AnnotationModule.startDrawing 未找到。");
        }
    }

    /**
     * 🆕 取消绘图
     */
    handleCancelDraw() {
        if (this.annotation && typeof this.annotation.stopDrawing === 'function') {
            this.annotation.stopDrawing();
        }
    }

    // 具体删除逻辑实现
    async handleDeleteSelectedFeature() {
        const targetId = Store.state.selectedFeatureId;
        if (!targetId) return;
        if (confirm('确认删除该标注？')) {
            try {
                // 1. 调用后端接口删除
                await VectorAPI.deleteFeature(targetId);
                // 2. 清理前端选中状态
                Store.setSelectedFeatureId(null);
                const delBtn = document.getElementById('btn-delete-feature');
                if (delBtn) delBtn.classList.add('hidden');
                // 3. 重新拉取当前视口的最新数据，刷新地图
                if (this.mapController) {
                    await this.mapController.refreshVectorLayer(Store.state.activeVectorLayerId);
                }
            } catch (err) {
                console.error('删除失败', err);
                alert('删除失败，请检查网络或控制台');
            }
        }
    }
}

// 实例化应用
const app = new App();
window.addEventListener('load', () => app.init());