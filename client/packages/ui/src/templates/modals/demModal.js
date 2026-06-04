export const demModal = `
<div id="dem-analysis-modal" class="hidden fixed inset-0 bg-slate-900/60 backdrop-blur-sm z-[2000] flex items-center justify-center p-4">
    <div class="bg-white w-full max-w-2xl rounded-2xl shadow-2xl overflow-hidden">
        <div class="p-5 border-b border-slate-100 flex justify-between items-center bg-slate-50/50">
            <div>
                <h3 id="dem-analysis-title" class="font-bold text-slate-800 uppercase text-xs tracking-widest">DEM Analysis</h3>
                <p id="dem-analysis-raster-hint" class="mt-1 text-[10px] font-medium text-slate-400 truncate"></p>
            </div>
            <button onclick="RS.closeDEMAnalysisModal()" class="w-7 h-7 rounded-lg text-slate-400 hover:text-slate-600 hover:bg-slate-100 transition-colors" title="Close">x</button>
        </div>

        <div class="p-5 bg-white max-h-[70vh] overflow-y-auto space-y-4">
            <div class="grid grid-cols-1 sm:grid-cols-2 gap-3">
                <div>
                    <label class="mb-1 block text-[10px] font-black uppercase tracking-widest text-slate-400">Source DEM</label>
                    <select id="dem-analysis-raster-select"
                            onchange="RS.handleDEMAnalysisInputChange()"
                            class="w-full rounded-xl border border-slate-200 bg-slate-50 px-3 py-2.5 text-xs font-semibold text-slate-700 outline-none focus:border-emerald-400 focus:ring-2 focus:ring-emerald-500/10"></select>
                </div>
                <div>
                    <label class="mb-1 block text-[10px] font-black uppercase tracking-widest text-slate-400">Product</label>
                    <select id="dem-analysis-operation-select"
                            onchange="RS.switchDEMAnalysisOperation(this.value)"
                            class="w-full rounded-xl border border-slate-200 bg-slate-50 px-3 py-2.5 text-xs font-semibold text-slate-700 outline-none focus:border-emerald-400 focus:ring-2 focus:ring-emerald-500/10">
                        <option value="elevation">Elevation</option>
                        <option value="slope">Slope</option>
                        <option value="aspect">Aspect</option>
                        <option value="hillshade">Shading / Hillshade</option>
                        <option value="curvature">Curvature</option>
                        <option value="relief">Topographic Relief</option>
                        <option value="twi">Topographic Humidity Index</option>
                        <option value="flow_direction">Flow Direction</option>
                        <option value="flow_accumulation">Flow Accumulation</option>
                        <option value="watershed">Watershed Delineation</option>
                    </select>
                </div>
            </div>

            <div class="grid grid-cols-1 sm:grid-cols-2 gap-3">
                <div>
                    <label class="mb-1 block text-[10px] font-black uppercase tracking-widest text-slate-400">DEM Band</label>
                    <input id="dem-analysis-band-index"
                           type="number"
                           min="1"
                           step="1"
                           value="1"
                           oninput="RS.handleDEMAnalysisInputChange()"
                           class="w-full rounded-xl border border-slate-200 bg-white px-3 py-2.5 text-xs font-mono text-slate-700 outline-none focus:border-emerald-400 focus:ring-2 focus:ring-emerald-500/10" />
                </div>
                <div>
                    <label class="mb-1 block text-[10px] font-black uppercase tracking-widest text-slate-400">Z Factor</label>
                    <input id="dem-analysis-z-factor"
                           type="number"
                           min="0"
                           step="any"
                           value="1"
                           oninput="RS.handleDEMAnalysisInputChange()"
                           class="w-full rounded-xl border border-slate-200 bg-white px-3 py-2.5 text-xs font-mono text-slate-700 outline-none focus:border-emerald-400 focus:ring-2 focus:ring-emerald-500/10" />
                </div>
            </div>

            <div id="dem-analysis-slope-section" class="dem-analysis-option">
                <label class="mb-1 block text-[10px] font-black uppercase tracking-widest text-slate-400">Slope Unit</label>
                <select id="dem-analysis-slope-unit"
                        onchange="RS.handleDEMAnalysisInputChange()"
                        class="w-full rounded-xl border border-slate-200 bg-slate-50 px-3 py-2.5 text-xs font-semibold text-slate-700 outline-none focus:border-emerald-400 focus:ring-2 focus:ring-emerald-500/10">
                    <option value="degrees">Degrees</option>
                    <option value="percent">Percent</option>
                    <option value="radians">Radians</option>
                </select>
            </div>

            <div id="dem-analysis-hillshade-section" class="dem-analysis-option hidden">
                <div class="grid grid-cols-1 sm:grid-cols-2 gap-3">
                    <div>
                        <label class="mb-1 block text-[10px] font-black uppercase tracking-widest text-slate-400">Azimuth</label>
                        <input id="dem-analysis-hillshade-azimuth"
                               type="number"
                               min="0"
                               max="360"
                               step="any"
                               value="315"
                               oninput="RS.handleDEMAnalysisInputChange()"
                               class="w-full rounded-xl border border-slate-200 bg-white px-3 py-2.5 text-xs font-mono text-slate-700 outline-none focus:border-emerald-400 focus:ring-2 focus:ring-emerald-500/10" />
                    </div>
                    <div>
                        <label class="mb-1 block text-[10px] font-black uppercase tracking-widest text-slate-400">Altitude</label>
                        <input id="dem-analysis-hillshade-altitude"
                               type="number"
                               min="1"
                               max="90"
                               step="any"
                               value="45"
                               oninput="RS.handleDEMAnalysisInputChange()"
                               class="w-full rounded-xl border border-slate-200 bg-white px-3 py-2.5 text-xs font-mono text-slate-700 outline-none focus:border-emerald-400 focus:ring-2 focus:ring-emerald-500/10" />
                    </div>
                </div>
            </div>

            <div id="dem-analysis-relief-section" class="dem-analysis-option hidden">
                <label class="mb-1 block text-[10px] font-black uppercase tracking-widest text-slate-400">Relief Window Size</label>
                <input id="dem-analysis-relief-window-size"
                       type="number"
                       min="3"
                       step="2"
                       value="3"
                       oninput="RS.handleDEMAnalysisInputChange()"
                       class="w-full rounded-xl border border-slate-200 bg-white px-3 py-2.5 text-xs font-mono text-slate-700 outline-none focus:border-emerald-400 focus:ring-2 focus:ring-emerald-500/10" />
            </div>

            <div id="dem-analysis-twi-section" class="dem-analysis-option hidden">
                <label class="mb-1 block text-[10px] font-black uppercase tracking-widest text-slate-400">Minimum Slope</label>
                <input id="dem-analysis-min-slope-degrees"
                       type="number"
                       min="0.000001"
                       step="any"
                       value="0.1"
                       oninput="RS.handleDEMAnalysisInputChange()"
                       class="w-full rounded-xl border border-slate-200 bg-white px-3 py-2.5 text-xs font-mono text-slate-700 outline-none focus:border-emerald-400 focus:ring-2 focus:ring-emerald-500/10" />
            </div>

            <div>
                <label class="mb-1 block text-[10px] font-black uppercase tracking-widest text-slate-400">Output Name</label>
                <input id="dem-analysis-name-input"
                       type="text"
                       oninput="RS.handleDEMAnalysisInputChange()"
                       class="w-full rounded-xl border border-slate-200 bg-white px-3 py-2.5 text-xs font-semibold text-slate-700 outline-none focus:border-emerald-400 focus:ring-2 focus:ring-emerald-500/10" />
            </div>
        </div>

        <div class="p-5 bg-slate-50 border-t border-slate-100 flex justify-end items-center space-x-3">
            <button onclick="RS.closeDEMAnalysisModal()" class="px-4 py-2 text-xs font-bold text-slate-400 hover:text-slate-600">Cancel</button>
            <button id="dem-analysis-run-btn"
                    onclick="RS.executeDEMAnalysis()"
                    disabled
                    class="bg-emerald-600 text-white px-6 py-2 rounded-lg text-xs font-bold shadow-lg shadow-emerald-200 disabled:opacity-50 disabled:shadow-none">Run Analysis</button>
        </div>
    </div>
</div>
`;
