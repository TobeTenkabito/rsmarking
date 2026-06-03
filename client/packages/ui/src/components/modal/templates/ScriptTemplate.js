/**
 * ScriptTemplate.js
 * Python script editor panel
 */
export const ScriptTemplate = {

    renderScriptEditor(rasters, selectedIds, currentScript = '') {
        return `
            <div class="flex h-full">

                <!-- Left side：Raster selection -->
                <div class="w-80 border-r border-slate-100 p-4 overflow-y-auto">
                    <div class="mb-4">
                        <h3 class="text-sm font-bold text-slate-700 mb-2">Input Imagery Selection</h3>
                        <div id="script-selected-count" class="text-xs text-slate-500">
                            Selected ${selectedIds.length} imagery items
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
                                        ${r.width} × ${r.height} | ${r.bands} bands
                                    </div>
                                </div>
                            </label>`
                        ).join('')}
                    </div>

                    <div class="mt-6 pt-6 border-t border-slate-100">
                        <label class="text-sm font-bold text-slate-700 block mb-2">Output File Name</label>
                        <input
                            type="text"
                            id="script-output-name"
                            placeholder="e.g. ndvi_result.tif"
                            class="w-full p-2 border border-slate-200 rounded-lg text-xs
                                   focus:ring-2 focus:ring-purple-500 focus:border-purple-500"
                            value="${currentScript ? '' : 'script_output_' + Date.now() + '.tif'}"
                        >
                    </div>
                </div>

                <!-- Right side：Code editor -->
                <div class="flex-1 flex flex-col p-4">

                    <!-- Toolbar -->
                    <div class="flex justify-between items-center mb-4">
                        <div class="flex items-center space-x-4">
                            <select id="script-template-selector"
                                    class="text-xs border border-slate-200 rounded-lg px-3 py-2
                                           focus:ring-2 focus:ring-purple-500">
                                <option value="">-- Select Template --</option>
                            </select>
                            <div class="flex items-center space-x-2">
                                <span class="text-xs text-slate-500">Environment:</span>
                                <span class="text-xs font-mono bg-slate-100 px-2 py-1 rounded">
                                    Python 3.10 + Rasterio/Numpy
                                </span>
                            </div>
                        </div>
                        <div id="script-validation" class="text-xs">
                            <!-- Dynamic validation message -->
                        </div>
                    </div>

                    <!-- Editor area -->
                    <div class="flex-1 border border-slate-200 rounded-lg overflow-hidden flex flex-row">
                        <!-- Line number column -->
                        <div id="line-numbers"
                             class="w-10 shrink-0 bg-slate-100 border-r border-slate-200
                                    pt-4 pb-4 text-right pr-2 font-mono text-xs text-slate-400
                                    select-none pointer-events-none overflow-hidden">
                            <!-- Generate line numbers dynamically -->
                        </div>
                        <!-- Code editor area -->
                        <textarea
                            id="script-editor-textarea"
                            class="flex-1 h-full p-4 font-mono text-sm bg-slate-50 resize-none
                                   focus:outline-none focus:bg-white"
                            placeholder="# Enter Python code here&#10;# Available variables: input_0, input_1, ... and OUTPUT_FILE&#10;# Container paths: /data/inputs/ and /data/outputs/&#10;&#10;import rasterio&#10;import numpy as np&#10;&#10;# Read the first selected raster&#10;with rasterio.open(input_0) as src:&#10;    data = src.read(1)&#10;    profile = src.profile&#10;&#10;# Process data&#10;processed_data = data&#10;&#10;# Save result&#10;with rasterio.open(OUTPUT_FILE, 'w', **profile) as dst:&#10;    dst.write(processed_data, 1)"
                            spellcheck="false"
                        >${currentScript}</textarea>
                    </div>

                    <!-- Security Note -->
                    <div class="mt-4 p-3 bg-amber-50 border border-amber-200 rounded-lg">
                        <div class="flex items-start space-x-2">
                            <svg class="w-4 h-4 text-amber-600 mt-0.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2"
                                      d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732
                                         4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z"/>
                            </svg>
                            <div class="flex-1">
                                <div class="text-xs font-bold text-amber-800 mb-1">Security Note</div>
                                <div class="text-[10px] text-amber-700 space-y-1">
                                    <div>• Scripts run in isolated Docker containers，maximum runtime is 10 minutes</div>
                                    <div>• Dangerous functions such as exec, eval, and __import__ are blocked</div>
                                    <div>• Available libraries: numpy, scipy, rasterio, scikit-image</div>
                                </div>
                            </div>
                        </div>
                    </div>

                    <!-- History panel（hidden） -->
                    <div id="script-history"
                         class="hidden mt-4 p-4 bg-slate-50 rounded-lg max-h-48 overflow-y-auto">
                        <!-- Dynamically load history -->
                    </div>
                </div>
            </div>`;
    },
};
