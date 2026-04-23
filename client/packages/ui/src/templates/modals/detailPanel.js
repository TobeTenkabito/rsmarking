export const detailPanel = `
        <div id="detail-panel" class="hidden fixed right-6 bottom-10 w-80 bg-white/95 backdrop-blur-md shadow-2xl rounded-2xl p-5 z-[1002] border border-slate-100 custom-shadow">
            <div class="flex justify-between items-start mb-4">
                <h3 class="font-bold text-slate-800 text-xs truncate max-w-[180px]" id="detail-title">影像详情</h3>
                <button onclick="RS.hideDetail()" class="text-slate-400 hover:text-slate-600">✕</button>
            </div>
            <div id="detail-content" class="text-slate-600 overflow-y-auto max-h-[300px]"></div>
        </div>
    `;