import { vi } from 'vitest';

/**
 * TestLogger - Englishenvironment logging and path audit during tests
 */
export const TestLogger = {
    /**
     * Print the current test execution context
     * @param {string} fileName test file name
     */
    logEnvironment: (fileName) => {
        const timestamp = new Date().toISOString();
        // In the Vitest environment，__dirname maps to the current test file directory
        const runDir = typeof __dirname !== 'undefined' ? __dirname : 'Unknown Execution Context';

        console.log(`\n[Test Audit] -----------------------------------------`);
        console.log(`[Test Audit] 🚀 Target: ${fileName}`);
        console.log(`[Test Audit] 📂 Location: ${runDir}`);
        console.log(`[Test Audit] ⏰ Timestamp: ${timestamp}`);
        console.log(`[Test Audit] -----------------------------------------\n`);
    }
};

/**
 * createMockApp - production-shaped app mock factory
 * uses parameter injection，supports full business-logic extension
 * * @param {Object} options custom configuration
 * @param {Object} options.initialState override default Store state
 * @param {Object} options.mapMethods inject additional Leaflet map methods
 * @param {Object} options.apiOverrides override default API mock behavior
 */
export const createMockApp = (options = {}) => {
    // 1. Mock the core map-engine shape
    const mockMap = {
        on: vi.fn(),
        off: vi.fn(),
        getContainer: vi.fn(() => {
            const el = document.createElement('div');
            el.id = 'test-map-container';
            return el;
        }),
        addLayer: vi.fn(),
        removeLayer: vi.fn(),
        getZoom: vi.fn(() => 10),
        ...options.mapMethods // allow specific map behavior injection
    };

    // 2. Build an app instance matching the runtime architecture
    return {
        // Key shape expected by AnnotationModule：this.map = app.mapEngine.map
        mapEngine: {
            map: mockMap,
            updateLayer: vi.fn(),
            clearAll: vi.fn()
        },

        // Mock core state management
        store: {
            state: {
                activeVectorLayerId: null,
                visibleVectorLayerIds: new Set(),
                user: { id: 'test-user-001', role: 'editor' },
                ...options.initialState // inject state required by the scenario
            },
            commit: vi.fn((type, payload) => {
                console.log(`[Mock Store] Commit: ${type}`, payload);
            }),
            dispatch: vi.fn(() => Promise.resolve())
        },

        // Mock the API service layer (Supports raster, vector English)
        api: {
            raster: {
                fetchTileInfo: vi.fn(() => Promise.resolve({ status: 'success' }))
            },
            vector: {
                saveAnnotation: vi.fn(() => Promise.resolve({ id: 'new-feature-id' }))
            },
            ...options.apiOverrides // allow error-case injection（such as a 500 error）
        }
    };
};