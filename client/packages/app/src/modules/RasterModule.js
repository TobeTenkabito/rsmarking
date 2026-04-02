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


    handleOpenExtractModal() {
        Store.setExtractSource(null);
        Store.clearExtractSelection();

        // 渲染 Step 1 源文件列表
        const sourceList = document.getElementById('extract-source-list');
        if (sourceList) {
            sourceList.innerHTML = ModalComponent.renderExtractSourceList(Store.state.rasters, null);
        }

        // 重置到 Step 1 狀態
        document.getElementById('extract-step-1')?.classList.remove('hidden');
        document.getElementById('extract-step-2')?.classList.add('hidden');
        document.getElementById('extract-next-btn')?.classList.remove('hidden');
        document.getElementById('confirm-extract-btn')?.classList.add('hidden');
        document.getElementById('extract-back-btn')?.classList.add('hidden');
        document.getElementById('extract-back-placeholder')?.classList.remove('hidden');

        const nextBtn = document.getElementById('extract-next-btn');
        if (nextBtn) nextBtn.disabled = true;

        // 重置步驟指示器
        document.getElementById('extract-step-1-dot')?.classList.replace('bg-slate-200', 'bg-emerald-500');
        document.getElementById('extract-step-1-dot')?.classList.replace('text-slate-400', 'text-white');
        document.getElementById('extract-step-2-dot')?.classList.replace('bg-emerald-500', 'bg-slate-200');
        document.getElementById('extract-step-2-dot')?.classList.replace('text-white', 'text-slate-400');

        document.getElementById('extract-modal')?.classList.remove('hidden');
    }

    handleToggleExtractSelection(bandIndex) {
        Store.toggleExtractSelection(bandIndex);
        const selectedIndices = Store.getExtractSelection();

        const rasterId = Store.getExtractSource();
        const raster = Store.state.rasters.find(r => r.index_id === rasterId);
        const list = document.getElementById('extract-selection-list');
        if (list) {
            list.innerHTML = ModalComponent.renderExtractList(raster, selectedIndices);
        }

        const btn = document.getElementById('confirm-extract-btn');
        if (btn) btn.disabled = selectedIndices.length < 1;
    }

    async handleExecuteExtract() {
        const rasterId = Store.getExtractSource();
        const indices = Store.getExtractSelection();
        const name = prompt("请输入提取影像名称", `Extracted_Band_${Date.now()}`);
        if (!name) return;

        this.app.ui.showGlobalLoader(true);
        try {
            await RasterAPI.extractBands(rasterId, indices.join(','), name);
            document.getElementById('extract-modal')?.classList.add('hidden');
            await this.refreshData();
        } catch (e) {
            alert("提取失败，请检查波段索引是否合法");
        } finally {
            this.app.ui.showGlobalLoader(false);
        }
    }

    handleSelectExtractSource(rasterId) {
        Store.setExtractSource(rasterId);
        const rasters = Store.state.rasters;
        const sourceList = document.getElementById('extract-source-list');
        if (sourceList) {
            sourceList.innerHTML = ModalComponent.renderExtractSourceList(rasters, rasterId);
        }
        const nextBtn = document.getElementById('extract-next-btn');
        if (nextBtn) nextBtn.disabled = false;
    }

    handleExtractStepNext() {
        const rasterId = Store.getExtractSource();
        const raster = Store.state.rasters.find(r => r.index_id === rasterId);
        const list = document.getElementById('extract-selection-list');
        if (list) {
            list.innerHTML = ModalComponent.renderExtractList(raster, []);
        }

        document.getElementById('extract-step-1')?.classList.add('hidden');
        document.getElementById('extract-step-2')?.classList.remove('hidden');
        document.getElementById('extract-next-btn')?.classList.add('hidden');
        document.getElementById('confirm-extract-btn')?.classList.remove('hidden');
        document.getElementById('extract-back-btn')?.classList.remove('hidden');
        document.getElementById('extract-back-placeholder')?.classList.add('hidden');

        const confirmBtn = document.getElementById('confirm-extract-btn');
        if (confirmBtn) confirmBtn.disabled = true;

        document.getElementById('extract-step-1-dot')?.classList.replace('bg-emerald-500', 'bg-slate-200');
        document.getElementById('extract-step-1-dot')?.classList.replace('text-white', 'text-slate-400');
        document.getElementById('extract-step-2-dot')?.classList.replace('bg-slate-200', 'bg-emerald-500');
        document.getElementById('extract-step-2-dot')?.classList.replace('text-slate-400', 'text-white');
    }

    handleExtractStepBack() {
        Store.clearExtractSelection();
        const rasters = Store.state.rasters;
        const selectedId = Store.getExtractSource();
        const sourceList = document.getElementById('extract-source-list');
        if (sourceList) {
            sourceList.innerHTML = ModalComponent.renderExtractSourceList(rasters, selectedId);
        }

        document.getElementById('extract-step-2')?.classList.add('hidden');
        document.getElementById('extract-step-1')?.classList.remove('hidden');
        document.getElementById('confirm-extract-btn')?.classList.add('hidden');
        document.getElementById('extract-back-btn')?.classList.add('hidden');
        document.getElementById('extract-back-placeholder')?.classList.remove('hidden');
        document.getElementById('extract-next-btn')?.classList.remove('hidden');

        const nextBtn = document.getElementById('extract-next-btn');
        if (nextBtn) nextBtn.disabled = false;

        document.getElementById('extract-step-2-dot')?.classList.replace('bg-emerald-500', 'bg-slate-200');
        document.getElementById('extract-step-2-dot')?.classList.replace('text-white', 'text-slate-400');
        document.getElementById('extract-step-1-dot')?.classList.replace('bg-slate-200', 'bg-emerald-500');
        document.getElementById('extract-step-1-dot')?.classList.replace('text-slate-400', 'text-white');
    }
}