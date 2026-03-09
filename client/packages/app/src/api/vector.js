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
    const defaultHeaders = { 'Content-Type': 'application/json' };
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
        throw error; // 向上抛出供 UI 层捕获
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

    /**
     * 获取 MVT 矢量瓦片服务的 URL 模板
     * 增加时间戳参数防止由于标注更新导致的浏览器缓存不一致
     */
    getMvtUrlTemplate(layerId) {
        return `${VTILE_BASE_URL}/tiles/${layerId}/{z}/{x}/{y}.pbf?t=${Date.now()}`;
    }
};
