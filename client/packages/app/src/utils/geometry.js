/**
 * Convert bounds_wgs84 array into GeoJSON Polygon geometry（rectangle clipping scenario）
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
