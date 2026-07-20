const LONGITUDE_SPAN = 360;
const HALF_LONGITUDE_SPAN = LONGITUDE_SPAN / 2;
const MAX_SEGMENT_ANGLE_DEGREES = 5;
const MAX_EXPLICIT_WORLD_TURNS_PER_EDGE = 64;
const COORDINATE_EPSILON = 1e-9;
const POLE_EPSILON = 1e-7;

function positiveModulo(value, divisor) {
    return ((value % divisor) + divisor) % divisor;
}

export function normalizeLongitude(longitude) {
    const value = Number(longitude);
    if (!Number.isFinite(value)) return NaN;
    return positiveModulo(value + HALF_LONGITUDE_SPAN, LONGITUDE_SPAN) - HALF_LONGITUDE_SPAN;
}

/**
 * Reflect coordinates that pass a pole instead of clipping them at +/-90.
 * The longitude is intentionally left unwrapped so an explicitly multi-world
 * path keeps its winding information until the render-only split stage.
 */
export function normalizeSphericalPosition(position) {
    if (!Array.isArray(position) || position.length < 2) return null;

    let longitude = Number(position[0]);
    const inputLatitude = Number(position[1]);
    if (!Number.isFinite(longitude) || !Number.isFinite(inputLatitude)) return null;

    const wrappedLatitude =
        positiveModulo(inputLatitude + 90, LONGITUDE_SPAN) - 90;
    let latitude = wrappedLatitude;
    if (wrappedLatitude > 90) {
        latitude = 180 - wrappedLatitude;
        longitude += 180;
    }

    return [longitude, latitude, ...position.slice(2)];
}

function longitudeIsCanonical(value) {
    return value >= -HALF_LONGITUDE_SPAN - COORDINATE_EPSILON &&
        value <= HALF_LONGITUDE_SPAN + COORDINATE_EPSILON;
}

function samePosition(a, b) {
    return !!a && !!b &&
        Math.abs(a[0] - b[0]) <= COORDINATE_EPSILON &&
        Math.abs(a[1] - b[1]) <= COORDINATE_EPSILON;
}

function interpolatePosition(a, b, ratio, longitude = null, latitude = null) {
    const dimensions = Math.max(a.length, b.length);
    const result = [
        longitude ?? (a[0] + (b[0] - a[0]) * ratio),
        latitude ?? (a[1] + (b[1] - a[1]) * ratio),
    ];

    for (let index = 2; index < dimensions; index += 1) {
        const start = Number(a[index]);
        const end = Number(b[index]);
        if (Number.isFinite(start) && Number.isFinite(end)) {
            result.push(start + (end - start) * ratio);
        } else if (a[index] !== undefined) {
            result.push(a[index]);
        } else if (b[index] !== undefined) {
            result.push(b[index]);
        }
    }
    return result;
}

function toUnitVector(position) {
    const longitude = position[0] * Math.PI / 180;
    const latitude = position[1] * Math.PI / 180;
    const cosLatitude = Math.cos(latitude);
    return [
        cosLatitude * Math.cos(longitude),
        cosLatitude * Math.sin(longitude),
        Math.sin(latitude),
    ];
}

function vectorLength(vector) {
    return Math.hypot(vector[0], vector[1], vector[2]);
}

function normalizeVector(vector) {
    const length = vectorLength(vector);
    if (length <= COORDINATE_EPSILON) return null;
    return vector.map(value => value / length);
}

function dot(a, b) {
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2];
}

function preferredAntipodalDirection(start, end) {
    const poleSign = start[1] + end[1] < 0 ? -1 : 1;
    const preferredPole = [0, 0, poleSign];
    const startVector = toUnitVector(start);
    const projection = dot(preferredPole, startVector);
    let perpendicular = preferredPole.map(
        (value, index) => value - projection * startVector[index]
    );

    if (vectorLength(perpendicular) <= COORDINATE_EPSILON) {
        perpendicular = [-startVector[1], startVector[0], 0];
    }
    return normalizeVector(perpendicular) ?? [0, 1, 0];
}

