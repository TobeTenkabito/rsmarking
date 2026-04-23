export const extractModal = `
<div id="extract-modal" class="hidden fixed inset-0 bg-slate-900/60 backdrop-blur-sm z-[2000] flex items-center justify-center p-4">
    <div class="bg-white w-full max-w-md rounded-2xl shadow-2xl overflow-hidden">

        <!-- Header -->
        <div class="p-5 border-b border-slate-100 flex justify-between items-center bg-slate-50/50">
            <div class="flex items-center space-x-3">
                <h3 class="font-bold text-slate-800 uppercase text-xs tracking-widest">波段提取</h3>
                <!-- 步驟指示器 -->
                <div class="flex items-center space-x-1">
                    <div id="extract-step-1-dot" class="w-5 h-5 rounded-full bg-emerald-500 text-white text-[9px] font-black flex items-center justify-center">1</div>
                    <div class="w-4 h-px bg-slate-200"></div>
                    <div id="extract-step-2-dot" class="w-5 h-5 rounded-full bg-slate-200 text-slate-400 text-[9px] font-black flex items-center justify-center">2</div>
                </div>
            </div>
            <button onclick="RS.closeExtractModal()" class="text-slate-400 hover:text-slate-600 transition-colors">✕</button>
        </div>

        <!-- Step 1：選擇源文件 -->
        <div id="extract-step-1" class="p-5 max-h-[400px] overflow-y-auto bg-white">
            <p class="text-[10px] text-slate-400 mb-3 font-medium">选择需要提取波段的影像</p>
            <div id="extract-source-list"></div>
        </div>

        <!-- Step 2：選擇波段（初始隱藏） -->
        <div id="extract-step-2" class="hidden p-5 max-h-[400px] overflow-y-auto bg-white">
            <p class="text-[10px] text-slate-400 mb-3 font-medium">选择需要提取的波段（可多选）</p>
            <div id="extract-selection-list"></div>
        </div>

        <!-- Footer -->
        <div class="p-5 bg-slate-50 border-t border-slate-100 flex justify-between items-center">
            <!-- 左側：上一步 / 占位 -->
            <div>
                <button id="extract-back-btn" onclick="RS.extractStepBack()" class="hidden px-4 py-2 text-xs font-bold text-slate-500 hover:text-slate-700 transition-colors">← 上一步</button>
                <div id="extract-back-placeholder" class="w-16"></div>
            </div>
            <!-- 右側：取消 / 下一步 / 確認 -->
            <div class="flex items-center space-x-3">
                <button onclick="RS.closeExtractModal()" class="px-4 py-2 text-xs font-bold text-slate-400">取消</button>
                <button id="extract-next-btn" onclick="RS.extractStepNext()" disabled class="bg-emerald-600 text-white px-6 py-2 rounded-lg text-xs font-bold shadow-lg disabled:opacity-50">下一步 →</button>
                <button id="confirm-extract-btn" onclick="RS.executeExtract()" disabled class="hidden bg-emerald-600 text-white px-6 py-2 rounded-lg text-xs font-bold shadow-lg disabled:opacity-50">确认提取</button>
            </div>
        </div>

    </div>
</div>
`;