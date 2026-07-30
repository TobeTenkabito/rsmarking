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
        this.orderedRasters = [];
        this.autoDatesText = '';
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
            this.orderedRasters = this._orderedRasters(Store.state.rasters);
            select.innerHTML = this._renderRasterOptions();
            const automaticIds = this._automaticSelectionIds(this.orderedRasters);
            Array.from(select.options).forEach((option) => {
                option.selected = automaticIds.has(String(option.value));
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
            this.autoDatesText = this._selectedRasters()
                .map((raster) => this._dateInfo(raster)?.date || '?')
                .join('\n');
            datesInput.value = this.autoDatesText;
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
            const result = await RasterAPI.timeSeriesAnalysis(payload);
            this.closeModal();
            await this.app.raster.refreshData();
            const warnings = result?.time_series?.warnings || [];
            if (warnings.length) {
                const suffix = warnings.length > 1
                    ? ` (+${warnings.length - 1} more)`
                    : '';
                this.app.ui.showToast(`${warnings[0]}${suffix}`, 'warning');
            } else {
                this.app.ui.showToast(
                    `${TIME_SERIES_OPERATIONS[this.currentOperation].title} completed.`,
                    'success'
                );
            }
        } catch (error) {
            console.error('[TimeSeriesModule] analysis failed:', error);
            alert(`${TIME_SERIES_OPERATIONS[this.currentOperation].title} failed: ${error.message}`);
        } finally {
            this.app.ui.showGlobalLoader(false);
        }
    }

    _readPayload() {
        const datesText = document.getElementById('time-series-dates-input')?.value || '';
        return {
            rasterIds: this._selectedRasters().map((raster) => Number(raster.index_id)),
            operation: this.currentOperation,
            bandIndex: this._integer('time-series-band-index', 1),
            // Unedited automatic dates are resolved from persisted backend
            // metadata so client filename guesses never become authoritative.
            dates: datesText.trim() === this.autoDatesText.trim()
                ? ''
                : datesText.trim(),
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
        const rasters = this.orderedRasters.length
            ? this.orderedRasters
            : this._orderedRasters(Store.state.rasters);
        return rasters.map((raster) => {
            const label = raster.file_name || raster.name || `Raster ${raster.index_id}`;
            const dateInfo = this._dateInfo(raster);
            const suffix = dateInfo
                ? ` | ${dateInfo.date} · ${dateInfo.source}`
                : ' | date unknown';
            const safeSuffix = this._escapeHtml(suffix);
            return `<option value="${this._escapeHtml(raster.index_id)}">${this._escapeHtml(label)}${safeSuffix}</option>`;
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
        const datedCount = selected.filter((raster) => this._dateInfo(raster)).length;
        hint.textContent = `${selected.length} raster(s) selected | ${datedCount} dated, ${selected.length - datedCount} unknown | band counts: ${bandCounts.join(', ')}`;
    }

    _selectedRasters() {
        const select = document.getElementById('time-series-raster-select');
        if (!select) return [];
        const ids = Array.from(select.selectedOptions).map((option) => Number(option.value));
        const rasters = this.orderedRasters.length
            ? this.orderedRasters
            : Store.state.rasters;
        return ids
            .map((id) => rasters.find((raster) => Number(raster.index_id) === id))
            .filter(Boolean);
    }

    _dateInfo(raster) {
        const acquired = raster.acquired_at || raster.acquiredAt;
        if (acquired) {
            return {
                date: String(acquired).slice(0, 10),
                source: raster.acquired_at_source || 'metadata',
                confidence: Number(raster.acquired_at_confidence || 0),
            };
        }

        const source = `${raster.file_name || raster.name || ''}`;
        const ymd = source.match(/((?:19|20)\d{2})[-_./]?(0[1-9]|1[0-2])[-_./]?([0-2]\d|3[01])/);
        if (ymd) {
            const year = Number(ymd[1]);
            const month = Number(ymd[2]);
            const day = Number(ymd[3]);
            const parsed = new Date(Date.UTC(year, month - 1, day));
            if (
                parsed.getUTCFullYear() !== year
                || parsed.getUTCMonth() !== month - 1
                || parsed.getUTCDate() !== day
            ) {
                return null;
            }
            return {
                date: [
                    String(year).padStart(4, '0'),
                    String(month).padStart(2, '0'),
                    String(day).padStart(2, '0'),
                ].join('-'),
                source: 'filename',
                confidence: 0.55,
            };
        }
        return null;
    }

    _dateParts(value) {
        const text = String(value || '').trim();
        if (!text) return [];
        return text
            .split(/[\n,;]/)
            .map((part) => part.trim());
    }

    _orderedRasters(rasters) {
        return [...rasters]
            .map((raster, index) => ({ raster, index, info: this._dateInfo(raster) }))
            .sort((left, right) => {
                if (left.info && right.info) {
                    const comparison = left.info.date.localeCompare(right.info.date);
                    return comparison || left.index - right.index;
                }
                if (left.info) return -1;
                if (right.info) return 1;
                return left.index - right.index;
            })
            .map((entry) => entry.raster);
    }

    _automaticSelectionIds(rasters) {
        const groups = new Map();
        rasters.forEach((raster) => {
            const key = this._seriesKey(raster);
            if (!groups.has(key)) groups.set(key, []);
            groups.get(key).push(raster);
        });
        const candidates = [...groups.values()].sort((left, right) => {
            if (right.length !== left.length) return right.length - left.length;
            const rightDated = right.filter((raster) => this._dateInfo(raster)).length;
            const leftDated = left.filter((raster) => this._dateInfo(raster)).length;
            return rightDated - leftDated;
        });
        const selected = candidates[0] || rasters;
        return new Set(selected.map((raster) => String(raster.index_id)));
    }

    _seriesKey(raster) {
        const productKey = [
            raster.platform || '',
            raster.sensor || '',
            raster.processing_level || '',
            raster.tile_id || '',
        ].join('|').toLowerCase();
        const spatialKey = this._spatialKey(raster);
        const gridKey = [
            raster.crs || '',
            raster.width || '',
            raster.height || '',
            Number(raster.resolution_x || 0).toPrecision(8),
            Number(raster.resolution_y || 0).toPrecision(8),
            ...(Array.isArray(raster.bounds)
                ? raster.bounds.map((value) => Number(value).toPrecision(10))
                : []),
            raster.bands || '',
        ].join('|').toLowerCase();
        if (productKey.replace(/\|/g, '')) {
            const tileId = String(raster.tile_id || '').trim();
            return tileId
                ? `${productKey}|${raster.bands || ''}`
                : `${productKey}|${spatialKey || gridKey}|${raster.bands || ''}`;
        }
        return spatialKey ? `${spatialKey}|${raster.bands || ''}` : gridKey;
    }

    _spatialKey(raster) {
        const bounds = Array.isArray(raster.bounds_wgs84)
            ? raster.bounds_wgs84.map(Number)
            : [];
        if (bounds.length >= 4 && bounds.slice(0, 4).every(Number.isFinite)) {
            const [west, south, east, north] = bounds;
            return [
                'wgs84',
                ((west + east) / 2).toFixed(3),
                ((south + north) / 2).toFixed(3),
                Math.abs(east - west).toFixed(3),
                Math.abs(north - south).toFixed(3),
            ].join('|');
        }
        const center = Array.isArray(raster.center) ? raster.center.map(Number) : [];
        if (center.length >= 2 && center.slice(0, 2).every(Number.isFinite)) {
            return `center|${center[0].toFixed(3)}|${center[1].toFixed(3)}`;
        }
        return '';
    }

    _escapeHtml(value) {
        return String(value ?? '')
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;')
            .replace(/'/g, '&#039;');
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
