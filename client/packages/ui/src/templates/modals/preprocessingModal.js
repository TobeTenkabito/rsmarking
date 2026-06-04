export const preprocessingModal = `
<div id="preprocessing-modal" class="hidden fixed inset-0 bg-slate-900/60 backdrop-blur-sm z-[2000] flex items-center justify-center p-4">
    <div class="bg-white w-full max-w-3xl rounded-2xl shadow-2xl overflow-hidden">
        <div class="p-5 border-b border-slate-100 flex justify-between items-center bg-slate-50/50">
            <div>
                <h3 id="preprocessing-title" class="font-bold text-slate-800 uppercase text-xs tracking-widest">Raster Preprocessing</h3>
                <p id="preprocessing-raster-hint" class="mt-1 text-[10px] font-medium text-slate-400 truncate"></p>
            </div>
            <button onclick="RS.closePreprocessingModal()" class="w-7 h-7 rounded-lg text-slate-400 hover:text-slate-600 hover:bg-slate-100 transition-colors" title="Close">x</button>
        </div>

        <div class="border-b border-slate-100 bg-white px-5 py-3">
            <div class="grid grid-cols-2 gap-2">
                <button id="preprocessing-mode-radiometric"
                        onclick="RS.switchPreprocessingMode('radiometric')"
                        class="preprocessing-mode-btn rounded-lg px-3 py-2 text-[10px] font-black uppercase tracking-widest transition-colors">
                    Radiometric
                </button>
                <button id="preprocessing-mode-geometric"
                        onclick="RS.switchPreprocessingMode('geometric')"
                        class="preprocessing-mode-btn rounded-lg px-3 py-2 text-[10px] font-black uppercase tracking-widest transition-colors">
                    Geometric
                </button>
            </div>
        </div>

        <div class="p-5 bg-white max-h-[70vh] overflow-y-auto space-y-4">
            <div class="grid grid-cols-1 sm:grid-cols-2 gap-3">
                <div>
                    <label class="mb-1 block text-[10px] font-black uppercase tracking-widest text-slate-400">Source Raster</label>
                    <select id="preprocessing-raster-select"
                            onchange="RS.handlePreprocessingInputChange()"
                            class="w-full rounded-xl border border-slate-200 bg-slate-50 px-3 py-2.5 text-xs font-semibold text-slate-700 outline-none focus:border-cyan-400 focus:ring-2 focus:ring-cyan-500/10"></select>
                </div>
                <div>
                    <label class="mb-1 block text-[10px] font-black uppercase tracking-widest text-slate-400">Output Name</label>
                    <input id="preprocessing-name-input"
                           type="text"
                           oninput="RS.handlePreprocessingInputChange()"
                           class="w-full rounded-xl border border-slate-200 bg-white px-3 py-2.5 text-xs font-semibold text-slate-700 outline-none focus:border-cyan-400 focus:ring-2 focus:ring-cyan-500/10" />
                </div>
            </div>

            <div id="preprocessing-radiometric-section" class="preprocessing-section space-y-4">
                <div class="grid grid-cols-1 sm:grid-cols-3 gap-3">
                    <div>
                        <label class="mb-1 block text-[10px] font-black uppercase tracking-widest text-slate-400">Calibration Type</label>
                        <select id="preprocessing-radiometric-type"
                                onchange="RS.handlePreprocessingInputChange()"
                                class="w-full rounded-xl border border-slate-200 bg-slate-50 px-3 py-2.5 text-xs font-semibold text-slate-700 outline-none focus:border-cyan-400 focus:ring-2 focus:ring-cyan-500/10">
                            <option value="auto">Auto</option>
                            <option value="scale">Scale / Offset</option>
                            <option value="radiance">Radiance</option>
                            <option value="reflectance">Reflectance</option>
                        </select>
                    </div>
                    <div>
                        <label class="mb-1 block text-[10px] font-black uppercase tracking-widest text-slate-400">Scale Factor</label>
                        <input id="preprocessing-scale-factor"
                               type="number"
                               step="any"
                               oninput="RS.handlePreprocessingInputChange()"
                               class="w-full rounded-xl border border-slate-200 bg-white px-3 py-2.5 text-xs font-mono text-slate-700 outline-none focus:border-cyan-400 focus:ring-2 focus:ring-cyan-500/10" />
                    </div>
                    <div>
                        <label class="mb-1 block text-[10px] font-black uppercase tracking-widest text-slate-400">Offset</label>
                        <input id="preprocessing-offset"
                               type="number"
                               step="any"
                               oninput="RS.handlePreprocessingInputChange()"
                               class="w-full rounded-xl border border-slate-200 bg-white px-3 py-2.5 text-xs font-mono text-slate-700 outline-none focus:border-cyan-400 focus:ring-2 focus:ring-cyan-500/10" />
                    </div>
                </div>

                <div class="grid grid-cols-1 sm:grid-cols-4 gap-3">
                    <div>
                        <label class="mb-1 block text-[10px] font-black uppercase tracking-widest text-slate-400">Radiance Mult</label>
                        <input id="preprocessing-radiance-mult"
                               type="number"
                               step="any"
                               oninput="RS.handlePreprocessingInputChange()"
                               class="w-full rounded-xl border border-slate-200 bg-white px-3 py-2.5 text-xs font-mono text-slate-700 outline-none focus:border-cyan-400 focus:ring-2 focus:ring-cyan-500/10" />
                    </div>
                    <div>
                        <label class="mb-1 block text-[10px] font-black uppercase tracking-widest text-slate-400">Radiance Add</label>
                        <input id="preprocessing-radiance-add"
                               type="number"
                               step="any"
                               oninput="RS.handlePreprocessingInputChange()"
                               class="w-full rounded-xl border border-slate-200 bg-white px-3 py-2.5 text-xs font-mono text-slate-700 outline-none focus:border-cyan-400 focus:ring-2 focus:ring-cyan-500/10" />
                    </div>
                    <div>
                        <label class="mb-1 block text-[10px] font-black uppercase tracking-widest text-slate-400">Reflectance Mult</label>
                        <input id="preprocessing-reflectance-mult"
                               type="number"
                               step="any"
                               oninput="RS.handlePreprocessingInputChange()"
                               class="w-full rounded-xl border border-slate-200 bg-white px-3 py-2.5 text-xs font-mono text-slate-700 outline-none focus:border-cyan-400 focus:ring-2 focus:ring-cyan-500/10" />
                    </div>
                    <div>
                        <label class="mb-1 block text-[10px] font-black uppercase tracking-widest text-slate-400">Reflectance Add</label>
                        <input id="preprocessing-reflectance-add"
                               type="number"
                               step="any"
                               oninput="RS.handlePreprocessingInputChange()"
                               class="w-full rounded-xl border border-slate-200 bg-white px-3 py-2.5 text-xs font-mono text-slate-700 outline-none focus:border-cyan-400 focus:ring-2 focus:ring-cyan-500/10" />
                    </div>
                </div>

                <div class="grid grid-cols-1 sm:grid-cols-3 gap-3">
                    <div>
                        <label class="mb-1 block text-[10px] font-black uppercase tracking-widest text-slate-400">Sun Elevation</label>
                        <input id="preprocessing-sun-elevation"
                               type="number"
                               step="any"
                               oninput="RS.handlePreprocessingInputChange()"
                               class="w-full rounded-xl border border-slate-200 bg-white px-3 py-2.5 text-xs font-mono text-slate-700 outline-none focus:border-cyan-400 focus:ring-2 focus:ring-cyan-500/10" />
                    </div>
                    <div>
                        <label class="mb-1 block text-[10px] font-black uppercase tracking-widest text-slate-400">Earth-Sun Distance</label>
                        <input id="preprocessing-earth-sun-distance"
                               type="number"
                               min="0"
                               step="any"
                               value="1"
                               oninput="RS.handlePreprocessingInputChange()"
                               class="w-full rounded-xl border border-slate-200 bg-white px-3 py-2.5 text-xs font-mono text-slate-700 outline-none focus:border-cyan-400 focus:ring-2 focus:ring-cyan-500/10" />
                    </div>
                    <div>
                        <label class="mb-1 block text-[10px] font-black uppercase tracking-widest text-slate-400">Solar Irradiance</label>
                        <input id="preprocessing-solar-irradiance"
                               type="number"
                               min="0"
                               step="any"
                               oninput="RS.handlePreprocessingInputChange()"
                               class="w-full rounded-xl border border-slate-200 bg-white px-3 py-2.5 text-xs font-mono text-slate-700 outline-none focus:border-cyan-400 focus:ring-2 focus:ring-cyan-500/10" />
                    </div>
                </div>

                <div class="grid grid-cols-1 sm:grid-cols-2 gap-3">
                    <label class="flex items-center gap-2 rounded-xl border border-slate-200 bg-slate-50 px-3 py-2.5 text-xs font-bold text-slate-600">
                        <input id="preprocessing-sun-correction"
                               type="checkbox"
                               checked
                               onchange="RS.handlePreprocessingInputChange()"
                               class="rounded border-slate-300 text-cyan-600 focus:ring-cyan-500" />
                        Sun elevation correction
                    </label>
                    <label class="flex items-center gap-2 rounded-xl border border-slate-200 bg-slate-50 px-3 py-2.5 text-xs font-bold text-slate-600">
                        <input id="preprocessing-clamp"
                               type="checkbox"
                               onchange="RS.handlePreprocessingInputChange()"
                               class="rounded border-slate-300 text-cyan-600 focus:ring-cyan-500" />
                        Clamp output to 0-1
                    </label>
                </div>
            </div>

            <div id="preprocessing-geometric-section" class="preprocessing-section space-y-4">
                <div class="grid grid-cols-1 sm:grid-cols-3 gap-3">
                    <div>
                        <label class="mb-1 block text-[10px] font-black uppercase tracking-widest text-slate-400">Target CRS</label>
                        <input id="preprocessing-dst-crs"
                               type="text"
                               placeholder="EPSG:4326"
                               oninput="RS.handlePreprocessingInputChange()"
                               class="w-full rounded-xl border border-slate-200 bg-white px-3 py-2.5 text-xs font-mono text-slate-700 outline-none focus:border-cyan-400 focus:ring-2 focus:ring-cyan-500/10" />
                    </div>
                    <div>
                        <label class="mb-1 block text-[10px] font-black uppercase tracking-widest text-slate-400">Resampling</label>
                        <select id="preprocessing-resampling-method"
                                onchange="RS.handlePreprocessingInputChange()"
                                class="w-full rounded-xl border border-slate-200 bg-slate-50 px-3 py-2.5 text-xs font-semibold text-slate-700 outline-none focus:border-cyan-400 focus:ring-2 focus:ring-cyan-500/10">
                            <option value="bilinear">Bilinear</option>
                            <option value="nearest">Nearest</option>
                            <option value="cubic">Cubic</option>
                            <option value="average">Average</option>
                            <option value="mode">Mode</option>
                        </select>
                    </div>
                    <div>
                        <label class="mb-1 block text-[10px] font-black uppercase tracking-widest text-slate-400">Rotation</label>
                        <input id="preprocessing-rotation-degrees"
                               type="number"
                               step="any"
                               value="0"
                               oninput="RS.handlePreprocessingInputChange()"
                               class="w-full rounded-xl border border-slate-200 bg-white px-3 py-2.5 text-xs font-mono text-slate-700 outline-none focus:border-cyan-400 focus:ring-2 focus:ring-cyan-500/10" />
                    </div>
                </div>

                <div class="grid grid-cols-1 sm:grid-cols-4 gap-3">
                    <div>
                        <label class="mb-1 block text-[10px] font-black uppercase tracking-widest text-slate-400">Resolution X</label>
                        <input id="preprocessing-target-resolution-x"
                               type="number"
                               min="0"
                               step="any"
                               oninput="RS.handlePreprocessingInputChange()"
                               class="w-full rounded-xl border border-slate-200 bg-white px-3 py-2.5 text-xs font-mono text-slate-700 outline-none focus:border-cyan-400 focus:ring-2 focus:ring-cyan-500/10" />
                    </div>
                    <div>
                        <label class="mb-1 block text-[10px] font-black uppercase tracking-widest text-slate-400">Resolution Y</label>
                        <input id="preprocessing-target-resolution-y"
                               type="number"
                               min="0"
                               step="any"
                               oninput="RS.handlePreprocessingInputChange()"
                               class="w-full rounded-xl border border-slate-200 bg-white px-3 py-2.5 text-xs font-mono text-slate-700 outline-none focus:border-cyan-400 focus:ring-2 focus:ring-cyan-500/10" />
                    </div>
                    <div>
                        <label class="mb-1 block text-[10px] font-black uppercase tracking-widest text-slate-400">Shift X</label>
                        <input id="preprocessing-shift-x"
                               type="number"
                               step="any"
                               value="0"
                               oninput="RS.handlePreprocessingInputChange()"
                               class="w-full rounded-xl border border-slate-200 bg-white px-3 py-2.5 text-xs font-mono text-slate-700 outline-none focus:border-cyan-400 focus:ring-2 focus:ring-cyan-500/10" />
                    </div>
                    <div>
                        <label class="mb-1 block text-[10px] font-black uppercase tracking-widest text-slate-400">Shift Y</label>
                        <input id="preprocessing-shift-y"
                               type="number"
                               step="any"
                               value="0"
                               oninput="RS.handlePreprocessingInputChange()"
                               class="w-full rounded-xl border border-slate-200 bg-white px-3 py-2.5 text-xs font-mono text-slate-700 outline-none focus:border-cyan-400 focus:ring-2 focus:ring-cyan-500/10" />
                    </div>
                </div>

                <div class="grid grid-cols-1 sm:grid-cols-2 gap-3">
                    <div>
                        <label class="mb-1 block text-[10px] font-black uppercase tracking-widest text-slate-400">Scale X</label>
                        <input id="preprocessing-scale-x"
                               type="number"
                               min="0"
                               step="any"
                               value="1"
                               oninput="RS.handlePreprocessingInputChange()"
                               class="w-full rounded-xl border border-slate-200 bg-white px-3 py-2.5 text-xs font-mono text-slate-700 outline-none focus:border-cyan-400 focus:ring-2 focus:ring-cyan-500/10" />
                    </div>
                    <div>
                        <label class="mb-1 block text-[10px] font-black uppercase tracking-widest text-slate-400">Scale Y</label>
                        <input id="preprocessing-scale-y"
                               type="number"
                               min="0"
                               step="any"
                               value="1"
                               oninput="RS.handlePreprocessingInputChange()"
                               class="w-full rounded-xl border border-slate-200 bg-white px-3 py-2.5 text-xs font-mono text-slate-700 outline-none focus:border-cyan-400 focus:ring-2 focus:ring-cyan-500/10" />
                    </div>
                </div>

                <div>
                    <label class="mb-1 block text-[10px] font-black uppercase tracking-widest text-slate-400">Ground Control Points JSON</label>
                    <textarea id="preprocessing-gcps"
                              rows="4"
                              placeholder='[{"row":0,"col":0,"x":120.0,"y":30.0}]'
                              oninput="RS.handlePreprocessingInputChange()"
                              class="w-full resize-y rounded-xl border border-slate-200 bg-white px-3 py-2.5 text-xs font-mono text-slate-700 outline-none focus:border-cyan-400 focus:ring-2 focus:ring-cyan-500/10"></textarea>
                </div>
            </div>
        </div>

        <div class="p-5 bg-slate-50 border-t border-slate-100 flex justify-end items-center space-x-3">
            <button onclick="RS.closePreprocessingModal()" class="px-4 py-2 text-xs font-bold text-slate-400 hover:text-slate-600">Cancel</button>
            <button id="preprocessing-run-btn"
                    onclick="RS.executePreprocessing()"
                    disabled
                    class="bg-cyan-600 text-white px-6 py-2 rounded-lg text-xs font-bold shadow-lg shadow-cyan-200 disabled:opacity-50 disabled:shadow-none">Run</button>
        </div>
    </div>
</div>
`;