function fromUnitVector(vector, templateA, templateB, ratio) {
    const normalized = normalizeVector(vector);
    if (!normalized) return null;
    const longitude = Math.atan2(normalized[1], normalized[0]) * 180 / Math.PI;
    const latitude = Math.atan2(
        normalized[2],
        Math.hypot(normalized[0], normalized[1])
    ) * 180 / Math.PI;
    return interpolatePosition(templateA, templateB, ratio, longitude, latitude);
}

function unwrapLongitudeNear(longitude, reference) {
    if (!Number.isFinite(reference)) return longitude;
    return longitude + LONGITUDE_SPAN * Math.round((reference - longitude) / LONGITUDE_SPAN);
}

function densifyGreatCircleSegment(start, end, maxAngleDegrees) {
    const startVector = toUnitVector(start);
    const endVector = toUnitVector(end);
    const cosine = Math.max(-1, Math.min(1, dot(startVector, endVector)));
    const angle = Math.acos(cosine);
    let steps = Math.max(1, Math.ceil(
        angle * 180 / Math.PI / maxAngleDegrees
    ));
    const longitudeSeparation = Math.abs(normalizeLongitude(end[0] - start[0]));
    if (
        Math.abs(longitudeSeparation - HALF_LONGITUDE_SPAN) <= COORDINATE_EPSILON &&
        start[1] * end[1] > 0 &&
        steps % 2 !== 0
    ) {
        // Sample the pole itself. Without this, an odd subdivision count jumps
        // between two near-pole points and leaves a false cross-map segment.
        steps += 1;
    }
    const positions = [];
    let previousLongitude = start[0];

    for (let index = 0; index <= steps; index += 1) {
        const ratio = index / steps;
        let vector;

        if (angle <= COORDINATE_EPSILON) {
            vector = startVector;
        } else if (Math.PI - angle <= COORDINATE_EPSILON) {
            const perpendicular = preferredAntipodalDirection(start, end);
            vector = startVector.map(
                (value, axis) =>
                    value * Math.cos(Math.PI * ratio) +
                    perpendicular[axis] * Math.sin(Math.PI * ratio)
            );
        } else {
            const sinAngle = Math.sin(angle);
            const startWeight = Math.sin((1 - ratio) * angle) / sinAngle;
            const endWeight = Math.sin(ratio * angle) / sinAngle;
            vector = startVector.map(
                (value, axis) => value * startWeight + endVector[axis] * endWeight
            );
        }

        const position = fromUnitVector(vector, start, end, ratio);
        if (!position) continue;
        position[0] = unwrapLongitudeNear(position[0], previousLongitude);
        previousLongitude = position[0];
        positions.push(position);
    }

    return positions;
}

function densifyExplicitWorldSegment(rawStart, rawEnd, maxAngleDegrees) {
    const maxExplicitDelta =
        LONGITUDE_SPAN * MAX_EXPLICIT_WORLD_TURNS_PER_EDGE;
    const longitudeDelta = Math.max(
        -maxExplicitDelta,
        Math.min(maxExplicitDelta, Number(rawEnd[0]) - Number(rawStart[0]))
    );
    const latitudeDelta = Math.max(
        -maxExplicitDelta,
        Math.min(maxExplicitDelta, Number(rawEnd[1]) - Number(rawStart[1]))
    );
    const boundedEnd = [
        Number(rawStart[0]) + longitudeDelta,
        Number(rawStart[1]) + latitudeDelta,
        ...rawEnd.slice(2),
    ];
    const steps = Math.max(1, Math.ceil(
        Math.max(Math.abs(longitudeDelta), Math.abs(latitudeDelta)) /
        maxAngleDegrees
    ));
    const positions = [];

    for (let index = 0; index <= steps; index += 1) {
        const ratio = index / steps;
        const rawPosition = interpolatePosition(rawStart, boundedEnd, ratio);
        const normalized = normalizeSphericalPosition(rawPosition);
        if (normalized) positions.push(normalized);
    }
    return positions;
}

