import { VectorAPI }      from '../api/vector.js';
import { ModalComponent } from '../../../ui/src/components/Modal.js';
import { Store }          from '../store/index.js';

export class AttributeTable {

    constructor(app) {
        this.app       = app;
        this.layerId   = null;
        this.layerName = '';
        this.fields    = [];
        this.features  = [];
        this._ctxMenu  = null;
        this._expanded = false;

        this._panel     = null;
        this._thead     = null;
        this._tbody     = null;
        this._title     = null;
        this._loader    = null;
        this._count     = null;
        this._expandBtn = null;
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
        this._bindDragResize();
    }

    async open(layerId, layerName = '') {
        this._initDom();
        this.layerId   = layerId;
        this.layerName = layerName;
        this._panel.classList.remove('hidden');
        this._setTitle(layerName);
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
            const [fields, fc] = await Promise.all([
                VectorAPI.fetchFields(this.layerId),
                VectorAPI.fetchFeaturesInBbox(this.layerId, [-180, -90, 180, 90]),
            ]);
            this.fields   = fields;
            this.features = fc.features ?? [];
            this._render();
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

    editCell(td) {
        if (td.querySelector('input,select')) return;

        const { featureId, fieldName, fieldType } = td.dataset;
        // ✅ Fix2: 从 this.features 取原始值，避免 dataset.raw 被 DOM 转义/trim 污染
        const feature  = this.features.find(f => String(f.id) === String(featureId));
        const rawVal   = feature?.properties?.[fieldName] ?? '';

        const span = td.querySelector('.cell-val');
        span.classList.add('hidden');

        const editor = this._makeEditor(fieldType, rawVal);
        editor.classList.add('cell-editor');
        td.appendChild(editor);
        editor.focus();

        let committed = false; // 防止 blur + Enter 双触发

        const commit = async () => {
            if (committed) return;
            committed = true;

            const editorVal = editor.tagName === 'SELECT' ? editor.dataset.val : editor.value;
            const newVal    = this._parseVal(editorVal, fieldType);

            editor.remove();
            span.classList.remove('hidden');

            // ✅ Fix2: 用解析后的类型值比较，而非字符串比较
            // 这样 england → England 不会被误判为"未修改"
            if (newVal === rawVal || (newVal == null && rawVal === '')) return;

            // 乐观更新 UI
            span.innerHTML = ModalComponent._attrFmtVal(newVal, fieldType);
            td.dataset.raw = String(newVal ?? '');

            try {
                // 调用后端保存
                await VectorAPI.updateFeature(featureId, {
                    properties: { [fieldName]: newVal }
                });

                // ✅ Fix1: 保存成功后同步更新本地 this.features 缓存
                // 这样 refresh() 重新渲染时不会丢失已编辑的数据
                if (feature) {
                    feature.properties = {
                        ...(feature.properties ?? {}),
                        [fieldName]: newVal,
                    };
                }

            } catch (err) {
                console.error('[AttributeTable] 保存失败:', err);
                // 回滚 UI
                span.innerHTML = ModalComponent._attrFmtVal(rawVal, fieldType);
                td.dataset.raw = String(rawVal ?? '');
            }
        };

        editor.addEventListener('blur', commit);
        editor.addEventListener('keydown', e => {
            if (e.key === 'Enter')  { e.preventDefault(); editor.blur(); }
            if (e.key === 'Escape') {
                committed = true; // 取消时标记，防止 blur 再次触发 commit
                editor.remove();
                span.classList.remove('hidden');
            }
        });
    }

    async deleteFeature(featureId) {
        if (!confirm('确定删除该要素？此操作不可撤销。')) return;
        try {
            await VectorAPI.deleteFeature(featureId);
            // ✅ Fix1: 同步从本地缓存移除，避免下次 _render() 还显示已删除行
            this.features = this.features.filter(f => String(f.id) !== String(featureId));
            this._render();
            // 同步刷新地图矢量图层
            if (this.app.mapController?.refreshVectorLayer) {
                await this.app.mapController.refreshVectorLayer(this.layerId);
            }
        } catch (err) {
            alert(`删除失败：${err.message}`);
        }
    }

    _render() {
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
        // ✅ Fix2: 直接赋值原始值，不经过任何转换，保留大小写
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