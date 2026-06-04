export const classificationModal = `
<div id="classification-modal" class="hidden fixed inset-0 bg-slate-900/60 backdrop-blur-sm z-[2000] flex items-center justify-center p-4">
    <div class="bg-white w-full max-w-3xl rounded-2xl shadow-2xl overflow-hidden">
        <div class="p-5 border-b border-slate-100 flex justify-between items-center bg-slate-50/50">
            <div>
                <h3 id="classification-title" class="font-bold text-slate-800 uppercase text-xs tracking-widest">Raster Classification</h3>
                <p id="classification-raster-hint" class="mt-1 text-[10px] font-medium text-slate-400 truncate"></p>
            </div>
            <button onclick="RS.closeClassificationModal()" class="w-7 h-7 rounded-lg text-slate-400 hover:text-slate-600 hover:bg-slate-100 transition-colors" title="Close">x</button>
        </div>

        <div class="border-b border-slate-100 bg-white px-5 py-3">
            <div class="grid grid-cols-3 gap-2">
                <button id="classification-mode-supervised"
                        onclick="RS.switchClassificationMode('supervised')"
                        class="classification-mode-btn rounded-lg px-3 py-2 text-[10px] font-black uppercase tracking-widest transition-colors">
                    Supervised
                </button>
                <button id="classification-mode-unsupervised"
                        onclick="RS.switchClassificationMode('unsupervised')"
                        class="classification-mode-btn rounded-lg px-3 py-2 text-[10px] font-black uppercase tracking-widest transition-colors">
                    Unsupervised
                </button>
                <button id="classification-mode-segmentation"
                        onclick="RS.switchClassificationMode('segmentation')"
                        class="classification-mode-btn rounded-lg px-3 py-2 text-[10px] font-black uppercase tracking-widest transition-colors">
                    Segmentation
                </button>
            </div>
        </div>

        <div class="p-5 bg-white max-h-[70vh] overflow-y-auto space-y-4">
            <div class="grid grid-cols-1 sm:grid-cols-2 gap-3">
                <div>
                    <label class="mb-1 block text-[10px] font-black uppercase tracking-widest text-slate-400">Source Raster</label>
                    <select id="classification-raster-select"
                            onchange="RS.handleClassificationInputChange()"
                            class="w-full rounded-xl border border-slate-200 bg-slate-50 px-3 py-2.5 text-xs font-semibold text-slate-700 outline-none focus:border-emerald-400 focus:ring-2 focus:ring-emerald-500/10"></select>
                </div>
                <div>
                    <label class="mb-1 block text-[10px] font-black uppercase tracking-widest text-slate-400">Output Name</label>
                    <input id="classification-name-input"
                           type="text"
                           oninput="RS.handleClassificationInputChange()"
                           class="w-full rounded-xl border border-slate-200 bg-white px-3 py-2.5 text-xs font-semibold text-slate-700 outline-none focus:border-emerald-400 focus:ring-2 focus:ring-emerald-500/10" />
                </div>
            </div>

            <div>
                <label class="mb-1 block text-[10px] font-black uppercase tracking-widest text-slate-400">Band Indices</label>
                <input id="classification-band-indices"
                       type="text"
                       placeholder="1,2,3"
                       oninput="RS.handleClassificationInputChange()"
                       class="w-full rounded-xl border border-slate-200 bg-white px-3 py-2.5 text-xs font-mono text-slate-700 outline-none focus:border-emerald-400 focus:ring-2 focus:ring-emerald-500/10" />
            </div>

            <div id="classification-supervised-section" class="classification-section space-y-4">
                <div class="grid grid-cols-1 sm:grid-cols-4 gap-3">
                    <div>
                        <label class="mb-1 block text-[10px] font-black uppercase tracking-widest text-slate-400">Classifier</label>
                        <select id="classification-classifier-select"
                                onchange="RS.handleClassificationInputChange()"
                                class="w-full rounded-xl border border-slate-200 bg-slate-50 px-3 py-2.5 text-xs font-semibold text-slate-700 outline-none focus:border-emerald-400 focus:ring-2 focus:ring-emerald-500/10">
                            <option value="nearest_centroid">Nearest Centroid</option>
                            <option value="random_forest">Random Forest</option>
                            <option value="svm">SVM</option>
                        </select>
                    </div>
                    <div>
                        <label class="mb-1 block text-[10px] font-black uppercase tracking-widest text-slate-400">Trees</label>
                        <input id="classification-n-estimators"
                               type="number"
                               min="1"
                               max="1000"
                               value="100"
                               oninput="RS.handleClassificationInputChange()"
                               class="w-full rounded-xl border border-slate-200 bg-white px-3 py-2.5 text-xs font-mono text-slate-700 outline-none focus:border-emerald-400 focus:ring-2 focus:ring-emerald-500/10" />
                    </div>
                    <div>
                        <label class="mb-1 block text-[10px] font-black uppercase tracking-widest text-slate-400">Seed</label>
                        <input id="classification-supervised-seed"
                               type="number"
                               value="13"
                               oninput="RS.handleClassificationInputChange()"
                               class="w-full rounded-xl border border-slate-200 bg-white px-3 py-2.5 text-xs font-mono text-slate-700 outline-none focus:border-emerald-400 focus:ring-2 focus:ring-emerald-500/10" />
                    </div>
                    <div>
                        <label class="mb-1 block text-[10px] font-black uppercase tracking-widest text-slate-400">Smoothing</label>
                        <input id="classification-supervised-smoothing"
                               type="number"
                               min="0"
                               max="5"
                               value="0"
                               oninput="RS.handleClassificationInputChange()"
                               class="w-full rounded-xl border border-slate-200 bg-white px-3 py-2.5 text-xs font-mono text-slate-700 outline-none focus:border-emerald-400 focus:ring-2 focus:ring-emerald-500/10" />
                    </div>
                </div>

                <div class="rounded-xl border border-slate-200 overflow-hidden">
                    <div class="px-3 py-2 bg-slate-50 border-b border-slate-200 flex items-center justify-between">
                        <span class="text-[10px] font-black uppercase tracking-widest text-slate-500">Training Samples</span>
                        <button onclick="RS.addClassificationSample()"
                                class="px-3 py-1.5 rounded-lg bg-emerald-600 text-white text-[10px] font-black uppercase tracking-widest hover:bg-emerald-700">
                            Add
                        </button>
                    </div>
                    <div class="grid grid-cols-[1fr_1fr_1fr_32px] gap-2 px-3 py-2 bg-white border-b border-slate-100 text-[9px] font-black uppercase tracking-widest text-slate-400">
                        <span>Class</span>
                        <span>Row</span>
                        <span>Col</span>
                        <span></span>
                    </div>
                    <div id="classification-samples-list" class="divide-y divide-slate-100"></div>
                </div>
            </div>

            <div id="classification-unsupervised-section" class="classification-section grid grid-cols-1 sm:grid-cols-5 gap-3">
                <div>
                    <label class="mb-1 block text-[10px] font-black uppercase tracking-widest text-slate-400">Classes</label>
                    <input id="classification-unsupervised-classes"
                           type="number"
                           min="2"
                           max="255"
                           value="5"
                           oninput="RS.handleClassificationInputChange()"
                           class="w-full rounded-xl border border-slate-200 bg-white px-3 py-2.5 text-xs font-mono text-slate-700 outline-none focus:border-emerald-400 focus:ring-2 focus:ring-emerald-500/10" />
                </div>
                <div>
                    <label class="mb-1 block text-[10px] font-black uppercase tracking-widest text-slate-400">Method</label>
                    <select id="classification-unsupervised-method"
                            onchange="RS.handleClassificationInputChange()"
                            class="w-full rounded-xl border border-slate-200 bg-slate-50 px-3 py-2.5 text-xs font-semibold text-slate-700 outline-none focus:border-emerald-400 focus:ring-2 focus:ring-emerald-500/10">
                        <option value="kmeans">KMeans</option>
                        <option value="mini_batch_kmeans">Mini Batch</option>
                    </select>
                </div>
                <div>
                    <label class="mb-1 block text-[10px] font-black uppercase tracking-widest text-slate-400">Max Samples</label>
                    <input id="classification-unsupervised-max-samples"
                           type="number"
                           min="100"
                           value="50000"
                           oninput="RS.handleClassificationInputChange()"
                           class="w-full rounded-xl border border-slate-200 bg-white px-3 py-2.5 text-xs font-mono text-slate-700 outline-none focus:border-emerald-400 focus:ring-2 focus:ring-emerald-500/10" />
                </div>
                <div>
                    <label class="mb-1 block text-[10px] font-black uppercase tracking-widest text-slate-400">Seed</label>
                    <input id="classification-unsupervised-seed"
                           type="number"
                           value="13"
                           oninput="RS.handleClassificationInputChange()"
                           class="w-full rounded-xl border border-slate-200 bg-white px-3 py-2.5 text-xs font-mono text-slate-700 outline-none focus:border-emerald-400 focus:ring-2 focus:ring-emerald-500/10" />
                </div>
                <div>
                    <label class="mb-1 block text-[10px] font-black uppercase tracking-widest text-slate-400">Smoothing</label>
                    <input id="classification-unsupervised-smoothing"
                           type="number"
                           min="0"
                           max="5"
                           value="0"
                           oninput="RS.handleClassificationInputChange()"
                           class="w-full rounded-xl border border-slate-200 bg-white px-3 py-2.5 text-xs font-mono text-slate-700 outline-none focus:border-emerald-400 focus:ring-2 focus:ring-emerald-500/10" />
                </div>
            </div>

            <div id="classification-segmentation-section" class="classification-section space-y-3">
                <div class="grid grid-cols-1 sm:grid-cols-3 gap-3">
                    <div>
                        <label class="mb-1 block text-[10px] font-black uppercase tracking-widest text-slate-400">Backend</label>
                        <select id="classification-segmentation-backend"
                                onchange="RS.handleClassificationInputChange()"
                                class="w-full rounded-xl border border-slate-200 bg-slate-50 px-3 py-2.5 text-xs font-semibold text-slate-700 outline-none focus:border-emerald-400 focus:ring-2 focus:ring-emerald-500/10">
                            <option value="auto">Auto</option>
                            <option value="spectral_spatial">Spectral Spatial</option>
                            <option value="onnx">ONNX</option>
                            <option value="slic">SLIC</option>
                            <option value="watershed">Watershed</option>
                        </select>
                    </div>
                    <div>
                        <label class="mb-1 block text-[10px] font-black uppercase tracking-widest text-slate-400">Classes</label>
                        <input id="classification-segmentation-classes"
                               type="number"
                               min="2"
                               max="255"
                               value="2"
                               oninput="RS.handleClassificationInputChange()"
                               class="w-full rounded-xl border border-slate-200 bg-white px-3 py-2.5 text-xs font-mono text-slate-700 outline-none focus:border-emerald-400 focus:ring-2 focus:ring-emerald-500/10" />
                    </div>
                    <div>
                        <label class="mb-1 block text-[10px] font-black uppercase tracking-widest text-slate-400">Threshold</label>
                        <input id="classification-segmentation-threshold"
                               type="number"
                               min="0"
                               max="1"
                               step="0.01"
                               value="0.5"
                               oninput="RS.handleClassificationInputChange()"
                               class="w-full rounded-xl border border-slate-200 bg-white px-3 py-2.5 text-xs font-mono text-slate-700 outline-none focus:border-emerald-400 focus:ring-2 focus:ring-emerald-500/10" />
                    </div>
                </div>

                <div>
                    <label class="mb-1 block text-[10px] font-black uppercase tracking-widest text-slate-400">ONNX Model Path</label>
                    <input id="classification-segmentation-model-path"
                           type="text"
                           oninput="RS.handleClassificationInputChange()"
                           class="w-full rounded-xl border border-slate-200 bg-white px-3 py-2.5 text-xs font-mono text-slate-700 outline-none focus:border-emerald-400 focus:ring-2 focus:ring-emerald-500/10" />
                </div>

                <div class="grid grid-cols-1 sm:grid-cols-4 gap-3">
                    <div>
                        <label class="mb-1 block text-[10px] font-black uppercase tracking-widest text-slate-400">Max Samples</label>
                        <input id="classification-segmentation-max-samples"
                               type="number"
                               min="100"
                               value="50000"
                               oninput="RS.handleClassificationInputChange()"
                               class="w-full rounded-xl border border-slate-200 bg-white px-3 py-2.5 text-xs font-mono text-slate-700 outline-none focus:border-emerald-400 focus:ring-2 focus:ring-emerald-500/10" />
                    </div>
                    <div>
                        <label class="mb-1 block text-[10px] font-black uppercase tracking-widest text-slate-400">Compactness</label>
                        <input id="classification-segmentation-compactness"
                               type="number"
                               min="0"
                               step="0.01"
                               value="0.15"
                               oninput="RS.handleClassificationInputChange()"
                               class="w-full rounded-xl border border-slate-200 bg-white px-3 py-2.5 text-xs font-mono text-slate-700 outline-none focus:border-emerald-400 focus:ring-2 focus:ring-emerald-500/10" />
                    </div>
                    <div>
                        <label class="mb-1 block text-[10px] font-black uppercase tracking-widest text-slate-400">Seed</label>
                        <input id="classification-segmentation-seed"
                               type="number"
                               value="13"
                               oninput="RS.handleClassificationInputChange()"
                               class="w-full rounded-xl border border-slate-200 bg-white px-3 py-2.5 text-xs font-mono text-slate-700 outline-none focus:border-emerald-400 focus:ring-2 focus:ring-emerald-500/10" />
                    </div>
                    <div>
                        <label class="mb-1 block text-[10px] font-black uppercase tracking-widest text-slate-400">Smoothing</label>
                        <input id="classification-segmentation-smoothing"
                               type="number"
                               min="0"
                               max="5"
                               value="1"
                               oninput="RS.handleClassificationInputChange()"
                               class="w-full rounded-xl border border-slate-200 bg-white px-3 py-2.5 text-xs font-mono text-slate-700 outline-none focus:border-emerald-400 focus:ring-2 focus:ring-emerald-500/10" />
                    </div>
                </div>
            </div>
        </div>

        <div class="p-5 bg-slate-50 border-t border-slate-100 flex justify-end items-center space-x-3">
            <button onclick="RS.closeClassificationModal()" class="px-4 py-2 text-xs font-bold text-slate-400 hover:text-slate-600">Cancel</button>
            <button id="classification-run-btn"
                    onclick="RS.executeClassification()"
                    disabled
                    class="bg-emerald-600 text-white px-6 py-2 rounded-lg text-xs font-bold shadow-lg shadow-emerald-200 disabled:opacity-50 disabled:shadow-none">Run</button>
        </div>
    </div>
</div>
`;
