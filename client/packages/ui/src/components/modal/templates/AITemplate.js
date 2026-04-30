/**
 * AITemplate.js
 * AI 分析目标数据下拉框选项
 */
export const AITemplate = {

    renderAITargetOptions(rasters = [], layers = []) {
        const rasterOptions = rasters.length
            ? rasters.map(r =>
                `<option value="${r.index_id}" data-type="raster">[栅格] ${r.file_name}</option>`
              ).join('')
            : '';

        const layerOptions = layers.length
            ? layers.map(l =>
                `<option value="${l.id}" data-type="vector">[矢量] ${l.name}</option>`
              ).join('')
            : '';

        if (!rasterOptions && !layerOptions) {
            return '<option value="">暂无可用数据</option>';
        }

        return `
            ${rasterOptions ? `<optgroup label="栅格影像">${rasterOptions}</optgroup>` : ''}
            ${layerOptions  ? `<optgroup label="矢量图层">${layerOptions}</optgroup>`  : ''}
        `;
    },
};