/**
 * Densify a path on the globe. Canonical endpoint pairs use the shortest
 * great-circle route (including polar crossings). Longitudes outside the
 * canonical world are treated as intentional winding and sampled without
 * collapsing full rotations.
 */
export function densifySphericalPath(
    coordinates,
    { maxAngleDegrees = MAX_SEGMENT_ANGLE_DEGREES } = {}
) {
    if (!Array.isArray(coordinates)) return [];

    const rawPositions = coordinates.filter(
        position => normalizeSphericalPosition(position) !== null
    );
    if (rawPositions.length === 0) return [];
    if (rawPositions.length === 1) {
        return [normalizeSphericalPosition(rawPositions[0])];
    }

    const result = [];
    let previousLongitude = null;

    for (let index = 1; index < rawPositions.length; index += 1) {
        const rawStart = rawPositions[index - 1];
        const rawEnd = rawPositions[index];
        const start = normalizeSphericalPosition(rawStart);
        const end = normalizeSphericalPosition(rawEnd);
        if (!start || !end) continue;

        const preserveExplicitWinding =
            !longitudeIsCanonical(Number(rawStart[0])) ||
            !longitudeIsCanonical(Number(rawEnd[0]));
        const segment = preserveExplicitWinding
            ? densifyExplicitWorldSegment(rawStart, rawEnd, maxAngleDegrees)
            : densifyGreatCircleSegment(start, end, maxAngleDegrees);

        for (let segmentIndex = 0; segmentIndex < segment.length; segmentIndex += 1) {
            if (index > 1 && segmentIndex === 0) continue;
            const position = [...segment[segmentIndex]];
            if (!preserveExplicitWinding) {
                position[0] = unwrapLongitudeNear(position[0], previousLongitude);
            }
            previousLongitude = position[0];
            if (!samePosition(result[result.length - 1], position)) {
                result.push(position);
            }
        }
    }

    return result;
}

function canonicalBoundary(longitude, direction) {
    const normalized = normalizeLongitude(longitude);
    if (Math.abs(Math.abs(normalized) - HALF_LONGITUDE_SPAN) <= COORDINATE_EPSILON) {
        return direction > 0 ? HALF_LONGITUDE_SPAN : -HALF_LONGITUDE_SPAN;
    }
    return normalized;
}

function canonicalBoundaryNear(reference) {
    return Math.abs(reference - HALF_LONGITUDE_SPAN) <
        Math.abs(reference + HALF_LONGITUDE_SPAN)
        ? HALF_LONGITUDE_SPAN
        : -HALF_LONGITUDE_SPAN;
}

function crossedWorldBoundaries(startLongitude, endLongitude) {
    const delta = endLongitude - startLongitude;
    if (Math.abs(delta) <= COORDINATE_EPSILON) return [];

    const lower = Math.min(startLongitude, endLongitude);
    const upper = Math.max(startLongitude, endLongitude);
    const firstIndex = Math.ceil(
        (lower - HALF_LONGITUDE_SPAN) / LONGITUDE_SPAN
    );
    const lastIndex = Math.floor(
        (upper - HALF_LONGITUDE_SPAN) / LONGITUDE_SPAN
    );
    const boundaries = [];

    for (let index = firstIndex; index <= lastIndex; index += 1) {
        const boundary = HALF_LONGITUDE_SPAN + LONGITUDE_SPAN * index;
        if (
            boundary > lower + COORDINATE_EPSILON &&
            boundary < upper - COORDINATE_EPSILON
        ) {
            boundaries.push(boundary);
        }
    }
    if (delta < 0) boundaries.reverse();
    return boundaries;
}

function isWorldBoundary(longitude) {
    const offset = positiveModulo(
        longitude - HALF_LONGITUDE_SPAN,
        LONGITUDE_SPAN
    );
    return offset <= COORDINATE_EPSILON ||
        LONGITUDE_SPAN - offset <= COORDINATE_EPSILON;
}

