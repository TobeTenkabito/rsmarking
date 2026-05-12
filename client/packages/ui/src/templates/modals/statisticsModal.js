export const statisticsModal = `
<div id="raster-statistics-modal"
     class="hidden fixed inset-0 bg-black/40 backdrop-blur-sm z-[2000] flex items-center justify-center p-4">
  <div class="bg-white rounded-2xl shadow-2xl w-full max-w-5xl border border-slate-100 overflow-hidden">
    <div class="flex items-center justify-between px-6 py-4 border-b border-slate-100 bg-slate-50/80">
      <div class="flex items-center space-x-3 min-w-0">
        <div class="w-9 h-9 rounded-lg bg-indigo-100 text-indigo-600 flex items-center justify-center shrink-0">
          <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2"
                  d="M4 19V5m0 14h16M8 17V9m4 8V7m4 10v-5"/>
          </svg>
        </div>
        <div class="min-w-0">
          <h3 class="text-sm font-bold text-slate-800 truncate">Raster Statistics</h3>
          <p id="raster-statistics-subtitle" class="text-[10px] text-slate-400 truncate">Per-band distribution</p>
        </div>
      </div>
      <div class="flex items-center space-x-2 shrink-0">
        <button onclick="RS.refreshRasterStatistics()"
                class="p-2 text-slate-400 hover:text-indigo-600 hover:bg-indigo-50 rounded-lg transition-colors"
                title="Refresh statistics">
          <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2"
                  d="M4 4v5h.58m15.36 2A8 8 0 004.58 9m0 0H9m11 11v-5h-.58m0 0A8 8 0 014.06 13m15.36 2H15"/>
          </svg>
        </button>
        <button onclick="RS.closeRasterStatistics()"
                class="p-2 text-slate-400 hover:text-slate-700 hover:bg-slate-100 rounded-lg transition-colors"
                title="Close">
          <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2"
                  d="M6 18L18 6M6 6l12 12"/>
          </svg>
        </button>
      </div>
    </div>

    <div id="raster-statistics-content" class="px-6 py-5 max-h-[72vh] overflow-y-auto"></div>
  </div>
</div>
`;
