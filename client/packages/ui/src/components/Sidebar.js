export const SidebarComponent = {
    render(rasters, activeIds, loadingIds) {
        if (!rasters || rasters.length === 0) {
            return '<div class="text-center py-20 text-slate-400 italic">未发现可用影像</div>';
        }
        const groups = {};
        rasters.forEach(r => {
            const bid = r.bundle_id || 'unclassed';
            if (!groups[bid]) groups[bid] = [];
            groups[bid].push(r);
        });

        return Object.entries(groups).map(([bid, items]) => `
            <div class="bg-slate-50 rounded-xl border border-slate-200 overflow-hidden mb-4">
                <div class="px-3 py-1.5 bg-slate-100 text-[9px] font-black text-slate-500 flex justify-between uppercase">
                    <span>BUNDLE: ${bid.substring(0, 6)}</span>
                    <span>${items.length} 成员</span>
                </div>
                <div class="divide-y divide-slate-100 bg-white">
                    ${items.map(r => this.renderItem(r, activeIds.has(r.id), loadingIds.has(r.id))).join('')}
                </div>
            </div>
        `).join('');
    },

    renderItem(raster, isActive, isLoading) {
        return `
            <div class="layer-item p-3 flex items-center hover:bg-slate-50 transition-all cursor-pointer ${isActive ? 'is-loaded' : ''}">
                <div class="mr-3">
                    <input type="checkbox" ${isActive ? 'checked' : ''} 
                           data-id="${raster.id}" class="layer-checkbox w-4 h-4 rounded border-slate-300">
                </div>
                <div class="flex-1 min-w-0 item-info" data-id="${raster.id}">
                    <div class="text-sm font-semibold text-slate-700 truncate">${raster.file_name}</div>
                    <div class="flex items-center space-x-2 mt-0.5">
                        <span class="text-[9px] font-mono text-slate-400">${raster.width} &times; ${raster.height}</span>
                        ${isActive ? '<span class="text-[9px] text-green-500 font-bold bg-green-50 px-1 rounded">已就绪</span>' : ''}
                        ${isLoading ? '<div class="loading-spinner h-2 w-2 border border-blue-500 border-t-transparent rounded-full"></div>' : ''}
                    </div>
                </div>
                <button data-id="${raster.id}" class="btn-delete ml-2 text-slate-300 hover:text-red-500 p-1">
                    🗑️
                </button>
            </div>
        `;
    }
};