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
});
