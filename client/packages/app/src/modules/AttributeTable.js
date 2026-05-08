import { VectorAPI }      from '../api/vector.js';
import { RasterAPI }      from '../api/raster.js';
import { ModalComponent } from '../../../ui/src/components/Modal.js';
import { Store }          from '../store/index.js';

/**
 * mode: 'vector' | 'raster'
 * 矢量模式：横向字段列 × 纵向 feature 行，可编辑 feature 属性值
 * 栅格模式：纵向字段行，分系统字段（只读）+ 用户字段（可编辑 default_val）
 */
export class AttributeTable {

    constructor(app) {
        this.app       = app;
        this.layerId   = null;   // 矢量 layerId  | 栅格 raster index_id
        this.layerName = '';
        this.mode      = 'vector';   // ← 新增

        // 矢量专用
        this.fields    = [];
        this.features  = [];

        // 栅格专用
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

    /** 打开矢量属性表 */
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

    /** 打开栅格属性表 */
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
            console.error('[AttributeTable] 加载失败:', err);
            if (this._tbody) {
                this._tbody.innerHTML = `
                    <tr><td colspan="99"
                        class="py-8 text-center text-xs text-red-400">
                        加载失败：${err.message}
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
        { field_name: 'file_name',  field_alias: '文件名',      field_type: 'string' },
        { field_name: 'width',      field_alias: '宽度 (px)',   field_type: 'number' },
        { field_name: 'height',     field_alias: '高度 (px)',   field_type: 'number' },
        { field_name: 'bands',      field_alias: '波段数',      field_type: 'number' },
        { field_name: 'crs',        field_alias: '坐标系',      field_type: 'string' },
        { field_name: 'data_type',  field_alias: '数据类型',    field_type: 'string' },
        { field_name: 'nodata',     field_alias: 'NoData 值',   field_type: 'string' },
        { field_name: 'resolution', field_alias: '分辨率',      field_type: 'string' },
        { field_name: 'bundle_id',  field_alias: '数据包 ID',   field_type: 'string' },
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
            this._count.textContent = `${this.features.length} 条要素`;
        }
    }

    _renderRaster() {
        if (this._thead) {
            this._thead.innerHTML = ModalComponent.renderRasterFieldTableHead();
        }
        if (this._tbody) {
            this._tbody.innerHTML = ModalComponent.renderRasterFieldTableBody(this.rasterFields);
        }
        if (this._count) {
            const userCount = this.rasterFields.filter(f => !f.is_system).length;
            const sysCount  = this.rasterFields.filter(f =>  f.is_system).length;
            this._count.textContent = `${sysCount} 系统 · ${userCount} 自定义`;
        }
    }

    /**
     * 切换模式时同步工具栏按钮文案
     * 栅格模式：「+ 新增列」→「+ 新增字段」
     */
    _syncToolbar() {
    if (!this._addColBtn) this._addColBtn = document.getElementById('attr-add-col-btn');
    if (!this._modeBadge) this._modeBadge = document.getElementById('attr-mode-badge');

    if (this._addColBtn) {
        this._addColBtn.textContent =
            this.mode === 'raster' ? '+ 新增字段' : '+ 新增列';
    }
    if (this._modeBadge) {
        this._modeBadge.classList.remove('hidden', 'bg-indigo-100', 'text-indigo-500',
                                                    'bg-amber-100',  'text-amber-600');
        if (this.mode === 'raster') {
            this._modeBadge.classList.add('bg-amber-100', 'text-amber-600');
            this._modeBadge.textContent = '栅格';
        } else {
            this._modeBadge.classList.add('bg-indigo-100', 'text-indigo-500');
            this._modeBadge.textContent = '矢量';
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
            this._expandBtn.textContent = expanded ? '⬇ 收起' : '⬆ 展开';
        }
    }

    async addColumn() {
        if (this.mode === 'raster') return this.addRasterField();

        const name = prompt('字段名（建议英文 + 下划线）：');
        if (!name?.trim()) return;

        const typeMap = { '1': 'string', '2': 'number', '3': 'boolean', '4': 'date' };
        const choice  = prompt('字段类型：\n1. 文本 (string)\n2. 数字 (number)\n3. 布尔 (boolean)\n4. 日期 (date)', '1');
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
            alert(`新增列失败：${err.message}`);
        }
    }

    async renameColumn(fieldId, currentAlias) {
        const alias = prompt('新的列显示名：', currentAlias);
        if (!alias?.trim() || alias === currentAlias) return;
        try {
            await VectorAPI.updateField(this.layerId, fieldId, { field_alias: alias.trim() });
            await this.refresh();
        } catch (err) {
            alert(`重命名失败：${err.message}`);
        }
    }

    async deleteColumn(fieldId, fieldName) {
        if (!confirm(`确定删除字段「${fieldName}」？\n历史数据中该字段的值将不再显示。`)) return;
        try {
            await VectorAPI.deleteField(this.layerId, fieldId);
            await this.refresh();
        } catch (err) {
            alert(`删除列失败：${err.message}`);
        }
    }

    exportCsv() {
        const rows = this.mode === 'raster'
            ? this._buildRasterCsvRows()
            : this._buildVectorCsvRows();

        if (rows.length <= 1) {
            alert('暂无属性数据可导出。');
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
                ✏️ 重命名
            </button>
            ${isSystem
                ? `<div class="ctx-disabled">🔒 系统字段不可删除</div>`
                : `<hr class="ctx-sep"/>
                   <button class="ctx-item ctx-danger"
                       onclick="RS.attrDeleteColumn('${fieldId}','${fieldName}')">
                       🗑 删除列
                   </button>`
            }`;

        document.body.appendChild(menu);
        this._ctxMenu = menu;
        setTimeout(() =>
            document.addEventListener('click', () => this._hideCtxMenu(), { once: true }), 0);
    }

    /** 新增用户自定义字段 */
    async addRasterField() {
        const name = prompt('字段名（建议英文 + 下划线）：');
        if (!name?.trim()) return;

        const typeMap = { '1': 'string', '2': 'number', '3': 'boolean', '4': 'date' };
        const choice  = prompt('字段类型：\n1. 文本 (string)\n2. 数字 (number)\n3. 布尔 (boolean)\n4. 日期 (date)', '1');
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
            alert(`新增字段失败：${err.message}`);
        }
    }

