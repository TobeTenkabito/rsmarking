import { Store } from '../store/index.js';
import { RasterAPI } from '../api/raster.js';
import { VectorAPI} from "../api/vector.js";

export class GlobalEvents {
    constructor(app) {
        this.app = app;
    }

    bindAll() {
        this.bindDOMDelegation();
        this.bindCustomEvents();
        this.bindMapEvents();
        this.bindKeyboardEvents();
    }

    bindDOMDelegation() {
    // 栅格列表委托点击
    const listContainer = document.getElementById('raster-list');
    listContainer?.addEventListener('click', async (e) => {
        const item = e.target.closest('[data-id]');
        if (!item) return;
        const id = item.dataset.id;

        if (e.target.classList.contains('layer-checkbox')) {
            await this.app.mapController.toggleLayer(id);
        } else if (e.target.closest('.btn-delete')) {
            await this.app.raster.handleDelete(id);
        } else if (e.target.closest('.item-info')) {
            const raster = Store.state.rasters.find(r => r.id == id);
            this.app.ui.showDetail(raster);
            await this.app.mapController.focusLayer(id);
        }
    });

    // 上传文件监听
    document.getElementById('raster-upload-input')?.addEventListener('change', async (e) => {
        const file = e.target.files?.[0];
        if (!file) return;
        this.app.ui.showGlobalLoader(true);
        try {
            await RasterAPI.upload(file);
            await this.app.raster.refreshData();
        } catch (err) {
            alert(`上传失败: ${err.message}`);
        } finally {
            this.app.ui.showGlobalLoader(false);
            e.target.value = "";
        }
    });

    // 导入 Shapefile 监听
    document.getElementById('shapefile-upload-input')?.addEventListener('change', async (e) => {
        const files = e.target.files;
        if (!files || files.length === 0) return;

        // 校验必要文件
        const names = Array.from(files).map(f => f.name.toLowerCase());
        const required = ['.shp', '.shx', '.dbf'];
        const missing = required.filter(ext => !names.some(n => n.endsWith(ext)));
        if (missing.length > 0) {
            alert(`缺少必要文件：${missing.join(', ')}`);
            e.target.value = "";
            return;
        }

        // 此处存的是 projectId
        const projectId = document.getElementById('shapefile-upload-input').dataset.layerId;
        if (!projectId) {
            alert("请先选择目标项目");
            e.target.value = "";
            return;
        }

        // 用 .shp 文件名（去掉扩展名）作为图层名
        const shpFile = Array.from(files).find(f => f.name.toLowerCase().endsWith('.shp'));
        const layerName = shpFile ? shpFile.name.replace(/\.[^.]+$/, '') : 'imported_layer';

        this.app.ui.showGlobalLoader(true);
        try {
            const newLayer = await VectorAPI.createLayer(projectId, layerName);
            const result = await VectorAPI.importShapefile(newLayer.id, files);
            alert(`导入成功：${result.imported} 个要素，${result.fields_registered} 个字段`);
            await this.app.project.refreshProjects();
            const layers = await VectorAPI.fetchLayers(projectId);
            Store.setVectorLayers(layers)
            const attrTable = this.app?.attributeTable ?? window.app?.attributeTable;
            if (attrTable?.layerId === newLayer.id) {
                await attrTable.refresh();}
        } catch (err) {
            alert(`导入失败: ${err.message}`);
        }});
}

    bindCustomEvents() {
        window.addEventListener('inspect-feature', (e) => {
            const featureId = e.detail.id;
            if (!featureId) return;
            Store.setSelectedFeatureId(featureId);

            const delBtn = document.getElementById('btn-delete-feature');
            if (delBtn) delBtn.classList.remove('hidden');

            if (this.app.mapController) {
                this.app.mapController.renderVectorData(Store.state.currentFeatures);
            }
        });
        // 脚本编辑器快捷键
        document.addEventListener('keydown', (e) => {
            // Ctrl/Cmd + E 打开脚本编辑器
            if ((e.ctrlKey || e.metaKey) && e.key === 'e') {
                e.preventDefault();
                this.app.script?.openScriptEditor();
            }
            // 在脚本编辑器中，Ctrl/Cmd + Enter 执行脚本
            if ((e.ctrlKey || e.metaKey) && e.key === 'Enter') {
                const modal = document.getElementById('script-modal');
                if (modal && !modal.classList.contains('hidden')) {
                    e.preventDefault();
                    this.app.script?.executeScript();
                }
            }
        });
    }

    bindMapEvents() {
        if (this.app.mapEngine && this.app.mapEngine.map) {
            this.app.mapEngine.map.on('click', () => {
                if (Store.state.selectedFeatureId) {
                    Store.setSelectedFeatureId(null);
                    const delBtn = document.getElementById('btn-delete-feature');
                    if (delBtn) delBtn.classList.add('hidden');
                    if (this.app.mapController) {
                        this.app.mapController.renderVectorData(Store.state.currentFeatures);
                    }
                }
            });
        }
    }

    bindKeyboardEvents() {
        document.addEventListener('keydown', async (e) => {
            if ((e.key === 'Delete' || e.key === 'Backspace') && Store.state.selectedFeatureId) {
                await this.app.project.handleDeleteSelectedFeature();
            }
        });
    }
}