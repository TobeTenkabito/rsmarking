import { MapEngine } from '../../core/src/map.js';
import { RasterAPI } from './api/raster.js';
import { Store } from './store/index.js';
import { SidebarComponent } from '../../ui/src/components/Sidebar.js';
import { ModalComponent } from '../../ui/src/components/Modal.js';

class App {
    constructor() {
        this.selectedForMerge = [];
        this.engine = null;
        console.log("%c[App] 🏗️ 构造函数调用完成", "color: #6366f1; font-weight: bold;");
    }

    async init() {
        console.group("%c[App] 🚀 开始初始化流程", "color: #6366f1; font-size: 12px; font-weight: bold;");

        try {
            const mapContainer = document.getElementById('map');
            if (mapContainer) {
                this.engine = new MapEngine('map');
                console.log("%c[App] 🗺️ MapEngine 实例已在 #map 容器上成功创建", "color: #10b981;");
            } else {
                console.warn("[App] ⚠️ 找不到地图容器 #map，跳过引擎初始化");
            }

            console.log("[App] 🔗 正在绑定 UI 事件、全局指令和列表监听器...");
            this.bindUploadEvent();
            this.bindGlobalCommands();
            this.bindListEvents();

            console.log("[App] 📥 正在请求后端初始数据列表...");
            await this.refreshData();

            console.log("%c[App] ✨ 初始化完全成功，应用已就绪", "color: #10b981; font-weight: bold;");
        } catch (error) {
            console.error("%c[App] ❌ 初始化过程中发生异常:", "color: #ef4444; font-weight: bold;", error);
        }
        console.groupEnd();
    }

    bindUploadEvent() {
        const uploadInput = document.getElementById('raster-upload-input');
        if (!uploadInput) {
            console.warn("[App] ⚠️ 未找到上传输入框元素 #raster-upload-input");
            return;
        }

        console.log("[App] ✅ 成功挂载上传事件监听器 (change)");

        uploadInput.addEventListener('change', async (event) => {
            const file = event.target.files ? event.target.files[0] : null;
            if (!file) return;

            console.group(`%c[Upload] 🛰️ 处理新文件: ${file.name}`, "color: #f59e0b; font-weight: bold;");
            console.log(`[Upload] 大小: ${(file.size / 1024 / 1024).toFixed(2)} MB`);

            const loader = document.getElementById('global-loader');
            try {
                if (loader) loader.classList.remove('hidden');

                // 调用 API
                console.log("[Upload] ⬆️ 发起 XHR 上传请求...");
                await RasterAPI.upload(file, null, (p) => {
                    console.log(`%c[Upload] ⏳ 进度: ${p.toFixed(2)}%`, "color: #3b82f6;");
                });

                console.log("%c[Upload] ✅ 上传完成，正在刷新列表...", "color: #10b981;");
                await this.refreshData();
                alert("影像上传成功！");
            } catch (err) {
                console.error("[Upload] ❌ 失败:", err);
                alert("上传失败: " + err.message);
            } finally {
                if (loader) loader.classList.add('hidden');
                event.target.value = "";
                console.groupEnd();
            }
        });
    }
    async refreshData() {
        console.log("[Data] 🔄 正在从 API 刷新影像列表...");
        try {
            const data = await RasterAPI.fetchAll();
            console.log(`[Data] 📦 收到 ${data.length} 条记录`);

            if (Store && typeof Store.setRasters === 'function') {
                Store.setRasters(data);
                console.log("[Data] 💾 Store 状态已更新");
            }
            this.updateUI();
        } catch (err) {
            console.error("[Data] ❌ 刷新失败:", err);
        }
    }

    updateUI() {
        const container = document.getElementById('raster-list');
        if (!container) return;

        console.log("[UI] 🖌️ 正在重新渲染列表容器...");
        if (SidebarComponent && Store) {
            container.innerHTML = SidebarComponent.render(
                Store.state.rasters,
                Store.state.activeLayerIds,
                Store.state.loadingIds
            );
        }

        const counter = document.getElementById('layer-counter');
        if (counter && Store) {
            counter.innerText = `已载入图层: ${Store.state.activeLayerIds.size}`;
        }
    }

