const BASE_URL = window.location.origin;

/**
 * ChangeAPI — 变化检测接口
 * 对应后端 change_router.py（prefix: /change）
 *
 * 响应结构（ChangeDetectResponse）:
 * {
 *   diff_index_id      : number,   // 差值图 index_id，可直接传入 RasterModule 加载
 *   mask_index_id      : number | null,  // 二值掩膜 index_id
 *   method             : string,
 *   change_pixel_count : number | null,
 *   change_area_ratio  : number | null,  // 变化像元占比 0~1
 * }
 */
export const ChangeAPI = {

  /**
   * 内部：统一 JSON POST 请求
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
      throw new Error(err.detail ?? `变化检测请求失败: ${response.status}`);
    }
    return await response.json();
  },

  // ─────────────────────────────────────────────
  // 单波段差值法
  // ─────────────────────────────────────────────

  /**
   * 单波段差值变化检测  →  POST /change/band-diff
   *
   * @param {number}  indexIdT1       - 早期影像 index_id
   * @param {number}  indexIdT2       - 晚期影像 index_id
   * @param {object}  [opts]
   * @param {number}  [opts.bandIdx=1]              - 使用的波段（1-based）
   * @param {number}  [opts.threshold=0.1]          - 变化判定阈值
   * @param {string}  [opts.thresholdMode="abs"]    - abs / positive / negative
   * @param {boolean} [opts.outputMask=true]        - 是否输出二值掩膜
   * @returns {Promise<ChangeDetectResponse>}
   *
   * @example
   * const result = await ChangeAPI.bandDiff(1001, 1002, { threshold: 0.15 });
   * // result.diff_index_id → 加载差值图
   * // result.mask_index_id → 加载变化掩膜
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

  // ─────────────────────────────────────────────
  // 单波段比值法
  // ─────────────────────────────────────────────

  /**
   * 单波段比值变化检测  →  POST /change/band-ratio
   *
   * 比值偏离 1.0 超过 threshold 视为变化，可消除光照差异影响。
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

  // ─────────────────────────────────────────────
  // 指数差值法（NDVI / NDWI / NDBI / MNDWI）
  // ─────────────────────────────────────────────

  /**
   * 指数差值变化检测  →  POST /change/index-diff
   *
   * 各 index_type 的波段约定（b1 / b2）:
   *   ndvi  : b1=Red,   b2=NIR
   *   ndwi  : b1=Green, b2=NIR
   *   ndbi  : b1=SWIR,  b2=NIR
   *   mndwi : b1=Green, b2=SWIR
   *
   * @param {object} t1Bands               - 早期影像波段 index_id
   * @param {number} t1Bands.b1            - 早期波段1 index_id
   * @param {number} t1Bands.b2            - 早期波段2 index_id
   * @param {object} t2Bands               - 晚期影像波段 index_id
   * @param {number} t2Bands.b1            - 晚期波段1 index_id
   * @param {number} t2Bands.b2            - 晚期波段2 index_id
   * @param {object} [opts]
   * @param {string} [opts.indexType="ndvi"]         - ndvi / ndwi / ndbi / mndwi
   * @param {number} [opts.threshold=0.15]
   * @param {string} [opts.thresholdMode="abs"]      - abs / positive / negative
   * @param {boolean}[opts.outputMask=true]
   * @returns {Promise<ChangeDetectResponse>}
   *
   * @example
   * // 检测植被变化（NDVI 差值）
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