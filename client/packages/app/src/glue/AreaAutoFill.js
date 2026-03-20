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

import { VectorAPI } from '../api/vector.js';

/** WGS84 椭球体平均半径，单位：千米 */
const EARTH_RADIUS_KM = 6371.0;

/** 自动创建的面积字段名（与后端 field_name 对应） */
const AREA_FIELD_NAME = 'area';


/**
 * 将角度转换为弧度
 * @param {number} deg
 * @returns {number}
 */
function toRad(deg) {
    return deg * Math.PI / 180;
}

/**
 * 计算 WGS84 球面多边形面积（球面过剩公式）
 *
 * 算法：对多边形每条边，累加球面梯形面积（Girard 定理的离散近似）。
 * 参考：Robert G. Chamberlain & William H. Duquette (2007)
 *       "Some Algorithms for Polygons on a Sphere"
 *
 * @param {Array<[number, number]>} ring  - 坐标环，格式 [[lng, lat], ...]，首尾可以相同
 * @returns {number} 面积，单位：平方千米（始终为正值）
 */
function computeRingAreaKm2(ring) {
    const n = ring.length;
    if (n < 3) return 0;

    let area = 0;

    for (let i = 0; i < n - 1; i++) {
        const [lng1, lat1] = ring[i];
        const [lng2, lat2] = ring[i + 1];

        // Chamberlain-Duquette 球面梯形公式
        area += toRad(lng2 - lng1) * (2 + Math.sin(toRad(lat1)) + Math.sin(toRad(lat2)));
    }

    // 绝对值 / 2，再乘以 R²
    return Math.abs(area * EARTH_RADIUS_KM * EARTH_RADIUS_KM / 2);
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