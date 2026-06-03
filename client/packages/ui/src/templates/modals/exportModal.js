export const exportModal = `
  <div id="export-modal" class="hidden fixed inset-0 bg-slate-900/60 backdrop-blur-sm z-[2000] flex items-center justify-center p-4">
      <div class="bg-white w-full max-w-md rounded-3xl shadow-2xl relative overflow-hidden flex flex-col max-h-[90vh]">
          <!-- Top color bar -->
          <div class="absolute top-0 left-0 w-full h-1.5 bg-gradient-to-r from-teal-500 to-cyan-500 z-10"></div>

          <!-- Title（English，English） -->
          <div class="flex items-center space-x-3 px-8 pt-8 pb-4 flex-shrink-0">
              <div class="p-2 bg-teal-50 rounded-xl">
                  <svg class="w-5 h-5 text-teal-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2"
                          d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4"/>
                  </svg>
              </div>
              <div>
                  <h2 class="text-base font-black text-slate-800">Export Current View</h2>
                  <p class="text-[10px] text-slate-400">Export Map View</p>
              </div>
          </div>

          <!-- scrollableEnglish -->
          <div class="export-scroll overflow-y-auto flex-1 px-8 space-y-5 pb-2">

              <!-- Export Format -->
              <div class="space-y-2">
                  <label class="text-[11px] font-bold text-slate-500 uppercase tracking-widest">Export Format</label>
                  <div class="grid grid-cols-2 sm:grid-cols-4 gap-2">
                      <label class="export-format-option">
                          <input type="radio" name="export-format" value="png" checked class="hidden">
                          <div class="format-card border-2 border-teal-500 bg-teal-50 text-teal-700 rounded-xl p-3 text-center cursor-pointer transition-all">
                              <div class="text-xl mb-1">🖼️</div>
                              <div class="text-[11px] font-bold">PNG</div>
                              <div class="text-[9px] opacity-60">Lossless transparent</div>
                          </div>
                      </label>
                      <label class="export-format-option">
                          <input type="radio" name="export-format" value="jpeg" class="hidden">
                          <div class="format-card border-2 border-slate-200 bg-white text-slate-600 rounded-xl p-3 text-center cursor-pointer transition-all hover:border-teal-300">
                              <div class="text-xl mb-1">📷</div>
                              <div class="text-[11px] font-bold">JPEG</div>
                              <div class="text-[9px] opacity-60">Smaller file</div>
                          </div>
                      </label>
                      <label class="export-format-option">
                          <input type="radio" name="export-format" value="svg" class="hidden">
                          <div class="format-card border-2 border-slate-200 bg-white text-slate-600 rounded-xl p-3 text-center cursor-pointer transition-all hover:border-teal-300">
                              <div class="text-xl mb-1">📐</div>
                              <div class="text-[11px] font-bold">SVG</div>
                              <div class="text-[9px] opacity-60">Vector graphics</div>
                          </div>
                      </label>
                      <label class="export-format-option">
                          <input type="radio" name="export-format" value="file" class="hidden">
                          <div class="format-card border-2 border-slate-200 bg-white text-slate-600 rounded-xl p-3 text-center cursor-pointer transition-all hover:border-teal-300">
                              <div class="text-xl mb-1">GIS</div>
                              <div class="text-[11px] font-bold">FILE</div>
                              <div class="text-[9px] opacity-60">Attribute table</div>
                          </div>
                      </label>
                  </div>
              </div>

              <!-- Export ContentEnglish -->
              <div class="space-y-2">
                  <label class="text-[11px] font-bold text-slate-500 uppercase tracking-widest">Export Content</label>
                  <div class="bg-slate-50 rounded-2xl p-4 space-y-3 border border-slate-100">

                      <label class="flex items-center justify-between cursor-pointer group" data-export-image-option>
                          <div class="flex items-center space-x-3">
                              <div class="w-7 h-7 rounded-lg bg-blue-100 flex items-center justify-center text-sm">🗺️</div>
                              <div>
                                  <p class="text-xs font-bold text-slate-700">Base Map</p>
                                  <p class="text-[9px] text-slate-400">OpenStreetMap tile layer</p>
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
                                  <p class="text-xs font-bold text-slate-700">Vector annotation layers</p>
                                  <p class="text-[9px] text-slate-400">Polygons / rectangles / markers</p>
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
                                  <p class="text-xs font-bold text-slate-700">Raster imagery layers</p>
                                  <p class="text-[9px] text-slate-400">Loaded TIFF imagery</p>
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

                      <label class="flex items-center justify-between cursor-pointer group" data-export-image-option>
                          <div class="flex items-center space-x-3">
                              <div class="w-7 h-7 rounded-lg bg-amber-100 flex items-center justify-center text-sm">🧭</div>
                              <div>
                                  <p class="text-xs font-bold text-slate-700">Map decoration elements</p>
                                  <p class="text-[9px] text-slate-400">Scale bar / north arrow / legend</p>
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
                      
<!-- Graticule -->
<label class="flex items-center justify-between cursor-pointer group" data-export-image-option>
    <div class="flex items-center space-x-3">
        <div class="w-7 h-7 rounded-lg bg-teal-100 flex items-center justify-center text-sm">🌐</div>
        <div>
            <p class="text-xs font-bold text-slate-700">Graticule</p>
            <p class="text-[9px] text-slate-400">Longitude/latitude grid overlay</p>
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

<!-- Line style selector; follows graticule visibility -->
<div id="graticule-style-group" class="hidden pl-10 pb-1" data-export-image-option>
    <div class="flex items-center space-x-4">
        <label class="flex items-center space-x-1.5 cursor-pointer">
            <input type="radio" name="graticule-style" value="solid" checked class="accent-teal-500">
            <span class="text-[11px] text-slate-600 font-medium">Solid</span>
        </label>
        <label class="flex items-center space-x-1.5 cursor-pointer">
            <input type="radio" name="graticule-style" value="dashed" class="accent-teal-500">
            <span class="text-[11px] text-slate-600 font-medium">Dashed</span>
        </label>
    </div>
</div>

<!-- Border coordinate labels; independent toggle -->
<label class="flex items-center justify-between cursor-pointer group" data-export-image-option>
    <div class="flex items-center space-x-3">
        <div class="w-7 h-7 rounded-lg bg-sky-100 flex items-center justify-center text-sm">📏</div>
        <div>
            <p class="text-xs font-bold text-slate-700">Border coordinate labels</p>
            <p class="text-[9px] text-slate-400">Label coordinate ticks around image edges</p>
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

              <!-- English / English -->
              <div id="export-image-settings" class="grid grid-cols-2 gap-3">
                  <div class="space-y-1.5">
                      <label class="text-[11px] font-bold text-slate-500 uppercase tracking-widest">Output Resolution</label>
                      <select id="export-dpi"
                          class="w-full text-xs bg-slate-50 border border-slate-200 rounded-xl px-3 py-2.5 text-slate-700 focus:outline-none focus:ring-2 focus:ring-teal-400">
                          <option value="1">Standard (1x)</option>
                          <option value="2" selected>High (2x)</option>
                          <option value="3">Ultra (3x)</option>
                          <option value="4">Maximum (4x)</option>
                      </select>
                  </div>
                  <div class="space-y-1.5" id="jpeg-quality-group">
                      <label class="text-[11px] font-bold text-slate-500 uppercase tracking-widest">
                          JPEG Quality <span id="jpeg-quality-val" class="text-teal-500">92%</span>
                      </label>
                      <input type="range" id="export-jpeg-quality" min="50" max="100" value="92"
                          oninput="document.getElementById('jpeg-quality-val').textContent = this.value + '%'"
                          class="w-full accent-teal-500">
                  </div>
              </div>

              <!-- File Name -->
              <div class="space-y-1.5">
                  <label class="text-[11px] font-bold text-slate-500 uppercase tracking-widest">File Name</label>
                  <div class="flex items-center space-x-2">
                      <input type="text" id="export-filename" value="RSMarking_Export"
                          class="flex-1 text-xs bg-slate-50 border border-slate-200 rounded-xl px-3 py-2.5 text-slate-700 focus:outline-none focus:ring-2 focus:ring-teal-400">
                      <span id="export-filename-ext" class="text-xs text-slate-400 font-mono">.png</span>
                  </div>
              </div>

              <!-- English -->
              <div class="space-y-2">
                  <div class="flex items-center justify-between">
                      <label class="text-[11px] font-bold text-slate-500 uppercase tracking-widest">Live Preview</label>
                      <button id="export-preview-refresh-btn" onclick="RS.refreshExportPreview()"
                          class="text-[10px] text-teal-600 hover:underline font-bold">Refresh Preview</button>
                  </div>
                  <div id="export-preview-container"
                      class="w-full h-36 bg-slate-100 rounded-2xl border-2 border-dashed border-slate-200 flex items-center justify-center overflow-hidden relative">
                      <div id="export-preview-placeholder" class="text-center">
                          <div class="text-2xl mb-1">🗺️</div>
                          <p class="text-[10px] text-slate-400">Click "Refresh Preview" to generate a thumbnail</p>
                      </div>
                      <canvas id="export-preview-canvas" class="hidden w-full h-full object-contain rounded-2xl"></canvas>
                      <div id="export-preview-loader" class="hidden absolute inset-0 bg-white/80 flex items-center justify-center">
                          <div class="w-5 h-5 border-2 border-teal-500 border-t-transparent rounded-full animate-spin"></div>
                      </div>
                  </div>
              </div>

          </div>
          <!-- English -->

          <!-- English（English，English） -->
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
                  <span id="export-execute-label">Export Image</span>
              </button>
              <button onclick="RS.closeExportModal()"
                  class="w-full text-slate-400 text-[10px] font-bold uppercase tracking-widest py-2">
                  Cancel
              </button>
          </div>

      </div>
  </div>

  <!-- English -->
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
      /* English */
      .export-scroll::-webkit-scrollbar { width: 4px; }
      .export-scroll::-webkit-scrollbar-track { background: transparent; }
      .export-scroll::-webkit-scrollbar-thumb { background: #cbd5e1; border-radius: 9999px; }
      .export-scroll::-webkit-scrollbar-thumb:hover { background: #94a3b8; }
  </style>
`;
