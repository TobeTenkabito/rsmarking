export const ModalComponent = {
    renderMergeList(rasters, selectedIds) {
        if (rasters.length === 0) {
            return `<div class="text-center py-8 text-slate-400">暂无可用数据</div>`;
        }

        return rasters.map(raster => {
            const isSelected = selectedIds.includes(raster.id);
            const selectIndex = selectedIds.indexOf(raster.id) + 1;

            return `
                <div class="flex items-center justify-between p-3 rounded-lg cursor-pointer transition-all border ${
                    isSelected 
                        ? 'border-indigo-500 bg-indigo-50 shadow-sm' 
                        : 'bg-slate-50 border-slate-200 hover:bg-slate-100'
                }" data-merge-id="${raster.id}">
                    <div class="flex items-center space-x-3 overflow-hidden">
                        <div class="selection-indicator w-6 h-6 border-2 rounded-full flex items-center justify-center text-[10px] font-bold transition-all ${
                            isSelected ? 'bg-indigo-500 border-indigo-500 text-white' : 'border-slate-300 bg-white'
                        }">
                            ${isSelected ? selectIndex : ''}
                        </div>
                        <div class="flex flex-col overflow-hidden">
                            <span class="text-sm font-medium text-slate-700 truncate">${raster.file_name}</span>
                            <span class="text-[10px] text-slate-400 font-mono">${raster.data_type || 'Unknown'}</span>
                        </div>
                    </div>
                    <div class="flex items-center space-x-2 shrink-0">
                        <span class="text-[9px] text-slate-500 bg-white px-2 py-0.5 rounded border border-slate-200 shadow-sm">
                            波段: ${raster.bands}
                        </span>
                    </div>
                </div>
            `;
        }).join('');
    },

    renderSelectOptions(rasters) {
        if (rasters.length === 0) return '<option value="">无可用数据</option>';
        return rasters.map(r => `<option value="${r.id}">${r.file_name} (Bands: ${r.bands})</option>`).join('');
    },

    renderDetail(raster) {
        const rows = [
            { label: '坐标系', value: raster.crs || 'WGS84', mono: true },
            { label: '数据类型', value: raster.data_type || 'Unknown', mono: true },
            { label: '分辨率', value: `${raster.width} x ${raster.height}`, mono: true },
            { label: '波段数量', value: raster.bands, mono: false }
        ];

        return `
            <div class="space-y-3">
                <div class="grid grid-cols-2 gap-2">
                    ${rows.map(row => `
                        <div class="bg-slate-50 p-2.5 rounded-lg border border-slate-100">
                            <p class="text-[10px] text-slate-400 uppercase font-semibold mb-1">${row.label}</p>
                            <p class="text-xs font-bold text-slate-700 truncate ${row.mono ? 'font-mono' : ''}">${row.value}</p>
                        </div>
                    `).join('')}
                </div>
                ${raster.bounds_wgs84 ? `
                    <div class="bg-indigo-50/50 p-2.5 rounded-lg border border-indigo-100">
                        <p class="text-[10px] text-indigo-400 uppercase font-semibold mb-1">地理范围 (WGS84)</p>
                        <p class="text-[10px] font-mono text-indigo-700 leading-tight">
                            N: ${raster.bounds_wgs84[3].toFixed(4)}<br>
                            S: ${raster.bounds_wgs84[1].toFixed(4)}<br>
                            W: ${raster.bounds_wgs84[0].toFixed(4)}<br>
                            E: ${raster.bounds_wgs84[2].toFixed(4)}
                        </p>
                    </div>
                ` : ''}
            </div>
        `;
    },

    renderActionLoading(message = "正在处理中...") {
        return `
            <div class="flex flex-col items-center justify-center py-10 space-y-4">
                <div class="w-10 h-10 border-4 border-indigo-500 border-t-transparent rounded-full animate-spin"></div>
                <p class="text-sm font-medium text-slate-500 italic">${message}</p>
            </div>
        `;
    }
};