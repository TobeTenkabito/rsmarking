import { afterEach, describe, expect, it, vi } from 'vitest';

import { RasterAPI } from '@app/api/raster.js';
import { ScriptModule } from '@app/modules/ScriptModule.js';
import { ModalComponent } from '../../../../client/packages/ui/src/components/Modal.js';


function createModule() {
    const app = {
        ui: {
            showGlobalLoading: vi.fn(),
            hideGlobalLoading: vi.fn(),
            showToast: vi.fn(),
        },
        raster: {
            refreshData: vi.fn(async () => {}),
        },
    };
    const module = new ScriptModule(app);
    module.currentScript = "import rasterio\nprint('ok')";
    module.selectedRasterIds = [101];
    module.outputName = 'script_output.tif';
    vi.spyOn(module, 'closeScriptEditor').mockImplementation(() => {});
    return { app, module };
}


describe('ScriptModule execution', () => {
    afterEach(() => {
        vi.restoreAllMocks();
        localStorage.clear();
    });

    it('uses the parsed RasterAPI script result directly', async () => {
        vi.spyOn(RasterAPI, 'executeScript').mockResolvedValue({
            status: 'success',
            result: { id: 12 },
        });
        const { app, module } = createModule();

        await module.executeScript();

        expect(RasterAPI.executeScript).toHaveBeenCalledWith(
            module.currentScript,
            [101],
            'script_output.tif'
        );
        expect(app.ui.showToast).toHaveBeenCalledWith(expect.any(String), 'success');
        expect(app.raster.refreshData).toHaveBeenCalledOnce();
        expect(module.closeScriptEditor).toHaveBeenCalledOnce();
        expect(app.ui.hideGlobalLoading).toHaveBeenCalledOnce();
    });

    it('shows sandbox error details returned by the API helper', async () => {
        vi.spyOn(RasterAPI, 'executeScript').mockResolvedValue({
            status: 'error',
            message: 'Sandbox exited with status code 1\nNameError: name open is not defined',
        });
        const { app, module } = createModule();

        await module.executeScript();

        expect(app.raster.refreshData).not.toHaveBeenCalled();
        expect(app.ui.showToast).toHaveBeenCalledWith(
            expect.stringContaining('Sandbox exited with status code 1'),
            'error'
        );
        expect(app.ui.hideGlobalLoading).toHaveBeenCalledOnce();
    });

    it('passes the concrete selected map feature to the sandbox', async () => {
        vi.spyOn(RasterAPI, 'executeScript').mockResolvedValue({
            status: 'success',
            result: { output_created: false },
        });
        const { app, module } = createModule();
        module.selectedRasterIds = [];
        module.selectedFeatureIds = ['76467ec3-bcef-43d5-9428-f66883b6b151'];

        await module.executeScript();

        expect(RasterAPI.executeScript).toHaveBeenCalledWith(
            module.currentScript,
            [],
            'script_output.tif',
            ['76467ec3-bcef-43d5-9428-f66883b6b151']
        );
        expect(app.raster.refreshData).not.toHaveBeenCalled();
        expect(module.closeScriptEditor).not.toHaveBeenCalled();
    });

    it('renders script examples with the real sandbox paths and variables', () => {
        const html = ModalComponent.renderScriptEditor([], [], '');

        expect(html).toContain('input_0');
        expect(html).not.toContain('input_file');
        expect(html).toContain('OUTPUT_FILE');
        expect(html).toContain('/data/inputs/');
        expect(html).toContain('/data/outputs/');
        expect(html).toContain('feature_0');
        expect(html).toContain('feature_shape()');
        expect(html).not.toContain('/input/image.tif');
    });
});
