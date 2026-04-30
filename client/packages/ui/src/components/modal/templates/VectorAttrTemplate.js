/**
 * VectorAttrTemplate.js
 * 矢量图层属性表：表头 / 数据行 / 加载状态
 */
import { esc, attrBadgeCls, attrTypeIcon, attrFmtVal } from '../utils.js';

export const VectorAttrTemplate = {

    renderAttrTableHead(fields) {
        const ths = [
            `<th class="attr-th w-12 text-center">#</th>`,
            ...fields.map(f => `
                <th class="attr-th"
                    data-field-id="${f.id}"
                    ondblclick="RS.attrRenameColumn('${esc(f.id)}','${esc(f.field_alias || f.field_name)}')"
                    oncontextmenu="RS.attrColumnMenu(event,'${esc(f.id)}','${esc(f.field_alias || f.field_name)}',${!!f.is_system})">
                    <div class="flex items-center gap-1 select-none">
                        <span class="type-badge ${attrBadgeCls(f.field_type)}" title="${f.field_type}">
                            ${attrTypeIcon(f.field_type)}
                        </span>
                        <span class="truncate max-w-[140px]" title="${esc(f.field_alias || f.field_name)}">
                            ${f.field_alias || f.field_name}
                        </span>
                        ${f.is_system
                            ? '<span class="ml-1 text-[9px] text-slate-300" title="文件导入字段，不可删除">系统</span>'
                            : ''}
                    </div>
                </th>`),
            `<th class="attr-th w-8 text-center" title="删除要素">🗑</th>`,
        ];
        return `<tr>${ths.join('')}</tr>`;
    },

    renderAttrTableBody(features, fields, selectedFeatureId = null) {
        if (!features.length) {
            return `
                <tr>
                    <td colspan="${fields.length + 2}"
                        class="py-10 text-center text-xs text-slate-400">
                        暂无要素数据
                    </td>
                </tr>`;
        }

        return features.map((feat, i) => {
            const isSelected = feat.id === selectedFeatureId;
            const rowCls     = isSelected
                ? 'bg-indigo-50 ring-1 ring-inset ring-indigo-200'
                : 'hover:bg-slate-50';

            const tds = [
                `<td class="attr-td text-center text-slate-400 font-mono text-[11px]">${i + 1}</td>`,
                ...fields.map(f => {
                    const raw     = feat.properties?.[f.field_name] ?? '';
                    const display = attrFmtVal(raw, f.field_type);
                    return `
                        <td class="attr-td cursor-text"
                            data-feature-id="${feat.id}"
                            data-field-name="${esc(f.field_name)}"
                            data-field-type="${f.field_type}"
                            data-raw="${esc(String(raw))}"
                            ondblclick="RS.attrEditCell(this)">
                            <span class="cell-val">${display}</span>
                        </td>`;
                }),
                `<td class="attr-td text-center">
                    <button onclick="RS.attrDeleteFeature('${feat.id}')"
                            class="text-slate-300 hover:text-red-500 transition-colors leading-none text-xs"
                            title="删除该要素">✕</button>
                </td>`,
            ];

            return `
                <tr class="group transition-colors ${rowCls}" data-feature-id="${feat.id}">
                    ${tds.join('')}
                </tr>`;
        }).join('');
    },

    renderAttrTableLoading() {
        return `
            <tr>
                <td colspan="99" class="py-10 text-center text-xs text-indigo-400 animate-pulse">
                    正在加载属性数据…
                </td>
            </tr>`;
    },
};
