/**
 * IndexTemplate.js
 * 遥感指数计算配置面板（NDVI / NDWI / NDBI / MNDWI）
 */
import { renderSelectOptions } from '../utils.js';

const INDEX_CONFIGS = {
    NDVI:  { b1: '红波段 (Red)',        b2: '近红外波段 (NIR)',   color: 'emerald' },
    NDWI:  { b1: '绿波段 (Green)',      b2: '近红外波段 (NIR)',   color: 'blue'    },
    NDBI:  { b1: '短波红外 (SWIR)',     b2: '近红外波段 (NIR)',   color: 'amber'   },
    MNDWI: { b1: '绿波段 (Green)',      b2: '短波红外 (SWIR)',    color: 'cyan'    },
};

export const IndexTemplate = {

    renderIndexConfig(type, rasters) {
        const options = renderSelectOptions(rasters);
        const cfg     = INDEX_CONFIGS[type] ?? INDEX_CONFIGS.NDVI;

        return `
            <div class="flex items-center space-x-3 mb-6 text-${cfg.color}-600">
                <div class="p-2 bg-${cfg.color}-50 rounded-lg">
                    <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2"
                              d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0
                                 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0
                                 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z"/>
                    </svg>
                </div>
                <h3 class="font-bold text-sm uppercase tracking-tight">${type} 遥感指数计算</h3>
            </div>

            <div class="space-y-4">
                <div>
                    <label class="text-[10px] font-bold text-slate-400 uppercase mb-1.5 block">${cfg.b1}</label>
                    <select id="index-b1-select"
                            class="w-full p-3 bg-slate-50 border border-slate-200 rounded-xl text-xs
                                   outline-none focus:ring-2 focus:ring-${cfg.color}-500/20">
                        ${options}
                    </select>
                </div>
                <div>
                    <label class="text-[10px] font-bold text-slate-400 uppercase mb-1.5 block">${cfg.b2}</label>
                    <select id="index-b2-select"
                            class="w-full p-3 bg-slate-50 border border-slate-200 rounded-xl text-xs
                                   outline-none focus:ring-2 focus:ring-${cfg.color}-500/20">
                        ${options}
                    </select>
                </div>
                <div>
                    <label class="text-[10px] font-bold text-slate-400 uppercase mb-1.5 block">输出文件名</label>
                    <input type="text"
                           id="index-name-input"
                           value="${type}_Result_${Date.now()}.tif"
                           class="w-full p-3 bg-slate-50 border border-slate-200 rounded-xl text-xs outline-none">
                </div>
            </div>`;
    },
};
