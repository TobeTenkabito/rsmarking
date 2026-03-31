/**
 * 将 bounds_wgs84 数组转为 GeoJSON Polygon Geometry（矩形裁剪场景）
 * @param {number[]} bounds - [minx, miny, maxx, maxy]
 * @returns {GeoJSON.Geometry}
 */
export function boundsToGeometry(bounds) {
    const [minx, miny, maxx, maxy] = bounds;
    return {
        type: "Polygon",
        coordinates: [[
            [minx, miny],
            [maxx, miny],
            [maxx, maxy],
            [minx, maxy],
            [minx, miny],
        ]],
    };
}
