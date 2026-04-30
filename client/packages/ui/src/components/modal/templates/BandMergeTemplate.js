/**
 * BandMergeTemplate.js
 * 波段合成选择列表模板
 */
export const BandMergeTemplate = {

    renderMergeList(rasters, selectedIds) {
        if (!rasters || rasters.length === 0) {
            return `
                <div class="text-center py-10 text-slate-400">
                    <p class="text-xs">暂无可用波段数据，请先上传影像</p>
                </div>`;
        }

        return rasters.map(raster => {
            const isSelected  = selectedIds.includes(raster.index_id);
            const selectOrder = selectedIds.indexOf(raster.index_id) + 1;

            return `
                <div
                    class="flex items-center justify-between p-3 rounded-xl cursor-pointer
                           transition-all border-2 mb-2 ${
                        isSelected
                            ? 'border-indigo-500 bg-indigo-50 shadow-sm'
                            : 'bg-slate-50 border-slate-100 hover:border-slate-200 hover:bg-slate-100'
                    }"
                    onclick="RS.toggleMergeItem(${raster.index_id})"
                    data-merge-id="${raster.index_id}"
                >
                    <div class="flex items-center space-x-3 overflow-hidden">
                        <div class="w-6 h-6 border-2 rounded-full flex items-center justify-center
                                    text-[10px] font-black transition-all ${
                            isSelected
                                ? 'bg-indigo-500 border-indigo-500 text-white'
                                : 'border-slate-300 bg-white'
                        }">
                            ${isSelected ? selectOrder : ''}
                        </div>
                        <div class="flex flex-col overflow-hidden">
                            <span class="text-xs font-bold text-slate-700 truncate">${raster.file_name}</span>
                            <span class="text-[9px] text-slate-400 font-mono uppercase">${raster.data_type || 'FLOAT32'}</span>
                        </div>
                    </div>
                    <div class="shrink-0">
                        <span class="text-[9px] font-bold text-slate-500 bg-white px-2 py-0.5 rounded border border-slate-200">
                            Bands: ${raster.bands}
                        </span>
                    </div>
                </div>`;
        }).join('');
    },
};
