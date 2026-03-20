/**
 * AreaAutoFill - 面积自动填充胶水层
 *
 * 职责：
 *   绘制完成后，自动为该矢量图层确保存在 "area" 字段，
 *   并将当前要素的 WGS84 球面面积（单位：平方千米）写入该字段。
 *
 * 依赖：
 *   - VectorAPI.fetchFields(layerId)
 *   - VectorAPI.createField(layerId, payload)
 *   - VectorAPI.updateFeature(featureId, updateData)
 *
 * 不依赖任何第三方库，面积计算使用球面过剩公式（Spherical Excess）。
 */

/** WGS84 椭球体参数 */
const WGS84_A = 6378.137;             // 长半轴，单位：千米
const WGS84_B = 6356.752314245;       // 短半轴，单位：千米
const E2 = 1 - (WGS84_B * WGS84_B) / (WGS84_A * WGS84_A); // 偏心率平方
const E = Math.sqrt(E2);              // 第一偏心率

/**
 * 计算 WGS84 等面积积分 q(phi)
 * @param {number} sinPhi 纬度的正弦值
 * @returns {number}
 */
function qFunc(sinPhi) {
    const eSinPhi = E * sinPhi;
    const term1 = sinPhi / (1 - eSinPhi * eSinPhi);
    const term2 = (1 / (2 * E)) * Math.log((1 - eSinPhi) / (1 + eSinPhi));
    return (1 - E2) * (term1 - term2);
}

// 极点处的 q 值及等面积球半径
const Q_P = qFunc(1.0);
const R_Q = WGS84_A * Math.sqrt(Q_P / 2); // 约 6371.00718 km

/**
 * 将几何纬度转换为等面积纬度的正弦值 (sin(beta))
 * @param {number} latDeg 纬度（度）
 * @returns {number}
 */
function getAuthalicSinLat(latDeg) {
    const latRad = toRad(latDeg);
    return qFunc(Math.sin(latRad)) / Q_P;
}

/**
 * 计算 WGS84 椭球面多边形面积（基于等面积球的球面过剩公式）
 * 复杂度：O(N)
 */
function computeRingAreaKm2(ring) {
    const n = ring.length;
    if (n < 3) return 0;

    let area = 0;

    for (let i = 0; i < n - 1; i++) {
        const [lng1, lat1] = ring[i];
        const [lng2, lat2] = ring[i + 1];

        // 核心修改：使用等面积纬度的正弦值替代原有理想球体的正弦值
        const sinBeta1 = getAuthalicSinLat(lat1);
        const sinBeta2 = getAuthalicSinLat(lat2);

        area += toRad(lng2 - lng1) * (2 + sinBeta1 + sinBeta2);
    }

    // 使用严密等效半径 R_Q 计算最终面积
    return Math.abs(area * R_Q * R_Q / 2);
}

/**
 * 计算 GeoJSON Geometry 的球面面积
 *
 * 支持：Polygon、MultiPolygon
 * 不支持（返回 0）：Point、LineString 等非面类型
 *
 * 对于带洞的多边形：外环面积 - 内环面积之和
 *
 * @param {Object} geometry - GeoJSON Geometry 对象
 * @returns {number} 面积，单位：平方千米
 */
function computeSphericalAreaKm2(geometry) {
    if (!geometry || !geometry.type) return 0;

    switch (geometry.type) {
        case 'Polygon': {
            const rings = geometry.coordinates;
            if (!rings || rings.length === 0) return 0;

            // 外环面积
            let area = computeRingAreaKm2(rings[0]);

            // 减去内环（洞）面积
            for (let i = 1; i < rings.length; i++) {
                area -= computeRingAreaKm2(rings[i]);
            }

            return Math.max(0, area);
        }

        case 'MultiPolygon': {
            return geometry.coordinates.reduce((sum, polygon) => {
                const rings = polygon;
                if (!rings || rings.length === 0) return sum;

                let polyArea = computeRingAreaKm2(rings[0]);
                for (let i = 1; i < rings.length; i++) {
                    polyArea -= computeRingAreaKm2(rings[i]);
                }

                return sum + Math.max(0, polyArea);
            }, 0);
        }

        default:
            // Point / LineString / GeometryCollection 等无面积类型
            return 0;
    }
}

/**
 * 确保图层存在 "area" 字段定义。
 *
 * 策略：先拉取字段列表，若已存在同名字段则直接返回其 id，
 *       否则调用 createField 创建后返回新字段 id。
 *
 * @param {string} layerId
 * @returns {Promise<string>} area 字段的 id
 */
async function ensureAreaField(layerId) {
    const fields = await VectorAPI.fetchFields(layerId);

    const existing = fields.find(f => f.field_name === AREA_FIELD_NAME);
    if (existing) {
        return existing.id;
    }

    // 字段不存在，创建之
    const newField = await VectorAPI.createField(layerId, {
        field_name : AREA_FIELD_NAME,
        field_alias: '面积(km²)',
        field_type : 'number',
        field_order: fields.length,   // 追加到末尾
    });

    return newField.id;
}

/**
 * 将面积值写入要素的 properties。
 *
 * 使用 PATCH /features/{featureId}，后端做 JSONB merge，
 * 不会覆盖其他已有属性。
 *
 * @param {string} featureId
 * @param {number} areaKm2
 * @returns {Promise<void>}
 */
async function writeAreaToFeature(featureId, areaKm2) {
    await VectorAPI.updateFeature(featureId, {
        properties: {
            [AREA_FIELD_NAME]: areaKm2
        }
    });
}

export const AreaAutoFill = {

    /**
     * 绘制完成后的主入口。
     *
     * 调用方（AnnotationModule）在 createFeature 成功后调用此方法，
     * 传入图层 ID、新要素 ID 和 GeoJSON geometry 对象。
     *
     * 此方法内部的失败不会向上抛出，仅打印警告，
     * 确保面积写入失败不影响主绘制流程。
     *
     * @param {string} layerId     - 当前矢量图层 ID
     * @param {string} featureId   - 刚创建的要素 ID
     * @param {Object} geometry    - GeoJSON Geometry（来自 layer.toGeoJSON().geometry）
     * @returns {Promise<void>}
     */
    async run(layerId, featureId, geometry) {
    console.log('[DEBUG] AreaAutoFill.run 已进入', layerId, featureId, geometry);
        try {
            // Step 1: 计算球面面积
            const areaKm2 = computeSphericalAreaKm2(geometry);

            // 非面类型（点、线）直接跳过，不写入
            if (areaKm2 === 0) {
                console.log('[AreaAutoFill] 非面类型要素，跳过面积写入');
                return;
            }

            // 保留 6 位有效数字，避免浮点噪声
            const areaRounded = parseFloat(areaKm2.toFixed(6));

            // Step 2: 确保 area 字段存在（幂等操作）
            await ensureAreaField(layerId);

            // Step 3: 将面积写入要素属性
            await writeAreaToFeature(featureId, areaRounded);

            console.log(`[AreaAutoFill] 面积写入成功 → featureId=${featureId}, area=${areaRounded} km²`);

        } catch (err) {
            // 面积写入失败不阻断主流程
            console.warn('[AreaAutoFill] 面积自动填充失败（不影响要素保存）:', err);
        }
    }
};