function cleanLine(line) {
    const cleaned = [];
    for (const position of line) {
        if (!samePosition(cleaned[cleaned.length - 1], position)) {
            cleaned.push(position);
        }
    }
    return cleaned;
}

/**
 * Split a continuous unwrapped line at each world boundary. Every returned
 * coordinate is valid in the canonical GeoJSON longitude range, preventing
 * both Leaflet and Cesium from joining a line through the wrong hemisphere.
 */
export function splitPathAtWorldBoundaries(coordinates) {
    const dense = densifySphericalPath(coordinates);
    if (dense.length < 2) return dense.length ? [dense] : [];

    const parts = [];
    let current = [[normalizeLongitude(dense[0][0]), dense[0][1], ...dense[0].slice(2)]];

    for (let index = 1; index < dense.length; index += 1) {
        const start = dense[index - 1];
        const end = dense[index];
        const direction = Math.sign(end[0] - start[0]) || 1;
        const boundaries = crossedWorldBoundaries(start[0], end[0]);
        let segmentStart = start;

        for (const boundary of boundaries) {
            const ratio = (boundary - segmentStart[0]) / (end[0] - segmentStart[0]);
            const crossing = interpolatePosition(segmentStart, end, ratio, boundary);
            const ending = [
                canonicalBoundary(boundary, direction),
                crossing[1],
                ...crossing.slice(2),
            ];
            current.push(ending);
            const cleaned = cleanLine(current);
            if (cleaned.length >= 2) parts.push(cleaned);

            current = [[
                direction > 0 ? -HALF_LONGITUDE_SPAN : HALF_LONGITUDE_SPAN,
                crossing[1],
                ...crossing.slice(2),
            ]];
            segmentStart = crossing;
        }

        const endsAtWorldBoundary = isWorldBoundary(end[0]);
        const incomingDelta = end[0] - start[0];
        const outgoingDelta = index < dense.length - 1
            ? dense[index + 1][0] - end[0]
            : 0;
        const crossesThroughWorldBoundary =
            endsAtWorldBoundary &&
            Math.abs(incomingDelta) > COORDINATE_EPSILON &&
            Math.abs(outgoingDelta) > COORDINATE_EPSILON &&
            Math.sign(incomingDelta) === Math.sign(outgoingDelta);
        const currentReference = current[current.length - 1]?.[0] ?? 0;
        current.push([
            endsAtWorldBoundary
                ? canonicalBoundaryNear(currentReference)
                : normalizeLongitude(end[0]),
            end[1],
            ...end.slice(2),
        ]);

        if (crossesThroughWorldBoundary) {
            const cleaned = cleanLine(current);
            if (cleaned.length >= 2) parts.push(cleaned);
            current = [[
                outgoingDelta > 0 ? -HALF_LONGITUDE_SPAN : HALF_LONGITUDE_SPAN,
                end[1],
                ...end.slice(2),
            ]];
            continue;
        }

        // A Web Mercator map cannot represent the pole itself. Starting a new
        // part there avoids a spurious horizontal stroke across the map edge;
        // on the globe both endpoints still meet at the same physical point.
        if (
            Math.abs(Math.abs(end[1]) - 90) <= POLE_EPSILON &&
            index < dense.length - 1
        ) {
            const cleaned = cleanLine(current);
            if (cleaned.length >= 2) parts.push(cleaned);
            current = [[
                normalizeLongitude(dense[index + 1][0]),
                end[1],
                ...end.slice(2),
            ]];
        }
    }

    const cleaned = cleanLine(current);
    if (cleaned.length >= 2) parts.push(cleaned);
    return parts;
}

function closeRing(ring) {
    const cleaned = cleanLine(ring);
    if (cleaned.length > 0 && !samePosition(cleaned[0], cleaned[cleaned.length - 1])) {
        cleaned.push([...cleaned[0]]);
    }
    return cleaned;
}

function interpolateAtLongitude(start, end, longitude) {
    const delta = end[0] - start[0];
    const ratio = Math.abs(delta) <= COORDINATE_EPSILON
        ? 0
        : (longitude - start[0]) / delta;
    return interpolatePosition(start, end, ratio, longitude);
}

