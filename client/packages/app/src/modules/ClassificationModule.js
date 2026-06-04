import { RasterAPI } from '../api/raster.js';
import { Store } from '../store/index.js';
import { ModalComponent } from '../../../ui/src/components/Modal.js';


const MODE_TITLES = {
    supervised: 'Supervised Classification',
    unsupervised: 'Unsupervised Classification',
    segmentation: 'Deep Learning Segmentation',
};

const MODE_OUTPUT_PREFIXES = {
    supervised: 'Supervised_Classification',
    unsupervised: 'Unsupervised_Classification',
    segmentation: 'Deep_Segmentation',
};


export class ClassificationModule {
    constructor(app) {
        this.app = app;
        this.currentMode = 'unsupervised';
        this.samples = [];
    }

    openModal(mode = 'unsupervised', rasterId = null) {
        if (Store.state.rasters.length === 0) {
            alert('Prepare source imagery first.');
            return;
        }

        const modal = document.getElementById('classification-modal');
        if (!modal) return;

        const select = document.getElementById('classification-raster-select');
        if (select) {
            select.innerHTML = ModalComponent.renderSelectOptions(Store.state.rasters);
            if (rasterId != null) select.value = String(rasterId);
        }

        if (this.samples.length === 0) {
            this.samples = [
                { class_id: 1, row: 0, col: 0 },
                { class_id: 2, row: 1, col: 1 },
            ];
        }
        this._renderSamples();
        this.switchMode(this._normalizeMode(mode), { resetName: true });
        modal.classList.remove('hidden');
    }

    closeModal() {
        document.getElementById('classification-modal')?.classList.add('hidden');
    }

    switchMode(mode, options = {}) {
        this.currentMode = this._normalizeMode(mode);

        document.querySelectorAll('.classification-section').forEach((section) => {
            section.classList.add('hidden');
        });
        document.getElementById(`classification-${this.currentMode}-section`)?.classList.remove('hidden');

        document.querySelectorAll('.classification-mode-btn').forEach((button) => {
            button.classList.remove('bg-emerald-600', 'text-white', 'shadow-sm');
            button.classList.add('bg-slate-100', 'text-slate-500', 'hover:bg-slate-200');
        });
        const activeButton = document.getElementById(`classification-mode-${this.currentMode}`);
        activeButton?.classList.remove('bg-slate-100', 'text-slate-500', 'hover:bg-slate-200');
        activeButton?.classList.add('bg-emerald-600', 'text-white', 'shadow-sm');

        const title = document.getElementById('classification-title');
        if (title) title.textContent = MODE_TITLES[this.currentMode];

        const nameInput = document.getElementById('classification-name-input');
        if (nameInput && (options.resetName || !nameInput.value.trim())) {
            nameInput.value = `${MODE_OUTPUT_PREFIXES[this.currentMode]}_${Date.now()}`;
        }

        this.handleInputChange();
    }

    handleInputChange() {
        this._syncSamplesFromDom();
        this._renderRasterHint();

        const runButton = document.getElementById('classification-run-btn');
        if (runButton) runButton.disabled = !this._isValidForm();
    }

    addSample() {
        this._syncSamplesFromDom();
        const nextIndex = this.samples.length;
        this.samples.push({
            class_id: nextIndex % 2 === 0 ? 1 : 2,
            row: nextIndex,
            col: nextIndex,
        });
        this._renderSamples();
        this.handleInputChange();
    }

    removeSample(index) {
        this._syncSamplesFromDom();
        if (this.samples.length <= 2) return;
        this.samples.splice(index, 1);
        this._renderSamples();
        this.handleInputChange();
    }

