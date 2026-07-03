/**
 * AITemplate.js
 * AI assistant target and backend-function rendering helpers.
 */
import { esc } from '../utils.js';

const CATEGORY_LABELS = {
    artifact_generation: 'Generated Files & Images',
    raster_catalog: 'Raster Data & Inspection',
    raster_fields: 'Raster Fields',
    task_monitoring: 'Processing Status',
    spectral_indices: 'Spectral Indices',
    raster_manipulation: 'Raster Tools',
    script_sandbox: 'Script Sandbox',
    extraction: 'Feature Extraction',
    clip: 'Spatial Clip',
    change_detection: 'Change Detection',
};

const CATEGORY_ORDER = [
    'artifact_generation',
    'raster_catalog',
    'raster_fields',
    'task_monitoring',
    'spectral_indices',
    'raster_manipulation',
    'extraction',
    'clip',
    'change_detection',
    'script_sandbox',
    'other',
];

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

function categoryLabel(category = 'other') {
    return CATEGORY_LABELS[category] ?? prettyName(category);
}

function groupedFunctions(functions = []) {
    const grouped = functions.reduce((acc, fn) => {
        const category = fn.category || 'other';
        acc[category] ??= [];
        acc[category].push(fn);
        return acc;
    }, {});

    return Object.entries(grouped)
        .map(([category, items]) => ({
            category,
            label: categoryLabel(category),
            items: [...items].sort((a, b) => prettyName(a.name).localeCompare(prettyName(b.name))),
        }))
        .sort((a, b) => {
            const orderA = CATEGORY_ORDER.includes(a.category) ? CATEGORY_ORDER.indexOf(a.category) : CATEGORY_ORDER.length;
            const orderB = CATEGORY_ORDER.includes(b.category) ? CATEGORY_ORDER.indexOf(b.category) : CATEGORY_ORDER.length;
            return orderA === orderB
                ? a.label.localeCompare(b.label)
                : orderA - orderB;
        });
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

    renderAIFunctionButtons(functions = [], selectedName = '', selectedCategory = '') {
        if (!functions.length) {
            return `
                <div class="rounded-lg border border-dashed border-slate-200 bg-white px-4 py-5 text-center">
                    <p class="text-[10px] font-bold uppercase tracking-widest text-slate-400">No backend functions loaded</p>
                </div>`;
        }

        const groups = groupedFunctions(functions);
        const selectedFunction = functions.find(fn => fn.name === selectedName);
        const activeCategory = groups.some(group => group.category === selectedCategory)
            ? selectedCategory
            : selectedFunction?.category || groups[0]?.category || 'other';
        const activeGroup = groups.find(group => group.category === activeCategory) ?? groups[0];

        const categories = groups.map((group) => {
            const isActive = group.category === activeGroup.category;
            const activeClass = isActive
                ? 'border-slate-900 bg-slate-900 text-white shadow-sm'
                : 'border-slate-200 bg-white text-slate-600 hover:border-slate-300 hover:bg-slate-50';
            return `
                <button type="button"
                    onclick="RS.aiSelectFunctionCategory('${esc(group.category)}')"
                    class="flex w-full items-center justify-between gap-3 rounded-lg border px-3 py-2 text-left transition-all ${activeClass}">
                    <span class="min-w-0 truncate text-[11px] font-black">${esc(group.label)}</span>
                    <span class="shrink-0 rounded-md ${isActive ? 'bg-white/15 text-white' : 'bg-slate-100 text-slate-500'} px-1.5 py-0.5 text-[9px] font-black">
                        ${group.items.length}
                    </span>
                </button>`;
        }).join('');

        const functionsList = activeGroup.items.map((fn) => {
            const isSelected = fn.name === selectedName;
            const selectedClass = isSelected
                ? 'border-sky-300 bg-sky-50 text-sky-800 shadow-sm'
                : 'border-slate-200 bg-white text-slate-600 hover:border-sky-200 hover:bg-white';
            const required = fn.parameters?.required ?? [];
            const requiredMeta = required.length ? `${required.length} required` : 'no required args';
            return `
                <button type="button"
                    onclick="RS.aiSelectFunction('${esc(fn.name)}')"
                    title="${esc(fn.description ?? '')}"
                    class="flex w-full min-w-0 items-start gap-3 rounded-lg border px-3 py-2.5 text-left transition-all ${selectedClass}">
                    <span class="mt-0.5 flex h-6 w-6 shrink-0 items-center justify-center rounded-md ${isSelected ? 'bg-sky-600 text-white' : 'bg-slate-100 text-slate-400'}">
                        <svg class="h-3.5 w-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M8 9h8M8 13h5m-8 8 3-3h8a4 4 0 004-4V7a4 4 0 00-4-4H8a4 4 0 00-4 4v7a4 4 0 004 4"/>
                        </svg>
                    </span>
                    <span class="min-w-0 flex-1">
                        <span class="block truncate text-[11px] font-black">${esc(prettyName(fn.name))}</span>
                        <span class="mt-0.5 block truncate font-mono text-[9px] opacity-70">${esc(fn.name)}</span>
                        <span class="mt-1 block truncate text-[9px] font-bold uppercase tracking-widest opacity-50">${esc(requiredMeta)}</span>
                    </span>
                </button>`;
        }).join('');

        return `
            <div class="grid gap-3 lg:grid-cols-[15rem_minmax(0,1fr)]">
                <div class="rounded-lg border border-slate-200 bg-white p-2">
                    <div class="px-1 pb-2 text-[10px] font-black uppercase tracking-widest text-slate-400">Function groups</div>
                    <div class="max-h-72 space-y-1 overflow-y-auto pr-1 sidebar-scroll">${categories}</div>
                </div>
                <div class="rounded-lg border border-slate-200 bg-white">
                    <div class="flex items-center justify-between gap-3 border-b border-slate-100 px-3 py-2.5">
                        <div class="min-w-0">
                            <div class="truncate text-[11px] font-black text-slate-700">${esc(activeGroup.label)}</div>
                            <div class="mt-0.5 text-[9px] font-bold uppercase tracking-widest text-slate-400">${activeGroup.items.length} functions</div>
                        </div>
                    </div>
                    <div class="max-h-72 space-y-2 overflow-y-auto p-2 sidebar-scroll">${functionsList}</div>
                </div>
            </div>`;
    },

    renderAIFunctionSummary(fn) {
        if (!fn) return '';

        const required = fn.parameters?.required ?? [];
        const requiredText = required.length ? required.join(', ') : 'none';

        return `
            <div class="space-y-1">
                <div class="flex flex-wrap items-center gap-2">
                    <span class="rounded-md bg-sky-100 px-2 py-1 text-[9px] font-black uppercase tracking-widest text-sky-700">
                        ${esc(categoryLabel(fn.category ?? 'other'))}
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
