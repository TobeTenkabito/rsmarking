const BASE_URL = window.location.origin;

/**
 * 构建 FormData，支持普通键值对与数组（自动展开为 id_1, id_2...）
 * @param {Record<string, any>} fields
 * @returns {FormData}
 */
function buildFormData(fields) {
  const fd = new FormData();
  for (const [key, value] of Object.entries(fields)) {
    if (value === null || value === undefined) continue;
    if (key === '__idList') {
      // 特殊约定：数组 ID 列表展开为 id_1, id_2...
      value.forEach((id, i) => fd.append(`id_${i + 1}`, id));
    } else {
      fd.append(key, String(value));
    }
  }
  return fd;
}

/**
 * 通用 fetch 封装，统一错误处理
 * @param {string} url
 * @param {RequestInit} options
 * @param {string} [errorMsg]
 * @returns {Promise<any>}
 */
async function request(url, options = {}, errorMsg = '请求失败') {
  const response = await fetch(url, options);
  if (!response.ok) {
    const err = await response.json().catch(() => ({}));
    throw new Error(err.detail ?? `${errorMsg}: ${response.status}`);
  }
  return response.json();
}

/**
 * 通用 POST FormData 封装
 * @param {string} path
 * @param {Record<string, any>} fields
 * @param {string} [errorMsg]
 */
async function postForm(path, fields, errorMsg) {
  return request(
    `${BASE_URL}${path}`,
    { method: 'POST', body: buildFormData(fields) },
    errorMsg
  );
}

/**
 * 通用 POST JSON 封装
 * @param {string} path
 * @param {object} payload
 * @param {string} [errorMsg]
 */
async function postJSON(path, payload, errorMsg) {
  return request(
    `${BASE_URL}${path}`,
    {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    },
    errorMsg
  );
}

/**
 * 构建掩膜提取通用参数对象
 * @param {number[]} bandIds
 * @param {string}   newName
 * @param {number}   threshold
 * @param {string}   mode
 */
function buildMaskFields(bandIds, newName, threshold, mode) {
  return {
    __idList: bandIds,
    new_name: newName,
    threshold,
    ...(mode ? { mode } : {}),
  };
}

/**
 * 构建指数计算通用参数对象
 * @param {Record<string, number>} ids  - 如 { red_id, nir_id }
 * @param {string} newName
 */
function buildIndexFields(ids, newName) {
  return { ...ids, new_name: newName };
}

