export const indexModal =`
        <div id="index-modal" class="hidden fixed inset-0 bg-slate-900/60 backdrop-blur-sm z-[2000] flex items-center justify-center p-4">
            <div class="bg-white w-full max-w-sm rounded-3xl p-8 shadow-2xl relative overflow-hidden">
                <div id="index-modal-bar" class="absolute top-0 left-0 w-full h-1.5 bg-indigo-500"></div>
                <div id="index-content"></div>
                <div class="pt-6 flex flex-col space-y-3">
                    <button onclick="RS.executeIndexCalculation()" class="w-full bg-slate-900 hover:bg-slate-800 text-white py-4 rounded-2xl font-bold text-sm shadow-xl transition-all active:scale-[0.98]">执行空间运算</button>
                    <button onclick="RS.closeIndexModal()" class="w-full text-slate-400 text-[10px] font-bold uppercase tracking-widest py-2">返回工作站</button>
                </div>
            </div>
        </div>
    `;
