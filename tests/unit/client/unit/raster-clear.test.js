import { afterEach, describe, expect, it, vi } from 'vitest';
import { RasterModule } from '@app/modules/RasterModule.js';
import { GlobalBridge } from '@app/core/GlobalBridge.js';
import { RasterAPI } from '@app/api/raster.js';
import { Store } from '@app/store/index.js';

afterEach(() => vi.restoreAllMocks());

describe('Administrator clear flow', () => {
    it('does not clear raster state when token entry is cancelled', async () => {
        vi.spyOn(window, 'prompt').mockReturnValue(null);
        const clear = vi.spyOn(RasterAPI, 'clearDB');
        const clearState = vi.spyOn(Store, 'clearRasterState');
        const raster = new RasterModule({});
        expect(await raster.handleClearDatabase({ confirmUser: false, reload: false })).toBe(false);
        expect(clear).not.toHaveBeenCalled();
        expect(clearState).not.toHaveBeenCalled();
    });

    it('preserves browser state when server rejects the token', async () => {
        vi.spyOn(window, 'prompt').mockReturnValue('wrong-token');
        vi.spyOn(RasterAPI, 'clearDB').mockRejectedValue(new Error('Invalid administrator credentials'));
        const clearState = vi.spyOn(Store, 'clearRasterState');
        const raster = new RasterModule({});
        await expect(raster.handleClearDatabase({ confirmUser: false, reload: false })).rejects.toThrow('Invalid administrator credentials');
        expect(clearState).not.toHaveBeenCalled();
    });

    it.each(['cancelled', 'rejected'])('does not delete vector projects when raster clearing is %s', async (outcome) => {
        vi.spyOn(window, 'confirm').mockReturnValue(true);
        vi.spyOn(window, 'alert').mockImplementation(() => {});
        vi.spyOn(console, 'error').mockImplementation(() => {});
        const clearRasters = outcome === 'cancelled'
            ? vi.fn().mockResolvedValue(false)
            : vi.fn().mockRejectedValue(new Error('Invalid administrator credentials'));
        const clearProjects = vi.fn();
        const loader = vi.fn();
        new GlobalBridge({
            raster: { handleClearDatabase: clearRasters },
            project: { handleDeleteAllProjects: clearProjects },
            ui: { showGlobalLoader: loader },
        }).mount();
        await window.RS.clearDatabase();
        expect(clearProjects).not.toHaveBeenCalled();
        expect(loader).toHaveBeenLastCalledWith(false);
    });
});