    async execute() {
        if (!this._isValidForm()) return;

        let payload;
        try {
            payload = this._readPayload();
        } catch (error) {
            alert(error.message);
            return;
        }

        this.app.ui.showGlobalLoader(true);
        try {
            if (this.currentMode === 'supervised') {
                await RasterAPI.supervisedClassification(payload);
            } else if (this.currentMode === 'segmentation') {
                await RasterAPI.deepLearningSegmentation(payload);
            } else {
                await RasterAPI.unsupervisedClassification(payload);
            }
            this.closeModal();
            await this.app.raster.refreshData();
        } catch (error) {
            console.error('[ClassificationModule] task failed:', error);
            alert(`${MODE_TITLES[this.currentMode]} failed: ${error.message}`);
        } finally {
            this.app.ui.showGlobalLoader(false);
        }
    }

    _readPayload() {
        const common = {
            rasterId: Number(document.getElementById('classification-raster-select')?.value),
            bandIndices: this._readBandIndices(),
            newName: document.getElementById('classification-name-input')?.value?.trim(),
        };

        if (this.currentMode === 'supervised') {
            return {
                ...common,
                samples: this._readSamples(),
                classifier: document.getElementById('classification-classifier-select')?.value || 'nearest_centroid',
                nEstimators: this._readInt('classification-n-estimators', 100),
                randomSeed: this._readInt('classification-supervised-seed', 13),
                smoothing: this._readInt('classification-supervised-smoothing', 0),
            };
        }

        if (this.currentMode === 'segmentation') {
            return {
                ...common,
                modelPath: document.getElementById('classification-segmentation-model-path')?.value?.trim() || null,
                backend: document.getElementById('classification-segmentation-backend')?.value || 'auto',
                nClasses: this._readInt('classification-segmentation-classes', 2),
                threshold: this._readNumber('classification-segmentation-threshold', 0.5),
                randomSeed: this._readInt('classification-segmentation-seed', 13),
                maxSamples: this._readInt('classification-segmentation-max-samples', 50000),
                compactness: this._readNumber('classification-segmentation-compactness', 0.15),
                smoothing: this._readInt('classification-segmentation-smoothing', 1),
            };
        }

        return {
            ...common,
            nClasses: this._readInt('classification-unsupervised-classes', 5),
            method: document.getElementById('classification-unsupervised-method')?.value || 'kmeans',
            maxSamples: this._readInt('classification-unsupervised-max-samples', 50000),
            randomSeed: this._readInt('classification-unsupervised-seed', 13),
            smoothing: this._readInt('classification-unsupervised-smoothing', 0),
        };
    }

    _isValidForm() {
        let payload;
        try {
            payload = this._readPayload();
        } catch {
            return false;
        }

        if (!Number.isFinite(payload.rasterId) || !payload.newName) return false;

        if (this.currentMode === 'supervised') {
            const samples = payload.samples;
            const classes = new Set(samples.map((sample) => sample.class_id));
            return samples.length >= 2
                && classes.size >= 2
                && payload.nEstimators >= 1
                && payload.nEstimators <= 1000
                && this._validSmoothing(payload.smoothing);
        }

        if (this.currentMode === 'segmentation') {
            const hasModel = Boolean(payload.modelPath);
            return payload.nClasses >= 2
                && payload.nClasses <= 255
                && payload.threshold >= 0
                && payload.threshold <= 1
                && payload.maxSamples >= 100
                && payload.compactness >= 0
                && this._validSmoothing(payload.smoothing)
                && (payload.backend !== 'onnx' || hasModel);
        }

        return payload.nClasses >= 2
            && payload.nClasses <= 255
            && payload.maxSamples >= 100
            && this._validSmoothing(payload.smoothing);
    }

    _readSamples() {
        this._syncSamplesFromDom();
        return this.samples.filter((sample) => (
            Number.isInteger(sample.class_id)
            && sample.class_id > 0
            && Number.isInteger(sample.row)
            && sample.row >= 0
            && Number.isInteger(sample.col)
            && sample.col >= 0
        ));
    }

    _syncSamplesFromDom() {
        const rows = Array.from(document.querySelectorAll('.classification-sample-row'));
        if (!rows.length) return;
        this.samples = rows.map((row) => ({
            class_id: this._rowInt(row, 'class'),
            row: this._rowInt(row, 'row'),
            col: this._rowInt(row, 'col'),
        }));
    }

