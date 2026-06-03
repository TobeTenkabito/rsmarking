import { VectorAPI }      from '../api/vector.js';
import { RasterAPI }      from '../api/raster.js';
import { ModalComponent } from '../../../ui/src/components/Modal.js';
import { Store }          from '../store/index.js';

/**
 * mode: 'vector' | 'raster'
 * VectorEnglish：English × English feature English，Editable feature English
 * English：English，EnglishSystem Fields（Read-only）+ English（Editable default_val）
 */
export class AttributeTable {

    constructor(app) {
        this.app       = app;
        this.layerId   = null;   // Vector layerId | raster index_id
        this.layerName = '';
        this.mode      = 'vector';   // new

        // VectorEnglish
        this.fields    = [];
        this.features  = [];

        // English
        this.rasterFields = [];  // RasterFieldOut[]

        this._ctxMenu  = null;
        this._expanded = false;

        this._panel     = null;
        this._thead     = null;
        this._tbody     = null;
        this._title     = null;
        this._loader    = null;
        this._count     = null;
        this._expandBtn = null;
        this._addColBtn = null;
        this._toolbar   = null;

        this._layoutStorageKey = 'rsmarking_attr_table_layout';
        this._minWidth = 360;
        this._minHeight = 180;
        this._viewportMargin = 8;
        this._floatingBound = false;
        this._featureById = new Map();
        this._rasterFieldById = new Map();
        this._resizeFrame = null;
        this._layoutFrame = null;
        this._pendingLayout = null;
    }

    _initDom() {
        if (this._panel) return;
        this._panel     = document.getElementById('attr-table-panel');
        this._toolbar   = document.getElementById('attr-toolbar');
        this._thead     = document.getElementById('attr-table-head');
        this._tbody     = document.getElementById('attr-table-body');
        this._title     = document.getElementById('attr-table-title');
        this._loader    = document.getElementById('attr-table-loader');
        this._count     = document.getElementById('attr-table-count');
        this._expandBtn = document.getElementById('attr-expand-btn');
        this._addColBtn = document.getElementById('attr-add-col-btn');
        this._modeBadge = document.getElementById('attr-mode-badge');
        this._restoreLayout();
        this._bindFloatingControls();
    }

    /** EnglishVectorAttribute table */
    async open(layerId, layerName = '') {
        this._initDom();
        this.mode      = 'vector';
        this.layerId   = layerId;
        this.layerName = layerName;
        this._syncToolbar();
        this._panel.classList.remove('hidden');
        this._clampPanelToViewport();
        this._setTitle(layerName);
        await this.refresh();
    }

    /** EnglishAttribute table */
    async openRaster(rasterId, rasterName = '', rasterMeta = null) {
        this._initDom();
        this.mode      = 'raster';
        this.layerId   = rasterId;
        this.layerName = rasterName;
        this.rasterMeta  = rasterMeta;
        this._syncToolbar();
        this._panel.classList.remove('hidden');
        this._clampPanelToViewport();
        this._setTitle(rasterName);
        await this.refresh();
    }

    close() {
        this._initDom();
        this.layerId = null;
        this._persistLayout();
        this._panel.classList.add('hidden');
        this._hideCtxMenu();
    }

    async refresh() {
        if (!this.layerId) return;
        this._initDom();
        this._loading(true);
        if (this._tbody) {
            this._tbody.innerHTML = ModalComponent.renderAttrTableLoading();
        }
        try {
            if (this.mode === 'raster') {
                await this._refreshRaster();
            } else {
                await this._refreshVector();
            }
        } catch (err) {
            console.error('[AttributeTable] Load failed:', err);
            if (this._tbody) {
                this._tbody.innerHTML = `
                    <tr><td colspan="99"
                        class="py-8 text-center text-xs text-red-400">
                        Load failed：${err.message}
                    </td></tr>`;
            }
        } finally {
            this._loading(false);
        }
    }

    async _refreshVector() {
        const [fields, fc] = await Promise.all([
            VectorAPI.fetchFields(this.layerId),
            VectorAPI.fetchFeaturesInBbox(this.layerId, [-180, -90, 180, 90]),
        ]);
        this.fields   = fields;
        this.features = fc.features ?? [];
        this._render();
    }

