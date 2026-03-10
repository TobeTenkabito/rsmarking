import { vi } from 'vitest';

/**
 * TestLogger - 负责测试运行时的环境记录与路径审计
 */
export const TestLogger = {
    /**
     * 打印当前测试的执行上下文信息
     * @param {string} fileName 测试文件名称
     */
    logEnvironment: (fileName) => {
        const timestamp = new Date().toISOString();
        // 在 Vitest 环境下，__dirname 映射为当前测试文件的物理目录
        const runDir = typeof __dirname !== 'undefined' ? __dirname : 'Unknown Execution Context';

        console.log(`\n[Test Audit] -----------------------------------------`);
        console.log(`[Test Audit] 🚀 Target: ${fileName}`);
        console.log(`[Test Audit] 📂 Location: ${runDir}`);
        console.log(`[Test Audit] ⏰ Timestamp: ${timestamp}`);
        console.log(`[Test Audit] -----------------------------------------\n`);
    }
};

/**
 * createMockApp - 工业级业务对象模拟工厂
 * 采用参数注入模式，支持全业务逻辑的扩展
 * * @param {Object} options 自定义配置
 * @param {Object} options.initialState 覆盖默认的 Store 状态
 * @param {Object} options.mapMethods 注入额外的 Leaflet 地图方法
 * @param {Object} options.apiOverrides 覆盖默认的 API 模拟行为
 */
export const createMockApp = (options = {}) => {
    // 1. 模拟核心地图引擎结构
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
        ...options.mapMethods // 允许注入特定的地图行为
    };

    // 2. 构建符合业务架构的 App 实例
    return {
        // 对应 AnnotationModule 报错的关键点：this.map = app.mapEngine.map
        mapEngine: {
            map: mockMap,
            updateLayer: vi.fn(),
            clearAll: vi.fn()
        },

        // 模拟核心状态管理
        store: {
            state: {
                activeVectorLayerId: null,
                visibleVectorLayerIds: new Set(),
                user: { id: 'test-user-001', role: 'editor' },
                ...options.initialState // 注入业务场景所需状态
            },
            commit: vi.fn((type, payload) => {
                console.log(`[Mock Store] Commit: ${type}`, payload);
            }),
            dispatch: vi.fn(() => Promise.resolve())
        },

        // 模拟 API 服务层 (支持 raster, vector 等模块)
        api: {
            raster: {
                fetchTileInfo: vi.fn(() => Promise.resolve({ status: 'success' }))
            },
            vector: {
                saveAnnotation: vi.fn(() => Promise.resolve({ id: 'new-feature-id' }))
            },
            ...options.apiOverrides // 允许注入异常情况（如模拟 500 错误）
        }
    };
};