const esc = (value) => String(value ?? '')
    .replace(/&/g, '&amp;')
    .replace(/'/g, '&#39;')
    .replace(/"/g, '&quot;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;');

function formatNumber(value, digits = 3) {
    if (value === null || value === undefined || Number.isNaN(Number(value))) return 'NoData';
    const number = Number(value);
    if (!Number.isFinite(number)) return 'NoData';
    if (Math.abs(number) >= 100000 || (Math.abs(number) > 0 && Math.abs(number) < 0.001)) {
        return number.toExponential(2);
    }
    return number.toLocaleString(undefined, {
        maximumFractionDigits: digits,
    });
}

function renderMetric(label, value, tone = 'slate') {
    const tones = {
        slate: 'text-slate-700 bg-slate-50 border-slate-100',
        emerald: 'text-emerald-700 bg-emerald-50 border-emerald-100',
        sky: 'text-sky-700 bg-sky-50 border-sky-100',
        amber: 'text-amber-700 bg-amber-50 border-amber-100',
    };
    return `
        <div class="border ${tones[tone] ?? tones.slate} rounded-lg px-3 py-2 min-w-0">
            <p class="text-[10px] font-bold uppercase tracking-wider opacity-60 truncate">${label}</p>
            <p class="text-sm font-black font-mono truncate">${formatNumber(value)}</p>
        </div>
    `;
}

function renderHistogram(band) {
    const bins = band?.histogram?.bins ?? [];
    if (!bins.length) {
        return `
            <div class="h-56 rounded-lg border border-dashed border-slate-200 bg-slate-50 flex items-center justify-center text-xs text-slate-400">
                No valid pixels
            </div>
        `;
    }

    const maxCount = Math.max(...bins.map(bin => Number(bin.count) || 0), 1);
    return `
        <div class="h-56 rounded-lg border border-slate-200 bg-white px-3 pt-4 pb-8 relative">
            <div class="absolute left-3 right-3 top-4 bottom-8 flex items-end gap-px">
                ${bins.map((bin) => {
                    const height = Math.max(2, (Number(bin.count) || 0) / maxCount * 100);
                    const title = `${formatNumber(bin.start)} - ${formatNumber(bin.end)}: ${formatNumber(bin.count, 0)}`;
                    return `
                        <div class="flex-1 min-w-[2px] flex items-end" title="${esc(title)}">
                            <div class="w-full rounded-t-sm bg-gradient-to-t from-indigo-500 to-sky-400 hover:from-indigo-600 hover:to-sky-500 transition-colors"
                                 style="height:${height}%"></div>
                        </div>
                    `;
                }).join('')}
            </div>
            <div class="absolute bottom-2 left-3 right-3 flex justify-between text-[10px] font-mono text-slate-400">
                <span>${formatNumber(bins[0].start)}</span>
                <span>${formatNumber(bins[bins.length - 1].end)}</span>
            </div>
        </div>
    `;
}

function renderBandTabs(stats, activeBandIndex) {
    const bands = stats?.bands ?? [];
    return bands.map((band) => {
        const active = Number(band.index) === Number(activeBandIndex);
        return `
            <button onclick="RS.selectRasterStatisticsBand(${band.index})"
                    class="px-3 py-2 rounded-lg text-xs font-bold border transition-all whitespace-nowrap
                           ${active
                               ? 'bg-indigo-600 border-indigo-600 text-white shadow-sm'
                               : 'bg-white border-slate-200 text-slate-500 hover:text-indigo-600 hover:border-indigo-300'}">
                B${band.index}
            </button>
        `;
    }).join('');
}

export const RasterStatisticsTemplate = {
    renderLoading(rasterName = '') {
        return `
            <div class="py-16 flex flex-col items-center justify-center text-slate-400">
                <div class="w-8 h-8 border-2 border-indigo-500 border-t-transparent rounded-full animate-spin mb-4"></div>
                <p class="text-sm font-bold">Computing statistics</p>
                <p class="text-xs mt-1 max-w-sm truncate">${esc(rasterName)}</p>
            </div>
        `;
    },

    renderError(message) {
        return `
            <div class="py-14 flex flex-col items-center justify-center text-center">
                <div class="w-10 h-10 rounded-lg bg-red-50 text-red-500 flex items-center justify-center mb-3">
                    <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2"
                              d="M12 9v4m0 4h.01M10.29 3.86L1.82 18a2 2 0 001.71 3h16.94a2 2 0 001.71-3L13.71 3.86a2 2 0 00-3.42 0z"/>
                    </svg>
                </div>
                <p class="text-sm font-bold text-slate-700">Statistics unavailable</p>
                <p class="text-xs text-slate-400 mt-1 max-w-md">${esc(message)}</p>
            </div>
        `;
    },

    render(stats, activeBandIndex = null) {
        const bands = stats?.bands ?? [];
        const activeIndex = activeBandIndex ?? bands[0]?.index;
        const activeBand = bands.find(band => Number(band.index) === Number(activeIndex)) ?? bands[0];

        if (!activeBand) {
            return this.renderError('No band statistics were returned.');
        }

        const sample = stats.sample ?? {};
        return `
            <div class="space-y-4">
                <div class="flex flex-wrap items-center justify-between gap-3">
                    <div class="min-w-0">
                        <p class="text-[10px] font-bold uppercase tracking-widest text-slate-400">Dataset</p>
                        <p class="text-sm font-black text-slate-800 truncate">${esc(stats.file_name ?? 'Raster')}</p>
                    </div>
                    <div class="flex items-center gap-2 overflow-x-auto max-w-full">
                        ${renderBandTabs(stats, activeBand.index)}
                    </div>
                </div>

                <div class="grid grid-cols-2 md:grid-cols-4 gap-2">
                    ${renderMetric('Min', activeBand.min, 'sky')}
                    ${renderMetric('Max', activeBand.max, 'sky')}
                    ${renderMetric('Mean', activeBand.mean, 'emerald')}
                    ${renderMetric('Std Dev', activeBand.std, 'amber')}
                    ${renderMetric('Median', activeBand.median)}
                    ${renderMetric('P2', activeBand.p2)}
                    ${renderMetric('P98', activeBand.p98)}
                    ${renderMetric('Valid %', activeBand.valid_percent)}
                </div>

                <div class="grid grid-cols-1 lg:grid-cols-[1fr_240px] gap-4">
                    <div>
                        <div class="flex items-center justify-between mb-2">
                            <p class="text-xs font-black text-slate-700">Band ${activeBand.index} Histogram</p>
                            <p class="text-[10px] font-mono text-slate-400">${formatNumber(activeBand.valid_count, 0)} valid pixels</p>
                        </div>
                        ${renderHistogram(activeBand)}
                    </div>

                    <div class="border border-slate-200 rounded-lg p-4 bg-slate-50/70 space-y-3">
                        <div>
                            <p class="text-[10px] font-bold uppercase tracking-widest text-slate-400">Sample</p>
                            <p class="text-sm font-black text-slate-700 font-mono">
                                ${formatNumber(sample.width, 0)} x ${formatNumber(sample.height, 0)}
                            </p>
                        </div>
                        <div class="grid grid-cols-2 gap-2 text-xs">
                            <div>
                                <p class="text-slate-400 font-bold">Raster</p>
                                <p class="font-mono text-slate-700">${formatNumber(stats.width, 0)} x ${formatNumber(stats.height, 0)}</p>
                            </div>
                            <div>
                                <p class="text-slate-400 font-bold">Bands</p>
                                <p class="font-mono text-slate-700">${formatNumber(stats.band_count, 0)}</p>
                            </div>
                            <div>
                                <p class="text-slate-400 font-bold">Data Type</p>
                                <p class="font-mono text-slate-700 truncate">${esc(activeBand.dtype ?? stats.data_type ?? '-')}</p>
                            </div>
                            <div>
                                <p class="text-slate-400 font-bold">NoData</p>
                                <p class="font-mono text-slate-700">${formatNumber(stats.nodata)}</p>
                            </div>
                        </div>
                        <div class="pt-2 border-t border-slate-200">
                            <div class="flex justify-between text-[11px] font-bold text-slate-500 mb-1">
                                <span>Valid</span>
                                <span>${formatNumber(activeBand.valid_percent)}%</span>
                            </div>
                            <div class="h-2 rounded-full bg-slate-200 overflow-hidden">
                                <div class="h-full bg-emerald-500 rounded-full" style="width:${Math.max(0, Math.min(100, Number(activeBand.valid_percent) || 0))}%"></div>
                            </div>
                            <p class="text-[10px] text-slate-400 mt-2 font-mono">
                                ${formatNumber(activeBand.nodata_count, 0)} nodata / masked sample pixels
                            </p>
                        </div>
                    </div>
                </div>
            </div>
        `;
    },
};
