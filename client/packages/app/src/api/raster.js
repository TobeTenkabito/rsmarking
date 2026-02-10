const BASE_URL = window.location.origin;

export const RasterAPI = {
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
    async calculateNDVI(redId, nirId, newName) {
        const formData = new FormData();
        formData.append('red_id', redId);
        formData.append('nir_id', nirId);
        formData.append('new_name', newName);
        return fetch(`${BASE_URL}/calculate-ndvi`, {
            method: 'POST',
            body: formData
        });
    },
    async mergeBands(rasterIds, newName) {
        const formData = new FormData();
        formData.append('raster_ids', rasterIds);
        formData.append('new_name', newName);
        return fetch(`${BASE_URL}/merge-bands`, { method: 'POST', body: formData });
    },
    async clearDB() {
        return fetch(`${BASE_URL}/debug/clear-db`);
    }
};