export const textureModal = `
<div id="texture-feature-modal" class="hidden fixed inset-0 bg-slate-900/60 backdrop-blur-sm z-[2000] flex items-center justify-center p-4">
    <div class="bg-white w-full max-w-2xl rounded-2xl shadow-2xl overflow-hidden">
        <div class="p-5 border-b border-slate-100 flex justify-between items-center bg-slate-50/50">
            <div>
                <h3 id="texture-feature-title" class="font-bold text-slate-800 uppercase text-xs tracking-widest">Texture Features</h3>
                <p id="texture-feature-raster-hint" class="mt-1 text-[10px] font-medium text-slate-400 truncate"></p>
            </div>
            <button onclick="RS.closeTextureFeatureModal()" class="w-7 h-7 rounded-lg text-slate-400 hover:text-slate-600 hover:bg-slate-100 transition-colors" title="Close">x</button>
        </div>

        <div class="p-5 bg-white max-h-[70vh] overflow-y-auto space-y-4">
            <div class="grid grid-cols-1 sm:grid-cols-2 gap-3">
                <div>
                    <label class="mb-1 block text-[10px] font-black uppercase tracking-widest text-slate-400">Source Raster</label>
                    <select id="texture-feature-raster-select"
                            onchange="RS.handleTextureFeatureInputChange()"
                            class="w-full rounded-xl border border-slate-200 bg-slate-50 px-3 py-2.5 text-xs font-semibold text-slate-700 outline-none focus:border-amber-400 focus:ring-2 focus:ring-amber-500/10"></select>
                </div>
                <div>
                    <label class="mb-1 block text-[10px] font-black uppercase tracking-widest text-slate-400">Tool</label>
                    <select id="texture-feature-type-select"
                            onchange="RS.switchTextureFeatureType(this.value)"
                            class="w-full rounded-xl border border-slate-200 bg-slate-50 px-3 py-2.5 text-xs font-semibold text-slate-700 outline-none focus:border-amber-400 focus:ring-2 focus:ring-amber-500/10">
                        <option value="glcm">GLCM</option>
                        <option value="local_statistics">Local Statistics Window</option>
                        <option value="gabor">Gabor Filtering</option>
                        <option value="lbp">LBP</option>
                    </select>
                </div>
            </div>

            <div>
                <label class="mb-1 block text-[10px] font-black uppercase tracking-widest text-slate-400">Input Band</label>
                <input id="texture-feature-band-index"
                       type="number"
                       min="1"
                       step="1"
                       value="1"
                       oninput="RS.handleTextureFeatureInputChange()"
                       class="w-full rounded-xl border border-slate-200 bg-white px-3 py-2.5 text-xs font-mono text-slate-700 outline-none focus:border-amber-400 focus:ring-2 focus:ring-amber-500/10" />
            </div>

            <div id="texture-feature-window-section" class="texture-feature-option">
                <div class="grid grid-cols-1 sm:grid-cols-2 gap-3">
                    <div>
                        <label class="mb-1 block text-[10px] font-black uppercase tracking-widest text-slate-400">Gray Levels</label>
                        <input id="texture-feature-gray-levels"
                               type="number"
                               min="2"
                               max="256"
                               step="1"
                               value="32"
                               oninput="RS.handleTextureFeatureInputChange()"
                               class="w-full rounded-xl border border-slate-200 bg-white px-3 py-2.5 text-xs font-mono text-slate-700 outline-none focus:border-amber-400 focus:ring-2 focus:ring-amber-500/10" />
                    </div>
                    <div>
                        <label class="mb-1 block text-[10px] font-black uppercase tracking-widest text-slate-400">Window Size</label>
                        <input id="texture-feature-window-size"
                               type="number"
                               min="3"
                               step="2"
                               value="7"
                               oninput="RS.handleTextureFeatureInputChange()"
                               class="w-full rounded-xl border border-slate-200 bg-white px-3 py-2.5 text-xs font-mono text-slate-700 outline-none focus:border-amber-400 focus:ring-2 focus:ring-amber-500/10" />
                    </div>
                </div>
            </div>

            <div id="texture-feature-glcm-section" class="texture-feature-option">
                <div class="grid grid-cols-1 sm:grid-cols-3 gap-3">
                    <div>
                        <label class="mb-1 block text-[10px] font-black uppercase tracking-widest text-slate-400">Property</label>
                        <select id="texture-feature-glcm-property"
                                onchange="RS.handleTextureFeatureInputChange()"
                                class="w-full rounded-xl border border-slate-200 bg-slate-50 px-3 py-2.5 text-xs font-semibold text-slate-700 outline-none focus:border-amber-400 focus:ring-2 focus:ring-amber-500/10">
                            <option value="contrast">Contrast</option>
                            <option value="dissimilarity">Dissimilarity</option>
                            <option value="homogeneity">Homogeneity</option>
                            <option value="asm">ASM</option>
                            <option value="energy">Energy</option>
                            <option value="entropy">Entropy</option>
                            <option value="correlation">Correlation</option>
                        </select>
                    </div>
                    <div>
                        <label class="mb-1 block text-[10px] font-black uppercase tracking-widest text-slate-400">Distance</label>
                        <input id="texture-feature-glcm-distance"
                               type="number"
                               min="1"
                               step="1"
                               value="1"
                               oninput="RS.handleTextureFeatureInputChange()"
                               class="w-full rounded-xl border border-slate-200 bg-white px-3 py-2.5 text-xs font-mono text-slate-700 outline-none focus:border-amber-400 focus:ring-2 focus:ring-amber-500/10" />
                    </div>
                    <div>
                        <label class="mb-1 block text-[10px] font-black uppercase tracking-widest text-slate-400">Angle</label>
                        <input id="texture-feature-glcm-angle"
                               type="number"
                               step="any"
                               value="0"
                               oninput="RS.handleTextureFeatureInputChange()"
                               class="w-full rounded-xl border border-slate-200 bg-white px-3 py-2.5 text-xs font-mono text-slate-700 outline-none focus:border-amber-400 focus:ring-2 focus:ring-amber-500/10" />
                    </div>
                </div>
            </div>

            <div id="texture-feature-local-section" class="texture-feature-option hidden">
                <label class="mb-1 block text-[10px] font-black uppercase tracking-widest text-slate-400">Statistic</label>
                <select id="texture-feature-local-stat"
                        onchange="RS.handleTextureFeatureInputChange()"
                        class="w-full rounded-xl border border-slate-200 bg-slate-50 px-3 py-2.5 text-xs font-semibold text-slate-700 outline-none focus:border-amber-400 focus:ring-2 focus:ring-amber-500/10">
                    <option value="mean">Mean</option>
                    <option value="std">Standard Deviation</option>
                    <option value="variance">Variance</option>
                    <option value="range">Range</option>
                    <option value="entropy">Entropy</option>
                </select>
            </div>

            <div id="texture-feature-gabor-section" class="texture-feature-option hidden">
                <div class="grid grid-cols-1 sm:grid-cols-3 gap-3">
                    <div>
                        <label class="mb-1 block text-[10px] font-black uppercase tracking-widest text-slate-400">Frequency</label>
                        <input id="texture-feature-gabor-frequency"
                               type="number"
                               min="0.000001"
                               step="any"
                               value="0.2"
                               oninput="RS.handleTextureFeatureInputChange()"
                               class="w-full rounded-xl border border-slate-200 bg-white px-3 py-2.5 text-xs font-mono text-slate-700 outline-none focus:border-amber-400 focus:ring-2 focus:ring-amber-500/10" />
                    </div>
                    <div>
                        <label class="mb-1 block text-[10px] font-black uppercase tracking-widest text-slate-400">Theta</label>
                        <input id="texture-feature-gabor-theta"
                               type="number"
                               step="any"
                               value="0"
                               oninput="RS.handleTextureFeatureInputChange()"
                               class="w-full rounded-xl border border-slate-200 bg-white px-3 py-2.5 text-xs font-mono text-slate-700 outline-none focus:border-amber-400 focus:ring-2 focus:ring-amber-500/10" />
                    </div>
                    <div>
                        <label class="mb-1 block text-[10px] font-black uppercase tracking-widest text-slate-400">Sigma</label>
                        <input id="texture-feature-gabor-sigma"
                               type="number"
                               min="0.000001"
                               step="any"
                               value="2"
                               oninput="RS.handleTextureFeatureInputChange()"
                               class="w-full rounded-xl border border-slate-200 bg-white px-3 py-2.5 text-xs font-mono text-slate-700 outline-none focus:border-amber-400 focus:ring-2 focus:ring-amber-500/10" />
                    </div>
                </div>
            </div>

            <div id="texture-feature-lbp-section" class="texture-feature-option hidden">
                <div class="grid grid-cols-1 sm:grid-cols-2 gap-3">
                    <div>
                        <label class="mb-1 block text-[10px] font-black uppercase tracking-widest text-slate-400">Radius</label>
                        <input id="texture-feature-lbp-radius"
                               type="number"
                               min="0.000001"
                               step="any"
                               value="1"
                               oninput="RS.handleTextureFeatureInputChange()"
                               class="w-full rounded-xl border border-slate-200 bg-white px-3 py-2.5 text-xs font-mono text-slate-700 outline-none focus:border-amber-400 focus:ring-2 focus:ring-amber-500/10" />
                    </div>
                    <div>
                        <label class="mb-1 block text-[10px] font-black uppercase tracking-widest text-slate-400">Points</label>
                        <input id="texture-feature-lbp-points"
                               type="number"
                               min="1"
                               max="24"
                               step="1"
                               value="8"
                               oninput="RS.handleTextureFeatureInputChange()"
                               class="w-full rounded-xl border border-slate-200 bg-white px-3 py-2.5 text-xs font-mono text-slate-700 outline-none focus:border-amber-400 focus:ring-2 focus:ring-amber-500/10" />
                    </div>
                </div>
            </div>

            <div>
                <label class="mb-1 block text-[10px] font-black uppercase tracking-widest text-slate-400">Output Name</label>
                <input id="texture-feature-name-input"
                       type="text"
                       oninput="RS.handleTextureFeatureInputChange()"
                       class="w-full rounded-xl border border-slate-200 bg-white px-3 py-2.5 text-xs font-semibold text-slate-700 outline-none focus:border-amber-400 focus:ring-2 focus:ring-amber-500/10" />
            </div>
        </div>

        <div class="p-5 bg-slate-50 border-t border-slate-100 flex justify-end items-center space-x-3">
            <button onclick="RS.closeTextureFeatureModal()" class="px-4 py-2 text-xs font-bold text-slate-400 hover:text-slate-600">Cancel</button>
            <button id="texture-feature-run-btn"
                    onclick="RS.executeTextureFeature()"
                    disabled
                    class="bg-amber-600 text-white px-6 py-2 rounded-lg text-xs font-bold shadow-lg shadow-amber-200 disabled:opacity-50 disabled:shadow-none">Run Analysis</button>
        </div>
    </div>
</div>
`;
