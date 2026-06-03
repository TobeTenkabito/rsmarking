export  const  conversionModal = `
    <div id="conversion-modal" class="hidden fixed inset-0 z-[2000] flex items-center justify-center bg-black/40 backdrop-blur-sm">
  <div class="bg-white rounded-2xl shadow-2xl w-full max-w-md mx-4 overflow-hidden">

    <!-- Header -->
    <div class="flex items-center justify-between px-6 py-4 border-b border-slate-100">
      <h2 class="text-base font-semibold text-slate-800">Vector to Raster</h2>
      <button onclick="RS.closeConversionModal()"
              class="text-slate-400 hover:text-slate-600 transition-colors">✕</button>
    </div>

    <!-- English -->
    <div class="flex items-center justify-center gap-3 px-6 pt-4">
      <div id="conversion-step-1-dot"
           class="w-6 h-6 rounded-full text-xs font-bold flex items-center justify-center
                  bg-indigo-500 text-white transition-all">1</div>
      <span class="text-xs text-slate-400">Select Vector Layer</span>
      <div class="flex-1 h-px bg-slate-200"></div>
      <div id="conversion-step-2-dot"
           class="w-6 h-6 rounded-full text-xs font-bold flex items-center justify-center
                  bg-slate-200 text-slate-400 transition-all">2</div>
      <span class="text-xs text-slate-400">Reference Raster & Naming</span>
    </div>

    <!-- Step 1：Vector LayerEnglish -->
    <div id="conversion-step-1" class="px-6 py-4 space-y-2 max-h-72 overflow-y-auto">
      <div id="conversion-step-1-list"></div>
    </div>

    <!-- Step 2：English + English -->
    <div id="conversion-step-2" class="hidden px-6 py-4 space-y-4">
      <div>
        <p class="text-xs font-medium text-slate-500 mb-2">Select a reference raster; it sets resolution and CRS</p>
        <div id="conversion-step-2-ref-list" class="space-y-2 max-h-44 overflow-y-auto"></div>
      </div>
      <div>
        <label class="text-xs font-medium text-slate-500 block mb-1">New Raster Name</label>
        <input id="conversion-name-input" type="text"
               oninput="RS.handleConversionNameInput()"
               class="w-full px-3 py-2 text-sm border border-slate-200 rounded-lg
                      focus:outline-none focus:ring-2 focus:ring-indigo-400"
               placeholder="Enter generated raster name" />
      </div>
    </div>

    <!-- Footer English -->
    <div class="flex items-center justify-between px-6 py-4 border-t border-slate-100 bg-slate-50">
      <button id="conversion-back-btn" onclick="RS.handleConversionStepBack()"
              class="hidden text-sm text-slate-500 hover:text-slate-700 transition-colors">← Previous</button>
      <div class="flex-1"></div>
      <button id="conversion-next-btn" onclick="RS.handleConversionStepNext()"
              disabled
              class="px-4 py-2 text-sm font-medium rounded-lg bg-indigo-500 text-white
                     hover:bg-indigo-600 disabled:opacity-40 disabled:cursor-not-allowed transition-all">
        Next →
      </button>
      <button id="conversion-confirm-btn" onclick="RS.handleConversionExecute()"
              disabled
              class="hidden px-4 py-2 text-sm font-medium rounded-lg bg-emerald-500 text-white
                     hover:bg-emerald-600 disabled:opacity-40 disabled:cursor-not-allowed transition-all">
        Start Conversion
      </button>
    </div>

  </div>
</div>

<div id="raster-vector-modal" class="hidden fixed inset-0 z-[2000] flex items-center justify-center bg-black/40 backdrop-blur-sm">
  <div class="bg-white rounded-2xl shadow-2xl w-full max-w-lg mx-4 overflow-hidden">
    <div class="flex items-center justify-between px-6 py-4 border-b border-slate-100">
      <div>
        <h2 class="text-base font-semibold text-slate-800">Raster to Vector</h2>
        <p id="raster-vector-project" class="text-xs text-slate-400 mt-1">Target project</p>
      </div>
      <button onclick="RS.closeRasterToVectorModal()"
              class="text-slate-400 hover:text-slate-600 transition-colors">x</button>
    </div>

    <div class="px-6 py-4 space-y-4">
      <div>
        <p class="text-xs font-medium text-slate-500 mb-2">Source raster</p>
        <div id="raster-vector-list" class="space-y-2 max-h-56 overflow-y-auto"></div>
      </div>

      <div class="grid grid-cols-1 sm:grid-cols-2 gap-3">
        <label class="text-xs font-medium text-slate-500">
          Band
          <input id="raster-vector-band-input" type="number" min="1" value="1"
                 class="mt-1 w-full px-3 py-2 text-sm border border-slate-200 rounded-lg
                        focus:outline-none focus:ring-2 focus:ring-violet-400">
        </label>
        <label class="text-xs font-medium text-slate-500">
          Max features
          <input id="raster-vector-max-input" type="number" min="1" value="10000"
                 class="mt-1 w-full px-3 py-2 text-sm border border-slate-200 rounded-lg
                        focus:outline-none focus:ring-2 focus:ring-violet-400">
        </label>
      </div>

      <label class="flex items-center gap-2 text-xs font-medium text-slate-600">
        <input id="raster-vector-skip-zero-input" type="checkbox" checked
               class="rounded border-slate-300 text-violet-600 focus:ring-violet-500">
        Skip zero pixels
      </label>

      <div>
        <label class="text-xs font-medium text-slate-500 block mb-1">New vector layer name</label>
        <input id="raster-vector-name-input" type="text"
               oninput="RS.handleRasterVectorNameInput()"
               class="w-full px-3 py-2 text-sm border border-slate-200 rounded-lg
                      focus:outline-none focus:ring-2 focus:ring-violet-400"
               placeholder="Vectorized layer name">
      </div>
    </div>

    <div class="flex items-center justify-end gap-2 px-6 py-4 border-t border-slate-100 bg-slate-50">
      <button onclick="RS.closeRasterToVectorModal()"
              class="px-4 py-2 text-sm font-medium rounded-lg border border-slate-200 text-slate-600
                     hover:bg-white transition-colors">
        Cancel
      </button>
      <button id="raster-vector-confirm-btn" onclick="RS.handleRasterToVectorExecute()"
              disabled
              class="px-4 py-2 text-sm font-medium rounded-lg bg-violet-500 text-white
                     hover:bg-violet-600 disabled:opacity-40 disabled:cursor-not-allowed transition-all">
        Create Vector Layer
      </button>
    </div>
  </div>
</div>
`;
