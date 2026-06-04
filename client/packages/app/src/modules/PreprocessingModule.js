import { RasterAPI } from '../api/raster.js';
import { Store } from '../store/index.js';
import { ModalComponent } from '../../../ui/src/components/Modal.js';


const MODE_TITLES = {
    radiometric: 'Radiometric Calibration',
    geometric: 'Geometric Correction',
};

const MODE_OUTPUT_PREFIXES = {
    radiometric: 'Radiometric_Calibration',
    geometric: 'Geometric_Correction',
};


export class PreprocessingModule {
    constructor(app) {
        this.app = app;
        this.currentMode = 'radiometric';
    }

    openModal(mode = 'radiometric', rasterId = null) {
        if (Store.state.rasters.length === 0) {
            alert('Prepare source imagery first.');
            return;
        }

        const modal = document.getElementById('preprocessing-modal');
        if (!modal) return;

        const select = document.getElementById('preprocessing-raster-select');
        if (select) {
            select.innerHTML = ModalComponent.renderSelectOptions(Store.state.rasters);
            if (rasterId != null) select.value = String(rasterId);
        }

        this.switchMode(this._normalizeMode(mode), { resetName: true });
        modal.classList.remove('hidden');
    }

    closeModal() {
        document.getElementById('preprocessing-modal')?.classList.add('hidden');
    }

    switchMode(mode, options = {}) {
        this.currentMode = this._normalizeMode(mode);

        document.querySelectorAll('.preprocessing-section').forEach((section) => {
            section.classList.add('hidden');
        });
        document.getElementById(`preprocessing-${this.currentMode}-section`)?.classList.remove('hidden');

        document.querySelectorAll('.preprocessing-mode-btn').forEach((button) => {
            button.classList.remove('bg-cyan-600', 'text-white', 'shadow-sm');
            button.classList.add('bg-slate-100', 'text-slate-500', 'hover:bg-slate-200');
        });
        const activeButton = document.getElementById(`preprocessing-mode-${this.currentMode}`);
        activeButton?.classList.remove('bg-slate-100', 'text-slate-500', 'hover:bg-slate-200');
        activeButton?.classList.add('bg-cyan-600', 'text-white', 'shadow-sm');

        const title = document.getElementById('preprocessing-title');
        if (title) title.textContent = MODE_TITLES[this.currentMode];

        const nameInput = document.getElementById('preprocessing-name-input');
        if (nameInput && (options.resetName || !nameInput.value.trim())) {
            nameInput.value = `${MODE_OUTPUT_PREFIXES[this.currentMode]}_${Date.now()}`;
        }

        this.handleInputChange();
    }

    handleInputChange() {
        this._renderRasterHint();

        const runButton = document.getElementById('preprocessing-run-btn');
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
            if (this.currentMode === 'geometric') {
                await RasterAPI.geometricCorrection(payload);
            } else {
                await RasterAPI.radiometricCalibration(payload);
            }
            this.closeModal();
            await this.app.raster.refreshData();
        } catch (error) {
            console.error('[PreprocessingModule] task failed:', error);
            alert(`${MODE_TITLES[this.currentMode]} failed: ${error.message}`);
        } finally {
            this.app.ui.showGlobalLoader(false);
        }
    }

    _readPayload() {
        const common = {
            rasterId: Number(document.getElementById('preprocessing-raster-select')?.value),
            newName: document.getElementById('preprocessing-name-input')?.value?.trim(),
        };

        if (this.currentMode === 'geometric') {
            return {
                ...common,
                dstCrs: document.getElementById('preprocessing-dst-crs')?.value?.trim() || null,
                resamplingMethod: document.getElementById('preprocessing-resampling-method')?.value || 'bilinear',
                targetResolutionX: this._optionalNumber('preprocessing-target-resolution-x'),
                targetResolutionY: this._optionalNumber('preprocessing-target-resolution-y'),
                shiftX: this._number('preprocessing-shift-x', 0),
                shiftY: this._number('preprocessing-shift-y', 0),
                scaleX: this._number('preprocessing-scale-x', 1),
                scaleY: this._number('preprocessing-scale-y', 1),
                rotationDegrees: this._number('preprocessing-rotation-degrees', 0),
                gcps: this._readGcps(),
            };
        }

        return {
            ...common,
            calibrationType: document.getElementById('preprocessing-radiometric-type')?.value || 'auto',
            scaleFactor: this._optionalNumber('preprocessing-scale-factor'),
            offset: this._optionalNumber('preprocessing-offset'),
            radianceMult: this._optionalNumber('preprocessing-radiance-mult'),
            radianceAdd: this._optionalNumber('preprocessing-radiance-add'),
            reflectanceMult: this._optionalNumber('preprocessing-reflectance-mult'),
            reflectanceAdd: this._optionalNumber('preprocessing-reflectance-add'),
            sunElevation: this._optionalNumber('preprocessing-sun-elevation'),
            earthSunDistance: this._number('preprocessing-earth-sun-distance', 1),
            solarIrradiance: this._optionalNumber('preprocessing-solar-irradiance'),
            sunElevationCorrection: Boolean(document.getElementById('preprocessing-sun-correction')?.checked),
            clamp: Boolean(document.getElementById('preprocessing-clamp')?.checked),
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

        if (this.currentMode === 'geometric') {
            return this._optionalPositive(payload.targetResolutionX)
                && this._optionalPositive(payload.targetResolutionY)
                && payload.scaleX > 0
                && payload.scaleY > 0
                && (!payload.gcps || payload.gcps.length >= 3);
        }

        return payload.earthSunDistance > 0
            && this._optionalPositive(payload.solarIrradiance);
    }

    _readGcps() {
        const raw = document.getElementById('preprocessing-gcps')?.value?.trim();
        if (!raw) return null;
        let parsed;
        try {
            parsed = JSON.parse(raw);
        } catch (error) {
            throw new Error(`GCP JSON is invalid: ${error.message}`);
        }
        if (!Array.isArray(parsed)) {
            throw new Error('GCP JSON must be an array.');
        }
        return parsed.map((item) => ({
            row: this._gcpNumber(item, 'row'),
            col: this._gcpNumber(item, 'col'),
            x: this._gcpNumber(item, 'x'),
            y: this._gcpNumber(item, 'y'),
        }));
    }

    _gcpNumber(item, key) {
        const value = Number(item?.[key]);
        if (!Number.isFinite(value)) {
            throw new Error(`Each GCP must include numeric ${key}.`);
        }
        return value;
    }

    _renderRasterHint() {
        const hint = document.getElementById('preprocessing-raster-hint');
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
        const rasterId = Number(document.getElementById('preprocessing-raster-select')?.value);
        return Store.state.rasters.find((raster) => Number(raster.index_id) === rasterId) ?? null;
    }

    _normalizeMode(mode) {
        const value = String(mode || '').toLowerCase();
        if (value === 'geometric' || value === 'geometric_correction') {
            return 'geometric';
        }
        return 'radiometric';
    }

    _optionalNumber(id) {
        const raw = document.getElementById(id)?.value?.trim();
        if (!raw) return null;
        const value = Number(raw);
        if (!Number.isFinite(value)) {
            throw new Error('Numeric fields must contain valid numbers.');
        }
        return value;
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

    _optionalPositive(value) {
        return value === null || value === undefined || value > 0;
    }
}
