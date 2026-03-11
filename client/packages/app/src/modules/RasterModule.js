import { Store } from '../store/index.js';
import { RasterAPI } from '../api/raster.js';
import { ModalComponent } from '../../../ui/src/components/Modal.js';

export class RasterModule {
    constructor(app) {
        this.app = app;
    }

    async refreshData() {
        try {
            const data = await RasterAPI.fetchAll();
            Store.setRasters(data);
            this.app.mapController?.updateUI();
        } catch (err) {
            console.error("[RasterModule] 栅格数据更新失败:", err);
        }
    }

    async handleDelete(id) {
        if (!confirm("确定从工作站移除此影像？该操作不可恢复。")) return;
        await RasterAPI.delete(id);
        this.app.mapEngine?.removeLayer(id);
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
        if (btn) btn.disabled = true;
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

        this.app.ui.showGlobalLoader(true);
        try {
            await RasterAPI.mergeBands(ids.join(','), name);
            document.getElementById('merge-modal')?.classList.add('hidden');
            await this.refreshData();
        } catch (e) {
            alert("合成失败，请检查波段兼容性");
        } finally {
            this.app.ui.showGlobalLoader(false);
        }
    }
}