    async _refreshRaster() {
        const userFields = await RasterAPI.getFields(this.layerId);
        const metaFields = this._buildMetaFields(this.rasterMeta);
        const metaNames = new Set(metaFields.map(f => f.field_name));
        const filteredUser = (Array.isArray(userFields) ? userFields : []).filter(f => !metaNames.has(f.field_name));
        this.rasterFields = [...metaFields, ...filteredUser];
        this._render();
    }

    _buildMetaFields(meta) {
    if (!meta) return [];

    const schema = [
        { field_name: 'file_name',  field_alias: 'File Name',      field_type: 'string' },
        { field_name: 'width',      field_alias: 'Width (px)',   field_type: 'number' },
        { field_name: 'height',     field_alias: 'Height (px)',   field_type: 'number' },
        { field_name: 'bands',      field_alias: 'Band Count',      field_type: 'number' },
        { field_name: 'crs',        field_alias: 'CRS',      field_type: 'string' },
        { field_name: 'data_type',  field_alias: 'Data Type',    field_type: 'string' },
        { field_name: 'nodata',     field_alias: 'NoData Value',   field_type: 'string' },
        { field_name: 'resolution', field_alias: 'Resolution',      field_type: 'string' },
        { field_name: 'bundle_id',  field_alias: 'Bundle ID',   field_type: 'string' },
    ];

    return schema
        .filter(s => meta[s.field_name] !== undefined
                  && meta[s.field_name] !== null
                  && meta[s.field_name] !== '')
        .map((s, i) => ({
            id          : `__meta__${s.field_name}`,
            field_name  : s.field_name,
            field_alias : s.field_alias,
            field_type  : s.field_type,
            default_val : String(meta[s.field_name]),
            is_system   : true,
            field_order : -(schema.length - i),
        }));
    }

    _render() {
        if (this.mode === 'raster') {
            this._renderRaster();
        } else {
            this._renderVector();
        }
    }

    _renderVector() {
        this._featureById = new Map(this.features.map(feature => [String(feature.id), feature]));
        if (this._thead) {
            this._thead.innerHTML = ModalComponent.renderAttrTableHead(this.fields);
        }
        if (this._tbody) {
            this._tbody.innerHTML = ModalComponent.renderAttrTableBody(
                this.features,
                this.fields,
                Store.state?.selectedFeatureId ?? null
            );
        }
        if (this._count) {
            this._count.textContent = `${this.features.length} features`;
        }
    }

    _renderRaster() {
        this._rasterFieldById = new Map(this.rasterFields.map(field => [String(field.id), field]));
        if (this._thead) {
            this._thead.innerHTML = ModalComponent.renderRasterFieldTableHead();
        }
        if (this._tbody) {
            this._tbody.innerHTML = ModalComponent.renderRasterFieldTableBody(this.rasterFields);
        }
        if (this._count) {
            let userCount = 0;
            let sysCount = 0;
            for (const field of this.rasterFields) {
                if (field.is_system) sysCount++;
                else userCount++;
            }
            this._count.textContent = `${sysCount} System · ${userCount} custom`;
        }
    }

    /**
     * EnglishToolbarEnglish
     * English：「+ Add Column」→「+ English」
     */
    _syncToolbar() {
    if (!this._addColBtn) this._addColBtn = document.getElementById('attr-add-col-btn');
    if (!this._modeBadge) this._modeBadge = document.getElementById('attr-mode-badge');

    if (this._addColBtn) {
        this._addColBtn.textContent =
            this.mode === 'raster' ? '+ Add Field' : '+ Add Column';
    }
    if (this._modeBadge) {
        this._modeBadge.classList.remove('hidden', 'bg-indigo-100', 'text-indigo-500',
                                                    'bg-amber-100',  'text-amber-600');
        if (this.mode === 'raster') {
            this._modeBadge.classList.add('bg-amber-100', 'text-amber-600');
            this._modeBadge.textContent = 'Raster';
        } else {
            this._modeBadge.classList.add('bg-indigo-100', 'text-indigo-500');
            this._modeBadge.textContent = 'Vector';
        }
        this._modeBadge.classList.remove('hidden');
    }
}

