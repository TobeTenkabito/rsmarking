const BASE_URL = window.location.origin;


function buildFormData(fields) {
  const fd = new FormData();
  for (const [key, value] of Object.entries(fields)) {
    if (value === null || value === undefined) continue;
    if (key === '__idList') {
      value.forEach((id, i) => fd.append(`id_${i + 1}`, id));
    } else {
      fd.append(key, String(value));
    }
  }
  return fd;
}


async function request(url, options = {}, errorMsg = 'Request failed') {
  const response = await fetch(url, options);
  if (!response.ok) {
    const err = await response.json().catch(() => ({}));
    throw new Error(err.detail ?? `${errorMsg}: ${response.status}`);
  }
  return response.json();
}


async function requestBlob(path, options = {}, errorMsg = 'Request failed') {
  const response = await fetch(`${BASE_URL}${path}`, options);
  if (!response.ok) {
    const err = await response.clone().json().catch(async () => ({
      detail: await response.text().catch(() => ''),
    }));
    throw new Error(err.detail ?? `${errorMsg}: ${response.status}`);
  }
  const blob = await response.blob();
  return {
    blob,
    filename: filenameFromDisposition(response.headers.get('content-disposition')),
  };
}


function filenameFromDisposition(header) {
  if (!header) return null;

  const utf8Match = header.match(/filename\*=UTF-8''([^;]+)/i);
  if (utf8Match?.[1]) {
    try {
      return decodeURIComponent(utf8Match[1].trim().replace(/^"|"$/g, ''));
    } catch {
      return utf8Match[1].trim().replace(/^"|"$/g, '');
    }
  }

  const plainMatch = header.match(/filename="?([^";]+)"?/i);
  return plainMatch?.[1] ?? null;
}


async function postForm(path, fields, errorMsg) {
  return request(
    `${BASE_URL}${path}`,
    { method: 'POST', body: buildFormData(fields) },
    errorMsg
  );
}


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


function buildMaskFields(bandIds, newName, threshold, mode) {
  return {
    __idList: bandIds,
    new_name: newName,
    threshold,
    ...(mode ? { mode } : {}),
  };
}


function buildIndexFields(ids, newName) {
  return { ...ids, new_name: newName };
}


