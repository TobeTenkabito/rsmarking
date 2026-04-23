export const  changeModal = `
<div id="change-modal"
     class="hidden fixed inset-0 bg-black/40 backdrop-blur-sm z-[2000] flex items-center justify-center p-4">
  <div class="bg-white rounded-2xl shadow-2xl w-full max-w-lg border border-slate-100 overflow-hidden">

    <!-- 标题栏 -->
    <div class="flex items-center justify-between px-6 py-4 border-b border-slate-100 bg-slate-50/60">
      <div class="flex items-center space-x-3">
        <div class="w-8 h-8 rounded-lg bg-orange-100 flex items-center justify-center text-lg">🔄</div>
        <div>
          <h3 class="text-sm font-bold text-slate-800">变化检测</h3>
          <p class="text-[10px] text-slate-400">Change Detection Analysis</p>
        </div>
      </div>
      <button onclick="RS.closeChangeModal()"
              class="text-slate-400 hover:text-slate-600 transition-colors text-lg leading-none">✕</button>
    </div>

    <!-- 方法选择 Tab -->
    <div class="flex border-b border-slate-100 bg-white px-6 pt-4 space-x-1">
      <button data-method="band-diff"
              onclick="RS.switchChangeMethod('band-diff')"
              class="change-method-tab px-3 py-1.5 text-[11px] font-bold rounded-t-lg border-b-2
                     border-orange-500 text-orange-600 bg-orange-50 transition-all">
        波段差值
      </button>
      <button data-method="band-ratio"
              onclick="RS.switchChangeMethod('band-ratio')"
              class="change-method-tab px-3 py-1.5 text-[11px] font-bold rounded-t-lg border-b-2
                     border-transparent text-slate-400 hover:text-slate-600 transition-all">
        波段比值
      </button>
      <button data-method="index-diff"
              onclick="RS.switchChangeMethod('index-diff')"
              class="change-method-tab px-3 py-1.5 text-[11px] font-bold rounded-t-lg border-b-2
                     border-transparent text-slate-400 hover:text-slate-600 transition-all">
        指数差值
      </button>
    </div>

    <div class="px-6 py-5 space-y-4 max-h-[60vh] overflow-y-auto">

      <!-- ── 公共：T1 / T2 主影像选择 ── -->
      <div id="change-section-main-select" class="grid grid-cols-2 gap-4">
        <div class="space-y-1.5">
          <label class="text-[11px] font-bold text-slate-500 flex items-center space-x-1.5">
            <span class="w-4 h-4 rounded-full bg-blue-100 text-blue-600 text-[9px] font-black
                         flex items-center justify-center flex-shrink-0">T1</span>
            <span>早期影像</span>
          </label>
          <select id="change-t1-select"
                  class="w-full bg-white border border-slate-200 rounded-lg px-3 py-2 text-xs
                         focus:ring-2 focus:ring-orange-400 focus:border-orange-400 transition-all">
            <option value="">— 请选择 —</option>
          </select>
        </div>
        <div class="space-y-1.5">
          <label class="text-[11px] font-bold text-slate-500 flex items-center space-x-1.5">
            <span class="w-4 h-4 rounded-full bg-orange-100 text-orange-600 text-[9px] font-black
                         flex items-center justify-center flex-shrink-0">T2</span>
            <span>晚期影像</span>
          </label>
          <select id="change-t2-select"
                  class="w-full bg-white border border-slate-200 rounded-lg px-3 py-2 text-xs
                         focus:ring-2 focus:ring-orange-400 focus:border-orange-400 transition-all">
            <option value="">— 请选择 —</option>
          </select>
        </div>
      </div>

      <!-- ── 参数区 A：band-diff / band-ratio 共用 ── -->
      <div id="change-params-band" class="space-y-3">
        <div class="grid grid-cols-2 gap-4">
          <div class="space-y-1.5">
            <label class="text-[11px] font-bold text-slate-500">波段编号</label>
            <input id="change-band-input" type="number" min="1" max="20" value="1"
                   class="w-full bg-white border border-slate-200 rounded-lg px-3 py-2 text-xs
                          focus:ring-2 focus:ring-orange-400 focus:border-orange-400 transition-all"/>
          </div>
          <div class="space-y-1.5">
            <label class="text-[11px] font-bold text-slate-500">
              变化阈值
              <span id="change-threshold-hint" class="text-slate-300 font-normal ml-1">（差值绝对值）</span>
            </label>
            <input id="change-threshold-input" type="number" step="0.01" value="0.1"
                   class="w-full bg-white border border-slate-200 rounded-lg px-3 py-2 text-xs
                          focus:ring-2 focus:ring-orange-400 focus:border-orange-400 transition-all"/>
          </div>
        </div>

        <div id="change-threshold-mode-row" class="space-y-1.5">
          <label class="text-[11px] font-bold text-slate-500">阈值判定模式</label>
          <select id="change-threshold-mode"
                  class="w-full bg-white border border-slate-200 rounded-lg px-3 py-2 text-xs
                         focus:ring-2 focus:ring-orange-400 focus:border-orange-400 transition-all">
            <option value="abs">abs — 绝对值超过阈值即为变化</option>
            <option value="positive">positive — 仅检测正向增加</option>
            <option value="negative">negative — 仅检测负向减少</option>
          </select>
        </div>
      </div>

      <!-- ── 参数区 B：index-diff 专用 ── -->
      <div id="change-params-index" class="hidden space-y-4">
        <div class="grid grid-cols-2 gap-4">
          <div class="space-y-1.5">
            <label class="text-[11px] font-bold text-slate-500">指数类型</label>
            <select id="change-index-select"
                    class="w-full bg-white border border-slate-200 rounded-lg px-3 py-2 text-xs
                           focus:ring-2 focus:ring-orange-400 focus:border-orange-400 transition-all">
              <option value="ndvi">NDVI（植被）</option>
              <option value="ndwi">NDWI（水体）</option>
              <option value="ndbi">NDBI（建筑）</option>
              <option value="mndwi">MNDWI（改进水体）</option>
            </select>
          </div>
          <div class="space-y-1.5">
            <label class="text-[11px] font-bold text-slate-500">变化阈值</label>
            <input id="change-index-threshold-input" type="number" step="0.01" value="0.15"
                   class="w-full bg-white border border-slate-200 rounded-lg px-3 py-2 text-xs
                          focus:ring-2 focus:ring-orange-400 focus:border-orange-400 transition-all"/>
          </div>
        </div>

        <div class="space-y-1.5">
          <label class="text-[11px] font-bold text-slate-500">阈值判定模式</label>
          <select id="change-index-threshold-mode"
                  class="w-full bg-white border border-slate-200 rounded-lg px-3 py-2 text-xs
                         focus:ring-2 focus:ring-orange-400 focus:border-orange-400 transition-all">
            <option value="abs">abs — 绝对值超过阈值即为变化</option>
            <option value="positive">positive — 仅检测正向增加（如植被增长）</option>
            <option value="negative">negative — 仅检测负向减少（如植被退化）</option>
          </select>
        </div>

        <div class="p-3 bg-slate-50 rounded-xl border border-slate-100">
          <p class="text-[10px] font-bold text-slate-500 mb-2">波段分配
            <span id="change-index-band-hint" class="text-slate-400 font-normal ml-1">
              NDVI：B1 = Red，B2 = NIR
            </span>
          </p>
          <div class="space-y-2 mb-3">
            <p class="text-[10px] font-bold text-blue-500 flex items-center space-x-1">
              <span class="w-4 h-4 rounded-full bg-blue-100 text-blue-600 text-[9px] font-black
                           flex items-center justify-center">T1</span>
              <span>早期影像波段</span>
            </p>
            <div class="grid grid-cols-2 gap-2">
              <div class="space-y-1">
                <label class="text-[10px] text-slate-400">B1（如 Red）</label>
                <select id="change-t1-b1-select"
                        class="w-full bg-white border border-slate-200 rounded-lg px-2 py-1.5 text-[11px]
                               focus:ring-2 focus:ring-orange-400 focus:border-orange-400 transition-all">
                  <option value="">— 选择 —</option>
                </select>
              </div>
              <div class="space-y-1">
                <label class="text-[10px] text-slate-400">B2（如 NIR）</label>
                <select id="change-t1-b2-select"
                        class="w-full bg-white border border-slate-200 rounded-lg px-2 py-1.5 text-[11px]
                               focus:ring-2 focus:ring-orange-400 focus:border-orange-400 transition-all">
                  <option value="">— 选择 —</option>
                </select>
              </div>
            </div>
          </div>
          <div class="space-y-2">
            <p class="text-[10px] font-bold text-orange-500 flex items-center space-x-1">
              <span class="w-4 h-4 rounded-full bg-orange-100 text-orange-600 text-[9px] font-black
                           flex items-center justify-center">T2</span>
              <span>晚期影像波段</span>
            </p>
            <div class="grid grid-cols-2 gap-2">
              <div class="space-y-1">
                <label class="text-[10px] text-slate-400">B1（如 Red）</label>
                <select id="change-t2-b1-select"
                        class="w-full bg-white border border-slate-200 rounded-lg px-2 py-1.5 text-[11px]
                               focus:ring-2 focus:ring-orange-400 focus:border-orange-400 transition-all">
                  <option value="">— 选择 —</option>
                </select>
              </div>
              <div class="space-y-1">
                <label class="text-[10px] text-slate-400">B2（如 NIR）</label>
                <select id="change-t2-b2-select"
                        class="w-full bg-white border border-slate-200 rounded-lg px-2 py-1.5 text-[11px]
                               focus:ring-2 focus:ring-orange-400 focus:border-orange-400 transition-all">
                  <option value="">— 选择 —</option>
                </select>
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- ── 结果预览区 ── -->
      <div id="change-result-area" class="hidden space-y-2">
        <div class="flex items-center space-x-3 p-3 bg-emerald-50 border border-emerald-200 rounded-xl">
          <svg class="w-4 h-4 text-emerald-500 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7"/>
          </svg>
          <div class="flex-1 min-w-0">
            <p class="text-[11px] font-bold text-emerald-700">检测完成</p>
            <p id="change-stat-text" class="text-[10px] text-emerald-600"></p>
          </div>
        </div>
        <div class="grid grid-cols-2 gap-2">
          <button id="change-load-diff-btn"
                  onclick="RS.loadChangeResult('diff')"
                  class="flex items-center justify-center space-x-1.5 px-3 py-2
                         text-[11px] font-bold text-white bg-orange-500 hover:bg-orange-600
                         rounded-xl shadow-md shadow-orange-100 transition-all active:scale-95">
            <svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2"
                    d="M9 20l-5.447-2.724A1 1 0 013 16.382V5.618a1 1 0 011.447-.894L9 7m0 13l6-3m-6 3V7m6 10l4.553 2.276A1 1 0 0021 18.382V7.618a1 1 0 00-.553-.894L15 4m0 13V4m0 0L9 7"/>
            </svg>
            <span>加载差值图</span>
          </button>
          <button id="change-load-mask-btn"
                  onclick="RS.loadChangeResult('mask')"
                  class="flex items-center justify-center space-x-1.5 px-3 py-2
                         text-[11px] font-bold text-slate-600 bg-white hover:bg-slate-50
                         border border-slate-200 hover:border-slate-300
                         rounded-xl transition-all active:scale-95">
            <svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2"
                    d="M7 21a4 4 0 01-4-4V5a2 2 0 012-2h4a2 2 0 012 2v12a4 4 0 01-4 4zm0 0h12a2 2 0 002-2v-4a2 2 0 00-2-2h-2.343M11 7.343l1.657-1.657a2 2 0 012.828 0l2.829 2.829a2 2 0 010 2.828l-8.486 8.485M7 17h.01"/>
            </svg>
            <span>加载变化掩膜</span>
          </button>
        </div>
      </div>

    </div>

    <!-- 底部操作栏 -->
    <div class="flex items-center justify-between px-6 py-4 border-t border-slate-100 bg-slate-50/60">
      <p id="change-status-text" class="text-[10px] text-slate-400 flex-1 mr-4 truncate">
        选择两期影像后执行分析
      </p>
      <div class="flex items-center space-x-2 flex-shrink-0">
        <button onclick="RS.closeChangeModal()"
                class="px-4 py-2 text-xs font-bold text-slate-500 hover:text-slate-700
                       bg-white border border-slate-200 rounded-xl hover:border-slate-300 transition-all">
          取消
        </button>
        <button id="change-run-btn"
                onclick="RS.runChangeDetection()"
                class="px-5 py-2 text-xs font-bold text-white bg-orange-500 hover:bg-orange-600
                       rounded-xl shadow-lg shadow-orange-200 transition-all active:scale-95
                       disabled:opacity-50 disabled:cursor-not-allowed">
          执行分析
        </button>
      </div>
    </div>

  </div>
</div>
`;