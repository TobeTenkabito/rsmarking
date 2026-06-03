/**
 * AreaAutoFill - area autofill integration layer
 *
 * Responsibilities：
 *   After drawing, ensure that the vector layer has an area field，
 *   and write the WGS84 spherical area in square kilometers to that field。
 *
 * Dependencies：
 *   - VectorAPI.fetchFields(layerId)
 *   - VectorAPI.createField(layerId, payload)
 *   - VectorAPI.updateFeature(featureId, updateData)
 *
 * No third-party dependencies; area uses the spherical excess formula（Spherical Excess）。
 */
import { VectorAPI } from '../api/vector.js';

/** WGS84 ellipsoid parameters */
const WGS84_A = 6378.137;             // semi-major axis in kilometers
const WGS84_B = 6356.752314245;       // semi-minor axis in kilometers
const E2 = 1 - (WGS84_B * WGS84_B) / (WGS84_A * WGS84_A); // eccentricity squared
const E = Math.sqrt(E2);              // first eccentricity
const AREA_FIELD_NAME = 'area';

/**
 * Compute WGS84 equal-area integral q(phi)
 * @param {number} sinPhi sine of latitude
 * @returns {number}
 */
function qFunc(sinPhi) {
    const eSinPhi = E * sinPhi;
    const term1 = sinPhi / (1 - eSinPhi * eSinPhi);
    const term2 = (1 / (2 * E)) * Math.log((1 - eSinPhi) / (1 + eSinPhi));
    return (1 - E2) * (term1 - term2);
}

// value at the pole and equal-area radius q English
const Q_P = qFunc(1.0);
const R_Q = WGS84_A * Math.sqrt(Q_P / 2); // about 6371.00718 km

/**
 * Convert degrees to radians
 * @param {number} deg
 * @returns {number}
 */
function toRad(deg) {
    return deg * Math.PI / 180;
}

/**
 * Convert geodetic latitude to equal-area latitude sine (sin(beta))
 * @param {number} latDeg latitude（English）
 * @returns {number}
 */
function getAuthalicSinLat(latDeg) {
    const latRad = toRad(latDeg);
    return qFunc(Math.sin(latRad)) / Q_P;
}

/**
 * Compute WGS84 ellipsoidal polygon area（based on an equal-area sphere and spherical excess）
 * Complexity：O(N)
 */
function computeRingAreaKm2(ring) {
    const n = ring.length;
    if (n < 3) return 0;

    let area = 0;

    for (let i = 0; i < n - 1; i++) {
        const [lng1, lat1] = ring[i];
        const [lng2, lat2] = ring[i + 1];

        // Use equal-area latitude sine instead of ideal-sphere sine
        const sinBeta1 = getAuthalicSinLat(lat1);
        const sinBeta2 = getAuthalicSinLat(lat2);

        area += toRad(lng2 - lng1) * (2 + sinBeta1 + sinBeta2);
    }

    // Use the equivalent radius R_Q for the final area
    return Math.abs(area * R_Q * R_Q / 2);
}

/**
 * Compute spherical area for GeoJSON geometry
 *
 * Supports：Polygon、MultiPolygon
 * Unsupported（returns 0）：Point、LineString Englishnon-polygon type
 *
 * For polygons with holes：outer ring area - sum of inner ring areas
 *
 * @param {Object} geometry - GeoJSON Geometry object
 * @returns {number} area in square kilometers
 */
function computeSphericalAreaKm2(geometry) {
    if (!geometry || !geometry.type) return 0;

    switch (geometry.type) {
        case 'Polygon': {
            const rings = geometry.coordinates;
            if (!rings || rings.length === 0) return 0;

            // outer ring area
            let area = computeRingAreaKm2(rings[0]);

            // subtract inner-ring hole area
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
            // Point / LineString / GeometryCollection non-area geometry types
            return 0;
    }
}

/**
 * Ensure the layer has an area field definition.
 *
 * Strategy: fetch fields first; return the existing field id when present,
 *       otherwise create the field and return the new id.
 *
 * @param {string} layerId
 * @returns {Promise<string>} area English id
 */
async function ensureAreaField(layerId) {
    const fields = await VectorAPI.fetchFields(layerId);

    const existing = fields.find(f => f.field_name === AREA_FIELD_NAME);
    if (existing) {
        return existing.id;
    }

    // Create the field when it is missing
    const newField = await VectorAPI.createField(layerId, {
        field_name : AREA_FIELD_NAME,
        field_alias: 'Area (km2)',
        field_type : 'number',
        field_order: fields.length,   // append to the end
    });

    return newField.id;
}

/**
 * Write the area value into feature properties.
 *
 * Use PATCH /features/{featureId}，English JSONB merge，
 * Existing properties are not overwritten.
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

/**
 * Compute spherical area for a circle（spherical cap formula，English R_Q）
 * @param {number} radiusMeters - circle radius in meters
 * @returns {number} area in square kilometers
 */
function computeCircleAreaKm2(radiusMeters) {
    const r = radiusMeters / 1000; // convert to kilometers
    // spherical cap area formula：A = 2πR²(1 - cos(r/R))
    return 2 * Math.PI * R_Q * R_Q * (1 - Math.cos(r / R_Q));
}

export const AreaAutoFill = {

    /**
     * Main entry point after drawing completes.
     *
     * Caller（AnnotationModule）calls this after createFeature succeeds，
     * passing layer ID, new feature ID, and GeoJSON geometry.
     *
     * Failures inside this method are logged only，
     * so area write failure does not affect drawing.
     *
     * @param {string} layerId     - current vector layer ID
     * @param {string} featureId   - newly created feature ID
     * @param {Object} geometry    - GeoJSON Geometry（from layer.toGeoJSON().geometry）
     * @returns {Promise<void>}
     */
    async run(layerId, featureId, geometry, properties = {}) {
    console.log('[DEBUG] AreaAutoFill.run entered', layerId, featureId, geometry);
    try {
        let areaKm2 = 0;

        const isCircle =
            geometry?.type === 'Point' &&
            properties?.draw_type === 'circle' &&
            typeof properties?.radius_meters === 'number';

        if (isCircle) {
            areaKm2 = computeCircleAreaKm2(properties.radius_meters);
        } else {
            areaKm2 = computeSphericalAreaKm2(geometry);
        }

        // non-polygon type（normal points and lines）skip directly
        if (areaKm2 === 0) {
            console.log('[AreaAutoFill] non-polygon feature; skipping area write');
            return;
        }

        const areaRounded = parseFloat(areaKm2.toFixed(6));

        await ensureAreaField(layerId);
        await writeAreaToFeature(featureId, areaRounded);

        console.log(`[AreaAutoFill] area write succeeded → featureId=${featureId}, area=${areaRounded} km²`);

    } catch (err) {
        console.warn('[AreaAutoFill] area autofill failed; feature save is unaffected:', err);
    }
}
};