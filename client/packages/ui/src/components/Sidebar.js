/**
 * SidebarComponent - 处理左侧影像资源列表的渲染
 */
export const SidebarComponent = {
    render(rasters, activeIds, loadingIds) {
        if (!rasters || rasters.length === 0) {
            return `
                <div class="flex flex-col items-center justify-center py-20 text-slate-300">
                    <svg class="w-12 h-12 mb-4 opacity-20" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path d="M4 16l4.586-4.586a2 2 0 012.828 0L16 16m-2-2l1.586-1.586a2 2 0 012.828 0L20 14m-6-6h.01M6 20h12a2 2 0 002-2V6a2 2 0 00-2-2H6a2 2 0 00-2 2v12a2 2 0 002 2z"></path></svg>
                    <span class="text-xs font-medium italic">等待数据载入...</span>
                </div>
            `;
        }

        const groups = {};
        rasters.forEach(r => {
            const bid = r.bundle_id || 'unclassed';
            if (!groups[bid]) groups[bid] = [];
            groups[bid].push(r);
        });

        return Object.entries(groups).map(([bid, items]) => `
            <div class="bg-slate-50 rounded-xl border border-slate-200 overflow-hidden mb-4 shadow-sm">
                <div class="px-3 py-2 bg-slate-100 border-b border-slate-200 text-[9px] font-black text-slate-500 flex justify-between items-center uppercase tracking-wider">
                    <div class="flex items-center">
                        <span class="w-1.5 h-1.5 rounded-full bg-slate-400 mr-2"></span>
                        数据包: ${bid.substring(0, 8)}
                    </div>
                    <span class="bg-white px-1.5 py-0.5 rounded border border-slate-300">${items.length} 成员</span>
                </div>
                <div class="divide-y divide-slate-100 bg-white">
                    ${items.map(r => this.renderItem(r, activeIds.has(r.id), loadingIds.has(r.id))).join('')}
                </div>
            </div>
        `).join('');
    },

/**
     * 渲染单个影像条目
     * @param {Object} raster 影像数据对象
     * @param {Boolean} isActive 图层是否已在地图上激活
     * @param {Boolean} isLoading 图层是否正在加载渲染中
     */
    renderItem(raster, isActive, isLoading) {
        // 关键修复：确保 checked 属性严格跟随 isActive 状态
        // 显式写入 checked="checked" 以确保浏览器渲染引擎正确识别
        const checkedAttr = isActive ? 'checked="checked"' : '';

        // 动态样式：激活时背景变色，文字变色
        const activeItemClass = isActive ? 'bg-indigo-50/50 border-indigo-100' : 'border-transparent';
        const activeTextClass = isActive ? 'text-indigo-700' : 'text-slate-700';

        return `
            <div class="layer-item p-3 flex items-center hover:bg-slate-50 transition-all group border-l-4 ${activeItemClass}" data-id="${raster.id}">
                <div class="mr-3 flex items-center justify-center">
                    <div class="relative w-4 h-4">
                        <input type="checkbox" 
                               ${checkedAttr} 
                               data-id="${raster.id}" 
                               class="layer-checkbox w-4 h-4 rounded border-slate-300 text-indigo-600 focus:ring-indigo-500 transition-all cursor-pointer">
                        
                        ${isLoading ? `
                            <div class="absolute inset-0 bg-white/90 flex items-center justify-center rounded-sm">
                                <div class="w-3 h-3 border-2 border-indigo-500 border-t-transparent rounded-full animate-spin"></div>
                            </div>
                        ` : ''}
                    </div>
                </div>
                
                <div class="flex-1 min-w-0 cursor-pointer item-info" data-id="${raster.id}">
                    <div class="text-sm font-bold ${activeTextClass} truncate flex items-center">
                        ${raster.file_name}
                    </div>
                    
                    <div class="flex items-center space-x-2 mt-1">
                        <span class="text-[9px] font-mono font-medium text-slate-400 bg-slate-100 px-1.5 py-0.5 rounded">
                            ${raster.width} × ${raster.height}
                        </span>
                        
                        <span class="text-[9px] font-bold text-slate-400">B:${raster.bands}</span>
                        
                        ${isActive ? `
                            <span class="flex items-center text-[9px] text-indigo-500 font-black uppercase tracking-tighter">
                                <span class="w-1 h-1 rounded-full bg-indigo-500 animate-pulse mr-1"></span>
                                ON MAP
                            </span>
                        ` : ''}
                    </div>
                </div>

                <div class="flex items-center opacity-0 group-hover:opacity-100 transition-opacity">
                    <button data-id="${raster.id}" 
                            class="btn-delete p-1.5 text-slate-300 hover:text-red-500 hover:bg-red-50 rounded-lg transition-colors" 
                            title="从工作站移除">
                        <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" 
                                  d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16">
                            </path>
                        </svg>
                    </button>
                </div>
            </div>
        `;
    }
};
