import { Store } from '../store/index.js';
import { ConversionAPI } from '../api/conversion.js';

/**
 * ConversionModule - 矢量转栅格功能模块
 *
 * 流程：
 *   Step 1 → 选择矢量图层 (来自 Store.state.vectorLayers)
 *   Step 2 → 选择参考栅格 (来自 Store.state.rasters) + 填写新名称
 *   执行   → 调用 ConversionAPI.vectorToRaster() → 刷新栅格列表
 *
 * 依赖：
 *   - app.ui.showGlobalLoader / showToast
 *   - app.raster.refreshData()          (刷新栅格侧边栏)
 *   - app.mapController.toggleLayer()   (可选：自动加载新栅格)
 */
export class ConversionModule {
    constructor(app) {
        this.app = app;

        // 内部状态：两步选择的暂存
        this._selectedLayerId  = null;
        this._selectedRefId    = null;   // 参考栅格的 index_id
    }

    /** 打开矢量转栅格 Modal，重置到 Step 1 */
    openModal() {
        const modal = document.getElementById('conversion-modal');
        if (!modal) return;

        // 直接从 Store 全量读取，不依赖任何激活状态
        const vectorLayers = Store.getVectorLayers?.() ?? Store.state.vectorLayers ?? [];

        // 重置内部状态
        this._selectedLayerId = null;
        this._selectedRefId   = null;

        this._renderStep1();
        this._goToStep(1);
        modal.classList.remove('hidden');
    }

    closeModal() {
        document.getElementById('conversion-modal')?.classList.add('hidden');
    }

    /** 用户点击某个矢量图层卡片 */
    handleSelectLayer(layerId) {
        this._selectedLayerId = layerId;

        // 高亮选中项
        document.querySelectorAll('[data-conversion-layer]').forEach(el => {
            const isActive = el.dataset.conversionLayer === layerId;
            el.classList.toggle('ring-2',           isActive);
            el.classList.toggle('ring-indigo-500',  isActive);
            el.classList.toggle('bg-indigo-50',     isActive);
        });

        const nextBtn = document.getElementById('conversion-next-btn');
        if (nextBtn) nextBtn.disabled = false;
    }

    /** Step 1 → Step 2 */
    handleStepNext() {
        if (!this._selectedLayerId) return;
        this._renderStep2();
        this._goToStep(2);
    }

    /** 用户点击某个参考栅格卡片 */
    handleSelectRef(indexId) {
        this._selectedRefId = indexId;

        document.querySelectorAll('[data-conversion-ref]').forEach(el => {
            const isActive = el.dataset.conversionRef === String(indexId);
            el.classList.toggle('ring-2',           isActive);
            el.classList.toggle('ring-emerald-500', isActive);
            el.classList.toggle('bg-emerald-50',    isActive);
        });

        this._updateConfirmBtn();
    }

    /** Step 2 → Step 1（返回） */
    handleStepBack() {
        this._selectedRefId = null;
        this._renderStep1();
        this._goToStep(1);

        // 恢复上一步的选中高亮
        if (this._selectedLayerId) {
            document.querySelectorAll('[data-conversion-layer]').forEach(el => {
                const isActive = el.dataset.conversionLayer === this._selectedLayerId;
                el.classList.toggle('ring-2',           isActive);
                el.classList.toggle('ring-indigo-500',  isActive);
                el.classList.toggle('bg-indigo-50',     isActive);
            });
        }
    }

    /** 名称输入框变化时实时校验确认按钮 */
    handleNameInput() {
        this._updateConfirmBtn();
    }

    async handleExecute() {
        const layerId  = this._selectedLayerId;
        const refId    = this._selectedRefId;
        const nameInput = document.getElementById('conversion-name-input');
        const newName  = nameInput?.value?.trim();

        if (!layerId || !refId || !newName) {
            this.app.ui.showToast('请完整填写所有参数', 'warning');
            return;
        }

        this.closeModal();
        this.app.ui.showGlobalLoader(true);

        try {
            const result = await ConversionAPI.vectorToRaster(layerId, refId, newName);
            console.log('[ConversionModule] 栅格化完成:', result);

            // 刷新栅格列表
            await this.app.raster?.refreshData();

            // 可选：自动将新栅格加载到地图
            const newRasterId = result?.id ?? result?.index_id;
            if (newRasterId && this.app.mapController) {
                await this.app.mapController.toggleLayer(newRasterId);
            }

            this.app.ui.showToast(`栅格化完成，新影像「${newName}」已生成`, 'success');
        } catch (err) {
            console.error('[ConversionModule] 矢量转栅格失败:', err);
            this.app.ui.showToast(`转换失败：${err.message}`, 'error');
        } finally {
            this.app.ui.showGlobalLoader(false);
        }
    }