export const RasterAPI = {
  async fetchAll() {
    try {
      return await request(`${BASE_URL}/list`, {}, 'Failed to fetch raster list');
    } catch (error) {
      console.error('[RasterAPI] fetchAll Error:', error);
      return [];
    }
  },

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
          reject(new Error(`Upload failed: ${xhr.status}`));
        }
      };
      xhr.onerror = () => reject(new Error('Network error while uploading'));
      xhr.send(fd);
    });
  },

  async delete(indexId) {
    try {
      const response = await fetch(`${BASE_URL}/raster/${indexId}`, { method: 'DELETE' });
      return response.ok;
    } catch (error) {
      console.error('[RasterAPI] delete Error:', error);
      return false;
    }
  },

  async mergeBands(rasterIds, newName) {
    return postForm('/merge-bands', { raster_ids: rasterIds, new_name: newName }, 'Band merge failed');
  },

  async extractBands(rasterId, bandIndices, newName) {
    return postForm(
      '/extract-bands',
      { raster_id: rasterId, band_indices: bandIndices, new_name: newName },
      'Band extraction failed'
    );
  },

  async calculateNDVI(redId, nirId, newName) {
    return postForm('/calculate-ndvi', buildIndexFields({ red_id: redId, nir_id: nirId }, newName), 'NDVI failed');
  },

  async calculateNDWI(greenId, nirId, newName) {
    return postForm('/calculate-ndwi', buildIndexFields({ green_id: greenId, nir_id: nirId }, newName), 'NDWI failed');
  },

  async calculateNDBI(swirId, nirId, newName) {
    return postForm('/calculate-ndbi', buildIndexFields({ swir_id: swirId, nir_id: nirId }, newName), 'NDBI failed');
  },

  async calculateMNDWI(greenId, swirId, newName) {
    return postForm('/calculate-mndwi', buildIndexFields({ green_id: greenId, swir_id: swirId }, newName), 'MNDWI failed');
  },

  async extractVegetation(bandIds, newName, threshold = 0.3, mode = '') {
    return postForm('/extract-vegetation', buildMaskFields(bandIds, newName, threshold, mode), 'Vegetation extraction failed');
  },

  async extractWater(bandIds, newName, threshold = 0.0, mode = '') {
    return postForm('/extract-water', buildMaskFields(bandIds, newName, threshold, mode), 'Water extraction failed');
  },

  async extractBuildings(bandIds, newName, threshold = 0.0, mode = '') {
    return postForm('/extract-buildings', buildMaskFields(bandIds, newName, threshold, mode), 'Building extraction failed');
  },

  async extractClouds(bandIds, newName, threshold = 0.0, mode = '') {
    return postForm('/extract-clouds', buildMaskFields(bandIds, newName, threshold, mode), 'Cloud extraction failed');
  },

  async runCalculator(expression, varMapping, newName) {
    return postForm(
      '/raster-calculator',
      { expression, new_name: newName, ...varMapping },
      'Raster calculator failed'
    );
  },

  async executeScript(script, rasterIds, outputName) {
    return postForm(
      '/execute-script',
      { script, raster_ids: rasterIds.join(','), output_name: outputName },
      'Script execution failed'
    );
  },

  async getScriptTemplates() {
    try {
      return await request(`${BASE_URL}/script-templates`, {}, 'Failed to fetch script templates');
    } catch (error) {
      console.error('[RasterAPI] getScriptTemplates Error:', error);
      return [];
    }
  },

  async getFields(rasterId) {
    try {
      return await request(`${BASE_URL}/raster/${rasterId}/fields`, {}, 'Failed to fetch raster fields');
    } catch (error) {
      console.error('[RasterAPI] getFields Error:', error);
      return [];
    }
  },

  async createField(rasterId, fieldData) {
    return postJSON(`/raster/${rasterId}/fields`, fieldData, 'Failed to create raster field');
  },

  async updateField(rasterId, fieldId, updates) {
    return request(
      `${BASE_URL}/raster/${rasterId}/fields/${fieldId}`,
      {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(updates),
      },
      'Failed to update raster field'
    );
  },

  async deleteField(rasterId, fieldId) {
    await request(
      `${BASE_URL}/raster/${rasterId}/fields/${fieldId}`,
      { method: 'DELETE' },
      'Failed to delete raster field'
    );
    return true;
  },

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
    return postJSON('/clip-raster-by-vector', payload, 'Clip failed');
  },

  async querySpectrum(rasterId, lng, lat) {
    try {
      const params = new URLSearchParams({ lng, lat });
      return await request(`${BASE_URL}/raster/${rasterId}/spectrum?${params}`, {}, 'Spectrum query failed');
    } catch (error) {
      console.error('[RasterAPI] querySpectrum Error:', error);
      return null;
    }
  },

  async getStatistics(rasterId, options = {}) {
    const params = new URLSearchParams({
      bins: String(options.bins ?? 32),
      max_size: String(options.maxSize ?? 768),
    });
    if (Array.isArray(options.bands) && options.bands.length > 0) {
      params.set('bands', options.bands.join(','));
    }
    return request(
      `${BASE_URL}/raster/${rasterId}/statistics?${params}`,
      {},
      'Raster statistics failed'
    );
  },

  async clearDB() {
    return request(`${BASE_URL}/debug/clear-db`, {}, 'Failed to clear raster database');
  },

  async exportWorkspaceFile(payload) {
    return requestBlob(
      '/export/workspace-file',
      {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      },
      'Workspace file export failed'
    );
  },
};
