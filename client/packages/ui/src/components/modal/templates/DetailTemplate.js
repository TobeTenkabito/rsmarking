/**
 * DetailTemplate.js
 * Imagery metadata detail panel
 */
export const DetailTemplate = {

    renderDetail(raster) {
        const stats = [
            { label: 'File Name',   value: raster.file_name,                          full: true  },
            { label: 'CRS',     value: raster.crs        || 'WGS 84',             mono: true  },
            { label: 'Data Type',   value: raster.data_type  || 'Float32',            mono: true  },
            { label: 'Spatial Resolution', value: `${raster.width} x ${raster.height}`,      mono: true  },
            { label: 'Band Count',   value: raster.bands,                              mono: false },
        ];

        return `
            <div class="space-y-4">
                <div class="grid grid-cols-2 gap-2">
                    ${stats.map(s => `
                        <div class="bg-slate-50/80 p-3 rounded-xl border border-slate-100 ${s.full ? 'col-span-2' : ''}">
                            <p class="text-[9px] text-slate-400 font-bold uppercase tracking-wider mb-1">${s.label}</p>
                            <p class="text-[11px] font-bold text-slate-700 truncate ${s.mono ? 'font-mono' : ''}">${s.value}</p>
                        </div>`
                    ).join('')}
                </div>

                ${raster.bounds_wgs84 ? `
                    <div class="bg-indigo-50 border border-indigo-100 p-3 rounded-xl">
                        <p class="text-[9px] text-indigo-400 font-bold uppercase mb-2">Geographic Bounding Box (WGS84)</p>
                        <div class="grid grid-cols-2 gap-y-2 text-[10px] font-mono font-medium text-indigo-700">
                            <div><span class="text-indigo-300 mr-1">N:</span>${raster.bounds_wgs84[3].toFixed(5)}</div>
                            <div><span class="text-indigo-300 mr-1">E:</span>${raster.bounds_wgs84[2].toFixed(5)}</div>
                            <div><span class="text-indigo-300 mr-1">S:</span>${raster.bounds_wgs84[1].toFixed(5)}</div>
                            <div><span class="text-indigo-300 mr-1">W:</span>${raster.bounds_wgs84[0].toFixed(5)}</div>
                        </div>
                    </div>` : ''}
            </div>`;
    },
};
