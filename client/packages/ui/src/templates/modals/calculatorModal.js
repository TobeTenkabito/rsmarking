export const calculatorModal = `
    <div id="calculator-modal" class="hidden fixed inset-0 bg-slate-900/60 backdrop-blur-sm z-[2000] flex items-center justify-center p-4">
        <div class="bg-white w-full max-w-lg rounded-3xl p-8 shadow-2xl relative overflow-hidden flex flex-col max-h-[90vh]">
            <div class="absolute top-0 left-0 w-full h-1.5 bg-purple-500"></div>
            
            <div class="flex justify-between items-center mb-6">
                <h2 class="text-xl font-black text-slate-800 tracking-tight">Raster Calculator</h2>
                <button onclick="RS.toggleCalcHelp()" class="flex items-center space-x-1 text-slate-400 hover:text-purple-600 transition-colors">
                    <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M8.228 9c.549-1.165 2.03-2 3.772-2 2.21 0 4 1.343 4 3 0 1.4-1.278 2.575-3.006 2.907-.542.104-.994.54-.994 1.093m0 3h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"></path></svg>
                    <span class="text-[10px] font-bold uppercase">Syntax Help</span>
                </button>
            </div>

            <div id="calc-help-panel" class="hidden mb-4 p-4 bg-purple-50 rounded-2xl border border-purple-100 text-[11px] text-purple-800 leading-relaxed animate-in fade-in slide-in-from-top-2">
                <p class="font-bold mb-1">💡 Syntax Guide：</p>
                <ul class="list-disc list-inside space-y-1 opacity-80">
                    <li>Use <code class="bg-purple-200 px-1 rounded">A, B</code> to represent all bands of the bound imagerybands</li>
                    <li>Use <code class="bg-purple-200 px-1 rounded">A_2</code> to represent band 2 of A as single-band output</li>
                    <li>Use <code class="bg-purple-200 px-1 rounded">A_2_3_4</code> to represent band 2、3、4 bands</li>
                    <li>Conditional operation：<code class="bg-purple-200 px-1 rounded">where(condition, true value, false value)</code></li>
                    <li>NDVI example：<code class="bg-purple-200 px-1 rounded">(A_4 - A_3) / (A_4 + A_3)</code></li>
                    <li>All-band normalization：<code class="bg-purple-200 px-1 rounded">(A - B) / (A + B)</code></li>
                </ul>
            </div>
            
            <div class="space-y-4 overflow-y-auto pr-2 custom-scrollbar">
                <div>
                    <label class="text-[10px] font-bold text-slate-400 uppercase mb-1.5 block">Math Expression</label>
                    <input type="text" id="calc-expression-input" placeholder="e.g.: (A + B) / sqrt(C)"
                           onkeyup="RS.updateCalculatorVariables()"
                           class="w-full p-4 bg-slate-50 border border-slate-200 rounded-xl text-sm font-mono outline-none focus:ring-2 focus:ring-purple-500/20">
                    
                    <div class="flex flex-wrap gap-1.5 mt-2">
                        ${['sin', 'cos', 'log', 'sqrt', 'exp', 'abs', 'where'].map(fn => `
                            <button onclick="RS.insertCalcFunction('${fn}')" class="px-2.5 py-1 bg-slate-100 hover:bg-purple-100 hover:text-purple-700 text-slate-500 rounded-md text-[10px] font-mono font-bold transition-all border border-slate-200/50">
                                ${fn}()
                            </button>
                        `).join('')}
                        <button onclick="RS.insertCalcFunction('where')" class="px-2.5 py-1 bg-indigo-50 hover:bg-indigo-100 text-indigo-600 rounded-md text-[10px] font-mono font-bold transition-all border border-indigo-100">
                            where(c,x,y)
                        </button>
                    </div>
                </div>

                <div id="calc-variables-container" class="space-y-2"></div>

                <div>
                    <label class="text-[10px] font-bold text-slate-400 uppercase mb-1.5 block">Result Layer Name</label>
                    <input type="text" id="calc-name-input" value="Calc_Result" class="w-full p-3 bg-slate-50 border border-slate-200 rounded-xl text-sm outline-none">
                </div>
            </div>

            <div class="pt-6 flex flex-col space-y-3">
                <button onclick="RS.executeCalculator()" class="w-full bg-purple-600 hover:bg-purple-700 text-white py-4 rounded-2xl font-bold text-sm shadow-xl">Run Calculation</button>
                <button onclick="RS.closeCalculatorModal()" class="w-full text-slate-400 text-[10px] font-bold uppercase tracking-widest py-2">Cancel</button>
            </div>
        </div>
    </div>
`;
