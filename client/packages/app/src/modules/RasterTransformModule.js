import { RasterAPI } from '../api/raster.js';
import { Store } from '../store/index.js';
import { ModalComponent } from '../../../ui/src/components/Modal.js';


const TRANSFORM_TYPES = {
    fourier: {
        title: 'Fourier Analysis',
        prefix: 'Fourier',
    },
    wavelet: {
        title: 'Wavelet Analysis',
        prefix: 'Wavelet',
    },
    pca: {
        title: 'PCA',
        prefix: 'PCA',
    },
};


export class RasterTransformModule {
    constructor(app) {
        this.app = app;
        this.currentType = 'fourier';
    }

    openModal(type = 'fourier', rasterId = null) {
        if (Store.state.rasters.length === 0) {
            alert('Prepare source imagery first.');
            return;
        }

        const modal = document.getElementById('transform-analysis-modal');
        if (!modal) return;

        const select = document.getElementById('transform-analysis-raster-select');
        if (select) {
            select.innerHTML = ModalComponent.renderSelectOptions(Store.state.rasters);
            if (rasterId != null) select.value = String(rasterId);
        }

        this.switchType(this._normalizeType(type), { resetName: true });
        modal.classList.remove('hidden');
    }

    closeModal() {
        document.getElementById('transform-analysis-modal')?.classList.add('hidden');
    }

    switchType(type, options = {}) {
        this.currentType = this._normalizeType(type);

        const typeSelect = document.getElementById('transform-analysis-type-select');
        if (typeSelect) typeSelect.value = this.currentType;

        document.querySelectorAll('.transform-analysis-option').forEach((section) => {
            section.classList.add('hidden');
        });

        if (this.currentType === 'pca') {
            document.getElementById('transform-analysis-pca-section')?.classList.remove('hidden');
        } else {
            document.getElementById('transform-analysis-band-section')?.classList.remove('hidden');
            if (this.currentType === 'wavelet') {
                document.getElementById('transform-analysis-wavelet-section')?.classList.remove('hidden');
            } else {
                document.getElementById('transform-analysis-fourier-section')?.classList.remove('hidden');
            }
        }

        const title = document.getElementById('transform-analysis-title');
        if (title) title.textContent = `Raster Transform - ${TRANSFORM_TYPES[this.currentType].title}`;

        const nameInput = document.getElementById('transform-analysis-name-input');
        if (nameInput && (options.resetName || !nameInput.value.trim())) {
            nameInput.value = `${TRANSFORM_TYPES[this.currentType].prefix}_${Date.now()}`;
        }

        this.handleInputChange();
    }

    handleInputChange() {
        this._renderRasterHint();

        const runButton = document.getElementById('transform-analysis-run-btn');
        if (runButton) runButton.disabled = !this._isValidForm();
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
            await RasterAPI.rasterTransformAnalysis(payload);
            this.closeModal();
            await this.app.raster.refreshData();
        } catch (error) {
            console.error('[RasterTransformModule] analysis failed:', error);
            alert(`${TRANSFORM_TYPES[this.currentType].title} failed: ${error.message}`);
        } finally {
            this.app.ui.showGlobalLoader(false);
        }
    }

    _readPayload() {
        return {
            rasterId: Number(document.getElementById('transform-analysis-raster-select')?.value),
            transformType: this.currentType,
            bandIndex: this._integer('transform-analysis-band-index', 1),
            fourierOutput: document.getElementById('transform-analysis-fourier-output')?.value || 'magnitude',
            waveletOutput: document.getElementById('transform-analysis-wavelet-output')?.value || 'detail_energy',
            waveletLevel: this._integer('transform-analysis-wavelet-level', 1),
            pcaComponents: this._integer('transform-analysis-pca-components', 3),
            pcaStandardize: Boolean(document.getElementById('transform-analysis-pca-standardize')?.checked),
            newName: document.getElementById('transform-analysis-name-input')?.value?.trim(),
        };
    }

    _isValidForm() {
        let payload;
        try {
            payload = this._readPayload();
        } catch {
            return false;
        }

        const raster = this._selectedRaster();
        if (!Number.isFinite(payload.rasterId) || !payload.newName || !raster) return false;

        if (payload.transformType === 'pca') {
            return Number(raster.bands) >= 2
                && Number.isInteger(payload.pcaComponents)
                && payload.pcaComponents >= 1
                && payload.pcaComponents <= Number(raster.bands);
        }

        if (!Number.isInteger(payload.bandIndex) || payload.bandIndex < 1 || payload.bandIndex > Number(raster.bands)) {
            return false;
        }

        if (payload.transformType === 'wavelet') {
            return Number.isInteger(payload.waveletLevel) && payload.waveletLevel >= 1;
        }
        return true;
    }

    _renderRasterHint() {
        const hint = document.getElementById('transform-analysis-raster-hint');
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
        const rasterId = Number(document.getElementById('transform-analysis-raster-select')?.value);
        return Store.state.rasters.find((raster) => Number(raster.index_id) === rasterId) ?? null;
    }

    _normalizeType(type) {
        const value = String(type || '').toLowerCase();
        return TRANSFORM_TYPES[value] ? value : 'fourier';
    }

    _integer(id, fallback) {
        const raw = document.getElementById(id)?.value?.trim();
        if (!raw) return fallback;
        const value = Number(raw);
        if (!Number.isInteger(value)) {
            throw new Error('Integer fields must contain whole numbers.');
        }
        return value;
    }
}
