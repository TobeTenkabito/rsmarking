import { afterEach, describe, expect, it, vi } from 'vitest';

import { RasterAPI } from '@app/api/raster.js';


describe('RasterAPI errors', () => {
    afterEach(() => {
        vi.restoreAllMocks();
        global.fetch.mockReset();
    });

    it('throws FastAPI detail text for failed script requests', async () => {
        global.fetch.mockResolvedValueOnce({
            ok: false,
            status: 400,
            text: vi.fn(async () => JSON.stringify({
                detail: 'Script contains a blocked operation: open()',
            })),
        });

        await expect(
            RasterAPI.executeScript('open("x")', [1], 'out.tif')
        ).rejects.toThrow('Script contains a blocked operation: open()');

        expect(global.fetch.mock.calls[0][0]).toContain('/execute-script');
        expect(global.fetch.mock.calls[0][1].method).toBe('POST');
    });

    it('throws plain text response bodies when JSON parsing is not possible', async () => {
        global.fetch.mockResolvedValueOnce({
            ok: false,
            status: 500,
            text: vi.fn(async () => 'Sandbox exited with status code 1'),
        });

        await expect(
            RasterAPI.executeScript('import rasterio', [1], 'out.tif')
        ).rejects.toThrow('Sandbox exited with status code 1');
    });

    it('sends selected vector feature ids with script requests', async () => {
        global.fetch.mockResolvedValueOnce({
            ok: true,
            status: 200,
            json: vi.fn(async () => ({ status: 'success' })),
        });

        await RasterAPI.executeScript(
            "print(feature_0)",
            [],
            'analysis.tif',
            ['76467ec3-bcef-43d5-9428-f66883b6b151']
        );

        const body = global.fetch.mock.calls[0][1].body;
        expect(body.get('raster_ids')).toBe('');
        expect(body.get('feature_ids')).toBe('76467ec3-bcef-43d5-9428-f66883b6b151');
    });

    it('requests the valid-pixel footprint instead of raster bounds', async () => {
        global.fetch.mockResolvedValueOnce({
            ok: true,
            status: 200,
            json: vi.fn(async () => ({
                geometry: { type: 'Polygon', coordinates: [] },
            })),
        });

        await RasterAPI.getFootprint(123, 'EPSG:4326');

        expect(global.fetch.mock.calls[0][0]).toContain(
            '/raster/123/footprint?dst_crs=EPSG%3A4326'
        );
    });

    it('loads automatic time-series candidates', async () => {
        global.fetch.mockResolvedValueOnce({
            ok: true,
            status: 200,
            json: vi.fn(async () => ({ candidates: [], candidate_count: 0 })),
        });

        await RasterAPI.fetchTimeSeriesCandidates();

        expect(global.fetch.mock.calls[0][0]).toContain('/time-series-candidates');
    });

    it('supports optional expert correction of temporal metadata', async () => {
        global.fetch.mockResolvedValueOnce({
            ok: true,
            status: 200,
            json: vi.fn(async () => ({ index_id: 123 })),
        });

        await RasterAPI.updateTemporalMetadata(123, {
            acquired_at: '2024-06-18T03:21:41Z',
        });

        const [, options] = global.fetch.mock.calls[0];
        expect(options.method).toBe('PATCH');
        expect(JSON.parse(options.body).acquired_at).toBe(
            '2024-06-18T03:21:41Z'
        );
    });
});
