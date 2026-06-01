/**
 * AITemplate.js
 * AI assistant target and backend-function rendering helpers.
 */
import { esc } from '../utils.js';

const CATEGORY_LABELS = {
    spectral_indices: 'Spectral Indices',
    raster_manipulation: 'Raster Tools',
    script_sandbox: 'Script Sandbox',
    extraction: 'Feature Extraction',
    clip: 'Spatial Clip',
    change_detection: 'Change Detection',
};

function prettyName(name = '') {
    return String(name)
        .replace(/^calculate_/, '')
        .replace(/^run_/, '')
        .replace(/^extract_/, 'extract ')
        .replace(/^detect_/, 'detect ')
        .replace(/_/g, ' ')
        .replace(/\b\w/g, (char) => char.toUpperCase())
        .replace(/\b(Ndvi|Ndwi|Ndbi|Mndwi)\b/g, (term) => term.toUpperCase());
}

export const AITemplate = {

    renderAITargetOptions(rasters = [], layers = []) {
        const rasterOptions = rasters.length
            ? rasters.map(r =>
                `<option value="${esc(r.index_id)}" data-type="raster">[Raster] ${esc(r.file_name ?? r.name ?? r.index_id)}</option>`
              ).join('')
            : '';

        const layerOptions = layers.length
            ? layers.map(l =>
                `<option value="${esc(l.id)}" data-type="vector">[Vector] ${esc(l.name ?? l.id)}</option>`
              ).join('')
            : '';

        if (!rasterOptions && !layerOptions) {
            return '<option value="">No available data</option>';
        }

        return `
            ${rasterOptions ? `<optgroup label="Raster Imagery">${rasterOptions}</optgroup>` : ''}
            ${layerOptions  ? `<optgroup label="Vector Layers">${layerOptions}</optgroup>`  : ''}
        `;
    },

    renderAIFunctionButtons(functions = [], selectedName = '') {
        if (!functions.length) {
            return `
                <div class="col-span-full rounded-2xl border border-dashed border-slate-200 bg-slate-50 px-4 py-5 text-center">
                    <p class="text-[10px] font-bold uppercase tracking-widest text-slate-400">No backend functions loaded</p>
                </div>`;
        }

        const grouped = functions.reduce((acc, fn) => {
            const category = fn.category || 'other';
            acc[category] ??= [];
            acc[category].push(fn);
            return acc;
        }, {});

        return Object.entries(grouped).map(([category, items]) => `
            <div class="col-span-full pt-1 text-[10px] font-black uppercase tracking-[0.2em] text-slate-400">
                ${esc(CATEGORY_LABELS[category] ?? prettyName(category))}
            </div>
            ${items.map((fn) => {
                const isSelected = fn.name === selectedName;
                const selectedClass = isSelected
                    ? 'border-sky-400 bg-sky-50 text-sky-700 shadow-sm'
                    : 'border-slate-200 bg-white text-slate-600 hover:border-sky-200 hover:bg-sky-50/60';
                return `
                    <button type="button"
                        onclick="RS.aiSelectFunction('${esc(fn.name)}')"
                        title="${esc(fn.description ?? '')}"
                        class="text-left rounded-2xl border px-3 py-2.5 transition-all ${selectedClass}">
                        <span class="block text-[11px] font-bold leading-tight">${esc(prettyName(fn.name))}</span>
                        <span class="mt-1 block truncate text-[9px] font-medium opacity-70">${esc(fn.name)}</span>
                    </button>`;
            }).join('')}
        `).join('');
    },

    renderAIFunctionSummary(fn) {
        if (!fn) return '';

        const required = fn.parameters?.required ?? [];
        const requiredText = required.length ? required.join(', ') : 'none';

        return `
            <div class="space-y-1">
                <div class="flex flex-wrap items-center gap-2">
                    <span class="rounded-full bg-sky-100 px-2 py-1 text-[9px] font-black uppercase tracking-widest text-sky-700">
                        ${esc(CATEGORY_LABELS[fn.category] ?? fn.category ?? 'Function')}
                    </span>
                    <span class="font-mono text-[10px] font-bold text-slate-500">${esc(fn.name)}</span>
                </div>
                <p class="text-[11px] leading-relaxed text-slate-600">${esc(fn.description ?? '')}</p>
                <p class="text-[10px] text-slate-400">
                    Required args: <span class="font-mono text-slate-500">${esc(requiredText)}</span>
                </p>
            </div>`;
    },
};