function clipRingAgainstBoundary(ring, longitude, keepGreater) {
    if (ring.length === 0) return [];
    const output = [];
    const inside = position => keepGreater
        ? position[0] >= longitude - COORDINATE_EPSILON
        : position[0] <= longitude + COORDINATE_EPSILON;

    let previous = ring[ring.length - 1];
    let previousInside = inside(previous);
    for (const current of ring) {
        const currentInside = inside(current);
        if (currentInside !== previousInside) {
            output.push(interpolateAtLongitude(previous, current, longitude));
        }
        if (currentInside) output.push(current);
        previous = current;
        previousInside = currentInside;
    }
    return output;
}

function clipRingToWorld(ring, west, east) {
    const clippedWest = clipRingAgainstBoundary(ring, west, true);
    const clipped = clipRingAgainstBoundary(clippedWest, east, false);
    return closeRing(clipped);
}

function signedRingArea(ring) {
    let area = 0;
    for (let index = 1; index < ring.length; index += 1) {
        area += ring[index - 1][0] * ring[index][1] -
            ring[index][0] * ring[index - 1][1];
    }
    return area / 2;
}

function alignRingToReference(ring, referenceLongitude) {
    if (ring.length === 0) return ring;
    const center = ring.reduce((sum, position) => sum + position[0], 0) / ring.length;
    const offset = LONGITUDE_SPAN * Math.round(
        (referenceLongitude - center) / LONGITUDE_SPAN
    );
    return ring.map(position => [position[0] + offset, ...position.slice(1)]);
}

function polygonFragments(rings) {
    if (!Array.isArray(rings) || rings.length === 0) return [];
    const outer = closeRing(densifySphericalPath(rings[0]));
    if (outer.length < 4) return [];

    const outerCenter = outer.reduce(
        (sum, position) => sum + position[0],
        0
    ) / outer.length;
    const holes = rings.slice(1)
        .map(ring => alignRingToReference(
            closeRing(densifySphericalPath(ring)),
            outerCenter
        ))
        .filter(ring => ring.length >= 4);
    const longitudeRange = outer.reduce(
        (range, position) => ({
            min: Math.min(range.min, position[0]),
            max: Math.max(range.max, position[0]),
        }),
        { min: Number.POSITIVE_INFINITY, max: Number.NEGATIVE_INFINITY }
    );
    const minWorld = Math.floor(
        (longitudeRange.min + HALF_LONGITUDE_SPAN) / LONGITUDE_SPAN
    );
    const maxWorld = Math.floor(
        (longitudeRange.max + HALF_LONGITUDE_SPAN) / LONGITUDE_SPAN
    );
    const fragments = [];

    for (let world = minWorld; world <= maxWorld; world += 1) {
        const west = -HALF_LONGITUDE_SPAN + LONGITUDE_SPAN * world;
        const east = HALF_LONGITUDE_SPAN + LONGITUDE_SPAN * world;
        const clippedOuter = clipRingToWorld(outer, west, east);
        if (
            clippedOuter.length < 4 ||
            Math.abs(signedRingArea(clippedOuter)) <= COORDINATE_EPSILON
        ) {
            continue;
        }

        const shift = LONGITUDE_SPAN * world;
        const shiftedOuter = clippedOuter.map(
            position => [position[0] - shift, ...position.slice(1)]
        );
        const shiftedHoles = holes
            .map(hole => clipRingToWorld(hole, west, east))
            .filter(hole =>
                hole.length >= 4 &&
                Math.abs(signedRingArea(hole)) > COORDINATE_EPSILON
            )
            .map(hole => hole.map(
                position => [position[0] - shift, ...position.slice(1)]
            ));
        fragments.push([shiftedOuter, ...shiftedHoles]);
    }

    return fragments;
}

