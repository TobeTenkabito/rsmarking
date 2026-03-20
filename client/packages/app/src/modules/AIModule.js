import { AIAPI } from '../api/ai.js';
import { Store } from '../store/index.js';
import { ModalComponent } from '../../../ui/src/components/Modal.js';
import { SidebarComponent } from '../../../ui/src/components/Sidebar.js';

export class AIModule {
    constructor(app) {
        this.app = app;

        // 当前 AI 任务的暂存状态
        // 用于"新建 vs 覆盖"二次确认流程
        this._pendingPayload = null;
        this._pendingResult  = null;
    }

    openModal() {
        const modal = document.getElementById('ai-modal');
        if (!modal) return;

        // 用 Store 中的栅格/矢量数据填充目标选择下拉框
        const rasters = Store.getRasters();
        const Layers = Store.getVectorLayers();
        document.getElementById('ai-target-select').innerHTML =
            ModalComponent.renderAITargetOptions(rasters, Layers);

        modal.classList.remove('hidden');
    }

    closeModal() {
        document.getElementById('ai-modal')?.classList.add('hidden');
        this._resetState();
    }

    async execute() {
        const targetId  = document.getElementById('ai-target-select')?.value;
        const dataType  = document.getElementById('ai-datatype-select')?.value;   // 'raster' | 'vector'
        const mode      = document.getElementById('ai-mode-select')?.value;       // 'analyze' | 'modify'
        const language  = document.getElementById('ai-language-select')?.value;   // 'zh' | 'en' | 'ja'
        const prompt    = document.getElementById('ai-prompt-input')?.value?.trim();

        if (!targetId || !prompt) {
            this._showError('请选择目标数据并输入指令');
            return;
        }

        const payload = { target_id: targetId, data_type: dataType, language, user_prompt: prompt };

        this._setLoading(true);
        this._clearResult();

        try {
            if (mode === 'analyze') {
                await this._runAnalyze(payload);
            } else {
                await this._runModify(payload);
            }
        } catch (err) {
            this._showError(err.message);
        } finally {
            this._setLoading(false);
        }
    }

    async _runAnalyze(payload) {
        const result = await AIAPI.analyze(payload);

        // 渲染报告文本到面板
        const reportEl = document.getElementById('ai-result-content');
        if (reportEl) reportEl.textContent = result.report;

        // 显示下载按钮
        const downloadBtn = document.getElementById('ai-download-btn');
        if (downloadBtn && result.file_url) {
            downloadBtn.href = result.file_url;
            downloadBtn.classList.remove('hidden');
        }

        document.getElementById('ai-result-section')?.classList.remove('hidden');
    }

    async _runModify(payload) {
        const result = await AIAPI.modify(payload);

        // 暂存 payload 和结果，供二次确认使用
        this._pendingPayload = payload;
        this._pendingResult  = result;

        // 渲染预览：展示 AI 返回的修改内容
        const previewEl = document.getElementById('ai-result-content');
        if (previewEl) {
            previewEl.textContent = JSON.stringify(result.modified_data, null, 2);
        }

        // 显示"新建"和"覆盖"两个确认按钮
        document.getElementById('ai-confirm-section')?.classList.remove('hidden');
        document.getElementById('ai-result-section')?.classList.remove('hidden');
    }

    async confirmCreate() {
        if (!this._pendingPayload || !this._pendingResult) return;

        this._setLoading(true);
        try {
            // ✅ 重新拉取数据并刷新侧边栏
            await this._refreshSidebar(this._pendingPayload.data_type);

            const newId = this._pendingResult?.index_id
                ?? this._pendingResult?.target_id
                ?? '未知';

            this._showSuccess(`已新建数据，ID: ${newId}`);
            this._resetState();
            setTimeout(() => this.closeModal(), 1200);

        } catch (err) {
            this._showError(err.message);
        } finally {
            this._setLoading(false);
        }
    }

    async confirmOverwrite() {
        if (!this._pendingPayload) return;

        const confirmed = window.confirm('确认覆盖原始数据？此操作不可撤销。');
        if (!confirmed) return;

        this._setLoading(true);
        try {
            await AIAPI.confirmOverwrite(this._pendingPayload);

            // ✅ 重新拉取数据并刷新侧边栏
            await this._refreshSidebar(this._pendingPayload.data_type);

            this._showSuccess('已成功覆盖原始数据');
            this._resetState();
            setTimeout(() => this.closeModal(), 1200);

        } catch (err) {
            this._showError(err.message);
        } finally {
            this._setLoading(false);
        }
    }

    _setLoading(isLoading) {
        const btn = document.getElementById('ai-execute-btn');
        const spinner = document.getElementById('ai-spinner');
        if (btn) btn.disabled = isLoading;
        if (spinner) spinner.classList.toggle('hidden', !isLoading);
    }

    _clearResult() {
        const resultEl = document.getElementById('ai-result-content');
        if (resultEl) resultEl.textContent = '';
        document.getElementById('ai-result-section')?.classList.add('hidden');
        document.getElementById('ai-confirm-section')?.classList.add('hidden');
        document.getElementById('ai-download-btn')?.classList.add('hidden');
    }

    _showError(msg) {
        const el = document.getElementById('ai-error-msg');
        if (el) { el.textContent = msg; el.classList.remove('hidden'); }
    }

    _showSuccess(msg) {
        const el = document.getElementById('ai-success-msg');
        if (el) { el.textContent = msg; el.classList.remove('hidden'); }
    }

    _resetState() {
        this._pendingPayload = null;
        this._pendingResult  = null;
        document.getElementById('ai-error-msg')?.classList.add('hidden');
        document.getElementById('ai-success-msg')?.classList.add('hidden');
    }

    /**
     * 重新拉取数据 → 更新 Store → 局部刷新侧边栏对应区域
     *
     * Raster：只更新 #raster-list 节点
     * Vector：只更新 #vector-list-container 节点
     *
     * @param {'raster'|'vector'} dataType
     */
    async _refreshSidebar(dataType) {
        if (dataType === 'raster') {
            await this.app.raster?.refreshData();
            const rasterListEl = document.getElementById('raster-list');
            if (rasterListEl) {
                rasterListEl.innerHTML = SidebarComponent.renderRasterSection(
                    Store.state.rasters,
                    Store.state.activeLayerIds,
                    Store.state.loadingIds
                );
            }

        } else {
            await this.app.project?.refreshProjects();
            const vectorContainerEl = document.getElementById('vector-list-container');
            if (vectorContainerEl) {
                vectorContainerEl.innerHTML = SidebarComponent.renderVectorSection(
                    Store.state.projects,
                    Store.state.activeProject,
                    Store.state.vectorLayers,
                    Store.state.activeVectorLayerId,
                    Store.state.visibleVectorLayerIds
                );
            }
        }
    }
}
