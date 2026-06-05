import { RasterAPI } from '../api/raster.js';
import { Store } from '../store/index.js';
import { ModalComponent } from '../../../ui/src/components/Modal.js';


const TEXTURE_TYPES = {
    glcm: {
        title: 'GLCM',
        prefix: 'Texture_GLCM',
    },
    local_statistics: {
        title: 'Local Statistics Window',
        prefix: 'Texture_LocalStats',
    },
    gabor: {
        title: 'Gabor Filtering',
        prefix: 'Texture_Gabor',
    },
    lbp: {
        title: 'LBP',
        prefix: 'Texture_LBP',
    },
};


export class TextureFeatureModule {
    constructor(app) {
        this.app = app;
        this.currentType = 'glcm';
    }

    openModal(type = 'glcm', rasterId = null) {
        if (Store.state.rasters.length === 0) {
            alert('Prepare source imagery first.');
            return;
        }

        const modal = document.getElementById('texture-feature-modal');
        if (!modal) return;

        const select = document.getElementById('texture-feature-raster-select');
        if (select) {
            select.innerHTML = ModalComponent.renderSelectOptions(Store.state.rasters);
            if (rasterId != null) select.value = String(rasterId);
        }

        this.switchType(this._normalizeType(type), { resetName: true });
        modal.classList.remove('hidden');
    }

    closeModal() {
        document.getElementById('texture-feature-modal')?.classList.add('hidden');
    }

    switchType(type, options = {}) {
        this.currentType = this._normalizeType(type);

        const typeSelect = document.getElementById('texture-feature-type-select');
        if (typeSelect) typeSelect.value = this.currentType;

        document.querySelectorAll('.texture-feature-option').forEach((section) => {
            section.classList.add('hidden');
        });

        if (this.currentType === 'glcm') {
            document.getElementById('texture-feature-window-section')?.classList.remove('hidden');
            document.getElementById('texture-feature-glcm-section')?.classList.remove('hidden');
        } else if (this.currentType === 'local_statistics') {
            document.getElementById('texture-feature-window-section')?.classList.remove('hidden');
            document.getElementById('texture-feature-local-section')?.classList.remove('hidden');
        } else if (this.currentType === 'gabor') {
            document.getElementById('texture-feature-gabor-section')?.classList.remove('hidden');
        } else if (this.currentType === 'lbp') {
            document.getElementById('texture-feature-lbp-section')?.classList.remove('hidden');
        }

        const title = document.getElementById('texture-feature-title');
        if (title) title.textContent = `Texture Features - ${TEXTURE_TYPES[this.currentType].title}`;

        const nameInput = document.getElementById('texture-feature-name-input');
        if (nameInput && (options.resetName || !nameInput.value.trim())) {
            nameInput.value = `${TEXTURE_TYPES[this.currentType].prefix}_${Date.now()}`;
        }

        this.handleInputChange();
    }

    handleInputChange() {
        this._renderRasterHint();

        const runButton = document.getElementById('texture-feature-run-btn');
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
            await RasterAPI.textureFeatureAnalysis(payload);
            this.closeModal();
            await this.app.raster.refreshData();
        } catch (error) {
            console.error('[TextureFeatureModule] extraction failed:', error);
            alert(`${TEXTURE_TYPES[this.currentType].title} failed: ${error.message}`);
        } finally {
            this.app.ui.showGlobalLoader(false);
        }
    }

    _readPayload() {
        return {
            rasterId: Number(document.getElementById('texture-feature-raster-select')?.value),
            textureType: this.currentType,
            bandIndex: this._integer('texture-feature-band-index', 1),
            grayLevels: this._integer('texture-feature-gray-levels', 32),
            windowSize: this._integer('texture-feature-window-size', 7),
            glcmDistance: this._integer('texture-feature-glcm-distance', 1),
            glcmAngle: this._number('texture-feature-glcm-angle', 0),
            glcmProperty: document.getElementById('texture-feature-glcm-property')?.value || 'contrast',
            localStat: document.getElementById('texture-feature-local-stat')?.value || 'mean',
            gaborFrequency: this._number('texture-feature-gabor-frequency', 0.2),
            gaborTheta: this._number('texture-feature-gabor-theta', 0),
            gaborSigma: this._number('texture-feature-gabor-sigma', 2),
            lbpRadius: this._number('texture-feature-lbp-radius', 1),
            lbpPoints: this._integer('texture-feature-lbp-points', 8),
            newName: document.getElementById('texture-feature-name-input')?.value?.trim(),
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
        if (!Number.isInteger(payload.bandIndex) || payload.bandIndex < 1 || payload.bandIndex > Number(raster.bands)) {
            return false;
        }

        if (payload.textureType === 'glcm' || payload.textureType === 'local_statistics') {
            if (!Number.isInteger(payload.grayLevels) || payload.grayLevels < 2 || payload.grayLevels > 256) return false;
            if (!Number.isInteger(payload.windowSize) || payload.windowSize < 3) return false;
        }

        if (payload.textureType === 'glcm') {
            return Number.isInteger(payload.glcmDistance)
                && payload.glcmDistance >= 1
                && payload.glcmDistance < payload.windowSize
                && Number.isFinite(payload.glcmAngle);
        }

        if (payload.textureType === 'gabor') {
            return Number.isFinite(payload.gaborFrequency)
                && payload.gaborFrequency > 0
                && Number.isFinite(payload.gaborTheta)
                && Number.isFinite(payload.gaborSigma)
                && payload.gaborSigma > 0;
        }

        if (payload.textureType === 'lbp') {
            return Number.isFinite(payload.lbpRadius)
                && payload.lbpRadius > 0
                && Number.isInteger(payload.lbpPoints)
                && payload.lbpPoints >= 1
                && payload.lbpPoints <= 24;
        }

        return true;
    }

    _renderRasterHint() {
        const hint = document.getElementById('texture-feature-raster-hint');
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
        const rasterId = Number(document.getElementById('texture-feature-raster-select')?.value);
        return Store.state.rasters.find((raster) => Number(raster.index_id) === rasterId) ?? null;
    }

    _normalizeType(type) {
        const value = String(type || '').toLowerCase().replace(/-/g, '_');
        return TEXTURE_TYPES[value] ? value : 'glcm';
    }

    _number(id, fallback) {
        const raw = document.getElementById(id)?.value?.trim();
        if (!raw) return fallback;
        const value = Number(raw);
        if (!Number.isFinite(value)) {
            throw new Error('Numeric fields must contain valid numbers.');
        }
        return value;
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