    bindGlobalCommands() {
        const app = this;
        console.log("[App] 🛠️ 绑定全局指令 (window.fetchRasters, etc.)");

        window.fetchRasters = () => {
            console.log("[Command] 手动触发列表刷新");
            app.refreshData();
        };

        window.clearDatabase = async () => {
            console.log("[Command] ⚠️ 尝试清空数据库...");
            if (confirm("确定要清空数据库并重置系统吗？此操作不可逆。")) {
                try {
                    await RasterAPI.clearDB();
                    console.log("[Command] ✅ 数据库已清空，页面准备重载");
                    window.location.reload();
                } catch (e) {
                    console.error("[Command] ❌ 清除失败:", e);
                }
            }
        };

        window.openNDVIModal = () => {
            console.log("[Command] 📊 打开 NDVI 计算面板");
            if (!Store || Store.state.rasters.length < 1) return alert("数据库中暂无影像，请先上传数据");
            const options = ModalComponent.renderSelectOptions(Store.state.rasters);
            document.getElementById('ndvi-red-select').innerHTML = options;
            document.getElementById('ndvi-nir-select').innerHTML = options;
            document.getElementById('ndvi-modal').classList.remove('hidden');
        };

        window.closeNDVIModal = () => document.getElementById('ndvi-modal').classList.add('hidden');

        window.executeNDVI = async () => {
            const redId = document.getElementById('ndvi-red-select').value;
            const nirId = document.getElementById('ndvi-nir-select').value;
            const name = document.getElementById('ndvi-name-input').value || `NDVI_${Date.now()}.tif`;

            console.log(`[Process] 🧮 启动 NDVI 计算: Red=${redId}, NIR=${nirId}, Name=${name}`);
            const btn = document.getElementById('execute-ndvi-btn');
            const originalText = btn ? btn.innerText : "确定";
            if (btn) {
                btn.disabled = true;
                btn.innerText = "计算中...";
            }

            try {
                await RasterAPI.calculateNDVI(redId, nirId, name);
                console.log("[Process] ✅ NDVI 计算成功，结果已保存为新影像");
                window.closeNDVIModal();
                await app.refreshData();
            } catch (e) {
                console.error("[Process] ❌ NDVI 失败:", e);
                alert("NDVI 计算失败");
            } finally {
                if (btn) {
                    btn.disabled = false;
                    btn.innerText = originalText;
                }
            }
        };

        window.openMergeModal = () => {
            console.log("[Command] 🎨 打开波段合成面板");
            app.selectedForMerge = [];
            app.updateMergeModalUI();
            document.getElementById('merge-modal').classList.remove('hidden');
        };

        window.closeMergeModal = () => document.getElementById('merge-modal').classList.add('hidden');

        window.executeMerge = async () => {
            console.log("[Process] 📦 准备合成波段:", app.selectedForMerge);
            if (app.selectedForMerge.length < 2) return alert("请至少选择两个波段进行合成");
            const name = prompt("请输入合成后的新影像名称", `Merged_${Date.now()}.tif`);
            if (!name) return;

            try {
                await RasterAPI.mergeBands(app.selectedForMerge.join(','), name);
                console.log("[Process] ✅ 合成成功");
                window.closeMergeModal();
                await app.refreshData();
            } catch (e) {
                console.error("[Process] ❌ 合成失败:", e);
                alert("合成失败");
            }
        };

        window.hideDetail = () => {
            console.log("[UI] 关闭详情面板");
            const panel = document.getElementById('detail-panel');
            if (panel) panel.classList.add('hidden');
        };
    }

