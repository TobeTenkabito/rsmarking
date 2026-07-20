import { describe, it, expect, vi } from 'vitest';
// Use aliases to keep path resolution consistent
import { AnnotationModule } from '@app/modules/AnnotationModule.js';
import { TestLogger, createMockApp } from '@test-utils/test-helper.js';

describe('AnnotationModule annotation interaction tests', () => {
    // Automatically record test environment information
    TestLogger.logEnvironment('annotation.test.js');

    it('undoLastPoint should call in polygon mode deleteLastVertex', () => {
        // Use a factory to create an app matching the runtime shape (fixes mapEngine.map errors)
        const mockApp = createMockApp();
        const module = new AnnotationModule(mockApp);

        const mockHandler = {
            enabled: () => true,
            deleteLastVertex: vi.fn()
        };
        module.currentHandler = mockHandler;

        module.undoLastPoint();
        expect(mockHandler.deleteLastVertex).toHaveBeenCalled();
    });

    it('resetCurrentAction should reset the action without leaving the mode', () => {
        const mockApp = createMockApp();
        const module = new AnnotationModule(mockApp);

        const mockHandler = {
            enabled: () => true,
            disable: vi.fn(),
        };

        // Mock internal methods to verify calls
        module.startDrawing = vi.fn();
        module.currentHandler = mockHandler;
        module.currentType = 'polygon';

        module.resetCurrentAction();

        expect(mockHandler.disable).toHaveBeenCalled();
        expect(module.startDrawing).toHaveBeenCalledWith('polygon');
    });

    it('keeps a 3D-drawn dateline path continuous in its saved coordinates', () => {
        const module = new AnnotationModule(createMockApp());
        module.cesiumDraw = {
            mode: 'polyline',
            vertices: [
                { lng: 170, lat: 10 },
                { lng: -170, lat: 10 },
            ],
            cursor: null,
        };

        const result = module._buildCesiumGeometry();

        expect(result.geometry).toEqual({
            type: 'LineString',
            coordinates: [[170, 10], [190, 10]],
        });
    });
});
