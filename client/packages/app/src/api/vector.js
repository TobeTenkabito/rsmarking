/**
 * VectorAPI - 负责矢量标注服务 (8001) 与 矢量切片服务 (8003) 的通讯
 */

// 优先从 Vite 环境变量读取地址，否则回退到本地默认端口
const ANNO_BASE_URL = import.meta.env?.VITE_ANNO_SERVICE_URL || "http://localhost:8001";
const VTILE_BASE_URL = import.meta.env?.VITE_VTILE_SERVICE_URL || "http://localhost:8003";

/**
 * 通用 Fetch 封装
 * 处理 Content-Type、异常拦截及 API 错误详情解析
 */
async function apiRequest(url, options = {}) {
    // FormData 时不设置 Content-Type，让浏览器自动附加 boundary
    const isFormData = options.body instanceof FormData;
    const defaultHeaders = isFormData ? {} : { 'Content-Type': 'application/json' };

    const config = {
        ...options,
        headers: { ...defaultHeaders, ...options.headers }
    };

    try {
        const response = await fetch(url, config);

        // 处理删除操作成功的 204 返回
        if (response.status === 204) return true;

        const data = await response.json();

        if (!response.ok) {
            // 解析 FastAPI 抛出的 HTTPException 详情
            const errorMsg = data.detail || `请求失败: ${response.status}`;
            throw new Error(errorMsg);
        }

        return data;
    } catch (error) {
        console.error(`[VectorAPI Error] Endpoint: ${url}`, error);
        throw error;
    }
}

export const VectorAPI = {

    /**
     * 获取所有标注项目
     */
    async fetchProjects() {
        return await apiRequest(`${ANNO_BASE_URL}/projects`);
    },

    /**
     * 创建新项目
     */
    async createProject(name) {
        return await apiRequest(`${ANNO_BASE_URL}/projects`, {
            method: 'POST',
            body: JSON.stringify({ name })
        });
    },

    /**
     * 获取项目下的所有图层
     */
    async fetchLayers(projectId) {
        return await apiRequest(`${ANNO_BASE_URL}/projects/${projectId}/layers`);
    },

    /**
     * 【危险/调试专用】删除所有项目及其关联的图层和要素
     */
    async deleteAllProjects() {
        return await apiRequest(`${ANNO_BASE_URL}/projects`, {
            method: 'DELETE'
        });
    },

    /**
     * 创建标注图层 (可关联影像 index_id)
     */
    async createLayer(projectId, name, sourceRasterIndexId = null) {
        return await apiRequest(`${ANNO_BASE_URL}/projects/${projectId}/layers`, {
            method: 'POST',
            body: JSON.stringify({
                name,
                source_raster_index_id: sourceRasterIndexId
            })
        });
    },

    /**
     * 根据视口 BBox 动态加载要素 (地图联动核心)
     * @param {string} layerId
     * @param {Array} bbox - [minx, miny, maxx, maxy]
     */
    async fetchFeaturesInBbox(layerId, bbox) {
        const [minx, miny, maxx, maxy] = bbox;
        const query = `minx=${minx}&miny=${miny}&maxx=${maxx}&maxy=${maxy}`;
        return await apiRequest(`${ANNO_BASE_URL}/layers/${layerId}/features?${query}`);
    },

    /**
     * 创建单个标注要素
     * @param {string} layerId
     * @param {Object} geojsonGeometry - 标准 GeoJSON geometry 对象
     * @param {Object} properties - 业务属性 (category, confidence等)
     */
    async createFeature(layerId, geojsonGeometry, properties = {}) {
        return await apiRequest(`${ANNO_BASE_URL}/layers/${layerId}/features`, {
            method: 'POST',
            body: JSON.stringify({
                geometry: geojsonGeometry,
                properties: properties
            })
        });
    },

    /**
     * 获取要素详情
     */
    async getFeature(featureId) {
        return await apiRequest(`${ANNO_BASE_URL}/features/${featureId}`);
    },

    /**
     * 更新要素 (几何或属性)
     */
    async updateFeature(featureId, updateData) {
        return await apiRequest(`${ANNO_BASE_URL}/features/${featureId}`, {
            method: 'PATCH',
            body: JSON.stringify(updateData)
        });
    },

    /**
     * 删除要素
     */
    async deleteFeature(featureId) {
        return await apiRequest(`${ANNO_BASE_URL}/features/${featureId}`, {
            method: 'DELETE'
        });
    },

    /**
     * 删除图层
     */
    async deleteLayer(layerID){
        return await apiRequest(`${ANNO_BASE_URL}/layers/${layerID}`,{
        method: 'DELETE'
        });
    },

    /**
     * 批量导入要素 (用于对接 AI 提取模块 ExtractionModule)
     * @param {string} layerId
     * @param {Array} features - [{geometry: {...}, properties: {...}}, ...]
     */
    async bulkCreateFeatures(layerId, features) {
        return await apiRequest(`${ANNO_BASE_URL}/layers/${layerId}/bulk`, {
            method: 'POST',
            body: JSON.stringify(features)
        });
    },

    fetchFields: (layerId) =>
        apiRequest(`${ANNO_BASE_URL}/${layerId}/fields`),

    createField: (layerId, payload) =>
        apiRequest(`${ANNO_BASE_URL}/${layerId}/fields`, {
            method: "POST",
            body: JSON.stringify(payload),
        }),

    updateField: (layerId, fieldId, payload) =>
        apiRequest(`${ANNO_BASE_URL}/${layerId}/fields/${fieldId}`, {
            method: "PATCH",
            body: JSON.stringify(payload),
        }),

    deleteField: (layerId, fieldId) =>
        apiRequest(`${ANNO_BASE_URL}/${layerId}/fields/${fieldId}`, { method: "DELETE" }),

    /**
    * 导入 Shapefile 文件包
    * @param {string} layerId - 目标图层 ID
    * @param {FileList | File[]} files - 同时上传 .shp/.shx/.dbf（必须）+ .prj/.cpg（推荐）
    * @returns {{ imported: number, fields_registered: number, layer_id: string }}
    */
    async importShapefile(layerId, files) {
        const formData = new FormData();
        for (const file of files) {
            formData.append("files", file);  // 与后端 files: List[UploadFile] 对应
        }
        return await apiRequest(`${ANNO_BASE_URL}/layers/${layerId}/import/shapefile`, {
            method: "POST",
            headers: {},        // 覆盖掉 apiRequest 默认的 application/json
            body: formData,
        });
    },

    /**
     * 获取 MVT 矢量瓦片服务的 URL 模板
     * 增加时间戳参数防止由于标注更新导致的浏览器缓存不一致
     */
    getMvtUrlTemplate(layerId) {
        return `${VTILE_BASE_URL}/tiles/${layerId}/{z}/{x}/{y}.pbf?t=${Date.now()}`;
    }
};
