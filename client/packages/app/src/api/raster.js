const BASE_URL = window.location.origin;

export const RasterAPI = {
    /**
     * 获取所有影像列表
     */
    async fetchAll() {
        try {
            const response = await fetch(`${BASE_URL}/list`);
            if (!response.ok) throw new Error("获取影像列表失败");
            return await response.json();
        } catch (error) {
            console.error("[RasterAPI] fetchAll Error:", error);
            return [];
        }
    },

    /**
     * 上传影像文件
     */
    async upload(file, bundleId = null, onProgress = null) {
        return new Promise((resolve, reject) => {
            const formData = new FormData();
            formData.append('file', file);
            if (bundleId !== null && bundleId !== undefined) {
                formData.append('bundle_id', String(bundleId));
            }
            const xhr = new XMLHttpRequest();
            xhr.open('POST', `${BASE_URL}/upload`, true);
            if (onProgress && xhr.upload) {
                xhr.upload.onprogress = (event) => {
                    if (event.lengthComputable) {
                        const percent = (event.loaded / event.total) * 100;
                        onProgress(percent);
                    }
                };
            }
            xhr.onload = () => {
                if (xhr.status >= 200 && xhr.status < 300) {
                    try {
                        const result = JSON.parse(xhr.responseText);
                        resolve(result);
                    } catch (e) {
                        resolve(xhr.responseText);
                    }
                } else {
                    reject(new Error(`上传失败: ${xhr.status}`));
                }
            };
            xhr.onerror = () => reject(new Error("网络错误，上传中断"));
            xhr.send(formData);
        });
    },

    /**
     * 删除指定影像
     */
    async delete(indexId) {
        try {
            const response = await fetch(`${BASE_URL}/raster/${indexId}`, {
                method: 'DELETE'
            });
            return response.ok;
        } catch (error) {
            console.error("[RasterAPI] delete Error:", error);
            return false;
        }
    },

    /**
     * 合并波段
     */
    async mergeBands(rasterIds, newName) {
        const formData = new FormData();
        formData.append('raster_ids', rasterIds);
        formData.append('new_name', newName);
        return fetch(`${BASE_URL}/merge-bands`, { method: 'POST', body: formData });
    },

    // --- 指数计算接口 ---

    async calculateNDVI(redId, nirId, newName) {
        const formData = new FormData();
        formData.append('red_id', redId);
        formData.append('nir_id', nirId);
        formData.append('new_name', newName);
        return fetch(`${BASE_URL}/calculate-ndvi`, { method: 'POST', body: formData });
    },

    async calculateNDWI(greenId, nirId, newName) {
        const formData = new FormData();
        formData.append('green_id', greenId);
        formData.append('nir_id', nirId);
        formData.append('new_name', newName);
        return fetch(`${BASE_URL}/calculate-ndwi`, { method: 'POST', body: formData });
    },

    async calculateNDBI(swirId, nirId, newName) {
        const formData = new FormData();
        formData.append('swir_id', swirId);
        formData.append('nir_id', nirId);
        formData.append('new_name', newName);
        return fetch(`${BASE_URL}/calculate-ndbi`, { method: 'POST', body: formData });
    },

    async calculateMNDWI(greenId, swirId, newName) {
        const formData = new FormData();
        formData.append('green_id', greenId);
        formData.append('swir_id', swirId);
        formData.append('new_name', newName);
        return fetch(`${BASE_URL}/calculate-mndwi`, { method: 'POST', body: formData });
    },

    // --- 掩膜提取接口---

    async extractVegetation(bandIds, newName, threshold = 0.3, ...extraIds) {
        const formData = new FormData();
        bandIds.forEach((id, index) => {
            formData.append(`id_${index + 1}`, id);
        });
        formData.append('new_name', newName);
        formData.append('threshold', threshold);
        if (mode) {
            formData.append('mode', mode);
        }
        return fetch(`${BASE_URL}/extract-vegetation`, { method: 'POST', body: formData });
    },

    async extractWater(bandIds, newName, threshold = 0.0, mode = "") {
        const formData = new FormData();
        bandIds.forEach((id, index) => {
            formData.append(`id_${index + 1}`, id);
        });
        formData.append('new_name', newName);
        formData.append('threshold', threshold);
        if (mode) {formData.append('mode', mode);}
        return fetch(`${BASE_URL}/extract-water`, {method: 'POST', body: formData});
    },

    async extractBuildings(bandIds, newName, redId = null) {
        const formData = new FormData();
        bandIds.forEach((id, index) => {
            formData.append(`id_${index + 1}`, id);
        });
        formData.append('new_name', newName);
        if (redId) formData.append('red_id', redId);
        return fetch(`${BASE_URL}/extract-buildings`, { method: 'POST', body: formData });
    },

    async extractClouds(bandIds, newName, swirId = null) {
        const formData = new FormData();
        bandIds.forEach((id, index) => {
            formData.append(`id_${index + 1}`, id);
        });
        formData.append('new_name', newName);
        if (swirId) formData.append('swir_id', swirId);
        return fetch(`${BASE_URL}/extract-clouds`, { method: 'POST', body: formData });
    },

    // --- 调试接口 ---

    async clearDB() {
        return fetch(`${BASE_URL}/debug/clear-db`);
    }
};