    /** 重命名字段显示名（双击显示名列触发） */
    async renameRasterField(fieldId, currentAlias) {
        const alias = prompt('新的显示名：', currentAlias);
        if (!alias?.trim() || alias === currentAlias) return;
        try {
            await RasterAPI.updateField(this.layerId, fieldId, { field_alias: alias.trim() });
            // 乐观更新本地缓存
            const f = this.rasterFields.find(f => String(f.id) === String(fieldId));
            if (f) f.field_alias = alias.trim();
            this._render();
        } catch (err) {
            alert(`重命名失败：${err.message}`);
            await this.refresh();
        }
    }

    /** 删除用户字段 */
    async deleteRasterField(fieldId, fieldName) {
        if (!confirm(`确定删除字段「${fieldName}」？`)) return;
        try {
            await RasterAPI.deleteField(this.layerId, fieldId);
            // 乐观更新本地缓存
            this.rasterFields = this.rasterFields.filter(f => String(f.id) !== String(fieldId));
            this._render();
        } catch (err) {
            alert(`删除失败：${err.message}`);
            await this.refresh();
        }
    }

    /**
     * 编辑栅格字段的默认值（双击默认值列触发）
     * @param {HTMLTableCellElement} td
     */
    editRasterDefault(td) {
        if (td.querySelector('input,select')) return;

        const { fieldId, fieldType } = td.dataset;
        const field   = this.rasterFields.find(f => String(f.id) === String(fieldId));
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

            // 值未变化则跳过
            const newStr = String(newVal ?? '');
            const oldStr = String(rawVal ?? '');
            if (newStr === oldStr) return;

            // 乐观更新 UI
            span.innerHTML = ModalComponent._attrFmtVal(newVal, fieldType);

            try {
                await RasterAPI.updateField(this.layerId, fieldId, {
                    default_val: newVal === null ? null : String(newVal),
                });
                // 同步本地缓存
                if (field) field.default_val = newVal === null ? null : String(newVal);
            } catch (err) {
                console.error('[AttributeTable] 保存默认值失败:', err);
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
        const feature  = this.features.find(f => String(f.id) === String(featureId));
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
                console.error('[AttributeTable] 保存失败:', err);
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
        if (!confirm('确定删除该要素？此操作不可撤销。')) return;
        try {
            await VectorAPI.deleteFeature(featureId);
            this.features = this.features.filter(f => String(f.id) !== String(featureId));
            this._render();
            if (this.app.mapController?.refreshVectorLayer) {
                await this.app.mapController.refreshVectorLayer(this.layerId);
            }
        } catch (err) {
            alert(`删除失败：${err.message}`);
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
            this._clampPanelToViewport();
            this._persistLayout();
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
            this._applyLayout(next);
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

            this._applyLayout(this._clampLayout(next));
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

    _syncExpandedStateFromHeight() {
        const height = this._getPanelLayout().height;
        this._expanded = height > 340;
        if (this._expandBtn) {
            this._expandBtn.textContent = this._expanded ? '⬇ 收起' : '⬆ 展开';
        }
    }

    _makeEditor(fieldType, rawValue) {
        if (fieldType === 'boolean') {
            const sel = document.createElement('select');
            sel.innerHTML = `<option value="true">是</option><option value="false">否</option>`;
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
        if (this._title) this._title.textContent = `属性表：${name}`;
    }

    _loading(show) {
        this._loader?.classList.toggle('hidden', !show);
    }

    _hideCtxMenu() {
        this._ctxMenu?.remove();
        this._ctxMenu = null;
    }
}