export function prepareGeometryForRendering(geometry) {
    if (!geometry || typeof geometry !== 'object') return geometry ?? null;

    switch (geometry.type) {
        case 'Point': {
            const position = normalizeSphericalPosition(geometry.coordinates);
            if (!position) return null;
            position[0] = normalizeLongitude(position[0]);
            return { ...geometry, coordinates: position };
        }
        case 'MultiPoint': {
            const coordinates = (geometry.coordinates || [])
                .map(normalizeSphericalPosition)
                .filter(Boolean)
                .map(position => [normalizeLongitude(position[0]), ...position.slice(1)]);
            return { ...geometry, coordinates };
        }
        case 'LineString': {
            const parts = splitPathAtWorldBoundaries(geometry.coordinates);
            if (parts.length === 0) return null;
            return parts.length === 1
                ? { ...geometry, coordinates: parts[0] }
                : { ...geometry, type: 'MultiLineString', coordinates: parts };
        }
        case 'MultiLineString': {
            const parts = (geometry.coordinates || [])
                .flatMap(splitPathAtWorldBoundaries);
            if (parts.length === 0) return null;
            return { ...geometry, coordinates: parts };
        }
        case 'Polygon': {
            const fragments = polygonFragments(geometry.coordinates);
            if (fragments.length === 0) return null;
            return fragments.length === 1
                ? { ...geometry, coordinates: fragments[0] }
                : { ...geometry, type: 'MultiPolygon', coordinates: fragments };
        }
        case 'MultiPolygon': {
            const fragments = (geometry.coordinates || []).flatMap(polygonFragments);
            if (fragments.length === 0) return null;
            return { ...geometry, coordinates: fragments };
        }
        case 'GeometryCollection': {
            const geometries = (geometry.geometries || [])
                .map(prepareGeometryForRendering)
                .filter(Boolean);
            return { ...geometry, geometries };
        }
        default:
            return geometry;
    }
}

/**
 * Prepare a render-only clone. Source GeoJSON is never mutated, so switching
 * engines repeatedly cannot accumulate coordinate wrapping or densification.
 */
export function prepareGeoJSONForRendering(geojson) {
    if (!geojson || typeof geojson !== 'object') return geojson;

    if (geojson.type === 'FeatureCollection') {
        return {
            ...geojson,
            features: (geojson.features || [])
                .map(feature => {
                    const geometry = prepareGeometryForRendering(feature?.geometry);
                    return geometry ? { ...feature, geometry } : null;
                })
                .filter(Boolean),
        };
    }
    if (geojson.type === 'Feature') {
        const geometry = prepareGeometryForRendering(geojson.geometry);
        return geometry ? { ...geojson, geometry } : null;
    }
    return prepareGeometryForRendering(geojson);
}

/**
 * Convert a possibly repeated-world or dateline-crossing view into one or two
 * canonical query envelopes. A single PostGIS envelope cannot cross the
 * antimeridian, so callers should fetch every returned envelope and de-dup.
 */
export function normalizeViewBboxes(bbox) {
    if (!Array.isArray(bbox) || bbox.length !== 4) return [];
    let [west, south, east, north] = bbox.map(Number);
    if (![west, south, east, north].every(Number.isFinite)) return [];

    if (north < south) [south, north] = [north, south];
    south = Math.max(-90, south);
    north = Math.min(90, north);
    if (south > north) return [];

    let width = east - west;
    if (Math.abs(width) >= LONGITUDE_SPAN - COORDINATE_EPSILON) {
        return [[-HALF_LONGITUDE_SPAN, south, HALF_LONGITUDE_SPAN, north]];
    }
    if (width < 0) width += LONGITUDE_SPAN;

    const canonicalWest = normalizeLongitude(west);
    const unwrappedEast = canonicalWest + width;
    if (unwrappedEast <= HALF_LONGITUDE_SPAN + COORDINATE_EPSILON) {
        return [[canonicalWest, south, Math.min(unwrappedEast, HALF_LONGITUDE_SPAN), north]];
    }

    return [
        [canonicalWest, south, HALF_LONGITUDE_SPAN, north],
        [-HALF_LONGITUDE_SPAN, south, unwrappedEast - LONGITUDE_SPAN, north],
    ];
}
