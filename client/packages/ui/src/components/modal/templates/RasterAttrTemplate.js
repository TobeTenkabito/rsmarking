/**
 * RasterAttrTemplate.js
 * Raster layer field management table：English / English（System FieldsEnglish + user field section）
 */
import { esc, attrBadgeCls, attrTypeIcon } from '../utils.js';

export const RasterAttrTemplate = {

    renderRasterFieldTableHead() {
        return `
            <tr>
                <th class="attr-th w-8 text-center">#</th>
                <th class="attr-th">Field Name</th>
                <th class="attr-th">Display Name</th>
                <th class="attr-th w-24">Type</th>
                <th class="attr-th">Default Value</th>
                <th class="attr-th w-16 text-center">Actions</th>
            </tr>`;
    },

    renderRasterFieldTableBody(fields) {
        if (!fields.length) {
            return `
                <tr>
                    <td colspan="6" class="py-10 text-center text-xs text-slate-400">
                        No field data
                    </td>
                </tr>`;
        }

        const systemFields = fields.filter(f =>  f.is_system);
        const userFields   = fields.filter(f => !f.is_system);

        const renderRow = (f, i, isSystem) => `
            <tr class="${isSystem
                    ? 'bg-slate-50 text-slate-400'
                    : 'hover:bg-slate-50 text-slate-700'
                } transition-colors group"
                data-field-id="${f.id}">

                <td class="attr-td text-center font-mono text-[11px] text-slate-300">
                    ${i + 1}
                </td>

                <td class="attr-td font-mono text-[11px]">
                    <span class="truncate max-w-[120px] block" title="${esc(f.field_name)}">
                        ${esc(f.field_name)}
                    </span>
                </td>

                <td class="attr-td ${isSystem ? '' : 'cursor-text'}"
                    data-field-id="${f.id}"
                    data-field-alias="${esc(f.field_alias || f.field_name)}"
                    ${isSystem ? '' : `ondblclick="RS.attrrenameRasterField('${f.id}','${esc(f.field_alias || f.field_name)}')"`}>
                    <div class="flex items-center gap-1">
                        <span class="type-badge ${attrBadgeCls(f.field_type)}" title="${f.field_type}">
                            ${attrTypeIcon(f.field_type)}
                        </span>
                        <span class="truncate max-w-[120px]" title="${esc(f.field_alias || f.field_name)}">
                            ${esc(f.field_alias || f.field_name)}
                        </span>
                        ${isSystem ? '<span class="ml-1 text-[9px] text-slate-300">System</span>' : ''}
                    </div>
                </td>

                <td class="attr-td text-[11px]">
                    <span class="type-badge ${attrBadgeCls(f.field_type)}">
                        ${attrTypeIcon(f.field_type)}
                    </span>
                    <span class="ml-1">${f.field_type}</span>
                </td>

                <td class="attr-td ${isSystem ? '' : 'cursor-text'}"
                    data-field-id="${f.id}"
                    data-field-type="${f.field_type}"
                    data-default-val="${esc(String(f.default_val ?? ''))}"
                    ${isSystem ? '' : `ondblclick="RS.attreditRasterDefault(this)"`}>
                    <span class="cell-val">
                        ${f.default_val !== null && f.default_val !== undefined && f.default_val !== ''
                            ? esc(String(f.default_val))
                            : '<span class="text-slate-300">—</span>'}
                    </span>
                </td>

                <td class="attr-td text-center">
                    ${isSystem
                        ? '<span class="text-[10px] text-slate-200" title="System fields cannot be deleted">🔒</span>'
                        : `<button onclick="RS.attrdeleteRasterField('${f.id}','${esc(f.field_name)}')"
                                   class="text-slate-300 hover:text-red-500 transition-colors text-xs"
                                   title="Delete field">✕</button>`}
                </td>
            </tr>`;

        const systemRows = systemFields.length
            ? [
                `<tr>
                    <td colspan="6"
                        class="px-3 py-1 text-[10px] font-semibold text-slate-300
                               bg-slate-50 border-y border-slate-100 select-none tracking-widest">
                        ▸ System Fields（Read-only）
                    </td>
                </tr>`,
                ...systemFields.map((f, i) => renderRow(f, i, true)),
              ]
            : [];

        const userRows = userFields.length
            ? [
                `<tr>
                    <td colspan="6"
                        class="px-3 py-1 text-[10px] font-semibold text-indigo-300
                               bg-indigo-50/40 border-y border-indigo-100 select-none tracking-widest">
                        ▸ Custom Fields（Editable）
                    </td>
                </tr>`,
                ...userFields.map((f, i) => renderRow(f, i, false)),
              ]
            : [
                `<tr>
                    <td colspan="6" class="py-6 text-center text-xs text-slate-300 italic">
                        No custom fields. Click + Add Column to add one.
                    </td>
                </tr>`,
              ];

        return [...systemRows, ...userRows].join('');
    },
};
