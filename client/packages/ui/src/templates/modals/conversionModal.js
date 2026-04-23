export  const  conversionModal = `
    <div id="conversion-modal" class="hidden fixed inset-0 z-[2000] flex items-center justify-center bg-black/40 backdrop-blur-sm">
  <div class="bg-white rounded-2xl shadow-2xl w-full max-w-md mx-4 overflow-hidden">

    <!-- Header -->
    <div class="flex items-center justify-between px-6 py-4 border-b border-slate-100">
      <h2 class="text-base font-semibold text-slate-800">矢量转栅格</h2>
      <button onclick="RS.closeConversionModal()"
              class="text-slate-400 hover:text-slate-600 transition-colors">✕</button>
    </div>

    <!-- 步骤指示器 -->
    <div class="flex items-center justify-center gap-3 px-6 pt-4">
      <div id="conversion-step-1-dot"
           class="w-6 h-6 rounded-full text-xs font-bold flex items-center justify-center
                  bg-indigo-500 text-white transition-all">1</div>
      <span class="text-xs text-slate-400">选择矢量图层</span>
      <div class="flex-1 h-px bg-slate-200"></div>
      <div id="conversion-step-2-dot"
           class="w-6 h-6 rounded-full text-xs font-bold flex items-center justify-center
                  bg-slate-200 text-slate-400 transition-all">2</div>
      <span class="text-xs text-slate-400">参考栅格 & 命名</span>
    </div>

    <!-- Step 1：矢量图层列表 -->
    <div id="conversion-step-1" class="px-6 py-4 space-y-2 max-h-72 overflow-y-auto">
      <div id="conversion-step-1-list"></div>
    </div>

    <!-- Step 2：参考栅格 + 名称输入 -->
    <div id="conversion-step-2" class="hidden px-6 py-4 space-y-4">
      <div>
        <p class="text-xs font-medium text-slate-500 mb-2">选择参考栅格（决定分辨率与坐标系）</p>
        <div id="conversion-step-2-ref-list" class="space-y-2 max-h-44 overflow-y-auto"></div>
      </div>
      <div>
        <label class="text-xs font-medium text-slate-500 block mb-1">新栅格名称</label>
        <input id="conversion-name-input" type="text"
               oninput="RS.handleConversionNameInput()"
               class="w-full px-3 py-2 text-sm border border-slate-200 rounded-lg
                      focus:outline-none focus:ring-2 focus:ring-indigo-400"
               placeholder="输入生成的栅格名称" />
      </div>
    </div>

    <!-- Footer 按钮 -->
    <div class="flex items-center justify-between px-6 py-4 border-t border-slate-100 bg-slate-50">
      <button id="conversion-back-btn" onclick="RS.handleConversionStepBack()"
              class="hidden text-sm text-slate-500 hover:text-slate-700 transition-colors">← 上一步</button>
      <div class="flex-1"></div>
      <button id="conversion-next-btn" onclick="RS.handleConversionStepNext()"
              disabled
              class="px-4 py-2 text-sm font-medium rounded-lg bg-indigo-500 text-white
                     hover:bg-indigo-600 disabled:opacity-40 disabled:cursor-not-allowed transition-all">
        下一步 →
      </button>
      <button id="conversion-confirm-btn" onclick="RS.handleConversionExecute()"
              disabled
              class="hidden px-4 py-2 text-sm font-medium rounded-lg bg-emerald-500 text-white
                     hover:bg-emerald-600 disabled:opacity-40 disabled:cursor-not-allowed transition-all">
        开始转换
      </button>
    </div>

  </div>
</div>
`;