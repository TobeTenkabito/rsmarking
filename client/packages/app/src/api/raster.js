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

    /**
    * 提取波段
    * @param {number} rasterId - 源文件 index_id
    * @param {string} bandIndices - 波段索引，逗號分隔，如 "1,3"
    * @param {string} newName - 輸出文件名
    */
    async extractBands(rasterId, bandIndices, newName) {
        const formData = new FormData();
        formData.append('raster_id', rasterId);
        formData.append('band_indices', bandIndices);
        formData.append('new_name', newName);
        return fetch(`${BASE_URL}/extract-bands`, { method: 'POST', body: formData });
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
    async extractVegetation(bandIds, newName, threshold = 0.3, mode = "") {
        const formData = new FormData();
        bandIds.forEach((id, index) => {
            formData.append(`id_${index + 1}`, id);
        });
        formData.append('new_name', newName);
        formData.append('threshold', threshold);
        if (mode) formData.append('mode', mode);
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

    async extractBuildings(bandIds, newName, threshold = 0.0, mode = "") {
        const formData = new FormData();
        bandIds.forEach((id, index) => {
            formData.append(`id_${index + 1}`, id);
        });
        formData.append('new_name', newName);
        formData.append('threshold', threshold);
        if (mode) formData.append('mode', mode);
        return fetch(`${BASE_URL}/extract-buildings`, { method: 'POST', body: formData });
    },

    async extractClouds(bandIds, newName, threshold = 0.0, mode = "") {
        const formData = new FormData();
        bandIds.forEach((id, index) => {
            formData.append(`id_${index + 1}`, id);
        });
        formData.append('new_name', newName);
        formData.append('threshold', threshold);
        if (mode) formData.append('mode', mode);
        return fetch(`${BASE_URL}/extract-clouds`, { method: 'POST', body: formData });
    },

    /**
     * 调用后端栅格计算器
     */
    async runCalculator(expression, varMapping, newName) {
        const formData = new FormData();
        formData.append('expression', expression);
        formData.append('new_name', newName);

        // 动态追加 var_A=id, var_B=id 等参数
        for (const [key, value] of Object.entries(varMapping)) {
            formData.append(key, value);
        }

        const response = await fetch(`${BASE_URL}/raster-calculator`, {
            method: 'POST',
            body: formData
        });
        if (!response.ok) throw new Error("计算器执行失败");
        return await response.json();
    },

    // --- 脚本执行接口 ---
    async executeScript(script, rasterIds, outputName) {
        const formData = new FormData();
        formData.append('script', script);
        formData.append('raster_ids', rasterIds.join(','));
        formData.append('output_name', outputName);

        return fetch(`${BASE_URL}/execute-script`, {
            method: 'POST',
            body: formData
        });
    },

    async getScriptTemplates() {
        try {
            const response = await fetch(`${BASE_URL}/script-templates`);
            if (!response.ok) throw new Error("获取脚本模板失败");
            return await response.json();
        } catch (error) {
            console.error("[RasterAPI] getScriptTemplates Error:", error);
            return [];
        }
    },

    // --- 业务字段接口 ---
    /**
     * 获取某栅格的全部业务字段
     * @param {number} rasterId - 栅格 index_id
     */
    async getFields(rasterId) {
        try {
            const response = await fetch(`${BASE_URL}/raster/${rasterId}/fields`);
            if (!response.ok) throw new Error("获取字段列表失败");
            return await response.json();
        } catch (error) {
            console.error("[RasterAPI] getFields Error:", error);
            return [];
        }
    },

    /**
     * 新增业务字段
     * @param {number} rasterId - 栅格 index_id
     * @param {{ field_name, field_alias?, field_type, field_order?, is_required?, default_val? }} fieldData
     */
    async createField(rasterId, fieldData) {
        try {
            const response = await fetch(`${BASE_URL}/raster/${rasterId}/fields`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(fieldData)
            });
            if (!response.ok) {
                const err = await response.json().catch(() => ({}));
                throw new Error(err.detail ?? "新增字段失败");
            }
            return await response.json();
        } catch (error) {
            console.error("[RasterAPI] createField Error:", error);
            throw error;
        }
    },

    /**
     * 修改业务字段（别名、类型、排序等）
     * @param {number} rasterId  - 栅格 index_id
     * @param {number} fieldId   - 字段 id
     * @param {{ field_alias?, field_type?, field_order?, is_required?, default_val? }} updates
     */
    async updateField(rasterId, fieldId, updates) {
        try {
            const response = await fetch(`${BASE_URL}/raster/${rasterId}/fields/${fieldId}`, {
                method: 'PATCH',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(updates)
            });
            if (!response.ok) {
                const err = await response.json().catch(() => ({}));
                throw new Error(err.detail ?? "更新字段失败");
            }
            return await response.json();
        } catch (error) {
            console.error("[RasterAPI] updateField Error:", error);
            throw error;
        }
    },

    /**
     * 删除业务字段（系统字段不可删除）
     * @param {number} rasterId - 栅格 index_id
     * @param {number} fieldId  - 字段 id
     */
    async deleteField(rasterId, fieldId) {
        try {
            const response = await fetch(`${BASE_URL}/raster/${rasterId}/fields/${fieldId}`, {
                method: 'DELETE'
            });
            if (!response.ok) {
                const err = await response.json().catch(() => ({}));
                throw new Error(err.detail ?? "删除字段失败");
            }
            return true;
        } catch (error) {
            console.error("[RasterAPI] deleteField Error:", error);
            throw error;
        }
    },

    /**
     * 用矢量多边形裁剪栅格，结果注册为新栅格记录走 COG 流程
     * @param {string}   rasterId       - 被裁剪的栅格 index_id
     * @param {string}   newName        - 输出栅格文件名（不含 .tif 也可）
     * @param {Array}    geometries     - GeoJSON geometry 对象数组
     * @param {string}   [srcVectorCrs] - 矢量数据的 CRS，默认 "EPSG:4326"
     * @param {boolean}  [crop=true]    - 是否按几何边界裁剪（false 则仅掩膜）
     * @param {number}   [nodata]       - 输出 nodata 值
     * @param {boolean}  [allTouched=false] - 是否包含边界接触像元
     * @returns {{ status, id, clip_meta }}
     */
    async clipRasterByVector(
        rasterId,
        newName,
        geometries,
        srcVectorCrs = "EPSG:4326",
        crop = true,
        nodata = null,
        allTouched = false,
    ) {
        const payload = {
            raster_id: rasterId,
            new_name: newName,
            geometries,
            src_vector_crs: srcVectorCrs,
            crop,
            all_touched: allTouched,
        };
        // nodata 为 null 时不传，避免后端接收到意外的 null 覆盖原始值
        if (nodata !== null && nodata !== undefined) {
            payload.nodata = nodata;
        }
        try {
            const response = await fetch(`${BASE_URL}/clip-raster-by-vector`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload),
            });
            if (!response.ok) {
                const err = await response.json().catch(() => ({}));
                throw new Error(err.detail ?? `裁剪失败: ${response.status}`);
            }
            return await response.json();
        } catch (error) {
            console.error("[RasterAPI] clipRasterByVector Error:", error);
            throw error;
        }
    },


    /**
    * 查詢指定影像在某 WGS84 坐標點的各波段像素值（光譜）
    * @param {number} rasterId  - 影像 index_id
    * @param {number} lng       - 經度 (WGS84)
    * @param {number} lat       - 緯度 (WGS84)
    * @returns {{
    *   bands: Array<{index: number, name: string, value: number|null}>,
    *   has_nodata: boolean,
    *   coordinate: {lng: number, lat: number}
    * } | null}
    */
    async querySpectrum(rasterId, lng, lat) {
    try {
        const params = new URLSearchParams({ lng, lat });
        const response = await fetch(
            `${BASE_URL}/raster/${rasterId}/spectrum?${params}`
        );
        if (!response.ok) {
            const err = await response.json().catch(() => ({}));
            throw new Error(err.detail ?? "光譜查詢失敗");
        }
        return await response.json();
    } catch (error) {
        console.error("[RasterAPI] querySpectrum Error:", error);
        return null;
    }
},

    // --- 调试接口 ---
    async clearDB() {
        return fetch(`${BASE_URL}/debug/clear-db`);
    }
};
