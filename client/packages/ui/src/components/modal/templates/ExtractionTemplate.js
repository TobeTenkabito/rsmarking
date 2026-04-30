/**
 * ExtractionTemplate.js
 * 地物提取配置面板（植被 / 水体 / 建筑 / 云层）
 */
import { renderSelectOptions } from '../utils.js';

const EXTRACTION_CONFIGS = {
    VEGETATION: { title: '植被提取 (NDVI Mask)',  color: 'emerald', threshold: 0.3  },
    WATER:      { title: '水体提取 (MNDWI Mask)', color: 'blue',    threshold: 0.0  },
    BUILDING:   { title: '建筑提取 (NDBI Mask)',  color: 'amber',   threshold: 0.1  },
    CLOUD:      { title: '云层提取',              color: 'slate',   threshold: 0.5  },
};

export const ExtractionTemplate = {

    renderExtractionConfig(type, rasters) {
        const options = renderSelectOptions(rasters);
        const cfg     = EXTRACTION_CONFIGS[type] ?? EXTRACTION_CONFIGS.VEGETATION;

        return `
            <div class="flex items-center space-x-3 mb-6 text-${cfg.color}-600">
                <div class="p-2 bg-${cfg.color}-50 rounded-lg">
                    <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2"
                              d="M13 10V3L4 14h7v7l9-11h-7z"/>
                    </svg>
                </div>
                <h3 class="font-bold text-sm uppercase tracking-tight">${cfg.title}</h3>
            </div>

            <div class="space-y-4">
                <!-- 动态波段选择容器 -->
                <div id="dynamic-bands-container" class="space-y-3">
                    <div>
                        <label class="text-[10px] font-bold text-slate-400 uppercase mb-1.5 block">选择波段 1 (必选)</label>
                        <select class="band-selector w-full p-3 bg-slate-50 border border-slate-200 rounded-xl
                                       text-xs outline-none focus:ring-2 focus:ring-${cfg.color}-500/20">
                            <option value="">-- 请选择波段 --</option>
                            ${options}
                        </select>
                    </div>
                    <div>
                        <label class="text-[10px] font-bold text-slate-400 uppercase mb-1.5 block">选择波段 2 (必选)</label>
                        <select class="band-selector w-full p-3 bg-slate-50 border border-slate-200 rounded-xl
                                       text-xs outline-none focus:ring-2 focus:ring-${cfg.color}-500/20">
                            <option value="">-- 请选择波段 --</option>
                            ${options}
                        </select>
                    </div>
                </div>

                <div>
                    <label class="text-[10px] font-bold text-slate-400 uppercase mb-1.5 block">计算模式 (Mode - 可选)</label>
                    <input type="text"
                           id="extract-mode-input"
                           placeholder="例如: MNDWI, AWEI"
                           class="w-full p-3 bg-slate-50 border border-slate-200 rounded-xl text-xs
                                  outline-none focus:ring-2 focus:ring-blue-500/20">
                </div>

                <div>
                    <label class="text-[10px] font-bold text-slate-400 uppercase mb-1.5 block">提取阈值 (Threshold)</label>
                    <input type="number"
                           step="0.01"
                           id="extract-threshold-input"
                           value="${cfg.threshold}"
                           class="w-full p-3 bg-slate-50 border border-slate-200 rounded-xl text-xs
                                  outline-none focus:ring-2 focus:ring-${cfg.color}-500/20">
                </div>

                <div>
                    <label class="text-[10px] font-bold text-slate-400 uppercase mb-1.5 block">结果存储名称</label>
                    <input type="text"
                           id="extract-name-input"
                           value="Extract_${type}_${Date.now()}.tif"
                           class="w-full p-3 bg-slate-50 border border-slate-200 rounded-xl text-xs
                                  outline-none focus:ring-2 focus:ring-${cfg.color}-500/20">
                </div>
            </div>`;
    },
};
