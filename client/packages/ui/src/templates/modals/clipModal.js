export const clipModal = `
    <div id="clip-modal"
         class="hidden fixed inset-0 bg-slate-900/60 backdrop-blur-sm z-[2000]
                flex items-center justify-center p-4">
        <div class="bg-white w-full max-w-sm rounded-3xl shadow-2xl relative overflow-hidden flex flex-col">

            <!-- 顶部色条 -->
            <div class="absolute top-0 left-0 w-full h-1.5
                        bg-gradient-to-r from-amber-400 to-orange-500"></div>

            <!-- 标题 -->
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
                    <h2 class="text-base font-black text-slate-800">空间裁剪</h2>
                    <p class="text-[10px] text-slate-400">Spatial Clip</p>
                </div>
            </div>

            <!-- 内容区 -->
            <div class="px-8 pb-4 space-y-4">

                <!-- ① 裁剪类型：三选一 -->
                <div class="space-y-1.5">
                    <label class="text-[11px] font-bold text-slate-500 uppercase tracking-widest">
                        裁剪类型
                    </label>
                    <div class="grid grid-cols-3 gap-2">

                        <label class="clip-type-option">
                            <input type="radio" name="clip-type" value="raster" checked class="hidden">
                            <div class="clip-type-card border-2 border-slate-200 bg-white 
                            text-slate-600 rounded-xl p-3 text-center cursor-pointer 
                            hover:border-amber-300">
                                <div class="text-xl mb-1">🛰️</div>
                                <div class="text-[11px] font-bold">裁栅格</div>
                                <div class="text-[9px] opacity-60">手绘裁影像</div>
                            </div>
                        </label>

                        <label class="clip-type-option">
                            <input type="radio" name="clip-type" value="vector" class="hidden">
                            <div class="clip-type-card border-2 border-slate-200 bg-white
                            text-slate-600 rounded-xl p-3 text-center cursor-pointer
                            hover:border-amber-300">
                                <div class="text-xl mb-1">🔷</div>
                                <div class="text-[11px] font-bold">裁矢量</div>
                                <div class="text-[9px] opacity-60">范围过滤要素</div>
                            </div>
                        </label>

                        <label class="clip-type-option">
                            <input type="radio" name="clip-type" value="layer" class="hidden">
                            <div class="clip-type-card border-2 border-slate-200 bg-white
                            text-slate-600 rounded-xl p-3 text-center cursor-pointer
                            hover:border-amber-300">
                                <div class="text-xl mb-1">✂️</div>
                                <div class="text-[11px] font-bold">图层互裁</div>
                                <div class="text-[9px] opacity-60">图层裁图层</div>
                            </div>
                        </label>

                    </div>
                </div>

                <!-- ② 当前激活栅格信息（raster / vector 模式显示，layer 模式隐藏） -->
                <div id="clip-raster-info-section" class="space-y-1">
                    <label class="text-[11px] font-bold text-slate-500 uppercase tracking-widest">
                        当前激活影像
                    </label>
                    <div id="clip-raster-info"
                         class="text-[11px] text-slate-500 bg-slate-50 border border-slate-100
                                rounded-xl px-3 py-2.5 leading-relaxed min-h-[36px]">
                    </div>
                </div>

                <!-- ③ 裁剪范围来源（仅 vector 模式显示） -->
                <div id="clip-source-section" class="hidden space-y-1.5">
                    <label class="text-[11px] font-bold text-slate-500 uppercase tracking-widest">
                        裁剪范围来源
                    </label>
                    <div class="grid grid-cols-2 gap-2">
                        <label class="clip-source-option">
                            <input type="radio" name="clip-source" value="bounds" checked class="hidden">
                            <div class="clip-source-card border-2 border-slate-200 bg-white
                                        text-slate-600 rounded-xl p-3 text-center cursor-pointer
                                        hover:border-amber-300">
                                <div class="text-lg mb-1">📐</div>
                                <div class="text-[11px] font-bold">影像范围</div>
                                <div class="text-[9px] opacity-60">用栅格 bounds</div>
                            </div>
                        </label>
                        <label class="clip-source-option">
                            <input type="radio" name="clip-source" value="draw" class="hidden">
                            <div class="clip-source-card border-2 border-slate-200 bg-white
                                        text-slate-600 rounded-xl p-3 text-center cursor-pointer
                                        hover:border-amber-300">
                                <div class="text-lg mb-1">✏️</div>
                                <div class="text-[11px] font-bold">手动绘制</div>
                                <div class="text-[9px] opacity-60">在地图上绘制</div>
                            </div>
                        </label>
                    </div>
                </div>

                <!-- ④ 目标图层（vector / layer 模式显示） -->
                <div id="clip-layer-section" class="hidden space-y-1.5">
                    <label class="text-[11px] font-bold text-slate-500 uppercase tracking-widest">
                        目标矢量图层（被裁剪）
                    </label>
                    <select id="clip-vector-layer-select"
                        class="w-full text-xs bg-slate-50 border border-slate-200 rounded-xl
                               px-3 py-2.5 text-slate-700 focus:outline-none
                               focus:ring-2 focus:ring-amber-400 transition-all">
                        <option value="">— 使用当前激活图层 —</option>
                    </select>
                </div>

                <!-- ⑤ 裁剪刀图层（仅 layer 模式显示） -->
                <div id="clip-knife-section" class="hidden space-y-1.5">
                    <label class="text-[11px] font-bold text-slate-500 uppercase tracking-widest">
                        裁剪刀图层（提供范围）
                    </label>
                    <select id="clip-knife-layer-select"
                        class="w-full text-xs bg-slate-50 border border-slate-200 rounded-xl
                               px-3 py-2.5 text-slate-700 focus:outline-none
                               focus:ring-2 focus:ring-amber-400 transition-all">
                        <option value="">— 请选择裁剪刀图层 —</option>
                    </select>
                    <p class="text-[10px] text-slate-400 pl-1">
                        ⚠ 裁剪刀图层与目标图层不能相同
                    </p>
                </div>

            </div>

            <!-- 底部按钮 -->
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
                    <span>开始裁剪</span>
                </button>
                <button onclick="RS.closeClipModal()"
                    class="w-full text-slate-400 text-[10px] font-bold uppercase tracking-widest py-2">
                    取消
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