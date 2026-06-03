/**
 * CalculatorTemplate.js
 * Raster calculator variable mapping list
 */
export const CalculatorTemplate = {

    renderCalculatorVariables(variables, rasters) {
        if (!variables || variables.length === 0) {
            return `
                <div class="py-6 text-center border-2 border-dashed border-slate-100 rounded-2xl">
                    <p class="text-[10px] text-slate-300 font-bold uppercase tracking-widest">Enter an expression above</p>
                </div>`;
        }

        return variables.map(v => `
            <div class="flex items-center space-x-3 p-3 bg-slate-50 border border-slate-100
                        rounded-xl hover:border-purple-200 transition-all">
                <div class="w-8 h-8 rounded-lg bg-purple-600 text-white flex items-center
                            justify-center font-mono font-bold text-xs shadow-sm">
                    ${v}
                </div>
                <div class="flex-1">
                    <select data-var="${v}"
                            class="calc-var-select w-full bg-transparent text-[11px] font-bold
                                   text-slate-600 outline-none cursor-pointer">
                        <option value="">Bind imagery layer...</option>
                        ${rasters.map(r => {
                            const bandCount   = r.bands ?? 1;
                            const bandLabel   = bandCount > 1 ? ` · ${bandCount} bands` : ' · single-band';
                            const displayName = r.file_name || r.name || r.index_id || r.id;
                            return `<option value="${r.index_id}">${displayName}${bandLabel}</option>`;
                        }).join('')}
                    </select>
                </div>
            </div>`
        ).join('');
    },
};
