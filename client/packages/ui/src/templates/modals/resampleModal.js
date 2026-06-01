export const resampleModal = `
<div id="resample-modal" class="hidden fixed inset-0 bg-slate-900/60 backdrop-blur-sm z-[2000] flex items-center justify-center p-4">
    <div class="bg-white w-full max-w-lg rounded-2xl shadow-2xl overflow-hidden">
        <div class="p-5 border-b border-slate-100 flex justify-between items-center bg-slate-50/50">
            <div>
                <h3 class="font-bold text-slate-800 uppercase text-xs tracking-widest">Raster Resampling</h3>
                <p id="resample-current-resolution" class="mt-1 text-[10px] font-medium text-slate-400 truncate"></p>
            </div>
            <button onclick="RS.closeResampleModal()" class="w-7 h-7 rounded-lg text-slate-400 hover:text-slate-600 hover:bg-slate-100 transition-colors" title="Close">x</button>
        </div>

        <div class="p-5 space-y-4 bg-white">
            <div>
                <label class="mb-1 block text-[10px] font-black uppercase tracking-widest text-slate-400">Source Raster</label>
                <select id="resample-raster-select"
                        onchange="RS.handleResampleInputChange()"
                        class="w-full rounded-xl border border-slate-200 bg-slate-50 px-3 py-2.5 text-xs font-semibold text-slate-700 outline-none focus:border-teal-400 focus:ring-2 focus:ring-teal-500/10"></select>
            </div>

            <div class="grid grid-cols-1 sm:grid-cols-2 gap-3">
                <div>
                    <label class="mb-1 block text-[10px] font-black uppercase tracking-widest text-slate-400">Resolution X</label>
                    <input id="resample-resolution-x"
                           type="number"
                           min="0"
                           step="any"
                           oninput="RS.handleResampleInputChange()"
                           class="w-full rounded-xl border border-slate-200 bg-white px-3 py-2.5 text-xs font-mono text-slate-700 outline-none focus:border-teal-400 focus:ring-2 focus:ring-teal-500/10" />
                </div>
                <div>
                    <label class="mb-1 block text-[10px] font-black uppercase tracking-widest text-slate-400">Resolution Y</label>
                    <input id="resample-resolution-y"
                           type="number"
                           min="0"
                           step="any"
                           oninput="RS.handleResampleInputChange()"
                           class="w-full rounded-xl border border-slate-200 bg-white px-3 py-2.5 text-xs font-mono text-slate-700 outline-none focus:border-teal-400 focus:ring-2 focus:ring-teal-500/10" />
                </div>
            </div>

            <div class="grid grid-cols-1 sm:grid-cols-2 gap-3">
                <div>
                    <label class="mb-1 block text-[10px] font-black uppercase tracking-widest text-slate-400">Unit</label>
                    <select id="resample-unit-select"
                            onchange="RS.handleResampleInputChange()"
                            class="w-full rounded-xl border border-slate-200 bg-slate-50 px-3 py-2.5 text-xs font-semibold text-slate-700 outline-none focus:border-teal-400 focus:ring-2 focus:ring-teal-500/10">
                        <option value="source">Source CRS units</option>
                        <option value="degrees">Degrees</option>
                        <option value="meters">Meters</option>
                    </select>
                </div>
                <div>
                    <label class="mb-1 block text-[10px] font-black uppercase tracking-widest text-slate-400">Method</label>
                    <select id="resample-method-select"
                            onchange="RS.handleResampleInputChange()"
                            class="w-full rounded-xl border border-slate-200 bg-slate-50 px-3 py-2.5 text-xs font-semibold text-slate-700 outline-none focus:border-teal-400 focus:ring-2 focus:ring-teal-500/10">
                        <option value="bilinear">Bilinear</option>
                        <option value="nearest">Nearest</option>
                        <option value="cubic">Cubic</option>
                        <option value="average">Average</option>
                        <option value="mode">Mode</option>
                    </select>
                </div>
            </div>

            <div>
                <label class="mb-1 block text-[10px] font-black uppercase tracking-widest text-slate-400">Output Name</label>
                <input id="resample-name-input"
                       type="text"
                       oninput="RS.handleResampleInputChange()"
                       class="w-full rounded-xl border border-slate-200 bg-white px-3 py-2.5 text-xs font-semibold text-slate-700 outline-none focus:border-teal-400 focus:ring-2 focus:ring-teal-500/10" />
            </div>
        </div>

        <div class="p-5 bg-slate-50 border-t border-slate-100 flex justify-end items-center space-x-3">
            <button onclick="RS.closeResampleModal()" class="px-4 py-2 text-xs font-bold text-slate-400 hover:text-slate-600">Cancel</button>
            <button id="resample-confirm-btn"
                    onclick="RS.executeResample()"
                    disabled
                    class="bg-teal-600 text-white px-6 py-2 rounded-lg text-xs font-bold shadow-lg shadow-teal-200 disabled:opacity-50 disabled:shadow-none">Resample</button>
        </div>
    </div>
</div>
`;
