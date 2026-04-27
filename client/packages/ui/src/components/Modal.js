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
     * 渲染波段提取的选择列表
     */
    renderExtractList(raster, selectedIndices) {
    if (!raster) {
        return `<div class="text-center py-10 text-slate-400">
            <p class="text-xs">未找到影像数据</p>
        </div>`;
    }

    if (!raster.bands || raster.bands < 1) {
        return `<div class="text-center py-10 text-slate-400">
            <p class="text-xs">该影像无可提取波段</p>
        </div>`;
    }

    // 根据 raster.bands 動態生成波段列表 [1, 2, 3, ...]
    const bandList = Array.from({ length: raster.bands }, (_, i) => i + 1);

    return bandList.map(bandIndex => {
        const isSelected = selectedIndices.includes(bandIndex);
        const selectOrder = selectedIndices.indexOf(bandIndex) + 1;

        return `
            <div 
                class="flex items-center justify-between p-3 rounded-xl cursor-pointer transition-all border-2 mb-2 ${
                    isSelected
                        ? 'border-emerald-500 bg-emerald-50 shadow-sm'
                        : 'bg-slate-50 border-slate-100 hover:border-slate-200 hover:bg-slate-100'
                }" 
                onclick="RS.toggleExtractItem(${bandIndex})" 
                data-extract-band="${bandIndex}"
            >
                <div class="flex items-center space-x-3 overflow-hidden">
                    <div class="w-6 h-6 border-2 rounded-full flex items-center justify-center text-[10px] font-black transition-all ${
                        isSelected ? 'bg-emerald-500 border-emerald-500 text-white' : 'border-slate-300 bg-white'
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
            </div>
        `;
    }).join('');
},


    renderExtractSourceList(rasters, selectedId) {
    if (!rasters || rasters.length === 0) {
        return `<div class="text-center py-10 text-slate-400">
            <p class="text-xs">暂无可用影像，请先上传</p>
        </div>`;
    }
    return rasters.map(raster => {
        const isSelected = raster.index_id === selectedId;
        return `
            <div
                class="flex items-center justify-between p-3 rounded-xl cursor-pointer transition-all border-2 mb-2 ${
                    isSelected
                        ? 'border-emerald-500 bg-emerald-50 shadow-sm'
                        : 'bg-slate-50 border-slate-100 hover:border-slate-200 hover:bg-slate-100'
                }"
                onclick="RS.selectExtractSource(${raster.index_id})"
            >
                <div class="flex items-center space-x-3 overflow-hidden">
                    <div class="w-6 h-6 border-2 rounded-full flex items-center justify-center transition-all ${
                        isSelected ? 'bg-emerald-500 border-emerald-500' : 'border-slate-300 bg-white'
                    }">
                        ${isSelected ? `<svg class="w-3 h-3 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="3" d="M5 13l4 4L19 7"/></svg>` : ''}
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
                    ${rasters.map(r => {
                        const bandCount = r.bands ?? 1;
                        const bandLabel = bandCount > 1
                            ? ` · ${bandCount} 波段`
                            : ` · 单波段`;
                        const displayName = r.file_name || r.name || r.index_id || r.id;
                        return `<option value="${r.index_id}">${displayName}${bandLabel}</option>`;
                    }).join('')}
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
     * 渲染 AI 目标数据下拉框选项
     * 同时展示栅格和矢量图层，供用户选择
     * @param {Array} rasters  - Store 中的栅格列表
     * @param {Array} layers   - Store 中的矢量图层列表
     */
    renderAITargetOptions(rasters = [], layers = []) {
        const rasterOptions = rasters.length
            ? rasters.map(r =>
                `<option value="${r.index_id}" data-type="raster">
                    [栅格] ${r.file_name}
                </option>`
              ).join('')
            : '';

        const layerOptions = layers.length
            ? layers.map(l =>
                `<option value="${l.id}" data-type="vector">
                    [矢量] ${l.name}
                </option>`
              ).join('')
            : '';

        if (!rasterOptions && !layerOptions) {
            return '<option value="">暂无可用数据</option>';
        }

        return `
            ${rasterOptions ? `<optgroup label="栅格影像">${rasterOptions}</optgroup>` : ''}
            ${layerOptions  ? `<optgroup label="矢量图层">${layerOptions}</optgroup>`  : ''}
        `;
    },

    /**
     * 渲染属性表表头行
     * @param {LayerFieldOut[]} fields
     */
    renderAttrTableHead(fields) {
        const ths = [
            `<th class="attr-th w-12 text-center">#</th>`,
            ...fields.map(f => `
                <th class="attr-th"
                    data-field-id="${f.id}"
                    ondblclick="RS.attrRenameColumn('${this._esc(f.id)}','${this._esc(f.field_alias || f.field_name)}')"
                    oncontextmenu="RS.attrColumnMenu(event,'${this._esc(f.id)}','${this._esc(f.field_alias || f.field_name)}',${!!f.is_system})">
                    <div class="flex items-center gap-1 select-none">
                        <span class="type-badge ${this._attrBadgeCls(f.field_type)}"
                              title="${f.field_type}">
                            ${this._attrTypeIcon(f.field_type)}
                        </span>
                        <span class="truncate max-w-[140px]"
                              title="${this._esc(f.field_alias || f.field_name)}">
                            ${f.field_alias || f.field_name}
                        </span>
                        ${f.is_system
                            ? '<span class="ml-1 text-[9px] text-slate-300" title="文件导入字段，不可删除">系统</span>'
                            : ''}
                    </div>
                </th>`),
            `<th class="attr-th w-8 text-center" title="删除要素">🗑</th>`,
        ];
        return `<tr>${ths.join('')}</tr>`;
    },

    /**
     * 渲染属性表数据行
     * @param {FeatureResponse[]} features
     * @param {LayerFieldOut[]}   fields
     * @param {string|null}       selectedFeatureId  当前选中要素 id
     */
    renderAttrTableBody(features, fields, selectedFeatureId = null) {
        if (!features.length) {
            return `
                <tr>
                    <td colspan="${fields.length + 2}"
                        class="py-10 text-center text-xs text-slate-400">
                        暂无要素数据
                    </td>
                </tr>`;
        }

        return features.map((feat, i) => {
            const isSelected = feat.id === selectedFeatureId;
            const rowCls = isSelected
                ? 'bg-indigo-50 ring-1 ring-inset ring-indigo-200'
                : 'hover:bg-slate-50';

            const tds = [
                // 序号列
                `<td class="attr-td text-center text-slate-400 font-mono text-[11px]">${i + 1}</td>`,

                // 数据列
                ...fields.map(f => {
                    const raw     = feat.properties?.[f.field_name] ?? '';
                    const display = this._attrFmtVal(raw, f.field_type);
                    return `
                        <td class="attr-td cursor-text"
                            data-feature-id="${feat.id}"
                            data-field-name="${this._esc(f.field_name)}"
                            data-field-type="${f.field_type}"
                            data-raw="${this._esc(String(raw))}"
                            ondblclick="RS.attrEditCell(this)">
                            <span class="cell-val">${display}</span>
                        </td>`;
                }),

                // 删除列
                `<td class="attr-td text-center">
                    <button onclick="RS.attrDeleteFeature('${feat.id}')"
                            class="text-slate-300 hover:text-red-500 transition-colors leading-none text-xs"
                            title="删除该要素">✕</button>
                </td>`,
            ];

            return `
                <tr class="group transition-colors ${rowCls}"
                    data-feature-id="${feat.id}">
                    ${tds.join('')}
                </tr>`;
        }).join('');
    },

    /**
     * 渲染属性表空状态（加载中）
     */
    renderAttrTableLoading() {
        return `
            <tr>
                <td colspan="99" class="py-10 text-center text-xs text-indigo-400 animate-pulse">
                    正在加载属性数据…
                </td>
            </tr>`;
    },

    _attrBadgeCls(type) {
        return { string: 'badge-str', number: 'badge-num',
                 boolean: 'badge-bool', date: 'badge-date' }[type] ?? 'badge-str';
    },

    _attrTypeIcon(type) {
        return { string: 'T', number: '#', boolean: '⊙', date: '▦' }[type] ?? '?';
    },

    _attrFmtVal(val, type) {
        if (val === null || val === undefined || val === '')
            return '<span class="text-slate-300 select-none">—</span>';
        if (type === 'boolean') return val ? '✅' : '❌';
        if (type === 'date') {
            try { return new Date(val).toLocaleDateString('zh-CN'); } catch { return String(val); }
        }
        return String(val);
    },

    /** HTML 属性值转义 */
    _esc(str) {
        return String(str)
            .replace(/&/g, '&amp;')
            .replace(/'/g, '&#39;')
            .replace(/"/g, '&quot;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;');
    },


    /**
    * 渲染栅格属性表表头
    */
    renderRasterFieldTableHead() {
      return `
          <tr>
              <th class="attr-th w-8 text-center">#</th>
              <th class="attr-th">字段名</th>
              <th class="attr-th">显示名</th>
              <th class="attr-th w-24">类型</th>
              <th class="attr-th">默认值</th>
              <th class="attr-th w-16 text-center">操作</th>
          </tr>`;
  },

    /**
    * 渲染栅格属性表数据行（方案C：系统字段区 + 用户字段区）
    * @param {RasterFieldOut[]} fields
    */
    renderRasterFieldTableBody(fields) {
      if (!fields.length) {
          return `
              <tr>
                  <td colspan="6"
                      class="py-10 text-center text-xs text-slate-400">
                      暂无字段数据
                  </td>
              </tr>`;
      }

      const systemFields = fields.filter(f => f.is_system);
      const userFields   = fields.filter(f => !f.is_system);

      const renderRow = (f, i, isSystem) => `
          <tr class="${isSystem
                  ? 'bg-slate-50 text-slate-400'
                  : 'hover:bg-slate-50 text-slate-700'
              } transition-colors group"
              data-field-id="${f.id}">

              <!-- 序号 -->
              <td class="attr-td text-center font-mono text-[11px] text-slate-300">
                  ${i + 1}
              </td>

              <!-- 字段名（只读） -->
              <td class="attr-td font-mono text-[11px]">
                  <span class="truncate max-w-[120px] block"
                        title="${this._esc(f.field_name)}">
                      ${this._esc(f.field_name)}
                  </span>
              </td>

              <!-- 显示名（双击可改） -->
              <td class="attr-td ${isSystem ? '' : 'cursor-text'}"
                  data-field-id="${f.id}"
                  data-field-alias="${this._esc(f.field_alias || f.field_name)}"
                  ${isSystem ? '' : `ondblclick="RS.attrrenameRasterField('${f.id}','${this._esc(f.field_alias || f.field_name)}')"` }>
                  <div class="flex items-center gap-1">
                      <span class="type-badge ${this._attrBadgeCls(f.field_type)}"
                            title="${f.field_type}">
                          ${this._attrTypeIcon(f.field_type)}
                      </span>
                      <span class="truncate max-w-[120px]"
                            title="${this._esc(f.field_alias || f.field_name)}">
                          ${this._esc(f.field_alias || f.field_name)}
                      </span>
                      ${isSystem
                          ? '<span class="ml-1 text-[9px] text-slate-300">系统</span>'
                          : ''}
                  </div>
              </td>

              <!-- 类型 -->
              <td class="attr-td text-[11px]">
                  <span class="type-badge ${this._attrBadgeCls(f.field_type)}">
                      ${this._attrTypeIcon(f.field_type)}
                  </span>
                  <span class="ml-1">${f.field_type}</span>
              </td>

              <!-- 默认值（用户字段可双击编辑） -->
              <td class="attr-td ${isSystem ? '' : 'cursor-text'}"
              data-field-id="${f.id}"
              data-field-type="${f.field_type}"
              data-default-val="${this._esc(String(f.default_val ?? ''))}"
              ${isSystem ? '' : `ondblclick="RS.attreditRasterDefault(this)"`}>
                <span class="cell-val">
                ${f.default_val !== null && f.default_val !== undefined && f.default_val !== ''? 
                this._esc(String(f.default_val)) : '<span class="text-slate-300">—</span>'}
              </span>
              </td>

              <!-- 操作列 -->
              <td class="attr-td text-center">
                  ${isSystem
                      ? '<span class="text-[10px] text-slate-200" title="系统字段不可删除">🔒</span>'
                      : `<button onclick="RS.attrdeleteRasterField('${f.id}','${this._esc(f.field_name)}')"
                                 class="text-slate-300 hover:text-red-500 transition-colors text-xs"
                                 title="删除字段">✕</button>`
                  }
              </td>
          </tr>`;

      const systemRows = systemFields.length
          ? [
              // 系统字段分隔行
              `<tr>
                  <td colspan="6"
                      class="px-3 py-1 text-[10px] font-semibold text-slate-300
                             bg-slate-50 border-y border-slate-100 select-none tracking-widest">
                      ▸ 系统字段（只读）
                  </td>
              </tr>`,
              ...systemFields.map((f, i) => renderRow(f, i, true)),
            ]
          : [];

      const userRows = userFields.length
          ? [
              // 用户字段分隔行
              `<tr>
                  <td colspan="6"
                      class="px-3 py-1 text-[10px] font-semibold text-indigo-300
                             bg-indigo-50/40 border-y border-indigo-100 select-none tracking-widest">
                      ▸ 自定义字段（可编辑）
                  </td>
              </tr>`,
              ...userFields.map((f, i) => renderRow(f, i, false)),
            ]
          : [
              `<tr>
                  <td colspan="6"
                      class="py-6 text-center text-xs text-slate-300 italic">
                      暂无自定义字段，点击「+ 新增列」添加
                  </td>
              </tr>`,
            ];

      return [...systemRows, ...userRows].join('');
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
    },

};
