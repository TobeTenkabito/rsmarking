/**
 * ScriptTemplate.js
 * Python 脚本编辑器面板
 */
export const ScriptTemplate = {

    renderScriptEditor(rasters, selectedIds, currentScript = '') {
        return `
            <div class="flex h-full">

                <!-- 左侧：栅格选择 -->
                <div class="w-80 border-r border-slate-100 p-4 overflow-y-auto">
                    <div class="mb-4">
                        <h3 class="text-sm font-bold text-slate-700 mb-2">输入影像选择</h3>
                        <div id="script-selected-count" class="text-xs text-slate-500">
                            已选择 ${selectedIds.length} 个影像
                        </div>
                    </div>

                    <div class="space-y-2">
                        ${rasters.map(r => `
                            <label class="flex items-center p-3 rounded-lg border border-slate-100
                                          hover:bg-slate-50 cursor-pointer transition-all">
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
                            </label>`
                        ).join('')}
                    </div>

                    <div class="mt-6 pt-6 border-t border-slate-100">
                        <label class="text-sm font-bold text-slate-700 block mb-2">输出文件名</label>
                        <input
                            type="text"
                            id="script-output-name"
                            placeholder="例: ndvi_result.tif"
                            class="w-full p-2 border border-slate-200 rounded-lg text-xs
                                   focus:ring-2 focus:ring-purple-500 focus:border-purple-500"
                            value="${currentScript ? '' : 'script_output_' + Date.now() + '.tif'}"
                        >
                    </div>
                </div>

                <!-- 右侧：代码编辑器 -->
                <div class="flex-1 flex flex-col p-4">

                    <!-- 工具栏 -->
                    <div class="flex justify-between items-center mb-4">
                        <div class="flex items-center space-x-4">
                            <select id="script-template-selector"
                                    class="text-xs border border-slate-200 rounded-lg px-3 py-2
                                           focus:ring-2 focus:ring-purple-500">
                                <option value="">-- 选择模板 --</option>
                            </select>
                            <div class="flex items-center space-x-2">
                                <span class="text-xs text-slate-500">环境:</span>
                                <span class="text-xs font-mono bg-slate-100 px-2 py-1 rounded">
                                    Python 3.9 + GDAL/Rasterio
                                </span>
                            </div>
                        </div>
                        <div id="script-validation" class="text-xs">
                            <!-- 动态验证信息 -->
                        </div>
                    </div>

                    <!-- 编辑区 -->
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
                            class="flex-1 h-full p-4 font-mono text-sm bg-slate-50 resize-none
                                   focus:outline-none focus:bg-white"
                            placeholder="# Enter Python code here&#10;# Available paths:&#10;#   /input/  - Input images directory&#10;#   /output/ - Output results directory&#10;&#10;import rasterio&#10;import numpy as np&#10;&#10;# Read image&#10;with rasterio.open('/input/image.tif') as src:&#10;    data = src.read()&#10;    profile = src.profile&#10;&#10;# Process data&#10;# ...&#10;&#10;# Save result&#10;with rasterio.open('/output/result.tif', 'w', **profile) as dst:&#10;    dst.write(processed_data)"
                            spellcheck="false"
                        >${currentScript}</textarea>
                    </div>

                    <!-- 安全提示 -->
                    <div class="mt-4 p-3 bg-amber-50 border border-amber-200 rounded-lg">
                        <div class="flex items-start space-x-2">
                            <svg class="w-4 h-4 text-amber-600 mt-0.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2"
                                      d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732
                                         4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z"/>
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
                    <div id="script-history"
                         class="hidden mt-4 p-4 bg-slate-50 rounded-lg max-h-48 overflow-y-auto">
                        <!-- 动态加载历史记录 -->
                    </div>
                </div>
            </div>`;
    },
};
