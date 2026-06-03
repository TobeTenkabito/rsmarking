/**
 * ConversionAPI - EnglishVectorEnglish
 * Backend endpoint rasterize_router.py
 */

import { API_CONFIG } from './config.js';

const BASE_URL = API_CONFIG.dataServiceUrl;

export const ConversionAPI = {
    /**
     * Vector LayerEnglish
     * @param {string} layerId     - Vector Layer UUID
     * @param {number} refIndexId  - English index_id
     * @param {string} newName     - EnglishNew Raster Name
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
                throw new Error(err.detail ?? `Rasterization task failed: ${response.status}`);
            }

            return await response.json();
        } catch (error) {
            console.error("[AnalysisAPI] vectorToRaster Error:", error);
            throw error;
        }
    },

    async rasterToVector(rasterIndexId, projectId, newName, options = {}) {
        try {
            const formData = new FormData();
            formData.append('raster_index_id', String(rasterIndexId));
            formData.append('project_id', projectId);
            formData.append('new_name', newName);
            formData.append('band_index', String(options.bandIndex ?? 1));
            formData.append('skip_nodata', String(options.skipNodata ?? true));
            formData.append('skip_zero', String(options.skipZero ?? true));
            formData.append('max_features', String(options.maxFeatures ?? 10000));
            formData.append('simplify_tolerance', String(options.simplifyTolerance ?? 0));

            const response = await fetch(`${BASE_URL}/rasterize/raster-to-vector`, {
                method: "POST",
                body: formData,
            });

            if (!response.ok) {
                const err = await response.json().catch(() => ({}));
                throw new Error(err.detail ?? `Raster vectorization failed: ${response.status}`);
            }

            return await response.json();
        } catch (error) {
            console.error("[AnalysisAPI] rasterToVector Error:", error);
            throw error;
        }
    }
};
