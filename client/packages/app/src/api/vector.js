/**
 * VectorAPI - EnglishVectorEnglish (8001) English VectorEnglish (8003) English
 */

import { API_CONFIG } from './config.js';

const ANNO_BASE_URL = API_CONFIG.annotationServiceUrl;
const VTILE_BASE_URL = API_CONFIG.vectorTileServiceUrl;

/**
 * English Fetch English
 * English Content-Type、English API English
 */
async function apiRequest(url, options = {}) {
    // FormData English Content-Type，English boundary
    const isFormData = options.body instanceof FormData;
    const defaultHeaders = isFormData ? {} : { 'Content-Type': 'application/json' };

    const config = {
        ...options,
        headers: { ...defaultHeaders, ...options.headers }
    };

    try {
        const response = await fetch(url, config);

        // EnglishActionsSucceededEnglish 204 returns
        if (response.status === 204) return true;

        const data = await response.json();

        if (!response.ok) {
            // English FastAPI English HTTPException English
            const errorMsg = data.detail || `Request failed: ${response.status}`;
            throw new Error(errorMsg);
        }

        return data;
    } catch (error) {
        if (error.name !== 'AbortError') {
            console.error(`[VectorAPI Error] Endpoint: ${url}`, error);
        }
        throw error;
    }
}

export const VectorAPI = {

    /**
     * EnglishAnnotation Project
     */
    async fetchProjects() {
        return await apiRequest(`${ANNO_BASE_URL}/projects`);
    },

    /**
     * EnglishProject
     */
    async createProject(name) {
        return await apiRequest(`${ANNO_BASE_URL}/projects`, {
            method: 'POST',
            body: JSON.stringify({ name })
        });
    },

    /**
     * EnglishProjectEnglish
     */
    async fetchLayers(projectId) {
        return await apiRequest(`${ANNO_BASE_URL}/projects/${projectId}/layers`);
    },

    /**
     * 【English/English】EnglishProjectEnglish
     */
    async deleteAllProjects() {
        return await apiRequest(`${ANNO_BASE_URL}/projects`, {
            method: 'DELETE'
        });
    },

    /**
     * EnglishAnnotation Layers (English index_id)
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
     * English BBox English (English)
     * @param {string} layerId
     * @param {Array} bbox - [minx, miny, maxx, maxy]
     */
    async fetchFeaturesInBbox(layerId, bbox, options = {}) {
        const [minx, miny, maxx, maxy] = bbox;
        const query = `minx=${minx}&miny=${miny}&maxx=${maxx}&maxy=${maxy}`;
        return await apiRequest(`${ANNO_BASE_URL}/layers/${layerId}/features?${query}`, options);
    },

    /**
     * English
     * @param {string} layerId
     * @param {Object} geojsonGeometry - Standard GeoJSON geometry object
     * @param {Object} properties - English (category, confidenceEnglish)
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
     * English
     */
    async getFeature(featureId) {
        return await apiRequest(`${ANNO_BASE_URL}/features/${featureId}`);
    },

    /**
     * English (English)
     */
    async updateFeature(featureId, updateData) {
        return await apiRequest(`${ANNO_BASE_URL}/features/${featureId}`, {
            method: 'PATCH',
            body: JSON.stringify(updateData)
        });
    },

    /**
     * Delete feature
     */
    async deleteFeature(featureId) {
        return await apiRequest(`${ANNO_BASE_URL}/features/${featureId}`, {
            method: 'DELETE'
        });
    },

    /**
     * Delete layer
     */
    async deleteLayer(layerID){
        return await apiRequest(`${ANNO_BASE_URL}/layers/${layerID}`,{
        method: 'DELETE'
        });
    },

    /**
     * English (English AI English ExtractionModule)
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
    * Import Shapefile English
    * @param {string} layerId - English ID
    * @param {FileList | File[]} files - English .shp/.shx/.dbf（English）+ .prj/.cpg（English）
    * @returns {{ imported: number, fields_registered: number, layer_id: string }}
    */
    async importShapefile(layerId, files) {
        const formData = new FormData();
        for (const file of files) {
            formData.append("files", file);  // Matches backend files: List[UploadFile]
        }
        return await apiRequest(`${ANNO_BASE_URL}/layers/${layerId}/import/shapefile`, {
            method: "POST",
            headers: {},        // Override apiRequest's default application/json header
            body: formData,
        });
    },

    /**
     * English MVT VectorEnglish URL English
     * English
     */
    getMvtUrlTemplate(layerId) {
        return `${VTILE_BASE_URL}/tiles/${layerId}/{z}/{x}/{y}.pbf?t=${Date.now()}`;
    },

    /**
     * EnglishVectorEnglish，EnglishActions，Englishreturns GeoJSON FeatureCollection
     *
     * @param {GeoJSON.Geometry} clipGeometry
     *   English GeoJSON Geometry object，CRSEnglish EPSG:4326。
     *   English：
     *     - Rectangle：EnglishCallerEnglish boundsToGeometry(bounds_wgs84) English
     *     - EnglishPolygon：English geometry
     *     - EnglishVectorEnglish：English feature.geometry
     *
     * @param {Array}   features       - GeoJSON Feature objectEnglish
     * @param {string}  [srcVectorCrs] - VectorEnglish CRS，English "EPSG:4326"
     * @param {string}  [mode]         - English: "intersects" | "within" | "clip"
     * @returns {Promise<GeoJSON.FeatureCollection>}
     */
    async clipVectorByGeometry(
        clipGeometry,
        features,
        srcVectorCrs = "EPSG:4326",
        mode = "intersects",
    ) {
        return await apiRequest(`${ANNO_BASE_URL}/spatial/clip-vector-by-raster`, {
            method: 'POST',
            body: JSON.stringify({
                clip_geometry: clipGeometry,
                features,
                src_vector_crs: srcVectorCrs,
                mode,
            }),
        });
    },
};