    toggleExpand() {
        this._initDom();
        this._setExpanded(!this._expanded);
    }

    _setExpanded(expanded) {
        this._expanded = expanded;
        if (!this._panel) return;
        const layout = this._clampLayout({
            ...this._getPanelLayout(),
            height: expanded ? 460 : 280,
        });
        this._applyLayout(layout);
        this._persistLayout();
        if (this._expandBtn) {
            this._expandBtn.textContent = expanded ? 'Collapse' : '⬆ Expand';
        }
    }

    async addColumn() {
        if (this.mode === 'raster') return this.addRasterField();

        const name = prompt('Field name (letters and underscores recommended):');
        if (!name?.trim()) return;

        const typeMap = { '1': 'string', '2': 'number', '3': 'boolean', '4': 'date' };
        const choice  = prompt('Field type:\n1. Text (string)\n2. Number (number)\n3. Boolean (boolean)\n4. Date (date)', '1');
        const fieldType = typeMap[choice?.trim()] ?? 'string';

        try {
            await VectorAPI.createField(this.layerId, {
                field_name : name.trim().toLowerCase().replace(/\s+/g, '_'),
                field_alias: name.trim(),
                field_type : fieldType,
                field_order: this.fields.length,
            });
            await this.refresh();
        } catch (err) {
            alert(`Add ColumnFailed：${err.message}`);
        }
    }

    async renameColumn(fieldId, currentAlias) {
        const alias = prompt('New column display name:', currentAlias);
        if (!alias?.trim() || alias === currentAlias) return;
        try {
            await VectorAPI.updateField(this.layerId, fieldId, { field_alias: alias.trim() });
            await this.refresh();
        } catch (err) {
            alert(`Rename failed：${err.message}`);
        }
    }

    async deleteColumn(fieldId, fieldName) {
        if (!confirm(`Delete field「${fieldName}」？\nExisting values for this field will no longer be shown.`)) return;
        try {
            await VectorAPI.deleteField(this.layerId, fieldId);
            await this.refresh();
        } catch (err) {
            alert(`Delete column failed：${err.message}`);
        }
    }

    exportCsv() {
        const rows = this.mode === 'raster'
            ? this._buildRasterCsvRows()
            : this._buildVectorCsvRows();

        if (rows.length <= 1) {
            alert('No attribute data to export.');
            return;
        }

        const csv = rows
            .map(row => row.map(v => this._csvCell(v)).join(','))
            .join('\r\n');
        const blob = new Blob([`\ufeff${csv}`], { type: 'text/csv;charset=utf-8;' });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = this._csvFileName();
        document.body.appendChild(a);
        a.click();
        a.remove();
        URL.revokeObjectURL(url);
    }

    _buildVectorCsvRows() {
        const header = [
            'feature_id',
            ...this.fields.map(f => f.field_alias || f.field_name),
        ];
        const rows = this.features.map(feature => [
            feature.id ?? '',
            ...this.fields.map(f => feature.properties?.[f.field_name] ?? ''),
        ]);

        return [header, ...rows];
    }

    _buildRasterCsvRows() {
        const header = ['field_name', 'display_name', 'type', 'value', 'scope'];
        const rows = this.rasterFields.map(field => [
            field.field_name ?? '',
            field.field_alias || field.field_name || '',
            field.field_type ?? '',
            field.default_val ?? '',
            field.is_system ? 'system' : 'custom',
        ]);

        return [header, ...rows];
    }

