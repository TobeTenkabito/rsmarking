export const mergeModal = `
        <div id="merge-modal" class="hidden fixed inset-0 bg-slate-900/60 backdrop-blur-sm z-[2000] flex items-center justify-center p-4">
            <div class="bg-white w-full max-w-md rounded-2xl shadow-2xl overflow-hidden">
                <div class="p-5 border-b border-slate-100 flex justify-between items-center bg-slate-50/50">
                    <h3 class="font-bold text-slate-800 uppercase text-xs tracking-widest">波段合成 (Band Stacking)</h3>
                    <button onclick="RS.closeMergeModal()" class="text-slate-400 hover:text-slate-600 transition-colors">✕</button>
                </div>
                <div id="merge-selection-list" class="p-5 max-h-[400px] overflow-y-auto space-y-2 bg-white"></div>
                <div class="p-5 bg-slate-50 border-t border-slate-100 flex justify-end items-center space-x-4">
                    <button onclick="RS.closeMergeModal()" class="px-4 py-2 text-xs font-bold text-slate-400">取消</button>
                    <button id="confirm-merge-btn" onclick="RS.executeMerge()" disabled class="bg-indigo-600 text-white px-6 py-2 rounded-lg text-xs font-bold shadow-lg disabled:opacity-50">确认合成</button>
                </div>
            </div>
        </div>
    `;