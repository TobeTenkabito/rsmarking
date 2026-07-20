import { describe, expect, it } from 'vitest';

import {
    densifySphericalPath,
    normalizeSphericalPosition,
    normalizeViewBboxes,
    prepareGeoJSONForRendering,
    prepareGeometryForRendering,
} from '@core/geo/geometryRender.js';

function geometryLongitudes(geometry) {
    const values = [];
    const visit = value => {
        if (!Array.isArray(value)) return;
        if (
            value.length >= 2 &&
            typeof value[0] === 'number' &&
            typeof value[1] === 'number'
        ) {
            values.push(value[0]);
            return;
        }
        value.forEach(visit);
    };
    visit(geometry.coordinates);
    return values;
}

describe('render-safe spherical geometry', () => {
    it('splits a dateline crossing instead of drawing through the opposite hemisphere', () => {
        const rendered = prepareGeometryForRendering({
            type: 'LineString',
            coordinates: [[170, 10], [-170, 10]],
        });

        expect(rendered.type).toBe('MultiLineString');
        expect(rendered.coordinates).toHaveLength(2);
        expect(rendered.coordinates[0].at(-1)[0]).toBe(180);
        expect(rendered.coordinates[1][0][0]).toBe(-180);
        expect(geometryLongitudes(rendered).every(
            longitude => longitude >= -180 && longitude <= 180
        )).toBe(true);
    });

    it('samples a polar great-circle crossing and keeps both map branches visible', () => {
        const dense = densifySphericalPath([[0, 80], [180, 80]]);
        const rendered = prepareGeometryForRendering({
            type: 'LineString',
            coordinates: [[0, 80], [180, 80]],
        });

        expect(Math.max(...dense.map(position => position[1]))).toBeCloseTo(90, 8);
        expect(rendered.type).toBe('MultiLineString');
        expect(rendered.coordinates).toHaveLength(2);
        expect(rendered.coordinates.flat().every(
            position => Number.isFinite(position[0]) && Number.isFinite(position[1])
        )).toBe(true);
    });

    it('preserves explicit multi-world winding while producing canonical render parts', () => {
        const source = {
            type: 'Feature',
            id: 'two-turn-line',
            properties: { color: '#123456' },
            geometry: {
                type: 'LineString',
                coordinates: [[0, 0], [720, 0]],
            },
        };
        const snapshot = structuredClone(source);
        const rendered = prepareGeoJSONForRendering(source);

        expect(rendered.geometry.type).toBe('MultiLineString');
        expect(rendered.geometry.coordinates.length).toBeGreaterThanOrEqual(3);
        expect(rendered.geometry.coordinates.flat().length).toBeGreaterThan(100);
        expect(geometryLongitudes(rendered.geometry).every(
            longitude => longitude >= -180 && longitude <= 180
        )).toBe(true);
        expect(source).toEqual(snapshot);
    });

    it('reflects coordinates across a pole instead of clipping them', () => {
        expect(normalizeSphericalPosition([10, 100])).toEqual([190, 80]);
        expect(normalizeSphericalPosition([10, -100])).toEqual([190, -80]);
    });

    it('splits dateline view queries and normalizes repeated map worlds', () => {
        expect(normalizeViewBboxes([170, -10, -170, 10])).toEqual([
            [170, -10, 180, 10],
            [-180, -10, -170, 10],
        ]);
        expect(normalizeViewBboxes([350, -100, 370, 100])).toEqual([
            [-10, -90, 10, 90],
        ]);
        expect(normalizeViewBboxes([-540, -90, 540, 90])).toEqual([
            [-180, -90, 180, 90],
        ]);
    });

    it('clips dateline polygons into canonical world fragments', () => {
        const rendered = prepareGeometryForRendering({
            type: 'Polygon',
            coordinates: [[
                [170, -10],
                [-170, -10],
                [-170, 10],
                [170, 10],
                [170, -10],
            ]],
        });

        expect(rendered.type).toBe('MultiPolygon');
        expect(rendered.coordinates).toHaveLength(2);
        expect(geometryLongitudes(rendered).every(
            longitude => longitude >= -180 && longitude <= 180
        )).toBe(true);
    });
});
