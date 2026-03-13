/**
 * Modals.js - 存放所有大型 HTML 骨架片段
 * 这种方式可以将 HTML 与主逻辑解耦，保持 index.html 的整洁
 */
export const ModalTemplates = {
    // 1. 指数计算弹窗骨架 (NDVI, NDWI 等)
    indexModal: `
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
    `,

    // 2. 要素提取弹窗骨架 (植被、水体提取等)
    extractionModal: `
        <div id="extraction-modal" class="hidden fixed inset-0 bg-slate-900/60 backdrop-blur-sm z-[2000] flex items-center justify-center p-4">
            <div class="bg-white w-full max-w-sm rounded-3xl p-8 shadow-2xl relative overflow-hidden">
                <div id="extraction-modal-bar" class="absolute top-0 left-0 w-full h-1.5 bg-indigo-500"></div>
                <div id="extraction-content"></div>
                <div class="pt-6 flex flex-col space-y-3">
                    <button onclick="RS.runExtraction()" class="w-full bg-slate-900 hover:bg-slate-800 text-white py-4 rounded-2xl font-bold text-sm shadow-xl transition-all active:scale-[0.98]">开始自动化提取</button>
                    <button onclick="RS.closeExtractionModal()" class="w-full text-slate-400 text-[10px] font-bold uppercase tracking-widest py-2">取消任务</button>
                </div>
            </div>
        </div>
    `,

    // 3. 波段合成弹窗骨架
    mergeModal: `
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
    `,

    // 栅格计算器骨架
    calculatorModal: `
        <div id="calculator-modal" class="hidden fixed inset-0 bg-slate-900/60 backdrop-blur-sm z-[2000] flex items-center justify-center p-4">
            <div class="bg-white w-full max-w-lg rounded-3xl p-8 shadow-2xl relative overflow-hidden">
                <div class="absolute top-0 left-0 w-full h-1.5 bg-purple-500"></div>
                <h2 class="text-xl font-black text-slate-800 mb-6 tracking-tight">栅格计算器 (Raster Calculator)</h2>
                
                <div class="space-y-4">
                    <div>
                        <label class="text-[10px] font-bold text-slate-400 uppercase mb-1.5 block">数学表达式</label>
                        <input type="text" id="calc-expression-input" placeholder="例如: (A + B - C) / (A - B + C * D)" 
                               onkeyup="RS.updateCalculatorVariables()"
                               class="w-full p-3 bg-slate-50 border border-slate-200 rounded-xl text-sm font-mono outline-none focus:ring-2 focus:ring-purple-500/20">
                    </div>

                    <div id="calc-variables-container" class="space-y-2 max-h-[200px] overflow-y-auto"></div>

                    <div>
                        <label class="text-[10px] font-bold text-slate-400 uppercase mb-1.5 block mt-4">结果图层名称</label>
                        <input type="text" id="calc-name-input" value="Calc_Result" class="w-full p-3 bg-slate-50 border border-slate-200 rounded-xl text-sm outline-none focus:ring-2 focus:ring-purple-500/20">
                    </div>
                </div>

                <div class="pt-6 flex flex-col space-y-3">
                    <button onclick="RS.executeCalculator()" class="w-full bg-purple-600 hover:bg-purple-700 text-white py-4 rounded-2xl font-bold text-sm shadow-xl transition-all">执行运算</button>
                    <button onclick="RS.closeCalculatorModal()" class="w-full text-slate-400 text-[10px] font-bold uppercase tracking-widest py-2">取消</button>
                </div>
            </div>
        </div>
    `,

    // 4. 右下角详情面板
    detailPanel: `
        <div id="detail-panel" class="hidden fixed right-6 bottom-10 w-80 bg-white/95 backdrop-blur-md shadow-2xl rounded-2xl p-5 z-[1002] border border-slate-100 custom-shadow">
            <div class="flex justify-between items-start mb-4">
                <h3 class="font-bold text-slate-800 text-xs truncate max-w-[180px]" id="detail-title">影像详情</h3>
                <button onclick="RS.hideDetail()" class="text-slate-400 hover:text-slate-600">✕</button>
            </div>
            <div id="detail-content" class="text-slate-600 overflow-y-auto max-h-[300px]"></div>
        </div>
    `
};