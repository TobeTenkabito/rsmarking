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
    }

    _initDom() {
        if (this._panel) return;
        this._panel     = document.getElementById('attr-table-panel');
        this._thead     = document.getElementById('attr-table-head');
        this._tbody     = document.getElementById('attr-table-body');
        this._title     = document.getElementById('attr-table-title');
        this._loader    = document.getElementById('attr-table-loader');
        this._count     = document.getElementById('attr-table-count');
        this._expandBtn = document.getElementById('attr-expand-btn');
        this._addColBtn = document.getElementById('attr-add-col-btn');
        this._modeBadge = document.getElementById('attr-mode-badge');
        this._bindDragResize();
    }

    /** 打开矢量属性表 */
    async open(layerId, layerName = '') {
        this._initDom();
        this.mode      = 'vector';
        this.layerId   = layerId;
        this.layerName = layerName;
        this._syncToolbar();
        this._panel.classList.remove('hidden');
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
        this._setTitle(rasterName);
        await this.refresh();
    }

    close() {
        this._initDom();
        this.layerId = null;
        this._panel.classList.add('hidden');
        this._hideCtxMenu();
        this._setExpanded(false);
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
        { field_name: 'file_name',  field_alias: '文件名',    field_type: 'string' },
        { field_name: 'width',      field_alias: '宽度 (px)', field_type: 'number' },
        { field_name: 'height',     field_alias: '高度 (px)', field_type: 'number' },
        { field_name: 'bands',      field_alias: '波段数',    field_type: 'number' },
        { field_name: 'crs',        field_alias: '坐标系',    field_type: 'string' },
        { field_name: 'data_type',  field_alias: '数据类型',  field_type: 'string' },
        { field_name: 'nodata',     field_alias: 'NoData 值', field_type: 'string' },
        { field_name: 'resolution', field_alias: '分辨率',    field_type: 'string' },
        { field_name: 'bundle_id',  field_alias: '数据包 ID', field_type: 'string' },
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
        this._panel.style.height = expanded ? '460px' : '280px';
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

    _bindDragResize() {
        const handle = document.getElementById('attr-drag-handle');
        if (!handle || !this._panel) return;

        let startY = 0;
        let startH = 0;

        handle.addEventListener('mousedown', e => {
            startY = e.clientY;
            startH = this._panel.offsetHeight;
            document.body.style.userSelect = 'none';

            const onMove = mv => {
                const delta = startY - mv.clientY;
                const newH  = Math.min(Math.max(startH + delta, 160), window.innerHeight * 0.8);
                this._panel.style.height = `${newH}px`;
                this._expanded = newH > 320;
                if (this._expandBtn) {
                    this._expandBtn.textContent = this._expanded ? '⬇ 收起' : '⬆ 展开';
                }
            };
            const onUp = () => {
                document.removeEventListener('mousemove', onMove);
                document.removeEventListener('mouseup', onUp);
                document.body.style.userSelect = '';
            };

            document.addEventListener('mousemove', onMove);
            document.addEventListener('mouseup', onUp);
        });
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