import { API_CONFIG } from './config.js';

const BASE_URL = API_CONFIG.dataServiceUrl;

/**
 * ChangeAPI — Change detection API
 * Backend endpoint change_router.py（prefix: /change）
 *
 * Response shape（ChangeDetectResponse）:
 * {
 *   diff_index_id      : number,   // difference raster index_id，can be loaded directly by RasterModule
 *   mask_index_id      : number | null,  // binary mask index_id
 *   method             : string,
 *   change_pixel_count : number | null,
 *   change_area_ratio  : number | null,  // changed-pixel ratio 0~1
 * }
 */
export const ChangeAPI = {

  /**
   * Internal shared JSON POST request
   * @param {string} endpoint
   * @param {object} payload
   * @returns {Promise<object>}
   */
  async _post(endpoint, payload) {
    const response = await fetch(`${BASE_URL}/change/${endpoint}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    if (!response.ok) {
      const err = await response.json().catch(() => ({}));
      throw new Error(err.detail ?? `Change detection request failed: ${response.status}`);
    }
    return await response.json();
  },


  /**
   * Single-band difference change detection  →  POST /change/band-diff
   *
   * @param {number}  indexIdT1       - earlier image index_id
   * @param {number}  indexIdT2       - later image index_id
   * @param {object}  [opts]
   * @param {number}  [opts.bandIdx=1]              - selected band（1-based）
   * @param {number}  [opts.threshold=0.1]          - change threshold
   * @param {string}  [opts.thresholdMode="abs"]    - abs / positive / negative
   * @param {boolean} [opts.outputMask=true]        - whether to output a binary mask
   * @returns {Promise<ChangeDetectResponse>}
   *
   * @example
   * const result = await ChangeAPI.bandDiff(1001, 1002, { threshold: 0.15 });
   * // result.diff_index_id → load difference raster
   * // result.mask_index_id → load change mask
   */
  async bandDiff(indexIdT1, indexIdT2, opts = {}) {
    const {
      bandIdx = 1,
      threshold = 0.1,
      thresholdMode = "abs",
      outputMask = true,
    } = opts;

    return this._post("band-diff", {
      index_id_t1:    indexIdT1,
      index_id_t2:    indexIdT2,
      band_idx:       bandIdx,
      threshold:      threshold,
      threshold_mode: thresholdMode,
      output_mask:    outputMask,
    });
  },


  /**
   * Single-band ratio change detection  →  POST /change/band-ratio
   *
   * Ratios that deviate from 1.0 beyond the threshold are treated as changes, reducing lighting effects.
   *
   * @param {number}  indexIdT1
   * @param {number}  indexIdT2
   * @param {object}  [opts]
   * @param {number}  [opts.bandIdx=1]
   * @param {number}  [opts.threshold=0.2]
   * @param {boolean} [opts.outputMask=true]
   * @returns {Promise<ChangeDetectResponse>}
   *
   * @example
   * const result = await ChangeAPI.bandRatio(1001, 1002);
   */
  async bandRatio(indexIdT1, indexIdT2, opts = {}) {
    const {
      bandIdx = 1,
      threshold = 0.2,
      outputMask = true,
    } = opts;

    return this._post("band-ratio", {
      index_id_t1: indexIdT1,
      index_id_t2: indexIdT2,
      band_idx:    bandIdx,
      threshold:   threshold,
      output_mask: outputMask,
    });
  },


  /**
   * Index-difference change detection  →  POST /change/index-diff
   *
   * Band conventions for each index_type（b1 / b2）:
   *   ndvi  : b1=Red,   b2=NIR
   *   ndwi  : b1=Green, b2=NIR
   *   ndbi  : b1=SWIR,  b2=NIR
   *   mndwi : b1=Green, b2=SWIR
   *
   * @param {object} t1Bands               - earlier image bands index_id
   * @param {number} t1Bands.b1            - earlier band1 index_id
   * @param {number} t1Bands.b2            - earlier band2 index_id
   * @param {object} t2Bands               - later image bands index_id
   * @param {number} t2Bands.b1            - later band1 index_id
   * @param {number} t2Bands.b2            - later band2 index_id
   * @param {object} [opts]
   * @param {string} [opts.indexType="ndvi"]         - ndvi / ndwi / ndbi / mndwi
   * @param {number} [opts.threshold=0.15]
   * @param {string} [opts.thresholdMode="abs"]      - abs / positive / negative
   * @param {boolean}[opts.outputMask=true]
   * @returns {Promise<ChangeDetectResponse>}
   *
   * @example
   * // Detect vegetation change（NDVI English）
   * const result = await ChangeAPI.indexDiff(
   *   { b1: redT1Id, b2: nirT1Id },
   *   { b1: redT2Id, b2: nirT2Id },
   *   { indexType: "ndvi", threshold: 0.2, thresholdMode: "negative" }
   * );
   */
  async indexDiff(t1Bands, t2Bands, opts = {}) {
    const {
      indexType = "ndvi",
      threshold = 0.15,
      thresholdMode = "abs",
      outputMask = true,
    } = opts;

    return this._post("index-diff", {
      index_id_t1_b1: t1Bands.b1,
      index_id_t1_b2: t1Bands.b2,
      index_id_t2_b1: t2Bands.b1,
      index_id_t2_b2: t2Bands.b2,
      index_type:     indexType,
      threshold:      threshold,
      threshold_mode: thresholdMode,
      output_mask:    outputMask,
    });
  },
};
