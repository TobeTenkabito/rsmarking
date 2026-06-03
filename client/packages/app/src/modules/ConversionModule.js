import { Store } from '../store/index.js';
import { ConversionAPI } from '../api/conversion.js';

const esc = (value) => String(value ?? '')
    .replace(/&/g, '&amp;')
    .replace(/'/g, '&#39;')
    .replace(/"/g, '&quot;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;');

const rasterDisplayName = (raster) =>
    raster?.file_name ?? raster?.name ?? `Raster_${raster?.index_id ?? ''}`;

const defaultVectorName = (raster) =>
    `${rasterDisplayName(raster).replace(/\.[^.]+$/, '')}_vectorized_${Date.now()}`;

/**
 * ConversionModule - Vector to RasterEnglish
 *
 * English：
 *   Step 1 → Select Vector Layer (from Store.state.vectorLayers)
 *   Step 2 → English (from Store.state.rasters) + English
 *   English   → English ConversionAPI.vectorToRaster() → RefreshEnglish
 *
 * Dependencies：
 *   - app.ui.showGlobalLoader / showToast
 *   - app.raster.refreshData()          (RefreshEnglishSidebar)
 *   - app.mapController.toggleLayer()   (Optional：English)
 */
export class ConversionModule {
    constructor(app) {
        this.app = app;

        // English：English
        this._selectedLayerId  = null;
        this._selectedRefId    = null;   // Reference raster index_id
        this._selectedRasterId = null;
    }

    /** EnglishVector to Raster Modal，English Step 1 */
    openModal() {
        const modal = document.getElementById('conversion-modal');
        if (!modal) return;

        // English Store English，EnglishDependenciesEnglish

        // English
        this._selectedLayerId = null;
        this._selectedRefId   = null;

        this._renderStep1();
        this._goToStep(1);
        modal.classList.remove('hidden');
    }

    closeModal() {
        document.getElementById('conversion-modal')?.classList.add('hidden');
    }

    openRasterToVectorModal(rasterId = null) {
        const modal = document.getElementById('raster-vector-modal');
        if (!modal) return;

        this._selectedRasterId = rasterId ? Number(rasterId) : null;
        const project = Store.state.activeProject;
        const projectInfo = document.getElementById('raster-vector-project');
        if (projectInfo) {
            projectInfo.textContent = project
                ? `Target project: ${project.name}`
                : 'Select or create a vector project first';
            projectInfo.classList.toggle('text-amber-500', !project);
            projectInfo.classList.toggle('text-slate-400', !!project);
        }

        const list = document.getElementById('raster-vector-list');
        if (list) {
            list.innerHTML = this._buildRasterVectorList(Store.state.rasters);
        }

        const bandInput = document.getElementById('raster-vector-band-input');
        if (bandInput) bandInput.value = '1';

        const maxInput = document.getElementById('raster-vector-max-input');
        if (maxInput) maxInput.value = '10000';

        const skipZeroInput = document.getElementById('raster-vector-skip-zero-input');
        if (skipZeroInput) skipZeroInput.checked = true;

        const selectedRaster = this._findRasterByIndexId(this._selectedRasterId);
        const nameInput = document.getElementById('raster-vector-name-input');
        if (nameInput) {
            nameInput.value = selectedRaster ? defaultVectorName(selectedRaster) : '';
        }

        this._updateRasterVectorConfirmBtn();
        modal.classList.remove('hidden');
    }

    closeRasterToVectorModal() {
        document.getElementById('raster-vector-modal')?.classList.add('hidden');
    }

    /** EnglishVector LayerEnglish */
    handleSelectLayer(layerId) {
        this._selectedLayerId = layerId;

        // English
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

    /** English */
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

    /** Step 2 → Step 1（returns） */
    handleStepBack() {
        this._selectedRefId = null;
        this._renderStep1();
        this._goToStep(1);

        // EnglishPreviousEnglish
        if (this._selectedLayerId) {
            document.querySelectorAll('[data-conversion-layer]').forEach(el => {
                const isActive = el.dataset.conversionLayer === this._selectedLayerId;
                el.classList.toggle('ring-2',           isActive);
                el.classList.toggle('ring-indigo-500',  isActive);
                el.classList.toggle('bg-indigo-50',     isActive);
            });
        }
    }

    /** English */
    handleNameInput() {
        this._updateConfirmBtn();
    }

    handleRasterVectorNameInput() {
        this._updateRasterVectorConfirmBtn();
    }

    handleSelectRaster(indexId) {
        this._selectedRasterId = Number(indexId);

        document.querySelectorAll('[data-raster-vector-source]').forEach(el => {
            const isActive = el.dataset.rasterVectorSource === String(indexId);
            el.classList.toggle('ring-2', isActive);
            el.classList.toggle('ring-violet-500', isActive);
            el.classList.toggle('bg-violet-50', isActive);
        });

        const raster = this._findRasterByIndexId(indexId);
        const nameInput = document.getElementById('raster-vector-name-input');
        if (nameInput && !nameInput.value.trim()) {
            nameInput.value = defaultVectorName(raster);
        }

        this._updateRasterVectorConfirmBtn();
    }

    async handleExecute() {
        const layerId  = this._selectedLayerId;
        const refId    = this._selectedRefId;
        const nameInput = document.getElementById('conversion-name-input');
        const newName  = nameInput?.value?.trim();

        if (!layerId || !refId || !newName) {
            this.app.ui.showToast('Fill in all parameters.', 'warning');
            return;
        }

        this.closeModal();
        this.app.ui.showGlobalLoader(true);

        try {
            const result = await ConversionAPI.vectorToRaster(layerId, refId, newName);

            // RefreshEnglish
            await this.app.raster?.refreshData();

            // Optional：English
            const newRasterId = result?.id ?? result?.index_id;
            if (newRasterId && this.app.mapController) {
                await this.app.mapController.toggleLayer(newRasterId);
            }

            this.app.ui.showToast(`Rasterization complete. New imagery "${newName}" has been created.`, 'success');
        } catch (err) {
            console.error('[ConversionModule] Vector to RasterFailed:', err);
            this.app.ui.showToast(`Conversion failed：${err.message}`, 'error');
        } finally {
            this.app.ui.showGlobalLoader(false);
        }
    }

    async handleRasterToVectorExecute() {
        const rasterId = this._selectedRasterId;
        const activeProject = Store.state.activeProject;
        const nameInput = document.getElementById('raster-vector-name-input');
        const bandInput = document.getElementById('raster-vector-band-input');
        const maxInput = document.getElementById('raster-vector-max-input');
        const skipZeroInput = document.getElementById('raster-vector-skip-zero-input');

        const newName = nameInput?.value?.trim();
        const bandIndex = Math.max(1, Number(bandInput?.value) || 1);
        const maxFeatures = Math.max(1, Number(maxInput?.value) || 10000);

        if (!activeProject) {
            this.app.ui.showToast('Select a vector project first', 'warning');
            return;
        }
        if (!rasterId || !newName) {
            this.app.ui.showToast('Select a raster and enter a layer name', 'warning');
            return;
        }

        this.closeRasterToVectorModal();
        this.app.ui.showGlobalLoader(true);

        try {
            const result = await ConversionAPI.rasterToVector(
                rasterId,
                activeProject.id,
                newName,
                {
                    bandIndex,
                    skipNodata: true,
                    skipZero: skipZeroInput?.checked ?? true,
                    maxFeatures,
                },
            );

            await this.app.project?.handleSelectProject(activeProject.id);
            if (result?.layer_id) {
                Store.setActiveVectorLayer(result.layer_id);
                await this.app.mapController?.refreshVectorLayer(result.layer_id);
            }

            this.app.ui.showToast(
                `Vector layer created with ${result?.feature_count ?? 0} features`,
                'success',
            );
        } catch (err) {
            console.error('[ConversionModule] raster to vector failed:', err);
            this.app.ui.showToast(`Vectorization failed: ${err.message}`, 'error');
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
        // English
        const refContainer = document.getElementById('conversion-step-2-ref-list');
        if (refContainer) {
            refContainer.innerHTML = this._buildRefList(Store.state.rasters);
        }

        // English：English
        const layer = Store.state.vectorLayers.find(l => l.id === this._selectedLayerId);
        const nameInput = document.getElementById('conversion-name-input');
        if (nameInput) {
            nameInput.value = `${layer?.name ?? 'vector'}_rasterized_${Date.now()}`;
        }

        // English
        const confirmBtn = document.getElementById('conversion-confirm-btn');
        if (confirmBtn) confirmBtn.disabled = true;
    }

    /**
     * English
     * @param {1|2} step
     */
    _goToStep(step) {
        // English
        document.getElementById('conversion-step-1')?.classList.toggle('hidden', step !== 1);
        document.getElementById('conversion-step-2')?.classList.toggle('hidden', step !== 2);

        // English
        document.getElementById('conversion-next-btn')?.classList.toggle('hidden',    step !== 1);
        document.getElementById('conversion-confirm-btn')?.classList.toggle('hidden', step !== 2);
        document.getElementById('conversion-back-btn')?.classList.toggle('hidden',    step !== 2);

        // English
        this._setStepDot('conversion-step-1-dot', step === 1);
        this._setStepDot('conversion-step-2-dot', step === 2);

        // Step 1 English Next English：English
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

    _updateRasterVectorConfirmBtn() {
        const nameInput = document.getElementById('raster-vector-name-input');
        const hasName = nameInput?.value?.trim().length > 0;
        const confirmBtn = document.getElementById('raster-vector-confirm-btn');
        if (confirmBtn) {
            confirmBtn.disabled = !(Store.state.activeProject && this._selectedRasterId && hasName);
        }
    }

    _findRasterByIndexId(indexId) {
        return Store.state.rasters.find(r => String(r.index_id) === String(indexId));
    }

    _buildRasterVectorList(rasters) {
        if (!rasters.length) {
            return `<p class="text-sm text-slate-400 text-center py-6">No rasters available</p>`;
        }
        return rasters.map((raster) => {
            const active = String(raster.index_id) === String(this._selectedRasterId);
            return `
                <div
                    data-raster-vector-source="${esc(raster.index_id)}"
                    class="flex items-center gap-3 p-3 rounded-lg border border-slate-200
                           cursor-pointer hover:bg-violet-50 hover:border-violet-300 transition-all
                           ${active ? 'ring-2 ring-violet-500 bg-violet-50' : ''}"
                    onclick="RS.handleRasterVectorSelectRaster(${raster.index_id})"
                >
                    <span class="w-2 h-2 rounded-full bg-violet-400 flex-shrink-0"></span>
                    <div class="flex-1 min-w-0">
                        <p class="text-sm font-medium text-slate-700 truncate">${esc(rasterDisplayName(raster))}</p>
                        <p class="text-xs text-slate-400">${esc(raster.width ?? '?')} x ${esc(raster.height ?? '?')} px
                           - ${esc(raster.bands ?? '?')} band(s)</p>
                    </div>
                </div>
            `;
        }).join('');
    }


    _buildLayerList(layers) {
        if (!layers.length) {
            return `<p class="text-sm text-slate-400 text-center py-6">No vector layers in the current project</p>`;
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
                    <p class="text-xs text-slate-400">${layer.feature_count ?? '?'} features</p>
                </div>
            </div>
        `).join('');
    }

    _buildRefList(rasters) {
        if (!rasters.length) {
            return `<p class="text-sm text-slate-400 text-center py-6">No available reference raster</p>`;
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
                       · ${r.crs ?? 'CRSUnknown'}</p>
                </div>
            </div>
        `).join('');
    }
}
