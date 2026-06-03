import { getDateLocale, t } from '../../../../app/src/i18n/index.js';

/**
 * modal/utils.js
 * Shared pure utility functions for templates，No business dependencies
 */

/** HTML Escape attribute values */
export function esc(str) {
    return String(str)
        .replace(/&/g, '&amp;')
        .replace(/'/g, '&#39;')
        .replace(/"/g, '&quot;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;');
}

/** Return badge CSS class by field type */
export function attrBadgeCls(type) {
    return { string: 'badge-str', number: 'badge-num',
             boolean: 'badge-bool', date: 'badge-date' }[type] ?? 'badge-str';
}

/** Return icon by field type */
export function attrTypeIcon(type) {
    return { string: 'T', number: '#', boolean: '⊙', date: '▦' }[type] ?? '?';
}

/** Format cell display value */
export function attrFmtVal(val, type) {
    if (val === null || val === undefined || val === '')
        return '<span class="text-slate-300 select-none">—</span>';
    if (type === 'boolean') return val ? '✅' : '❌';
    if (type === 'date') {
        try { return new Date(val).toLocaleDateString(getDateLocale()); } catch { return String(val); }
    }
    return String(val);
}

/** Render shared dropdown <option> English */
export function renderSelectOptions(rasters) {
    if (!rasters || rasters.length === 0)
        return `<option value="">${t('modal.selectRasterFirst')}</option>`;
    return rasters.map(r =>
        `<option value="${r.index_id}">${r.file_name} (${t('modal.bandSuffix', { count: r.bands })})</option>`
    ).join('');
}

/** Render shared loading state */
export function renderActionLoading(message = t('script.validation.running')) {
    return `
        <div class="flex flex-col items-center justify-center py-12">
            <div class="w-10 h-10 border-4 border-indigo-500 border-t-transparent rounded-full animate-spin mb-4"></div>
            <p class="text-xs font-bold text-slate-600">${message}</p>
            <p class="text-[9px] text-slate-400 mt-2 tracking-widest uppercase">${t('ui.loading.serverHint')}</p>
        </div>
    `;
}
