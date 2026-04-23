export const exportModal = `
  <div id="export-modal" class="hidden fixed inset-0 bg-slate-900/60 backdrop-blur-sm z-[2000] flex items-center justify-center p-4">
      <div class="bg-white w-full max-w-md rounded-3xl shadow-2xl relative overflow-hidden flex flex-col max-h-[90vh]">
          <!-- 顶部色条 -->
          <div class="absolute top-0 left-0 w-full h-1.5 bg-gradient-to-r from-teal-500 to-cyan-500 z-10"></div>

          <!-- 标题（固定，不参与滚动） -->
          <div class="flex items-center space-x-3 px-8 pt-8 pb-4 flex-shrink-0">
              <div class="p-2 bg-teal-50 rounded-xl">
                  <svg class="w-5 h-5 text-teal-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2"
                          d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4"/>
                  </svg>
              </div>
              <div>
                  <h2 class="text-base font-black text-slate-800">导出当前视图</h2>
                  <p class="text-[10px] text-slate-400">Export Map View</p>
              </div>
          </div>

          <!-- 可滚动内容区 -->
          <div class="export-scroll overflow-y-auto flex-1 px-8 space-y-5 pb-2">

              <!-- 导出格式 -->
              <div class="space-y-2">
                  <label class="text-[11px] font-bold text-slate-500 uppercase tracking-widest">导出格式</label>
                  <div class="grid grid-cols-3 gap-2">
                      <label class="export-format-option">
                          <input type="radio" name="export-format" value="png" checked class="hidden">
                          <div class="format-card border-2 border-teal-500 bg-teal-50 text-teal-700 rounded-xl p-3 text-center cursor-pointer transition-all">
                              <div class="text-xl mb-1">🖼️</div>
                              <div class="text-[11px] font-bold">PNG</div>
                              <div class="text-[9px] opacity-60">无损透明</div>
                          </div>
                      </label>
                      <label class="export-format-option">
                          <input type="radio" name="export-format" value="jpeg" class="hidden">
                          <div class="format-card border-2 border-slate-200 bg-white text-slate-600 rounded-xl p-3 text-center cursor-pointer transition-all hover:border-teal-300">
                              <div class="text-xl mb-1">📷</div>
                              <div class="text-[11px] font-bold">JPEG</div>
                              <div class="text-[9px] opacity-60">体积更小</div>
                          </div>
                      </label>
                      <label class="export-format-option">
                          <input type="radio" name="export-format" value="svg" class="hidden">
                          <div class="format-card border-2 border-slate-200 bg-white text-slate-600 rounded-xl p-3 text-center cursor-pointer transition-all hover:border-teal-300">
                              <div class="text-xl mb-1">📐</div>
                              <div class="text-[11px] font-bold">SVG</div>
                              <div class="text-[9px] opacity-60">矢量图形</div>
                          </div>
                      </label>
                  </div>
              </div>

              <!-- 导出内容选项 -->
              <div class="space-y-2">
                  <label class="text-[11px] font-bold text-slate-500 uppercase tracking-widest">导出内容</label>
                  <div class="bg-slate-50 rounded-2xl p-4 space-y-3 border border-slate-100">

                      <label class="flex items-center justify-between cursor-pointer group">
                          <div class="flex items-center space-x-3">
                              <div class="w-7 h-7 rounded-lg bg-blue-100 flex items-center justify-center text-sm">🗺️</div>
                              <div>
                                  <p class="text-xs font-bold text-slate-700">地图底图</p>
                                  <p class="text-[9px] text-slate-400">OpenStreetMap 瓦片图层</p>
                              </div>
                          </div>
                          <div class="relative">
                              <input type="checkbox" id="export-include-basemap" checked
                                  class="sr-only peer">
                              <div class="w-9 h-5 bg-slate-200 peer-checked:bg-teal-500 rounded-full transition-colors cursor-pointer
                                          after:content-[''] after:absolute after:top-0.5 after:left-0.5
                                          after:w-4 after:h-4 after:bg-white after:rounded-full after:shadow
                                          after:transition-transform peer-checked:after:translate-x-4"></div>
                          </div>
                      </label>

                      <label class="flex items-center justify-between cursor-pointer group">
                          <div class="flex items-center space-x-3">
                              <div class="w-7 h-7 rounded-lg bg-indigo-100 flex items-center justify-center text-sm">🔷</div>
                              <div>
                                  <p class="text-xs font-bold text-slate-700">矢量标注图层</p>
                                  <p class="text-[9px] text-slate-400">多边形 / 矩形 / 标记点</p>
                              </div>
                          </div>
                          <div class="relative">
                              <input type="checkbox" id="export-include-vectors" checked
                                  class="sr-only peer">
                              <div class="w-9 h-5 bg-slate-200 peer-checked:bg-teal-500 rounded-full transition-colors cursor-pointer
                                          after:content-[''] after:absolute after:top-0.5 after:left-0.5
                                          after:w-4 after:h-4 after:bg-white after:rounded-full after:shadow
                                          after:transition-transform peer-checked:after:translate-x-4"></div>
                          </div>
                      </label>

                      <label class="flex items-center justify-between cursor-pointer group">
                          <div class="flex items-center space-x-3">
                              <div class="w-7 h-7 rounded-lg bg-emerald-100 flex items-center justify-center text-sm">🛰️</div>
                              <div>
                                  <p class="text-xs font-bold text-slate-700">栅格影像图层</p>
                                  <p class="text-[9px] text-slate-400">已加载的 TIFF 影像</p>
                              </div>
                          </div>
                          <div class="relative">
                              <input type="checkbox" id="export-include-rasters" checked
                                  class="sr-only peer">
                              <div class="w-9 h-5 bg-slate-200 peer-checked:bg-teal-500 rounded-full transition-colors cursor-pointer
                                          after:content-[''] after:absolute after:top-0.5 after:left-0.5
                                          after:w-4 after:h-4 after:bg-white after:rounded-full after:shadow
                                          after:transition-transform peer-checked:after:translate-x-4"></div>
                          </div>
                      </label>

                      <label class="flex items-center justify-between cursor-pointer group">
                          <div class="flex items-center space-x-3">
                              <div class="w-7 h-7 rounded-lg bg-amber-100 flex items-center justify-center text-sm">🧭</div>
                              <div>
                                  <p class="text-xs font-bold text-slate-700">地图装饰元素</p>
                                  <p class="text-[9px] text-slate-400">比例尺 / 指北针 / 图例</p>
                              </div>
                          </div>
                          <div class="relative">
                              <input type="checkbox" id="export-include-decorations" checked
                                  class="sr-only peer">
                              <div class="w-9 h-5 bg-slate-200 peer-checked:bg-teal-500 rounded-full transition-colors cursor-pointer
                                          after:content-[''] after:absolute after:top-0.5 after:left-0.5
                                          after:w-4 after:h-4 after:bg-white after:rounded-full after:shadow
                                          after:transition-transform peer-checked:after:translate-x-4"></div>
                          </div>
                      </label>
                      
<!-- 经纬网格线 -->
<label class="flex items-center justify-between cursor-pointer group">
    <div class="flex items-center space-x-3">
        <div class="w-7 h-7 rounded-lg bg-teal-100 flex items-center justify-center text-sm">🌐</div>
        <div>
            <p class="text-xs font-bold text-slate-700">经纬网格线</p>
            <p class="text-[9px] text-slate-400">叠加在地图上的经纬网</p>
        </div>
    </div>
    <div class="relative">
        <input type="checkbox" id="export-include-graticule" class="sr-only peer">
        <div class="w-9 h-5 bg-slate-200 peer-checked:bg-teal-500 rounded-full transition-colors cursor-pointer
                    after:content-[''] after:absolute after:top-0.5 after:left-0.5
                    after:w-4 after:h-4 after:bg-white after:rounded-full after:shadow
                    after:transition-transform peer-checked:after:translate-x-4"></div>
    </div>
</label>

<!-- 线型选择（跟随经纬网显隐） -->
<div id="graticule-style-group" class="hidden pl-10 pb-1">
    <div class="flex items-center space-x-4">
        <label class="flex items-center space-x-1.5 cursor-pointer">
            <input type="radio" name="graticule-style" value="solid" checked class="accent-teal-500">
            <span class="text-[11px] text-slate-600 font-medium">实线</span>
        </label>
        <label class="flex items-center space-x-1.5 cursor-pointer">
            <input type="radio" name="graticule-style" value="dashed" class="accent-teal-500">
            <span class="text-[11px] text-slate-600 font-medium">虚线</span>
        </label>
    </div>
</div>

<!-- 外框经纬度标注（独立开关） -->
<label class="flex items-center justify-between cursor-pointer group">
    <div class="flex items-center space-x-3">
        <div class="w-7 h-7 rounded-lg bg-sky-100 flex items-center justify-center text-sm">📏</div>
        <div>
            <p class="text-xs font-bold text-slate-700">外框经纬度标注</p>
            <p class="text-[9px] text-slate-400">在图像边缘标注经纬度刻度</p>
        </div>
    </div>
    <div class="relative">
        <input type="checkbox" id="export-include-frame-labels" class="sr-only peer">
        <div class="w-9 h-5 bg-slate-200 peer-checked:bg-teal-500 rounded-full transition-colors cursor-pointer
                    after:content-[''] after:absolute after:top-0.5 after:left-0.5
                    after:w-4 after:h-4 after:bg-white after:rounded-full after:shadow
                    after:transition-transform peer-checked:after:translate-x-4"></div>
    </div>
</label>


                  </div>
              </div>

              <!-- 分辨率 / 质量 -->
              <div class="grid grid-cols-2 gap-3">
                  <div class="space-y-1.5">
                      <label class="text-[11px] font-bold text-slate-500 uppercase tracking-widest">输出分辨率</label>
                      <select id="export-dpi"
                          class="w-full text-xs bg-slate-50 border border-slate-200 rounded-xl px-3 py-2.5 text-slate-700 focus:outline-none focus:ring-2 focus:ring-teal-400">
                          <option value="1">标准 (1x)</option>
                          <option value="2" selected>高清 (2x)</option>
                          <option value="3">超清 (3x)</option>
                          <option value="4">极清 (4x)</option>
                      </select>
                  </div>
                  <div class="space-y-1.5" id="jpeg-quality-group">
                      <label class="text-[11px] font-bold text-slate-500 uppercase tracking-widest">
                          JPEG 质量 <span id="jpeg-quality-val" class="text-teal-500">92%</span>
                      </label>
                      <input type="range" id="export-jpeg-quality" min="50" max="100" value="92"
                          oninput="document.getElementById('jpeg-quality-val').textContent = this.value + '%'"
                          class="w-full accent-teal-500">
                  </div>
              </div>

              <!-- 文件名 -->
              <div class="space-y-1.5">
                  <label class="text-[11px] font-bold text-slate-500 uppercase tracking-widest">文件名</label>
                  <div class="flex items-center space-x-2">
                      <input type="text" id="export-filename" value="RSMarking_Export"
                          class="flex-1 text-xs bg-slate-50 border border-slate-200 rounded-xl px-3 py-2.5 text-slate-700 focus:outline-none focus:ring-2 focus:ring-teal-400">
                      <span id="export-filename-ext" class="text-xs text-slate-400 font-mono">.png</span>
                  </div>
              </div>

              <!-- 预览缩略图 -->
              <div class="space-y-2">
                  <div class="flex items-center justify-between">
                      <label class="text-[11px] font-bold text-slate-500 uppercase tracking-widest">实时预览</label>
                      <button onclick="RS.refreshExportPreview()"
                          class="text-[10px] text-teal-600 hover:underline font-bold">刷新预览</button>
                  </div>
                  <div id="export-preview-container"
                      class="w-full h-36 bg-slate-100 rounded-2xl border-2 border-dashed border-slate-200 flex items-center justify-center overflow-hidden relative">
                      <div id="export-preview-placeholder" class="text-center">
                          <div class="text-2xl mb-1">🗺️</div>
                          <p class="text-[10px] text-slate-400">点击"刷新预览"生成缩略图</p>
                      </div>
                      <canvas id="export-preview-canvas" class="hidden w-full h-full object-contain rounded-2xl"></canvas>
                      <div id="export-preview-loader" class="hidden absolute inset-0 bg-white/80 flex items-center justify-center">
                          <div class="w-5 h-5 border-2 border-teal-500 border-t-transparent rounded-full animate-spin"></div>
                      </div>
                  </div>
              </div>

          </div>
          <!-- 滚动区结束 -->

          <!-- 底部按钮（固定，不参与滚动） -->
          <div class="px-8 pt-4 pb-6 flex flex-col space-y-3 flex-shrink-0 border-t border-slate-100">
              <button id="export-execute-btn" onclick="RS.executeExport()"
                  class="w-full bg-gradient-to-r from-teal-600 to-cyan-600 hover:from-teal-700 hover:to-cyan-700
                         text-white py-4 rounded-2xl font-bold text-sm shadow-xl shadow-teal-500/20
                         transition-all active:scale-[0.98] flex items-center justify-center space-x-2">
                  <svg id="export-spinner" class="hidden animate-spin w-4 h-4 text-white" fill="none" viewBox="0 0 24 24">
                      <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"/>
                      <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8H4z"/>
                  </svg>
                  <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2"
                          d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4"/>
                  </svg>
                  <span>导出图像</span>
              </button>
              <button onclick="RS.closeExportModal()"
                  class="w-full text-slate-400 text-[10px] font-bold uppercase tracking-widest py-2">
                  取消
              </button>
          </div>

      </div>
  </div>

  <!-- 格式选择联动样式 -->
  <style>
      .export-format-option input:checked + .format-card {
          border-color: #0d9488 !important;
          background: #f0fdfa !important;
          color: #0f766e !important;
      }
      .export-format-option .format-card {
          transition: all 0.15s ease;
      }
      .export-format-option .format-card:hover {
          transform: translateY(-1px);
          box-shadow: 0 4px 12px rgba(0,0,0,0.08);
      }
      /* 滚动条美化 */
      .export-scroll::-webkit-scrollbar { width: 4px; }
      .export-scroll::-webkit-scrollbar-track { background: transparent; }
      .export-scroll::-webkit-scrollbar-thumb { background: #cbd5e1; border-radius: 9999px; }
      .export-scroll::-webkit-scrollbar-thumb:hover { background: #94a3b8; }
  </style>
`;