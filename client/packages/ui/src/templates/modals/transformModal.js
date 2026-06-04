export const transformModal = `
<div id="transform-analysis-modal" class="hidden fixed inset-0 bg-slate-900/60 backdrop-blur-sm z-[2000] flex items-center justify-center p-4">
    <div class="bg-white w-full max-w-2xl rounded-2xl shadow-2xl overflow-hidden">
        <div class="p-5 border-b border-slate-100 flex justify-between items-center bg-slate-50/50">
            <div>
                <h3 id="transform-analysis-title" class="font-bold text-slate-800 uppercase text-xs tracking-widest">Raster Transform Analysis</h3>
                <p id="transform-analysis-raster-hint" class="mt-1 text-[10px] font-medium text-slate-400 truncate"></p>
            </div>
            <button onclick="RS.closeTransformAnalysisModal()" class="w-7 h-7 rounded-lg text-slate-400 hover:text-slate-600 hover:bg-slate-100 transition-colors" title="Close">x</button>
        </div>

        <div class="p-5 bg-white max-h-[70vh] overflow-y-auto space-y-4">
            <div class="grid grid-cols-1 sm:grid-cols-2 gap-3">
                <div>
                    <label class="mb-1 block text-[10px] font-black uppercase tracking-widest text-slate-400">Source Raster</label>
                    <select id="transform-analysis-raster-select"
                            onchange="RS.handleTransformAnalysisInputChange()"
                            class="w-full rounded-xl border border-slate-200 bg-slate-50 px-3 py-2.5 text-xs font-semibold text-slate-700 outline-none focus:border-violet-400 focus:ring-2 focus:ring-violet-500/10"></select>
                </div>
                <div>
                    <label class="mb-1 block text-[10px] font-black uppercase tracking-widest text-slate-400">Tool</label>
                    <select id="transform-analysis-type-select"
                            onchange="RS.switchTransformAnalysisType(this.value)"
                            class="w-full rounded-xl border border-slate-200 bg-slate-50 px-3 py-2.5 text-xs font-semibold text-slate-700 outline-none focus:border-violet-400 focus:ring-2 focus:ring-violet-500/10">
                        <option value="fourier">Fourier Analysis</option>
                        <option value="wavelet">Wavelet Analysis</option>
                        <option value="pca">PCA</option>
                    </select>
                </div>
            </div>

            <div id="transform-analysis-band-section" class="transform-analysis-option">
                <label class="mb-1 block text-[10px] font-black uppercase tracking-widest text-slate-400">Input Band</label>
                <input id="transform-analysis-band-index"
                       type="number"
                       min="1"
                       step="1"
                       value="1"
                       oninput="RS.handleTransformAnalysisInputChange()"
                       class="w-full rounded-xl border border-slate-200 bg-white px-3 py-2.5 text-xs font-mono text-slate-700 outline-none focus:border-violet-400 focus:ring-2 focus:ring-violet-500/10" />
            </div>

            <div id="transform-analysis-fourier-section" class="transform-analysis-option">
                <label class="mb-1 block text-[10px] font-black uppercase tracking-widest text-slate-400">Fourier Output</label>
                <select id="transform-analysis-fourier-output"
                        onchange="RS.handleTransformAnalysisInputChange()"
                        class="w-full rounded-xl border border-slate-200 bg-slate-50 px-3 py-2.5 text-xs font-semibold text-slate-700 outline-none focus:border-violet-400 focus:ring-2 focus:ring-violet-500/10">
                    <option value="magnitude">Log Magnitude Spectrum</option>
                    <option value="power">Log Power Spectrum</option>
                    <option value="phase">Phase Spectrum</option>
                </select>
            </div>

            <div id="transform-analysis-wavelet-section" class="transform-analysis-option hidden">
                <div class="grid grid-cols-1 sm:grid-cols-2 gap-3">
                    <div>
                        <label class="mb-1 block text-[10px] font-black uppercase tracking-widest text-slate-400">Wavelet Output</label>
                        <select id="transform-analysis-wavelet-output"
                                onchange="RS.handleTransformAnalysisInputChange()"
                                class="w-full rounded-xl border border-slate-200 bg-slate-50 px-3 py-2.5 text-xs font-semibold text-slate-700 outline-none focus:border-violet-400 focus:ring-2 focus:ring-violet-500/10">
                            <option value="detail_energy">Detail Energy</option>
                            <option value="approximation">Approximation</option>
                            <option value="horizontal">Horizontal Detail</option>
                            <option value="vertical">Vertical Detail</option>
                            <option value="diagonal">Diagonal Detail</option>
                        </select>
                    </div>
                    <div>
                        <label class="mb-1 block text-[10px] font-black uppercase tracking-widest text-slate-400">Level</label>
                        <input id="transform-analysis-wavelet-level"
                               type="number"
                               min="1"
                               step="1"
                               value="1"
                               oninput="RS.handleTransformAnalysisInputChange()"
                               class="w-full rounded-xl border border-slate-200 bg-white px-3 py-2.5 text-xs font-mono text-slate-700 outline-none focus:border-violet-400 focus:ring-2 focus:ring-violet-500/10" />
                    </div>
                </div>
            </div>

            <div id="transform-analysis-pca-section" class="transform-analysis-option hidden">
                <div class="grid grid-cols-1 sm:grid-cols-2 gap-3">
                    <div>
                        <label class="mb-1 block text-[10px] font-black uppercase tracking-widest text-slate-400">Components</label>
                        <input id="transform-analysis-pca-components"
                               type="number"
                               min="1"
                               step="1"
                               value="3"
                               oninput="RS.handleTransformAnalysisInputChange()"
                               class="w-full rounded-xl border border-slate-200 bg-white px-3 py-2.5 text-xs font-mono text-slate-700 outline-none focus:border-violet-400 focus:ring-2 focus:ring-violet-500/10" />
                    </div>
                    <label class="flex items-center gap-2 rounded-xl border border-slate-200 bg-slate-50 px-3 py-2.5 text-xs font-bold text-slate-600">
                        <input id="transform-analysis-pca-standardize"
                               type="checkbox"
                               onchange="RS.handleTransformAnalysisInputChange()"
                               class="rounded border-slate-300 text-violet-600 focus:ring-violet-500" />
                        <span>Standardize bands</span>
                    </label>
                </div>
            </div>

            <div>
                <label class="mb-1 block text-[10px] font-black uppercase tracking-widest text-slate-400">Output Name</label>
                <input id="transform-analysis-name-input"
                       type="text"
                       oninput="RS.handleTransformAnalysisInputChange()"
                       class="w-full rounded-xl border border-slate-200 bg-white px-3 py-2.5 text-xs font-semibold text-slate-700 outline-none focus:border-violet-400 focus:ring-2 focus:ring-violet-500/10" />
            </div>
        </div>

        <div class="p-5 bg-slate-50 border-t border-slate-100 flex justify-end items-center space-x-3">
            <button onclick="RS.closeTransformAnalysisModal()" class="px-4 py-2 text-xs font-bold text-slate-400 hover:text-slate-600">Cancel</button>
            <button id="transform-analysis-run-btn"
                    onclick="RS.executeTransformAnalysis()"
                    disabled
                    class="bg-violet-600 text-white px-6 py-2 rounded-lg text-xs font-bold shadow-lg shadow-violet-200 disabled:opacity-50 disabled:shadow-none">Run Analysis</button>
        </div>
    </div>
</div>
`;
