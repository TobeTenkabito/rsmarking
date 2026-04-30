/**
 * BandExtractTemplate.js
 * 波段提取：来源影像选择 + 波段勾选列表
 */
export const BandExtractTemplate = {

    renderExtractList(raster, selectedIndices) {
        if (!raster) {
            return `
                <div class="text-center py-10 text-slate-400">
                    <p class="text-xs">未找到影像数据</p>
                </div>`;
        }
        if (!raster.bands || raster.bands < 1) {
            return `
                <div class="text-center py-10 text-slate-400">
                    <p class="text-xs">该影像无可提取波段</p>
                </div>`;
        }

        const bandList = Array.from({ length: raster.bands }, (_, i) => i + 1);

        return bandList.map(bandIndex => {
            const isSelected  = selectedIndices.includes(bandIndex);
            const selectOrder = selectedIndices.indexOf(bandIndex) + 1;

            return `
                <div
                    class="flex items-center justify-between p-3 rounded-xl cursor-pointer
                           transition-all border-2 mb-2 ${
                        isSelected
                            ? 'border-emerald-500 bg-emerald-50 shadow-sm'
                            : 'bg-slate-50 border-slate-100 hover:border-slate-200 hover:bg-slate-100'
                    }"
                    onclick="RS.toggleExtractItem(${bandIndex})"
                    data-extract-band="${bandIndex}"
                >
                    <div class="flex items-center space-x-3 overflow-hidden">
                        <div class="w-6 h-6 border-2 rounded-full flex items-center justify-center
                                    text-[10px] font-black transition-all ${
                            isSelected
                                ? 'bg-emerald-500 border-emerald-500 text-white'
                                : 'border-slate-300 bg-white'
                        }">
                            ${isSelected ? selectOrder : ''}
                        </div>
                        <div class="flex flex-col overflow-hidden">
                            <span class="text-xs font-bold text-slate-700">Band ${bandIndex}</span>
                            <span class="text-[9px] text-slate-400 font-mono uppercase">${raster.data_type || 'FLOAT32'}</span>
                        </div>
                    </div>
                    <div class="shrink-0">
                        <span class="text-[9px] font-bold text-slate-500 bg-white px-2 py-0.5 rounded border border-slate-200">
                            ${raster.file_name}
                        </span>
                    </div>
                </div>`;
        }).join('');
    },

    renderExtractSourceList(rasters, selectedId) {
        if (!rasters || rasters.length === 0) {
            return `
                <div class="text-center py-10 text-slate-400">
                    <p class="text-xs">暂无可用影像，请先上传</p>
                </div>`;
        }

        return rasters.map(raster => {
            const isSelected = raster.index_id === selectedId;

            return `
                <div
                    class="flex items-center justify-between p-3 rounded-xl cursor-pointer
                           transition-all border-2 mb-2 ${
                        isSelected
                            ? 'border-emerald-500 bg-emerald-50 shadow-sm'
                            : 'bg-slate-50 border-slate-100 hover:border-slate-200 hover:bg-slate-100'
                    }"
                    onclick="RS.selectExtractSource(${raster.index_id})"
                >
                    <div class="flex items-center space-x-3 overflow-hidden">
                        <div class="w-6 h-6 border-2 rounded-full flex items-center justify-center transition-all ${
                            isSelected
                                ? 'bg-emerald-500 border-emerald-500'
                                : 'border-slate-300 bg-white'
                        }">
                            ${isSelected
                                ? `<svg class="w-3 h-3 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                       <path stroke-linecap="round" stroke-linejoin="round" stroke-width="3" d="M5 13l4 4L19 7"/>
                                   </svg>`
                                : ''}
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
