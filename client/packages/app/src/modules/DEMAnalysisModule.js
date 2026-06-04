import { RasterAPI } from '../api/raster.js';
import { Store } from '../store/index.js';
import { ModalComponent } from '../../../ui/src/components/Modal.js';


const DEM_OPERATIONS = {
    elevation: {
        title: 'Elevation',
        prefix: 'DEM_Elevation',
    },
    slope: {
        title: 'Slope',
        prefix: 'DEM_Slope',
    },
    aspect: {
        title: 'Aspect',
        prefix: 'DEM_Aspect',
    },
    hillshade: {
        title: 'Shading / Hillshade',
        prefix: 'DEM_Hillshade',
    },
    curvature: {
        title: 'Curvature',
        prefix: 'DEM_Curvature',
    },
    relief: {
        title: 'Topographic Relief',
        prefix: 'DEM_Relief',
    },
    twi: {
        title: 'Topographic Humidity Index',
        prefix: 'DEM_TWI',
    },
    flow_direction: {
        title: 'Flow Direction',
        prefix: 'DEM_Flow_Direction',
    },
    flow_accumulation: {
        title: 'Flow Accumulation',
        prefix: 'DEM_Flow_Accumulation',
    },
    watershed: {
        title: 'Watershed Delineation',
        prefix: 'DEM_Watershed',
    },
};


export class DEMAnalysisModule {
    constructor(app) {
        this.app = app;
        this.currentOperation = 'slope';
    }

    openModal(operation = 'slope', rasterId = null) {
        if (Store.state.rasters.length === 0) {
            alert('Prepare a DEM raster first.');
            return;
        }

        const modal = document.getElementById('dem-analysis-modal');
        if (!modal) return;

        const select = document.getElementById('dem-analysis-raster-select');
        if (select) {
            select.innerHTML = ModalComponent.renderSelectOptions(Store.state.rasters);
            if (rasterId != null) select.value = String(rasterId);
        }

        this.switchOperation(this._normalizeOperation(operation), { resetName: true });
        modal.classList.remove('hidden');
    }

    closeModal() {
        document.getElementById('dem-analysis-modal')?.classList.add('hidden');
    }

    switchOperation(operation, options = {}) {
        this.currentOperation = this._normalizeOperation(operation);

        const operationSelect = document.getElementById('dem-analysis-operation-select');
        if (operationSelect) operationSelect.value = this.currentOperation;

        document.querySelectorAll('.dem-analysis-option').forEach((section) => {
            section.classList.add('hidden');
        });

        if (this.currentOperation === 'slope') {
            document.getElementById('dem-analysis-slope-section')?.classList.remove('hidden');
        } else if (this.currentOperation === 'hillshade') {
            document.getElementById('dem-analysis-hillshade-section')?.classList.remove('hidden');
        } else if (this.currentOperation === 'relief') {
            document.getElementById('dem-analysis-relief-section')?.classList.remove('hidden');
        } else if (this.currentOperation === 'twi') {
            document.getElementById('dem-analysis-twi-section')?.classList.remove('hidden');
        }

        const title = document.getElementById('dem-analysis-title');
        if (title) title.textContent = `DEM Analysis - ${DEM_OPERATIONS[this.currentOperation].title}`;

        const nameInput = document.getElementById('dem-analysis-name-input');
        if (nameInput && (options.resetName || !nameInput.value.trim())) {
            nameInput.value = `${DEM_OPERATIONS[this.currentOperation].prefix}_${Date.now()}`;
        }

        this.handleInputChange();
    }

    handleInputChange() {
        this._renderRasterHint();

        const runButton = document.getElementById('dem-analysis-run-btn');
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
            await RasterAPI.demAnalysis(payload);
            this.closeModal();
            await this.app.raster.refreshData();
        } catch (error) {
            console.error('[DEMAnalysisModule] analysis failed:', error);
            alert(`DEM analysis failed: ${error.message}`);
        } finally {
            this.app.ui.showGlobalLoader(false);
        }
    }

    _readPayload() {
        return {
            rasterId: Number(document.getElementById('dem-analysis-raster-select')?.value),
            operation: this.currentOperation,
            bandIndex: this._integer('dem-analysis-band-index', 1),
            zFactor: this._number('dem-analysis-z-factor', 1),
            slopeUnit: document.getElementById('dem-analysis-slope-unit')?.value || 'degrees',
            hillshadeAzimuth: this._number('dem-analysis-hillshade-azimuth', 315),
            hillshadeAltitude: this._number('dem-analysis-hillshade-altitude', 45),
            reliefWindowSize: this._integer('dem-analysis-relief-window-size', 3),
            minSlopeDegrees: this._number('dem-analysis-min-slope-degrees', 0.1),
            newName: document.getElementById('dem-analysis-name-input')?.value?.trim(),
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
        if (!Number.isInteger(payload.bandIndex) || payload.bandIndex < 1) return false;
        const raster = this._selectedRaster();
        if (raster && payload.bandIndex > Number(raster.bands)) return false;
        if (!Number.isFinite(payload.zFactor) || payload.zFactor <= 0) return false;

        if (payload.operation === 'hillshade') {
            return Number.isFinite(payload.hillshadeAzimuth)
                && payload.hillshadeAltitude > 0
                && payload.hillshadeAltitude <= 90;
        }
        if (payload.operation === 'relief') {
            return Number.isInteger(payload.reliefWindowSize) && payload.reliefWindowSize >= 3;
        }
        if (payload.operation === 'twi') {
            return Number.isFinite(payload.minSlopeDegrees) && payload.minSlopeDegrees > 0;
        }
        return true;
    }

    _renderRasterHint() {
        const hint = document.getElementById('dem-analysis-raster-hint');
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
        const rasterId = Number(document.getElementById('dem-analysis-raster-select')?.value);
        return Store.state.rasters.find((raster) => Number(raster.index_id) === rasterId) ?? null;
    }

    _normalizeOperation(operation) {
        const value = String(operation || '').toLowerCase();
        return DEM_OPERATIONS[value] ? value : 'slope';
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