    _renderStep1() {
        const container = document.getElementById('conversion-step-1-list');
        if (!container) return;
        container.innerHTML = this._buildLayerList(Store.state.vectorLayers);
    }

    _renderStep2() {
        // 参考栅格列表
        const refContainer = document.getElementById('conversion-step-2-ref-list');
        if (refContainer) {
            refContainer.innerHTML = this._buildRefList(Store.state.rasters);
        }

        // 默认名称：以选中图层名为前缀
        const layer = Store.state.vectorLayers.find(l => l.id === this._selectedLayerId);
        const nameInput = document.getElementById('conversion-name-input');
        if (nameInput) {
            nameInput.value = `${layer?.name ?? 'vector'}_rasterized_${Date.now()}`;
        }

        // 重置确认按钮
        const confirmBtn = document.getElementById('conversion-confirm-btn');
        if (confirmBtn) confirmBtn.disabled = true;
    }

    /**
     * 切换步骤的显隐与步骤指示器样式
     * @param {1|2} step
     */
    _goToStep(step) {
        // 面板显隐
        document.getElementById('conversion-step-1')?.classList.toggle('hidden', step !== 1);
        document.getElementById('conversion-step-2')?.classList.toggle('hidden', step !== 2);

        // 底部按钮组
        document.getElementById('conversion-next-btn')?.classList.toggle('hidden',    step !== 1);
        document.getElementById('conversion-confirm-btn')?.classList.toggle('hidden', step !== 2);
        document.getElementById('conversion-back-btn')?.classList.toggle('hidden',    step !== 2);

        // 步骤指示器
        this._setStepDot('conversion-step-1-dot', step === 1);
        this._setStepDot('conversion-step-2-dot', step === 2);

        // Step 1 的 Next 按钮：若已选则可用
        if (step === 1) {
            const nextBtn = document.getElementById('conversion-next-btn');
            if (nextBtn) nextBtn.disabled = !this._selectedLayerId;
        }
    }

    _setStepDot(id, active) {
        const el = document.getElementById(id);
        if (!el) return;
        el.classList.toggle('bg-indigo-500', active);
        el.classList.toggle('text-white',    active);
        el.classList.toggle('bg-slate-200',  !active);
        el.classList.toggle('text-slate-400', !active);
    }

    _updateConfirmBtn() {
        const nameInput = document.getElementById('conversion-name-input');
        const hasName   = nameInput?.value?.trim().length > 0;
        const confirmBtn = document.getElementById('conversion-confirm-btn');
        if (confirmBtn) confirmBtn.disabled = !(this._selectedRefId && hasName);
    }


    _buildLayerList(layers) {
        if (!layers.length) {
            return `<p class="text-sm text-slate-400 text-center py-6">当前项目暂无矢量图层</p>`;
        }
        return layers.map(layer => `
            <div
                data-conversion-layer="${layer.id}"
                class="flex items-center gap-3 p-3 rounded-lg border border-slate-200
                       cursor-pointer hover:bg-indigo-50 hover:border-indigo-300 transition-all"
                onclick="RS.handleConversionSelectLayer('${layer.id}')"
            >
                <span class="w-2 h-2 rounded-full bg-indigo-400 flex-shrink-0"></span>
                <div class="flex-1 min-w-0">
                    <p class="text-sm font-medium text-slate-700 truncate">${layer.name ?? layer.id}</p>
                    <p class="text-xs text-slate-400">${layer.feature_count ?? '?'} 个要素</p>
                </div>
            </div>
        `).join('');
    }

    _buildRefList(rasters) {
        if (!rasters.length) {
            return `<p class="text-sm text-slate-400 text-center py-6">暂无可用参考栅格</p>`;
        }
        return rasters.map(r => `
            <div
                data-conversion-ref="${r.index_id}"
                class="flex items-center gap-3 p-3 rounded-lg border border-slate-200
                       cursor-pointer hover:bg-emerald-50 hover:border-emerald-300 transition-all"
                onclick="RS.handleConversionSelectRef(${r.index_id})"
            >
                <span class="w-2 h-2 rounded-full bg-emerald-400 flex-shrink-0"></span>
                <div class="flex-1 min-w-0">
                    <p class="text-sm font-medium text-slate-700 truncate">${r.name ?? r.index_id}</p>
                    <p class="text-xs text-slate-400">${r.width ?? '?'} × ${r.height ?? '?'} px
                       · ${r.crs ?? 'CRS未知'}</p>
                </div>
            </div>
        `).join('');
    }
}
