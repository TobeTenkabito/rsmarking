export const clipModal = `
    <div id="clip-modal"
         class="hidden fixed inset-0 bg-slate-900/60 backdrop-blur-sm z-[2000]
                flex items-center justify-center p-4">
        <div class="bg-white w-full max-w-sm rounded-3xl shadow-2xl relative overflow-hidden flex flex-col">

            <!-- Top color bar -->
            <div class="absolute top-0 left-0 w-full h-1.5
                        bg-gradient-to-r from-amber-400 to-orange-500"></div>

            <!-- Title -->
            <div class="flex items-center space-x-3 px-8 pt-8 pb-4">
                <div class="p-2 bg-amber-50 rounded-xl">
                    <svg class="w-5 h-5 text-amber-500" fill="none"
                         stroke="currentColor" viewBox="0 0 24 24">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2"
                            d="M6 2v4m0 0a2 2 0 100 4 2 2 0 000-4zm0 0H2
                               m16 14v-4m0 0a2 2 0 100-4 2 2 0 000 4zm0 0h4
                               M6 6l12 12"/>
                    </svg>
                </div>
                <div>
                    <h2 class="text-base font-black text-slate-800">Spatial Clip</h2>
                    <p class="text-[10px] text-slate-400">Spatial Clip</p>
                </div>
            </div>

            <!-- English -->
            <div class="px-8 pb-4 space-y-4">

                <!-- ① EnglishType：English -->
                <div class="space-y-1.5">
                    <label class="text-[11px] font-bold text-slate-500 uppercase tracking-widest">
                        Clip Type
                    </label>
                    <div class="grid grid-cols-3 gap-2">

                        <label class="clip-type-option">
                            <input type="radio" name="clip-type" value="raster" checked class="hidden">
                            <div class="clip-type-card border-2 border-slate-200 bg-white 
                            text-slate-600 rounded-xl p-3 text-center cursor-pointer 
                            hover:border-amber-300">
                                <div class="text-xl mb-1">🛰️</div>
                                <div class="text-[11px] font-bold">Clip Raster</div>
                                <div class="text-[9px] opacity-60">Draw an area to crop imagery</div>
                            </div>
                        </label>

                        <label class="clip-type-option">
                            <input type="radio" name="clip-type" value="vector" class="hidden">
                            <div class="clip-type-card border-2 border-slate-200 bg-white
                            text-slate-600 rounded-xl p-3 text-center cursor-pointer
                            hover:border-amber-300">
                                <div class="text-xl mb-1">🔷</div>
                                <div class="text-[11px] font-bold">Clip Vector</div>
                                <div class="text-[9px] opacity-60">Filter features by area</div>
                            </div>
                        </label>

                        <label class="clip-type-option">
                            <input type="radio" name="clip-type" value="layer" class="hidden">
                            <div class="clip-type-card border-2 border-slate-200 bg-white
                            text-slate-600 rounded-xl p-3 text-center cursor-pointer
                            hover:border-amber-300">
                                <div class="text-xl mb-1">✂️</div>
                                <div class="text-[11px] font-bold">Layer Clip</div>
                                <div class="text-[9px] opacity-60">Clip one layer by another</div>
                            </div>
                        </label>

                    </div>
                </div>

                <!-- ② English（raster / vector English，layer Englishhidden） -->
                <div id="clip-raster-info-section" class="space-y-1">
                    <label class="text-[11px] font-bold text-slate-500 uppercase tracking-widest">
                        Active Imagery
                    </label>
                    <div id="clip-raster-info"
                         class="text-[11px] text-slate-500 bg-slate-50 border border-slate-100
                                rounded-xl px-3 py-2.5 leading-relaxed min-h-[36px]">
                    </div>
                </div>

                <!-- ③ English（English vector English） -->
                <div id="clip-source-section" class="hidden space-y-1.5">
                    <label class="text-[11px] font-bold text-slate-500 uppercase tracking-widest">
                        Clip Extent Source
                    </label>
                    <div class="grid grid-cols-2 gap-2">
                        <label class="clip-source-option">
                            <input type="radio" name="clip-source" value="bounds" checked class="hidden">
                            <div class="clip-source-card border-2 border-slate-200 bg-white
                                        text-slate-600 rounded-xl p-3 text-center cursor-pointer
                                        hover:border-amber-300">
                                <div class="text-lg mb-1">📐</div>
                                <div class="text-[11px] font-bold">Imagery Bounds</div>
                                <div class="text-[9px] opacity-60">Use raster bounds</div>
                            </div>
                        </label>
                        <label class="clip-source-option">
                            <input type="radio" name="clip-source" value="draw" class="hidden">
                            <div class="clip-source-card border-2 border-slate-200 bg-white
                                        text-slate-600 rounded-xl p-3 text-center cursor-pointer
                                        hover:border-amber-300">
                                <div class="text-lg mb-1">✏️</div>
                                <div class="text-[11px] font-bold">Draw Manually</div>
                                <div class="text-[9px] opacity-60">Draw on the map</div>
                            </div>
                        </label>
                    </div>
                </div>

                <!-- ④ English（vector / layer English） -->
                <div id="clip-layer-section" class="hidden space-y-1.5">
                    <label class="text-[11px] font-bold text-slate-500 uppercase tracking-widest">
                        Target Vector Layer (clipped)
                    </label>
                    <select id="clip-vector-layer-select"
                        class="w-full text-xs bg-slate-50 border border-slate-200 rounded-xl
                               px-3 py-2.5 text-slate-700 focus:outline-none
                               focus:ring-2 focus:ring-amber-400 transition-all">
                        <option value="">-- Use current active layer --</option>
                    </select>
                </div>

                <!-- ⑤ English（English layer English） -->
                <div id="clip-knife-section" class="hidden space-y-1.5">
                    <label class="text-[11px] font-bold text-slate-500 uppercase tracking-widest">
                        Clip Layer (provides extent)
                    </label>
                    <select id="clip-knife-layer-select"
                        class="w-full text-xs bg-slate-50 border border-slate-200 rounded-xl
                               px-3 py-2.5 text-slate-700 focus:outline-none
                               focus:ring-2 focus:ring-amber-400 transition-all">
                        <option value="">— Please select a clip layer —</option>
                    </select>
                    <p class="text-[10px] text-slate-400 pl-1">
                        Clip and target layers cannot be the same
                    </p>
                </div>

            </div>

            <!-- English -->
            <div class="px-8 pb-8 pt-2 flex flex-col space-y-3">
                <button id="clip-execute-btn" onclick="RS.executeClip()"
                    class="w-full bg-gradient-to-r from-amber-500 to-orange-500
                           hover:from-amber-600 hover:to-orange-600
                           text-white py-4 rounded-2xl font-bold text-sm
                           shadow-xl shadow-amber-500/20 transition-all active:scale-[0.98]
                           flex items-center justify-center space-x-2">
                    <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2"
                            d="M14.121 14.121L19 19m-7-7l7-7m-7 7l-2.879 2.879
                               M12 12L9.121 9.121m0 0L4 4m5.121 5.121L4 14"/>
                    </svg>
                    <span>Start Clipping</span>
                </button>
                <button onclick="RS.closeClipModal()"
                    class="w-full text-slate-400 text-[10px] font-bold uppercase tracking-widest py-2">
                    Cancel
                </button>
            </div>

        </div>
    </div>

    <style>
        .clip-type-option   input:checked + .clip-type-card,
        .clip-source-option input:checked + .clip-source-card {
            border-color: #f59e0b !important;
            background:   #fffbeb !important;
            color:        #b45309 !important;
        }
        .clip-type-card,
        .clip-source-card {
            transition: all 0.15s ease;
        }
        .clip-type-card:hover,
        .clip-source-card:hover {
            transform:  translateY(-1px);
            box-shadow: 0 4px 12px rgba(0,0,0,0.08);
        }
    </style>
`;