    bindListEvents() {
        const listContainer = document.getElementById('raster-list');
        if (!listContainer) return;

        console.log("[App] ✅ 列表容器事件委托已绑定 (Click)");

        listContainer.addEventListener('click', async (e) => {
            const item = e.target.closest('[data-id]');
            if (!item) return;
            const id = parseInt(item.dataset.id);

            if (e.target.classList.contains('layer-checkbox')) {
                console.log(`[Interact] 🔘 切换图层显示状态: ID=${id}`);
                await this.handleToggle(id);
            } else if (e.target.closest('.btn-delete')) {
                console.log(`[Interact] 🗑️ 请求删除影像: ID=${id}`);
                await this.handleDelete(id);
            } else if (e.target.closest('.item-info')) {
                console.log(`[Interact] ℹ️ 点击影像信息: ID=${id}`);
                await this.handleFocus(id);
            }
        });

        const mergeList = document.getElementById('merge-selection-list');
        if (mergeList) {
            mergeList.addEventListener('click', (e) => {
                const item = e.target.closest('[data-merge-id]');
                if (!item) return;

                const id = parseInt(item.dataset.mergeId);
                const index = this.selectedForMerge.indexOf(id);

                if (index > -1) {
                    this.selectedForMerge.splice(index, 1);
                } else {
                    this.selectedForMerge.push(id);
                }
                console.log("[Process] 当前合成选择序列:", this.selectedForMerge);
                this.updateMergeModalUI();
            });
        }
    }

    async handleToggle(id) {
        const raster = Store.state.rasters.find(r => r.id === id);
        if (!raster || !this.engine) return;

        if (Store.state.activeLayerIds.has(id)) {
            console.log(`[Map] ➖ 移除地图图层: ${raster.index_id} (ID: ${id})`);
            this.engine.removeLayer(raster.index_id);

            Store.removeActiveLayer(id);
        } else {
            console.log(`[Map] ➕ 添加图层到地图: ${raster.index_id}...`);
            Store.setLoading(id, true);
            this.updateUI();
            try {
                await this.engine.addGeoRasterLayer(raster);
                Store.addActiveLayer(id);
                console.log(`[Map] ✅ 图层 ${id} 已加载`);
            } catch (err) {
                console.error(`[Map] ❌ 加载图层 ${id} 失败`, err);
            } finally {
                Store.setLoading(id, false);
            }
        }
        this.updateUI();
    }

    async handleFocus(id) {
        const raster = Store.state.rasters.find(r => r.id === id);
        if (!raster) return;

        console.log(`[UI] 🔍 聚焦影像: ${raster.file_name}`);
        const panel = document.getElementById('detail-panel');
        const title = document.getElementById('detail-title');
        const content = document.getElementById('detail-content');

        if (title) title.innerText = raster.file_name || '影像详情';
        if (content && ModalComponent) content.innerHTML = ModalComponent.renderDetail(raster);
        if (panel) panel.classList.remove('hidden');
        if (!Store.state.activeLayerIds.has(id)) {
            await this.handleToggle(id);
        }

        if (this.engine) {
            console.log("[Map] 🎯 自动缩放至影像范围:", raster.index_id);
            this.engine.fitLayer(raster.index_id, raster.bounds || raster.extent);
        }
    }

    async handleDelete(id) {
        if (!confirm("确定要删除吗？此操作不可逆。")) return;
        try {
            console.log(`[API] 正在请求后端删除资源 ID: ${id}`);
            await RasterAPI.delete(id);
            if (Store.state.activeLayerIds.has(id) && this.engine) {
                this.engine.removeLayer(id);
                Store.removeActiveLayer(id);
            }
            console.log("[API] ✅ 删除成功，更新列表");
            await this.refreshData();
        } catch (e) {
            console.error("[API] ❌ 删除失败:", e);
            alert("删除失败");
        }
    }

    updateMergeModalUI() {
        const list = document.getElementById('merge-selection-list');
        if (list && ModalComponent) {
            list.innerHTML = ModalComponent.renderMergeList(Store.state.rasters, this.selectedForMerge);
        }
        const btn = document.getElementById('confirm-merge-btn');
        if (btn) {
            btn.disabled = this.selectedForMerge.length < 2;
        }
    }
}

const app = new App();
document.addEventListener('DOMContentLoaded', () => {
    app.init().catch(err => console.error("%c[App] 🚨 致命启动崩溃:", "color: white; background: red; padding: 4px;", err));
});