/**
 * ConversionAPI - 处理矢量与栅格的转换任务
 * 对应后端 rasterize_router.py
 */

const BASE_URL = window.location.origin;

export const ConversionAPI = {
    /**
     * 矢量图层栅格化
     * @param {string} layerId     - 矢量图层 UUID
     * @param {number} refIndexId  - 参考栅格的 index_id
     * @param {string} newName     - 生成的新栅格名称
     */
    async vectorToRaster(layerId, refIndexId, newName) {
        try {
            const formData = new FormData();
            formData.append('layer_id', layerId);
            formData.append('ref_index_id', String(refIndexId));
            formData.append('new_name', newName);

            const response = await fetch(`${BASE_URL}/rasterize/layer-to-raster`, {
                method: "POST",
                body: formData,
            });

            if (!response.ok) {
                const err = await response.json().catch(() => ({}));
                throw new Error(err.detail ?? `栅格化任务启动失败: ${response.status}`);
            }

            return await response.json();
        } catch (error) {
            console.error("[AnalysisAPI] vectorToRaster Error:", error);
            throw error;
        }
    }
};