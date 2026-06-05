import { RasterAPI } from '../api/raster.js';
import { Store } from '../store/index.js';


const TIME_SERIES_OPERATIONS = {
    monthly_composite: {
        title: 'Monthly Compositing',
        prefix: 'TS_Monthly',
        minInputs: 1,
    },
    annual_composite: {
        title: 'Annual Compositing',
        prefix: 'TS_Annual',
        minInputs: 1,
    },
    maximum_composite: {
        title: 'Maximum Value Compositing',
        prefix: 'TS_Maximum',
        minInputs: 1,
    },
    median_composite: {
        title: 'Median Compositing',
        prefix: 'TS_Median',
        minInputs: 1,
    },
    moving_window_smoothing: {
        title: 'Moving Window Smoothing',
        prefix: 'TS_MovingSmooth',
        minInputs: 2,
    },
    savitzky_golay: {
        title: 'Savitzky-Golay Filtering',
        prefix: 'TS_SavGol',
        minInputs: 3,
    },
    trend: {
        title: 'Trend Analysis',
        prefix: 'TS_Trend',
        minInputs: 2,
    },
    seasonality: {
        title: 'Seasonality Analysis',
        prefix: 'TS_Seasonality',
        minInputs: 2,
    },
    phenology: {
        title: 'Phenological Parameters',
        prefix: 'TS_Phenology',
        minInputs: 2,
    },
};


export class TimeSeriesModule {
    constructor(app) {
        this.app = app;
        this.currentOperation = 'monthly_composite';
    }

    openModal(operation = 'monthly_composite') {
        if (Store.state.rasters.length === 0) {
            alert('Prepare time-series imagery first.');
            return;
        }

        const modal = document.getElementById('time-series-modal');
        if (!modal) return;

        const select = document.getElementById('time-series-raster-select');
        if (select) {
            select.innerHTML = this._renderRasterOptions();
            Array.from(select.options).forEach((option) => {
                option.selected = true;
            });
        }

        this.switchOperation(this._normalizeOperation(operation), { resetName: true });
        this.handleSelectionChange();
        modal.classList.remove('hidden');
    }

    closeModal() {
        document.getElementById('time-series-modal')?.classList.add('hidden');
    }

    switchOperation(operation, options = {}) {
        this.currentOperation = this._normalizeOperation(operation);

        const operationSelect = document.getElementById('time-series-operation-select');
        if (operationSelect) operationSelect.value = this.currentOperation;

        document.querySelectorAll('.time-series-option').forEach((section) => {
            section.classList.add('hidden');
        });

        if (this.currentOperation === 'moving_window_smoothing') {
            document.getElementById('time-series-moving-section')?.classList.remove('hidden');
        } else if (this.currentOperation === 'savitzky_golay') {
            document.getElementById('time-series-savgol-section')?.classList.remove('hidden');
        } else if (this.currentOperation === 'phenology') {
            document.getElementById('time-series-phenology-section')?.classList.remove('hidden');
        }

        const title = document.getElementById('time-series-title');
        if (title) title.textContent = `Time-Series Analysis - ${TIME_SERIES_OPERATIONS[this.currentOperation].title}`;

        const nameInput = document.getElementById('time-series-name-input');
        if (nameInput && (options.resetName || !nameInput.value.trim())) {
            nameInput.value = `${TIME_SERIES_OPERATIONS[this.currentOperation].prefix}_${Date.now()}`;
        }

        this.handleInputChange();
    }

    handleSelectionChange() {
        this._renderSelectionHint();
        const datesInput = document.getElementById('time-series-dates-input');
        if (datesInput) {
            datesInput.value = this._selectedRasters()
                .map((raster) => this._inferDate(raster))
                .filter(Boolean)
                .join(', ');
        }
        this.handleInputChange();
    }

