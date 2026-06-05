export const timeSeriesModal = `
<div id="time-series-modal" class="hidden fixed inset-0 bg-slate-900/60 backdrop-blur-sm z-[2000] flex items-center justify-center p-4">
    <div class="bg-white w-full max-w-3xl rounded-2xl shadow-2xl overflow-hidden">
        <div class="p-5 border-b border-slate-100 flex justify-between items-center bg-slate-50/50">
            <div>
                <h3 id="time-series-title" class="font-bold text-slate-800 uppercase text-xs tracking-widest">Time-Series Analysis</h3>
                <p id="time-series-selection-hint" class="mt-1 text-[10px] font-medium text-slate-400 truncate"></p>
            </div>
            <button onclick="RS.closeTimeSeriesModal()" class="w-7 h-7 rounded-lg text-slate-400 hover:text-slate-600 hover:bg-slate-100 transition-colors" title="Close">x</button>
        </div>

        <div class="p-5 bg-white max-h-[72vh] overflow-y-auto space-y-4">
            <div class="grid grid-cols-1 sm:grid-cols-2 gap-3">
                <div>
                    <label class="mb-1 block text-[10px] font-black uppercase tracking-widest text-slate-400">Operation</label>
                    <select id="time-series-operation-select"
                            onchange="RS.switchTimeSeriesOperation(this.value)"
                            class="w-full rounded-xl border border-slate-200 bg-slate-50 px-3 py-2.5 text-xs font-semibold text-slate-700 outline-none focus:border-teal-400 focus:ring-2 focus:ring-teal-500/10">
                        <option value="monthly_composite">Monthly Compositing</option>
                        <option value="annual_composite">Annual Compositing</option>
                        <option value="maximum_composite">Maximum Value Compositing</option>
                        <option value="median_composite">Median Compositing</option>
                        <option value="moving_window_smoothing">Moving Window Smoothing</option>
                        <option value="savitzky_golay">Savitzky-Golay Filtering</option>
                        <option value="trend">Trend Analysis</option>
                        <option value="seasonality">Seasonality Analysis</option>
                        <option value="phenology">Phenological Parameters</option>
                    </select>
                </div>
                <div>
                    <label class="mb-1 block text-[10px] font-black uppercase tracking-widest text-slate-400">Input Band</label>
                    <input id="time-series-band-index"
                           type="number"
                           min="1"
                           step="1"
                           value="1"
                           oninput="RS.handleTimeSeriesInputChange()"
                           class="w-full rounded-xl border border-slate-200 bg-white px-3 py-2.5 text-xs font-mono text-slate-700 outline-none focus:border-teal-400 focus:ring-2 focus:ring-teal-500/10" />
                </div>
            </div>

            <div class="grid grid-cols-1 lg:grid-cols-2 gap-3">
                <div>
                    <label class="mb-1 block text-[10px] font-black uppercase tracking-widest text-slate-400">Rasters</label>
                    <select id="time-series-raster-select"
                            multiple
                            size="8"
                            onchange="RS.handleTimeSeriesSelectionChange()"
                            class="w-full rounded-xl border border-slate-200 bg-white px-3 py-2 text-xs font-semibold text-slate-700 outline-none focus:border-teal-400 focus:ring-2 focus:ring-teal-500/10"></select>
                </div>
                <div>
                    <label class="mb-1 block text-[10px] font-black uppercase tracking-widest text-slate-400">Acquisition Dates</label>
                    <textarea id="time-series-dates-input"
                              rows="8"
                              oninput="RS.handleTimeSeriesInputChange()"
                              class="w-full rounded-xl border border-slate-200 bg-white px-3 py-2 text-xs font-mono text-slate-700 outline-none focus:border-teal-400 focus:ring-2 focus:ring-teal-500/10"></textarea>
                </div>
            </div>

            <div id="time-series-moving-section" class="time-series-option hidden">
                <label class="mb-1 block text-[10px] font-black uppercase tracking-widest text-slate-400">Moving Window Size</label>
                <input id="time-series-moving-window-size"
                       type="number"
                       min="1"
                       step="2"
                       value="3"
                       oninput="RS.handleTimeSeriesInputChange()"
                       class="w-full rounded-xl border border-slate-200 bg-white px-3 py-2.5 text-xs font-mono text-slate-700 outline-none focus:border-teal-400 focus:ring-2 focus:ring-teal-500/10" />
            </div>

            <div id="time-series-savgol-section" class="time-series-option hidden">
                <div class="grid grid-cols-1 sm:grid-cols-2 gap-3">
                    <div>
                        <label class="mb-1 block text-[10px] font-black uppercase tracking-widest text-slate-400">Window Length</label>
                        <input id="time-series-savgol-window-length"
                               type="number"
                               min="3"
                               step="2"
                               value="5"
                               oninput="RS.handleTimeSeriesInputChange()"
                               class="w-full rounded-xl border border-slate-200 bg-white px-3 py-2.5 text-xs font-mono text-slate-700 outline-none focus:border-teal-400 focus:ring-2 focus:ring-teal-500/10" />
                    </div>
                    <div>
                        <label class="mb-1 block text-[10px] font-black uppercase tracking-widest text-slate-400">Polynomial Order</label>
                        <input id="time-series-savgol-polyorder"
                               type="number"
                               min="0"
                               step="1"
                               value="2"
                               oninput="RS.handleTimeSeriesInputChange()"
                               class="w-full rounded-xl border border-slate-200 bg-white px-3 py-2.5 text-xs font-mono text-slate-700 outline-none focus:border-teal-400 focus:ring-2 focus:ring-teal-500/10" />
                    </div>
                </div>
            </div>

            <div id="time-series-phenology-section" class="time-series-option hidden">
                <label class="mb-1 block text-[10px] font-black uppercase tracking-widest text-slate-400">Threshold Ratio</label>
                <input id="time-series-phenology-threshold"
                       type="number"
                       min="0"
                       max="1"
                       step="0.01"
                       value="0.2"
                       oninput="RS.handleTimeSeriesInputChange()"
                       class="w-full rounded-xl border border-slate-200 bg-white px-3 py-2.5 text-xs font-mono text-slate-700 outline-none focus:border-teal-400 focus:ring-2 focus:ring-teal-500/10" />
            </div>

            <div>
                <label class="mb-1 block text-[10px] font-black uppercase tracking-widest text-slate-400">Output Name</label>
                <input id="time-series-name-input"
                       type="text"
                       oninput="RS.handleTimeSeriesInputChange()"
                       class="w-full rounded-xl border border-slate-200 bg-white px-3 py-2.5 text-xs font-semibold text-slate-700 outline-none focus:border-teal-400 focus:ring-2 focus:ring-teal-500/10" />
            </div>
        </div>

        <div class="p-5 bg-slate-50 border-t border-slate-100 flex justify-end items-center space-x-3">
            <button onclick="RS.closeTimeSeriesModal()" class="px-4 py-2 text-xs font-bold text-slate-400 hover:text-slate-600">Cancel</button>
            <button id="time-series-run-btn"
                    onclick="RS.executeTimeSeriesAnalysis()"
                    disabled
                    class="bg-teal-600 text-white px-6 py-2 rounded-lg text-xs font-bold shadow-lg shadow-teal-200 disabled:opacity-50 disabled:shadow-none">Run Analysis</button>
        </div>
    </div>
</div>
`;