    _csvCell(value) {
        if (value === null || value === undefined) return '';

        let text;
        if (Array.isArray(value)) {
            text = value.join('; ');
        } else if (typeof value === 'object') {
            text = JSON.stringify(value);
        } else {
            text = String(value);
        }

        if (/[",\r\n]/.test(text)) {
            return `"${text.replace(/"/g, '""')}"`;
        }
        return text;
    }

    _csvFileName() {
        const base = `${this.mode}_${this.layerName || this.layerId || 'attributes'}`
            .trim()
            .replace(/[\\/:*?"<>|]+/g, '_')
            .replace(/\s+/g, '_')
            .slice(0, 80) || 'attributes';

        return `${base}_attributes.csv`;
    }

    showColumnMenu(event, fieldId, fieldName, isSystem) {
        event.preventDefault();
        this._hideCtxMenu();

        const menu = document.createElement('div');
        menu.className = 'attr-ctx-menu';
        menu.style.left = `${event.clientX}px`;
        menu.style.top  = `${event.clientY}px`;
        menu.innerHTML  = `
            <button class="ctx-item"
                onclick="RS.attrRenameColumn('${fieldId}','${fieldName}')">
                Rename
            </button>
            ${isSystem
                ? `<div class="ctx-disabled">🔒 System fields cannot be deleted</div>`
                : `<hr class="ctx-sep"/>
                   <button class="ctx-item ctx-danger"
                       onclick="RS.attrDeleteColumn('${fieldId}','${fieldName}')">
                       Delete Column
                   </button>`
            }`;

        document.body.appendChild(menu);
        this._ctxMenu = menu;
        setTimeout(() =>
            document.addEventListener('click', () => this._hideCtxMenu(), { once: true }), 0);
    }

    /** EnglishCustom Fields */
    async addRasterField() {
        const name = prompt('Field name (letters and underscores recommended):');
        if (!name?.trim()) return;

        const typeMap = { '1': 'string', '2': 'number', '3': 'boolean', '4': 'date' };
        const choice  = prompt('Field type:\n1. Text (string)\n2. Number (number)\n3. Boolean (boolean)\n4. Date (date)', '1');
        const fieldType = typeMap[choice?.trim()] ?? 'string';

        try {
            await RasterAPI.createField(this.layerId, {
                field_name : name.trim().toLowerCase().replace(/\s+/g, '_'),
                field_alias: name.trim(),
                field_type : fieldType,
                field_order: this.rasterFields.length,
            });
            await this.refresh();
        } catch (err) {
            alert(`Add field failed：${err.message}`);
        }
    }

    /** EnglishDisplay Name（EnglishDisplay NameEnglish） */
    async renameRasterField(fieldId, currentAlias) {
        const alias = prompt('New display name:', currentAlias);
        if (!alias?.trim() || alias === currentAlias) return;
        try {
            await RasterAPI.updateField(this.layerId, fieldId, { field_alias: alias.trim() });
            // English
            const f = this._rasterFieldById.get(String(fieldId));
            if (f) f.field_alias = alias.trim();
            this._render();
        } catch (err) {
            alert(`Rename failed：${err.message}`);
            await this.refresh();
        }
    }

    /** English */
    async deleteRasterField(fieldId, fieldName) {
        if (!confirm(`Delete field「${fieldName}」？`)) return;
        try {
            await RasterAPI.deleteField(this.layerId, fieldId);
            // English
            this.rasterFields = this.rasterFields.filter(f => String(f.id) !== String(fieldId));
            this._render();
        } catch (err) {
            alert(`Delete failed：${err.message}`);
            await this.refresh();
        }
    }

    /**
     * EnglishDefault Value（EnglishDefault ValueEnglish）
     * @param {HTMLTableCellElement} td
     */
    editRasterDefault(td) {
        if (td.querySelector('input,select')) return;

        const { fieldId, fieldType } = td.dataset;
        const field   = this._rasterFieldById.get(String(fieldId));
        const rawVal  = field?.default_val ?? '';
        const span    = td.querySelector('.cell-val');
        span.classList.add('hidden');

        const editor = this._makeEditor(fieldType, rawVal);
        editor.classList.add('cell-editor');
        td.appendChild(editor);
        editor.focus();

        let committed = false;

        const commit = async () => {
            if (committed) return;
            committed = true;

            const editorVal = editor.tagName === 'SELECT' ? editor.dataset.val : editor.value;
            const newVal    = this._parseVal(editorVal, fieldType);

            editor.remove();
            span.classList.remove('hidden');

            // English
            const newStr = String(newVal ?? '');
            const oldStr = String(rawVal ?? '');
            if (newStr === oldStr) return;

            // English UI
            span.innerHTML = ModalComponent._attrFmtVal(newVal, fieldType);

            try {
                await RasterAPI.updateField(this.layerId, fieldId, {
                    default_val: newVal === null ? null : String(newVal),
                });
                // English
                if (field) field.default_val = newVal === null ? null : String(newVal);
            } catch (err) {
                console.error('[AttributeTable] Failed to save default value:', err);
                span.innerHTML = ModalComponent._attrFmtVal(rawVal, fieldType);
                await this.refresh();
            }
        };

        editor.addEventListener('blur', commit);
        editor.addEventListener('keydown', e => {
            if (e.key === 'Enter')  { e.preventDefault(); editor.blur(); }
            if (e.key === 'Escape') {
                committed = true;
                editor.remove();
                span.classList.remove('hidden');
            }
        });
    }

    editCell(td) {
        if (td.querySelector('input,select')) return;

        const { featureId, fieldName, fieldType } = td.dataset;
        const feature  = this._featureById.get(String(featureId));
        const rawVal   = feature?.properties?.[fieldName] ?? '';

        const span = td.querySelector('.cell-val');
        span.classList.add('hidden');

        const editor = this._makeEditor(fieldType, rawVal);
        editor.classList.add('cell-editor');
        td.appendChild(editor);
        editor.focus();

        let committed = false;

        const commit = async () => {
            if (committed) return;
            committed = true;

            const editorVal = editor.tagName === 'SELECT' ? editor.dataset.val : editor.value;
            const newVal    = this._parseVal(editorVal, fieldType);

            editor.remove();
            span.classList.remove('hidden');

            if (newVal === rawVal || (newVal == null && rawVal === '')) return;

            span.innerHTML = ModalComponent._attrFmtVal(newVal, fieldType);
            td.dataset.raw = String(newVal ?? '');

            try {
                await VectorAPI.updateFeature(featureId, {
                    properties: { [fieldName]: newVal }
                });
                if (feature) {
                    feature.properties = {
                        ...(feature.properties ?? {}),
                        [fieldName]: newVal,
                    };
                }
            } catch (err) {
                console.error('[AttributeTable] Save failed:', err);
                span.innerHTML = ModalComponent._attrFmtVal(rawVal, fieldType);
                td.dataset.raw = String(rawVal ?? '');
            }
        };

        editor.addEventListener('blur', commit);
        editor.addEventListener('keydown', e => {
            if (e.key === 'Enter')  { e.preventDefault(); editor.blur(); }
            if (e.key === 'Escape') {
                committed = true;
                editor.remove();
                span.classList.remove('hidden');
            }
        });
    }

    async deleteFeature(featureId) {
        if (!confirm('Delete this feature? This action cannot be undone.')) return;
        try {
            await VectorAPI.deleteFeature(featureId);
            this.features = this.features.filter(f => String(f.id) !== String(featureId));
            this._render();
            if (this.app.mapController?.refreshVectorLayer) {
                await this.app.mapController.refreshVectorLayer(this.layerId);
            }
        } catch (err) {
            alert(`Delete failed：${err.message}`);
        }
    }

    _bindFloatingControls() {
        if (!this._panel || this._floatingBound) return;
        this._floatingBound = true;

        this._toolbar?.addEventListener('mousedown', e => {
            if (e.button !== 0) return;
            if (e.target.closest('button,input,select,textarea,a,[data-attr-resize]')) return;
            this._startPanelDrag(e);
        });

        this._panel.querySelectorAll('[data-attr-resize]').forEach(handle => {
            handle.addEventListener('mousedown', e => {
                if (e.button !== 0) return;
                e.stopPropagation();
                this._startPanelResize(e, handle.dataset.attrResize);
            });
        });

        window.addEventListener('resize', () => {
            if (!this._panel || this._panel.classList.contains('hidden')) return;
            if (this._resizeFrame) return;
            this._resizeFrame = requestAnimationFrame(() => {
                this._resizeFrame = null;
                this._clampPanelToViewport();
                this._persistLayout();
            });
        });
    }

    _startPanelDrag(e) {
        e.preventDefault();
        const start = this._getPanelLayout();
        const startX = e.clientX;
        const startY = e.clientY;
        this._beginPanelInteraction();

        const onMove = mv => {
            const next = this._clampLayout({
                ...start,
                left: start.left + mv.clientX - startX,
                top: start.top + mv.clientY - startY,
            });
            this._scheduleApplyLayout(next);
        };
        const onUp = () => this._finishPanelInteraction(onMove, onUp);

        document.addEventListener('mousemove', onMove);
        document.addEventListener('mouseup', onUp);
    }

    _startPanelResize(e, direction) {
        e.preventDefault();
        const start = this._getPanelLayout();
        const startX = e.clientX;
        const startY = e.clientY;
        this._beginPanelInteraction();

        const onMove = mv => {
            const dx = mv.clientX - startX;
            const dy = mv.clientY - startY;
            const next = { ...start };
            const limits = this._getLayoutLimits();

            if (direction.includes('e')) next.width = start.width + dx;
            if (direction.includes('s')) next.height = start.height + dy;
            if (direction.includes('w')) {
                next.left = start.left + dx;
                next.width = start.width - dx;
                if (next.width < limits.minWidth) {
                    next.width = limits.minWidth;
                    next.left = start.left + start.width - limits.minWidth;
                }
                if (next.width > limits.maxWidth) {
                    next.width = limits.maxWidth;
                    next.left = start.left + start.width - limits.maxWidth;
                }
            }
            if (direction.includes('n')) {
                next.top = start.top + dy;
                next.height = start.height - dy;
                if (next.height < limits.minHeight) {
                    next.height = limits.minHeight;
                    next.top = start.top + start.height - limits.minHeight;
                }
                if (next.height > limits.maxHeight) {
                    next.height = limits.maxHeight;
                    next.top = start.top + start.height - limits.maxHeight;
                }
            }

            this._scheduleApplyLayout(this._clampLayout(next));
            this._syncExpandedStateFromHeight();
        };
        const onUp = () => this._finishPanelInteraction(onMove, onUp);

        document.addEventListener('mousemove', onMove);
        document.addEventListener('mouseup', onUp);
    }

    _beginPanelInteraction() {
        document.body.style.userSelect = 'none';
        document.body.style.cursor = 'grabbing';
        this._panel?.classList.add('is-moving');
    }

    _finishPanelInteraction(onMove, onUp) {
        document.removeEventListener('mousemove', onMove);
        document.removeEventListener('mouseup', onUp);
        if (this._pendingLayout) {
            this._applyLayout(this._pendingLayout);
            this._pendingLayout = null;
        }
        document.body.style.userSelect = '';
        document.body.style.cursor = '';
        this._panel?.classList.remove('is-moving');
        this._syncExpandedStateFromHeight();
        this._persistLayout();
    }

    _getPanelLayout() {
        const rect = this._panel.getBoundingClientRect();
        const fallback = this._defaultLayout();
        return {
            left: Number.isFinite(rect.left) && rect.width ? rect.left : this._readPxStyle('left', fallback.left),
            top: Number.isFinite(rect.top) && rect.height ? rect.top : this._readPxStyle('top', fallback.top),
            width: rect.width || this._readPxStyle('width', fallback.width),
            height: rect.height || this._readPxStyle('height', fallback.height),
        };
    }

    _readPxStyle(prop, fallback) {
        const value = parseFloat(this._panel?.style?.[prop]);
        return Number.isFinite(value) ? value : fallback;
    }

    _defaultLayout() {
        const margin = this._viewportMargin;
        const width = Math.min(920, Math.max(this._minWidth, window.innerWidth - margin * 2));
        const height = 280;
        return {
            left: margin + 4,
            top: Math.max(margin, window.innerHeight - height - margin - 4),
            width,
            height,
        };
    }

    _restoreLayout() {
        const saved = this._loadLayout();
        this._applyLayout(this._clampLayout(saved || this._defaultLayout()));
        this._syncExpandedStateFromHeight();
    }

    _loadLayout() {
        try {
            const raw = localStorage.getItem(this._layoutStorageKey);
            if (!raw) return null;
            const parsed = JSON.parse(raw);
            const keys = ['left', 'top', 'width', 'height'];
            if (!keys.every(key => Number.isFinite(Number(parsed[key])))) return null;
            return Object.fromEntries(keys.map(key => [key, Number(parsed[key])]));
        } catch {
            return null;
        }
    }

    _persistLayout() {
        if (!this._panel) return;
        try {
            localStorage.setItem(this._layoutStorageKey, JSON.stringify(this._getPanelLayout()));
        } catch {
            // Ignore storage failures in private or restricted browser modes.
        }
    }

    _clampPanelToViewport() {
        this._applyLayout(this._clampLayout(this._getPanelLayout()));
    }

    _clampLayout(layout) {
        const limits = this._getLayoutLimits();
        const width = Math.min(Math.max(layout.width, limits.minWidth), limits.maxWidth);
        const height = Math.min(Math.max(layout.height, limits.minHeight), limits.maxHeight);
        const left = Math.min(Math.max(layout.left, limits.margin), Math.max(limits.margin, window.innerWidth - width - limits.margin));
        const top = Math.min(Math.max(layout.top, limits.margin), Math.max(limits.margin, window.innerHeight - height - limits.margin));

        return { left, top, width, height };
    }

    _getLayoutLimits() {
        const margin = this._viewportMargin;
        const maxWidth = Math.max(120, window.innerWidth - margin * 2);
        const maxHeight = Math.max(120, window.innerHeight - margin * 2);
        const minWidth = Math.min(this._minWidth, maxWidth);
        const minHeight = Math.min(this._minHeight, maxHeight);

        return { margin, minWidth, minHeight, maxWidth, maxHeight };
    }

    _applyLayout(layout) {
        if (!this._panel) return;
        this._panel.style.left = `${Math.round(layout.left)}px`;
        this._panel.style.top = `${Math.round(layout.top)}px`;
        this._panel.style.width = `${Math.round(layout.width)}px`;
        this._panel.style.height = `${Math.round(layout.height)}px`;
        this._panel.style.right = 'auto';
        this._panel.style.bottom = 'auto';
    }

    _scheduleApplyLayout(layout) {
        this._pendingLayout = layout;
        if (this._layoutFrame) return;
        this._layoutFrame = requestAnimationFrame(() => {
            this._layoutFrame = null;
            const next = this._pendingLayout;
            this._pendingLayout = null;
            if (next) this._applyLayout(next);
        });
    }

    _syncExpandedStateFromHeight() {
        const height = this._getPanelLayout().height;
        this._expanded = height > 340;
        if (this._expandBtn) {
            this._expandBtn.textContent = this._expanded ? 'Collapse' : '⬆ Expand';
        }
    }

    _makeEditor(fieldType, rawValue) {
        if (fieldType === 'boolean') {
            const sel = document.createElement('select');
            sel.innerHTML = `<option value="true">Yes</option><option value="false">No</option>`;
            sel.value = String(rawValue) === 'true' ? 'true' : 'false';
            sel.dataset.val = sel.value;
            sel.addEventListener('change', () => { sel.dataset.val = sel.value; });
            return sel;
        }
        const input = document.createElement('input');
        input.type  = { number: 'number', date: 'date' }[fieldType] ?? 'text';
        input.value = rawValue ?? '';
        return input;
    }

    _parseVal(val, type) {
        if (type === 'number')  return val === '' ? null : Number(val);
        if (type === 'boolean') return val === 'true';
        return val;
    }

    _setTitle(name) {
        if (this._title) this._title.textContent = `Attribute table: ${name}`;
    }

    _loading(show) {
        this._loader?.classList.toggle('hidden', !show);
    }

    _hideCtxMenu() {
        this._ctxMenu?.remove();
        this._ctxMenu = null;
    }
}