    handleInputChange() {
        this._renderSelectionHint();

        const runButton = document.getElementById('time-series-run-btn');
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
            await RasterAPI.timeSeriesAnalysis(payload);
            this.closeModal();
            await this.app.raster.refreshData();
        } catch (error) {
            console.error('[TimeSeriesModule] analysis failed:', error);
            alert(`${TIME_SERIES_OPERATIONS[this.currentOperation].title} failed: ${error.message}`);
        } finally {
            this.app.ui.showGlobalLoader(false);
        }
    }

    _readPayload() {
        return {
            rasterIds: this._selectedRasters().map((raster) => Number(raster.index_id)),
            operation: this.currentOperation,
            bandIndex: this._integer('time-series-band-index', 1),
            dates: document.getElementById('time-series-dates-input')?.value?.trim() || '',
            movingWindowSize: this._integer('time-series-moving-window-size', 3),
            savgolWindowLength: this._integer('time-series-savgol-window-length', 5),
            savgolPolyorder: this._integer('time-series-savgol-polyorder', 2),
            phenologyThresholdRatio: this._number('time-series-phenology-threshold', 0.2),
            newName: document.getElementById('time-series-name-input')?.value?.trim(),
        };
    }

    _isValidForm() {
        let payload;
        try {
            payload = this._readPayload();
        } catch {
            return false;
        }

        const selected = this._selectedRasters();
        const minInputs = TIME_SERIES_OPERATIONS[this.currentOperation].minInputs;
        if (!payload.newName || selected.length < minInputs) return false;
        if (!Number.isInteger(payload.bandIndex) || payload.bandIndex < 1) return false;
        if (selected.some((raster) => payload.bandIndex > Number(raster.bands))) return false;

        const dateParts = this._dateParts(payload.dates);
        if (dateParts.length > 0 && dateParts.length !== selected.length) return false;

        if (payload.operation === 'moving_window_smoothing') {
            return Number.isInteger(payload.movingWindowSize) && payload.movingWindowSize >= 1;
        }
        if (payload.operation === 'savitzky_golay') {
            return Number.isInteger(payload.savgolWindowLength)
                && payload.savgolWindowLength >= 3
                && Number.isInteger(payload.savgolPolyorder)
                && payload.savgolPolyorder >= 0
                && payload.savgolPolyorder < payload.savgolWindowLength;
        }
        if (payload.operation === 'phenology') {
            return Number.isFinite(payload.phenologyThresholdRatio)
                && payload.phenologyThresholdRatio >= 0
                && payload.phenologyThresholdRatio <= 1;
        }
        return true;
    }

    _renderRasterOptions() {
        return Store.state.rasters.map((raster) => {
            const label = raster.file_name || raster.name || `Raster ${raster.index_id}`;
            const date = this._inferDate(raster);
            const suffix = date ? ` | ${date}` : '';
            return `<option value="${raster.index_id}">${label}${suffix}</option>`;
        }).join('');
    }

    _renderSelectionHint() {
        const hint = document.getElementById('time-series-selection-hint');
        if (!hint) return;
        const selected = this._selectedRasters();
        if (!selected.length) {
            hint.textContent = '';
            return;
        }

        const bandCounts = [...new Set(selected.map((raster) => Number(raster.bands)))].sort((a, b) => a - b);
        hint.textContent = `${selected.length} raster(s) selected | band counts: ${bandCounts.join(', ')}`;
    }

    _selectedRasters() {
        const select = document.getElementById('time-series-raster-select');
        if (!select) return [];
        const ids = Array.from(select.selectedOptions).map((option) => Number(option.value));
        return ids
            .map((id) => Store.state.rasters.find((raster) => Number(raster.index_id) === id))
            .filter(Boolean);
    }

    _inferDate(raster) {
        const source = `${raster.file_name || raster.name || ''}`;
        const ymd = source.match(/(19|20)\d{2}[-_./]?(0[1-9]|1[0-2])[-_./]?([0-2]\d|3[01])/);
        if (ymd) {
            const text = ymd[0].replace(/[_.\/]/g, '-');
            if (/^\d{8}$/.test(text)) return `${text.slice(0, 4)}-${text.slice(4, 6)}-${text.slice(6, 8)}`;
            return text;
        }
        const ym = source.match(/(19|20)\d{2}[-_./]?(0[1-9]|1[0-2])/);
        if (ym) {
            const text = ym[0].replace(/[_.\/]/g, '-');
            if (/^\d{6}$/.test(text)) return `${text.slice(0, 4)}-${text.slice(4, 6)}-01`;
            return `${text}-01`;
        }
        const created = raster.created_at || raster.createdAt;
        if (created) return String(created).slice(0, 10);
        return '';
    }

    _dateParts(value) {
        return String(value || '')
            .split(/[\n,;]+/)
            .map((part) => part.trim())
            .filter(Boolean);
    }

    _normalizeOperation(operation) {
        const value = String(operation || '').toLowerCase().replace(/-/g, '_');
        return TIME_SERIES_OPERATIONS[value] ? value : 'monthly_composite';
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