    _renderSamples() {
        const list = document.getElementById('classification-samples-list');
        if (!list) return;

        list.innerHTML = this.samples.map((sample, index) => `
            <div class="classification-sample-row grid grid-cols-[1fr_1fr_1fr_32px] gap-2 p-3 bg-white"
                 data-index="${index}">
                <input data-sample-field="class"
                       type="number"
                       min="1"
                       value="${this._escapeAttr(sample.class_id)}"
                       oninput="RS.handleClassificationInputChange()"
                       class="rounded-lg border border-slate-200 px-2 py-2 text-xs font-mono text-slate-700 outline-none focus:border-emerald-400 focus:ring-2 focus:ring-emerald-500/10" />
                <input data-sample-field="row"
                       type="number"
                       min="0"
                       value="${this._escapeAttr(sample.row)}"
                       oninput="RS.handleClassificationInputChange()"
                       class="rounded-lg border border-slate-200 px-2 py-2 text-xs font-mono text-slate-700 outline-none focus:border-emerald-400 focus:ring-2 focus:ring-emerald-500/10" />
                <input data-sample-field="col"
                       type="number"
                       min="0"
                       value="${this._escapeAttr(sample.col)}"
                       oninput="RS.handleClassificationInputChange()"
                       class="rounded-lg border border-slate-200 px-2 py-2 text-xs font-mono text-slate-700 outline-none focus:border-emerald-400 focus:ring-2 focus:ring-emerald-500/10" />
                <button onclick="RS.removeClassificationSample(${index})"
                        class="rounded-lg text-slate-300 hover:bg-red-50 hover:text-red-500 disabled:opacity-30"
                        ${this.samples.length <= 2 ? 'disabled' : ''}
                        title="Remove">x</button>
            </div>
        `).join('');
    }

    _readBandIndices() {
        const raw = document.getElementById('classification-band-indices')?.value?.trim();
        if (!raw) return null;
        const values = raw.split(',').map((item) => Number(item.trim()));
        if (!values.length || values.some((value) => !Number.isInteger(value) || value <= 0)) {
            throw new Error('Band indices must be positive integers separated by commas.');
        }
        return values;
    }

    _renderRasterHint() {
        const hint = document.getElementById('classification-raster-hint');
        if (!hint) return;
        const raster = this._selectedRaster();
        if (!raster) {
            hint.textContent = '';
            return;
        }

        const resolution = [raster.resolution_x, raster.resolution_y]
            .filter((value) => value !== null && value !== undefined)
            .map((value) => Number(value).toPrecision(5))
            .join(' x ');
        hint.textContent = `${raster.width} x ${raster.height} px | ${raster.bands} band(s)${resolution ? ` | ${resolution}` : ''}`;
    }

    _selectedRaster() {
        const rasterId = Number(document.getElementById('classification-raster-select')?.value);
        return Store.state.rasters.find((raster) => Number(raster.index_id) === rasterId) ?? null;
    }

    _normalizeMode(mode) {
        const value = String(mode || '').toLowerCase();
        if (value === 'classification' || value === 'supervised_classification' || value === 'supervised') {
            return 'supervised';
        }
        if (value === 'deep_learning_segmentation' || value === 'segment' || value === 'segmentation') {
            return 'segmentation';
        }
        return 'unsupervised';
    }

    _readInt(id, fallback) {
        const value = Number(document.getElementById(id)?.value);
        return Number.isInteger(value) ? value : fallback;
    }

    _readNumber(id, fallback) {
        const value = Number(document.getElementById(id)?.value);
        return Number.isFinite(value) ? value : fallback;
    }

    _rowInt(row, field) {
        const value = Number(row.querySelector(`[data-sample-field="${field}"]`)?.value);
        return Number.isInteger(value) ? value : NaN;
    }

    _validSmoothing(value) {
        return Number.isInteger(value) && value >= 0 && value <= 5;
    }

    _escapeAttr(value) {
        return String(value ?? '')
            .replace(/&/g, '&amp;')
            .replace(/"/g, '&quot;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;');
    }
}