export const RasterAPI = {

  /**
   * 获取所有影像列表
   * @returns {Promise<Array>}
   */
  async fetchAll() {
    try {
      return await request(`${BASE_URL}/list`, {}, '获取影像列表失败');
    } catch (error) {
      console.error('[RasterAPI] fetchAll Error:', error);
      return [];
    }
  },

  /**
   * 上传影像文件（支持进度回调）
   * @param {File}     file
   * @param {number|null} [bundleId]
   * @param {((percent: number) => void)|null} [onProgress]
   * @returns {Promise<any>}
   */
  async upload(file, bundleId = null, onProgress = null) {
    return new Promise((resolve, reject) => {
      const fd = new FormData();
      fd.append('file', file);
      if (bundleId != null) fd.append('bundle_id', String(bundleId));

      const xhr = new XMLHttpRequest();
      xhr.open('POST', `${BASE_URL}/upload`, true);

      if (onProgress && xhr.upload) {
        xhr.upload.onprogress = ({ lengthComputable, loaded, total }) => {
          if (lengthComputable) onProgress((loaded / total) * 100);
        };
      }

      xhr.onload = () => {
        if (xhr.status >= 200 && xhr.status < 300) {
          try {
            resolve(JSON.parse(xhr.responseText));
          } catch {
            resolve(xhr.responseText);
          }
        } else {
          reject(new Error(`上传失败: ${xhr.status}`));
        }
      };
      xhr.onerror = () => reject(new Error('网络错误，上传中断'));
      xhr.send(fd);
    });
  },

  /**
   * 删除指定影像
   * @param {number} indexId
   * @returns {Promise<boolean>}
   */
  async delete(indexId) {
    try {
      const response = await fetch(`${BASE_URL}/raster/${indexId}`, { method: 'DELETE' });
      return response.ok;
    } catch (error) {
      console.error('[RasterAPI] delete Error:', error);
      return false;
    }
  },

  /**
   * 合并波段
   * @param {number[]} rasterIds
   * @param {string}   newName
   */
  async mergeBands(rasterIds, newName) {
    return postForm('/merge-bands', { raster_ids: rasterIds, new_name: newName }, '合并波段失败');
  },

  /**
   * 提取波段
   * @param {number} rasterId     - 源文件 index_id
   * @param {string} bandIndices  - 波段索引，逗号分隔，如 "1,3"
   * @param {string} newName      - 输出文件名
   */
  async extractBands(rasterId, bandIndices, newName) {
    return postForm('/extract-bands', { raster_id: rasterId, band_indices: bandIndices, new_name: newName }, '提取波段失败');
  },

  /**
   * 计算 NDVI（归一化植被指数）
   * @param {number} redId
   * @param {number} nirId
   * @param {string} newName
   */
  async calculateNDVI(redId, nirId, newName) {
    return postForm('/calculate-ndvi', buildIndexFields({ red_id: redId, nir_id: nirId }, newName), '计算 NDVI 失败');
  },

  /**
   * 计算 NDWI（归一化水体指数）
   * @param {number} greenId
   * @param {number} nirId
   * @param {string} newName
   */
  async calculateNDWI(greenId, nirId, newName) {
    return postForm('/calculate-ndwi', buildIndexFields({ green_id: greenId, nir_id: nirId }, newName), '计算 NDWI 失败');
  },

  /**
   * 计算 NDBI（归一化建筑指数）
   * @param {number} swirId
   * @param {number} nirId
   * @param {string} newName
   */
  async calculateNDBI(swirId, nirId, newName) {
    return postForm('/calculate-ndbi', buildIndexFields({ swir_id: swirId, nir_id: nirId }, newName), '计算 NDBI 失败');
  },

  /**
   * 计算 MNDWI（改进归一化水体指数）
   * @param {number} greenId
   * @param {number} swirId
   * @param {string} newName
   */
  async calculateMNDWI(greenId, swirId, newName) {
    return postForm('/calculate-mndwi', buildIndexFields({ green_id: greenId, swir_id: swirId }, newName), '计算 MNDWI 失败');
  },

  /**
   * 提取植被掩膜
   * @param {number[]} bandIds
   * @param {string}   newName
   * @param {number}   [threshold=0.3]
   * @param {string}   [mode=""]
   */
  async extractVegetation(bandIds, newName, threshold = 0.3, mode = '') {
    return postForm('/extract-vegetation', buildMaskFields(bandIds, newName, threshold, mode), '提取植被掩膜失败');
  },

  /**
   * 提取水体掩膜
   * @param {number[]} bandIds
   * @param {string}   newName
   * @param {number}   [threshold=0.0]
   * @param {string}   [mode=""]
   */
  async extractWater(bandIds, newName, threshold = 0.0, mode = '') {
    return postForm('/extract-water', buildMaskFields(bandIds, newName, threshold, mode), '提取水体掩膜失败');
  },

  /**
   * 提取建筑掩膜
   * @param {number[]} bandIds
   * @param {string}   newName
   * @param {number}   [threshold=0.0]
   * @param {string}   [mode=""]
   */
  async extractBuildings(bandIds, newName, threshold = 0.0, mode = '') {
    return postForm('/extract-buildings', buildMaskFields(bandIds, newName, threshold, mode), '提取建筑掩膜失败');
  },

  /**
   * 提取云掩膜
   * @param {number[]} bandIds
   * @param {string}   newName
   * @param {number}   [threshold=0.0]
   * @param {string}   [mode=""]
   */
  async extractClouds(bandIds, newName, threshold = 0.0, mode = '') {
    return postForm('/extract-clouds', buildMaskFields(bandIds, newName, threshold, mode), '提取云掩膜失败');
  },

  /**
   * 调用后端栅格计算器
   * @param {string}              expression  - 计算表达式
   * @param {Record<string, any>} varMapping  - 变量映射，如 { var_A: 1, var_B: 2 }
   * @param {string}              newName
   */
  async runCalculator(expression, varMapping, newName) {
    return postForm(
      '/raster-calculator',
      { expression, new_name: newName, ...varMapping },
      '计算器执行失败'
    );
  },

  /**
   * 执行自定义脚本
   * @param {string}   script
   * @param {number[]} rasterIds
   * @param {string}   outputName
   */
  async executeScript(script, rasterIds, outputName) {
    return postForm(
      '/execute-script',
      { script, raster_ids: rasterIds.join(','), output_name: outputName },
      '脚本执行失败'
    );
  },

  /**
   * 获取脚本模板列表
   * @returns {Promise<Array>}
   */
  async getScriptTemplates() {
    try {
      return await request(`${BASE_URL}/script-templates`, {}, '获取脚本模板失败');
    } catch (error) {
      console.error('[RasterAPI] getScriptTemplates Error:', error);
      return [];
    }
  },

  /**
   * 获取某栅格的全部业务字段
   * @param {number} rasterId
   * @returns {Promise<Array>}
   */
  async getFields(rasterId) {
    try {
      return await request(`${BASE_URL}/raster/${rasterId}/fields`, {}, '获取字段列表失败');
    } catch (error) {
      console.error('[RasterAPI] getFields Error:', error);
      return [];
    }
  },

  /**
   * 新增业务字段
   * @param {number} rasterId
   * @param {{ field_name: string, field_alias?: string, field_type: string, field_order?: number, is_required?: boolean, default_val?: any }} fieldData
   */
  async createField(rasterId, fieldData) {
    return postJSON(`/raster/${rasterId}/fields`, fieldData, '新增字段失败');
  },

  /**
   * 修改业务字段
   * @param {number} rasterId
   * @param {number} fieldId
   * @param {{ field_alias?: string, field_type?: string, field_order?: number, is_required?: boolean, default_val?: any }} updates
   */
  async updateField(rasterId, fieldId, updates) {
    return request(
      `${BASE_URL}/raster/${rasterId}/fields/${fieldId}`,
      {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(updates),
      },
      '更新字段失败'
    );
  },

  /**
   * 删除业务字段（系统字段不可删除）
   * @param {number} rasterId
   * @param {number} fieldId
   * @returns {Promise<true>}
   */
  async deleteField(rasterId, fieldId) {
    await request(
      `${BASE_URL}/raster/${rasterId}/fields/${fieldId}`,
      { method: 'DELETE' },
      '删除字段失败'
    );
    return true;
  },

  /**
   * 用矢量多边形裁剪栅格，结果注册为新栅格记录走 COG 流程
   * @param {number}    rasterId
   * @param {string}    newName
   * @param {object[]}  geometries      - GeoJSON geometry 对象数组
   * @param {string}    [srcVectorCrs="EPSG:4326"]
   * @param {boolean}   [crop=true]     - false 则仅掩膜不裁边界
   * @param {number|null} [nodata=null] - 输出 nodata 值，null 则不传
   * @param {boolean}   [allTouched=false]
   * @returns {Promise<{ status: string, id: number, clip_meta: object }>}
   */
  async clipRasterByVector(
    rasterId,
    newName,
    geometries,
    srcVectorCrs = 'EPSG:4326',
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
      ...(nodata != null ? { nodata } : {}),
    };
    return postJSON('/clip-raster-by-vector', payload, '裁剪失败');
  },

  /**
   * 查询指定影像在某 WGS84 坐标点的各波段像素值（光谱）
   * @param {number} rasterId
   * @param {number} lng  - 经度 (WGS84)
   * @param {number} lat  - 纬度 (WGS84)
   * @returns {Promise<{
   *   bands: Array<{ index: number, name: string, value: number|null }>,
   *   has_nodata: boolean,
   *   coordinate: { lng: number, lat: number }
   * } | null>}
   */
  async querySpectrum(rasterId, lng, lat) {
    try {
      const params = new URLSearchParams({ lng, lat });
      return await request(`${BASE_URL}/raster/${rasterId}/spectrum?${params}`, {}, '光谱查询失败');
    } catch (error) {
      console.error('[RasterAPI] querySpectrum Error:', error);
      return null;
    }
  },

  /** 清空数据库（仅调试用） */
  async clearDB() {
    return fetch(`${BASE_URL}/debug/clear-db`);
  },
};