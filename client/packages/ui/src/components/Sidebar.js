/**
 * SidebarComponent - 处理左侧影像资源列表（栅格）与标注项目（矢量）的渲染
 */
export const SidebarComponent = {
    /**
     * 主渲染函数
     * @param {Object} data 包含 rasters, projects 等所有状态
     */
    render(data) {
        const {
            rasters, activeLayerIds, loadingIds,
            projects, activeProject, vectorLayers, activeVectorLayerId, visibleVectorLayerIds
        } = data;

        return `
            <!-- 1. 栅格影像区域 -->
            <div class="mb-6">
                <div class="px-4 py-2 flex justify-between items-center mb-1">
                    <h3 class="text-[10px] font-black text-slate-400 uppercase tracking-widest">影像资源 (Raster)</h3>
                    <button onclick="document.getElementById('raster-upload-input').click()" class="text-indigo-500 hover:text-indigo-700 font-bold text-[10px]">+ 导入</button>
                </div>
                <div id="raster-list">
                    ${this.renderRasterSection(rasters, activeLayerIds, loadingIds)}
                </div>
            </div>

            <!-- 分割线 -->
            <div class="mx-4 border-t border-slate-100 my-4"></div>

            <!-- 2. 矢量标注区域 -->
            <div class="mb-6">
                <div class="px-4 py-2 flex justify-between items-center mb-1">
                    <h3 class="text-[10px] font-black text-slate-400 uppercase tracking-widest">标注项目 (Vector)</h3>
                    <button onclick="RS.createProject()" class="text-emerald-500 hover:text-emerald-700 font-bold text-[10px]">+ 新建项目</button>
                </div>
                <div id="vector-list-container">
                    ${this.renderVectorSection(projects, activeProject, vectorLayers, 
            activeVectorLayerId, visibleVectorLayerIds)}
                </div>
            </div>
        `;
    },

    /**
     * 栅格部分逻辑 - 保持不变
     */
    renderRasterSection(rasters, activeIds, loadingIds) {
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
            <div class="bg-slate-50 rounded-xl border border-slate-200 overflow-hidden mb-4 mx-2 shadow-sm">
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
     * 渲染单个影像条目 - 保持不变
     */
    renderItem(raster, isActive, isLoading) {
        const checkedAttr = isActive ? 'checked="checked"' : '';
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
    },


    renderVectorSection(projects, activeProject, layers, activeLayerId, visibleIds) {
    if (!projects || projects.length === 0) return this.renderEmpty('暂无标注项目');

    return `
        <div class="mx-2">
            <select onchange="RS.selectProject(this.value)" class="w-full mb-3 p-2 text-xs border border-slate-200 rounded-lg bg-white text-slate-600 focus:ring-2 focus:ring-emerald-500/20 outline-none transition-all">
                <option value="">-- 选择标注项目 --</option>
                ${projects.map(p => `<option value="${p.id}" ${activeProject?.id === p.id ? 'selected' : ''}>${p.name}</option>`).join('')}
            </select>

            ${activeProject ? `
                <div class="bg-emerald-50/30 rounded-xl border border-emerald-100 overflow-hidden shadow-sm">
                    <div class="px-3 py-2 bg-emerald-100/50 border-b border-emerald-100 flex justify-between items-center">
                        <span class="text-[9px] font-black text-emerald-700 uppercase tracking-wider">📂 项目: ${activeProject.name}</span>
                        <button onclick="RS.createLayer()" class="w-5 h-5 flex items-center justify-center bg-white rounded border border-emerald-200 text-emerald-600 hover:bg-emerald-50 transition-colors" title="新建图层">＋</button>
                    </div>
                    <div class="divide-y divide-emerald-50 bg-white" id="vector-list">
                        ${layers.length === 0 ? '<div class="p-6 text-center text-[10px] text-slate-400 italic">尚未创建标注图层</div>' : 
                          // 传入第三个参数：判断当前图层 ID 是否存在于可见集合中
                          layers.map(l => this.renderVectorItem(l, activeLayerId === l.id, visibleIds?.has(l.id))).join('')}
                    </div>
                </div>
            ` : '<div class="text-center py-6 text-[10px] text-slate-300 italic">请先从下拉菜单选择项目</div>'}
        </div>
    `;
},

    // 接收 isVisible 参数
    renderVectorItem(layer, isActive, isVisible) {
    return `
        <div class="p-3 flex items-center hover:bg-emerald-50/50 transition-all group ${isActive ? 'border-l-4 border-emerald-500 bg-emerald-50/20' : 'border-l-4 border-transparent'}" data-vector-id="${layer.id}">
            <div class="mr-3">
                <input type="checkbox" ${isVisible ? 'checked' : ''} 
                       onclick="event.stopPropagation(); RS.toggleVectorVisibility('${layer.id}')"
                       class="vector-layer-checkbox w-4 h-4 rounded border-emerald-300 text-emerald-600 focus:ring-emerald-500 transition-all cursor-pointer">
            </div>
            <div class="flex-1 min-w-0 cursor-pointer" onclick="RS.setActiveVectorLayer('${layer.id}')">
                <div class="text-sm font-bold ${isActive ? 'text-emerald-700' : 'text-slate-700'} truncate">${layer.name}</div>
                <div class="text-[9px] text-slate-400 mt-0.5 tracking-tight font-mono">
                    ${isActive ? '<span class="text-emerald-600 font-bold">● 当前编辑图层</span>' : '点击激活编辑'}
                </div>
            </div>
        </div>
    `;
},

    renderEmpty(text) {
        return `<div class="text-center py-10 text-[10px] text-slate-300 italic tracking-widest uppercase">${text}</div>`;
    }
};
