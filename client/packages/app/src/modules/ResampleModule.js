import { RasterAPI } from '../api/raster.js';
import { Store } from '../store/index.js';
import { ModalComponent } from '../../../ui/src/components/Modal.js';


export class ResampleModule {
    constructor(app) {
        this.app = app;
    }

    openModal(rasterId = null) {
        const modal = document.getElementById('resample-modal');
        if (!modal) return;

        const select = document.getElementById('resample-raster-select');
        if (select) {
            select.innerHTML = ModalComponent.renderSelectOptions(Store.state.rasters);
            if (rasterId != null) select.value = String(rasterId);
        }

        const nameInput = document.getElementById('resample-name-input');
        if (nameInput) nameInput.value = `Resampled_${Date.now()}`;

        this._seedResolutionInputs();
        this.handleInputChange();
        modal.classList.remove('hidden');
    }

    closeModal() {
        document.getElementById('resample-modal')?.classList.add('hidden');
    }

    handleInputChange() {
        const raster = this._selectedRaster();
        this._renderResolutionHint(raster);

        const confirm = document.getElementById('resample-confirm-btn');
        if (confirm) confirm.disabled = !this._isValidForm();
    }

    async execute() {
        if (!this._isValidForm()) return;

        const payload = this._readForm();
        this.app.ui.showGlobalLoader(true);
        try {
            await RasterAPI.resampleRaster(payload);
            this.closeModal();
            await this.app.raster.refreshData();
        } catch (error) {
            console.error('[ResampleModule] resampling failed:', error);
            alert(`Resampling failed: ${error.message}`);
        } finally {
            this.app.ui.showGlobalLoader(false);
        }
    }

    _readForm() {
        const targetResolutionY = Number(document.getElementById('resample-resolution-y')?.value);
        return {
            rasterId: Number(document.getElementById('resample-raster-select')?.value),
            targetResolutionX: Number(document.getElementById('resample-resolution-x')?.value),
            targetResolutionY: Number.isFinite(targetResolutionY) && targetResolutionY > 0 ? targetResolutionY : null,
            resolutionUnit: document.getElementById('resample-unit-select')?.value || 'source',
            resamplingMethod: document.getElementById('resample-method-select')?.value || 'bilinear',
            newName: document.getElementById('resample-name-input')?.value?.trim(),
        };
    }

    _isValidForm() {
        const payload = this._readForm();
        return Number.isFinite(payload.rasterId)
            && Number.isFinite(payload.targetResolutionX)
            && payload.targetResolutionX > 0
            && (!payload.targetResolutionY || payload.targetResolutionY > 0)
            && Boolean(payload.newName);
    }

    _selectedRaster() {
        const rasterId = Number(document.getElementById('resample-raster-select')?.value);
        return Store.state.rasters.find(raster => Number(raster.index_id) === rasterId) ?? null;
    }

    _seedResolutionInputs() {
        const raster = this._selectedRaster();
        const xInput = document.getElementById('resample-resolution-x');
        const yInput = document.getElementById('resample-resolution-y');

        if (xInput) {
            xInput.value = this._formatResolution(raster?.resolution_x ?? 1);
        }
        if (yInput) {
            yInput.value = this._formatResolution(raster?.resolution_y ?? raster?.resolution_x ?? 1);
        }
    }

    _renderResolutionHint(raster) {
        const hint = document.getElementById('resample-current-resolution');
        if (!hint) return;
        if (!raster) {
            hint.textContent = '';
            return;
        }

        const resolution = [raster.resolution_x, raster.resolution_y]
            .map(value => this._formatResolution(value ?? 0))
            .join(' x ');
        hint.textContent = `${raster.width} x ${raster.height} px | current ${resolution}`;
    }

    _formatResolution(value) {
        const number = Number(value);
        if (!Number.isFinite(number)) return '1';
        return Number(number.toPrecision(8)).toString();
    }
}
