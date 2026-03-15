/**
 * ModalComponent - 负责所有弹出层内容的 HTML 模板渲染
 */
export const ModalComponent = {
    /**
     * 渲染波段合成的选择列表
     */
    renderMergeList(rasters, selectedIds) {
        if (!rasters || rasters.length === 0) {
            return `<div class="text-center py-10 text-slate-400">
                <p class="text-xs">暂无可用波段数据，请先上传影像</p>
            </div>`;
        }

        return rasters.map(raster => {
            const isSelected = selectedIds.includes(raster.index_id);
            const selectOrder = selectedIds.indexOf(raster.index_id) + 1;

            return `
                <div 
                    class="flex items-center justify-between p-3 rounded-xl cursor-pointer transition-all border-2 mb-2 ${
                        isSelected 
                            ? 'border-indigo-500 bg-indigo-50 shadow-sm' 
                            : 'bg-slate-50 border-slate-100 hover:border-slate-200 hover:bg-slate-100'
                    }" 
                    onclick="RS.toggleMergeItem(${raster.index_id})" 
                    data-merge-id="${raster.index_id}"
                >
                    <div class="flex items-center space-x-3 overflow-hidden">
                        <div class="w-6 h-6 border-2 rounded-full flex items-center justify-center text-[10px] font-black transition-all ${
                            isSelected ? 'bg-indigo-500 border-indigo-500 text-white' : 'border-slate-300 bg-white'
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
                </div>
            `;
        }).join('');
    },


    /**
     * 渲染下拉选择框选项
     */
    renderSelectOptions(rasters) {
        if (!rasters || rasters.length === 0) return '<option value="">请先上传影像</option>';
        return rasters.map(r => `
            <option value="${r.index_id}">${r.file_name} (${r.bands} 波段)</option>
        `).join('');
    },

    /**
     * 渲染通用的指数计算配置（NDVI, NDWI, NDBI, MNDWI）
     * @param {string} type - 指数类型
     */
    renderIndexConfig(type, rasters) {
        const options = this.renderSelectOptions(rasters);
        const configs = {
            'NDVI': { b1: '红波段 (Red)', b2: '近红外波段 (NIR)', color: 'emerald' },
            'NDWI': { b1: '绿波段 (Green)', b2: '近红外波段 (NIR)', color: 'blue' },
            'NDBI': { b1: '短波红外 (SWIR)', b2: '近红外波段 (NIR)', color: 'amber' },
            'MNDWI': { b1: '绿波段 (Green)', b2: '短波红外 (SWIR)', color: 'cyan' }
        };
        const cfg = configs[type] || configs.NDVI;

        return `
            <div class="flex items-center space-x-3 mb-6 text-${cfg.color}-600">
                <div class="p-2 bg-${cfg.color}-50 rounded-lg">
                    <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z"></path></svg>
                </div>
                <h3 class="font-bold text-sm uppercase tracking-tight">${type} 遥感指数计算</h3>
            </div>
            <div class="space-y-4">
                <div>
                    <label class="text-[10px] font-bold text-slate-400 uppercase mb-1.5 block">${cfg.b1}</label>
                    <select id="index-b1-select" class="w-full p-3 bg-slate-50 border border-slate-200 rounded-xl text-xs outline-none focus:ring-2 focus:ring-${cfg.color}-500/20">${options}</select>
                </div>
                <div>
                    <label class="text-[10px] font-bold text-slate-400 uppercase mb-1.5 block">${cfg.b2}</label>
                    <select id="index-b2-select" class="w-full p-3 bg-slate-50 border border-slate-200 rounded-xl text-xs outline-none focus:ring-2 focus:ring-${cfg.color}-500/20">${options}</select>
                </div>
                <div>
                    <label class="text-[10px] font-bold text-slate-400 uppercase mb-1.5 block">输出文件名</label>
                    <input type="text" id="index-name-input" value="${type}_Result_${Date.now()}.tif" class="w-full p-3 bg-slate-50 border border-slate-200 rounded-xl text-xs outline-none">
                </div>
            </div>
        `;
    },

    /**
     * 渲染影像元数据详情
     */
    renderDetail(raster) {
        const stats = [
            { label: '文件名称', value: raster.file_name, full: true },
            { label: '坐标系', value: raster.crs || 'WGS 84', mono: true },
            { label: '数据类型', value: raster.data_type || 'Float32', mono: true },
            { label: '空间分辨率', value: `${raster.width} x ${raster.height}`, mono: true },
            { label: '波段数量', value: raster.bands, mono: false }
        ];

        return `
            <div class="space-y-4">
                <div class="grid grid-cols-2 gap-2">
                    ${stats.map(s => `
                        <div class="bg-slate-50/80 p-3 rounded-xl border border-slate-100 ${s.full ? 'col-span-2' : ''}">
                            <p class="text-[9px] text-slate-400 font-bold uppercase tracking-wider mb-1">${s.label}</p>
                            <p class="text-[11px] font-bold text-slate-700 truncate ${s.mono ? 'font-mono' : ''}">${s.value}</p>
                        </div>
                    `).join('')}
                </div>
                ${raster.bounds_wgs84 ? `
                    <div class="bg-indigo-50 border border-indigo-100 p-3 rounded-xl">
                        <p class="text-[9px] text-indigo-400 font-bold uppercase mb-2">地理包围盒 (WGS84)</p>
                        <div class="grid grid-cols-2 gap-y-2 text-[10px] font-mono font-medium text-indigo-700">
                            <div><span class="text-indigo-300 mr-1">N:</span>${raster.bounds_wgs84[3].toFixed(5)}</div>
                            <div><span class="text-indigo-300 mr-1">E:</span>${raster.bounds_wgs84[2].toFixed(5)}</div>
                            <div><span class="text-indigo-300 mr-1">S:</span>${raster.bounds_wgs84[1].toFixed(5)}</div>
                            <div><span class="text-indigo-300 mr-1">W:</span>${raster.bounds_wgs84[0].toFixed(5)}</div>
                        </div>
                    </div>
                ` : ''}
            </div>
        `;
    },


    /**
    * 渲染提取工具的配置内容
    * 适配动态波段选择逻辑：初始显示两个必选波段，后续动态追加
    */
    renderExtractionConfig(type, rasters) {
        const options = this.renderSelectOptions(rasters);
        const configs = {
            'VEGETATION': { title: '植被提取 (NDVI Mask)', color: 'emerald', threshold: 0.3 },
            'WATER': { title: '水体提取 (MNDWI Mask)', color: 'blue', threshold: 0.0 },
            'BUILDING': { title: '建筑提取 (NDBI Mask)', color: 'amber', threshold: 0.1 },
            'CLOUD': { title: '云层提取', color: 'slate', threshold: 0.5 }
        };
        const cfg = configs[type] || configs.VEGETATION;

        return `
            <div class="flex items-center space-x-3 mb-6 text-${cfg.color}-600">
                <div class="p-2 bg-${cfg.color}-50 rounded-lg">
                    <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 10V3L4 14h7v7l9-11h-7z"></path>
                    </svg>
                </div>
                <h3 class="font-bold text-sm uppercase tracking-tight">${cfg.title}</h3>
            </div>

            <div class="space-y-4">
                <!-- 动态波段选择容器 -->
                <div id="dynamic-bands-container" class="space-y-3">
                    <div>
                        <label class="text-[10px] font-bold text-slate-400 uppercase mb-1.5 block">选择波段 1 (必选)</label>
                        <select class="band-selector w-full p-3 bg-slate-50 border border-slate-200 rounded-xl text-xs outline-none focus:ring-2 focus:ring-${cfg.color}-500/20">
                            <option value="">-- 请选择波段 --</option>
                            ${options}
                        </select>
                    </div>
                    <div>
                        <label class="text-[10px] font-bold text-slate-400 uppercase mb-1.5 block">选择波段 2 (必选)</label>
                        <select class="band-selector w-full p-3 bg-slate-50 border border-slate-200 rounded-xl text-xs outline-none focus:ring-2 focus:ring-${cfg.color}-500/20">
                            <option value="">-- 请选择波段 --</option>
                            ${options}
                        </select>
                    </div>
                </div>
                <!-- Mode 输入框 -->
                <div>
                    <label class="text-[10px] font-bold text-slate-400 uppercase mb-1.5 block">计算模式 (Mode - 可选)</label>
                    <input type="text" id="extract-mode-input" placeholder="例如: MNDWI, AWEI" class="w-full p-3 bg-slate-50 border border-slate-200 rounded-xl text-xs outline-none focus:ring-2 focus:ring-blue-500/20">
                </div>
                <div>
                    <label class="text-[10px] font-bold text-slate-400 uppercase mb-1.5 block">提取阈值 (Threshold)</label>
                    <input type="number" step="0.01" id="extract-threshold-input" value="${cfg.threshold}" class="w-full p-3 bg-slate-50 border border-slate-200 rounded-xl text-xs outline-none focus:ring-2 focus:ring-${cfg.color}-500/20">
                </div>

                <div>
                    <label class="text-[10px] font-bold text-slate-400 uppercase mb-1.5 block">结果存储名称</label>
                    <input type="text" id="extract-name-input" value="Extract_${type}_${Date.now()}.tif" class="w-full p-3 bg-slate-50 border border-slate-200 rounded-xl text-xs outline-none focus:ring-2 focus:ring-${cfg.color}-500/20">
                </div>
            </div>
        `;
    },

    /**
     * 渲染计算器变量映射列表
     * @param {Array} variables 提取出的变量 ['A', 'B']
     * @param {Array} rasters Store中的影像列表
     */
    renderCalculatorVariables(variables, rasters) {
        if (!variables || variables.length === 0) {
            return `
                <div class="py-6 text-center border-2 border-dashed border-slate-100 rounded-2xl">
                    <p class="text-[10px] text-slate-300 font-bold uppercase tracking-widest">请在上方输入公式</p>
                </div>
            `;
        }

        return variables.map(v => `
            <div class="flex items-center space-x-3 p-3 bg-slate-50 border border-slate-100 rounded-xl hover:border-purple-200 transition-all">
                <div class="w-8 h-8 rounded-lg bg-purple-600 text-white flex items-center justify-center font-mono font-bold text-xs shadow-sm">
                    ${v}
                </div>
                <div class="flex-1">
                    <select data-var="${v}" class="calc-var-select w-full bg-transparent text-[11px] font-bold text-slate-600 outline-none cursor-pointer">
                        <option value="">绑定影像图层...</option>
                        ${rasters.map(r => `
                            <option value="${r.index_id}">${r.file_name || r.name || r.index_id || r.id}</option>
                        `).join('')}
                    </select>
                </div>
            </div>
        `).join('');
    },

    /**
     * 渲染脚本编辑器
     */
    renderScriptEditor(rasters, selectedIds, currentScript = '') {
        return `
            <div class="flex h-full">
                <!-- 左侧：栅格选择 -->
                <div class="w-80 border-r border-slate-100 p-4 overflow-y-auto">
                    <div class="mb-4">
                        <h3 class="text-sm font-bold text-slate-700 mb-2">输入影像选择</h3>
                        <div id="script-selected-count" class="text-xs text-slate-500">已选择 ${selectedIds.length} 个影像</div>
                    </div>
                    
                    <div class="space-y-2">
                        ${rasters.map(r => `
                            <label class="flex items-center p-3 rounded-lg border border-slate-100 hover:bg-slate-50 cursor-pointer transition-all">
                                <input 
                                    type="checkbox" 
                                    value="${r.index_id}" 
                                    class="script-raster-checkbox mr-3"
                                    ${selectedIds.includes(r.index_id) ? 'checked' : ''}
                                >
                                <div class="flex-1 overflow-hidden">
                                    <div class="text-xs font-bold text-slate-700 truncate">${r.file_name}</div>
                                    <div class="text-[10px] text-slate-400">
                                        ${r.width} × ${r.height} | ${r.bands} 波段
                                    </div>
                                </div>
                            </label>
                        `).join('')}
                    </div>
                    
                    <div class="mt-6 pt-6 border-t border-slate-100">
                        <label class="text-sm font-bold text-slate-700 block mb-2">输出文件名</label>
                        <input 
                            type="text" 
                            id="script-output-name" 
                            placeholder="例: ndvi_result.tif"
                            class="w-full p-2 border border-slate-200 rounded-lg text-xs focus:ring-2 focus:ring-purple-500 focus:border-purple-500"
                            value="${currentScript ? '' : 'script_output_' + Date.now() + '.tif'}"
                        >
                    </div>
                </div>
                
                <!-- 右侧：代码编辑器 -->
                <div class="flex-1 flex flex-col p-4">
                    <!-- 工具栏 -->
                    <div class="flex justify-between items-center mb-4">
                        <div class="flex items-center space-x-4">
                            <select id="script-template-selector" class="text-xs border border-slate-200 rounded-lg px-3 py-2 focus:ring-2 focus:ring-purple-500">
                                <option value="">-- 选择模板 --</option>
                            </select>
                            
                            <div class="flex items-center space-x-2">
                                <span class="text-xs text-slate-500">环境:</span>
                                <span class="text-xs font-mono bg-slate-100 px-2 py-1 rounded">Python 3.9 + GDAL/Rasterio</span>
                            </div>
                        </div>
                        
                        <div id="script-validation" class="text-xs">
                            <!-- 动态验证信息 -->
                        </div>
                    </div>
                    
                    <div class="flex-1 border border-slate-200 rounded-lg overflow-hidden flex flex-row">
                    <!-- 行号列 -->
                        <div id="line-numbers"
                             class="w-10 shrink-0 bg-slate-100 border-r border-slate-200
                                pt-4 pb-4 text-right pr-2 font-mono text-xs text-slate-400
                                select-none pointer-events-none overflow-hidden">
                                <!-- 动态生成行号 -->
                                </div>

                    <!-- 代码编辑区 -->
                    <textarea
                        id="script-editor-textarea"
                        class="flex-1 h-full p-4 font-mono text-sm bg-slate-50 resize-none focus:outline-none focus:bg-white"
                        placeholder="# Enter Python code here\n# Available paths:\n#   /input/  - Input images directory\n#   /output/ - Output results directory\n\nimport rasterio\nimport numpy as np\n\n# Read image\nwith rasterio.open('/input/image.tif') as src:\n    data = src.read()\n    profile = src.profile\n\n# Process data\n# ...\n\n# Save result\nwith rasterio.open('/output/result.tif', 'w', **profile) as dst:\n    dst.write(processed_data)"
                        spellcheck="false"
                        >${currentScript}</textarea>
                        </div>
                    
                    <!-- 提示信息 -->
                    <div class="mt-4 p-3 bg-amber-50 border border-amber-200 rounded-lg">
                        <div class="flex items-start space-x-2">
                            <svg class="w-4 h-4 text-amber-600 mt-0.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z"></path>
                            </svg>
                            <div class="flex-1">
                                <div class="text-xs font-bold text-amber-800 mb-1">安全提示</div>
                                <div class="text-[10px] text-amber-700 space-y-1">
                                    <div>• 脚本在隔离的Docker容器中执行，最大运行时间10分钟</div>
                                    <div>• 禁止使用 exec, eval, __import__ 等危险函数</div>
                                    <div>• 可用库: numpy, scipy, rasterio, gdal, scikit-image</div>
                                </div>
                            </div>
                        </div>
                    </div>
                    
                    <!-- 历史记录面板（隐藏） -->
                    <div id="script-history" class="hidden mt-4 p-4 bg-slate-50 rounded-lg max-h-48 overflow-y-auto">
                        <!-- 动态加载历史记录 -->
                    </div>
                </div>
            </div>
        `;
    },

    /**
     * 动作等待状态
     */
    renderActionLoading(message = "正在执行算法...") {
        return `
            <div class="flex flex-col items-center justify-center py-12">
                <div class="w-10 h-10 border-4 border-indigo-500 border-t-transparent rounded-full animate-spin mb-4"></div>
                <p class="text-xs font-bold text-slate-600">${message}</p>
                <p class="text-[9px] text-slate-400 mt-2 tracking-widest uppercase">请稍候，服务器正在处理数据</p>
            </div>
        `;
    }
};
