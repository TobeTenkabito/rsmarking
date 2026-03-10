import { vi } from 'vitest';

// 模拟 Leaflet 全局对象
global.L = {
    map: vi.fn(() => ({
        on: vi.fn(),
        off: vi.fn(),
        remove: vi.fn(),
        addLayer: vi.fn(),
        removeLayer: vi.fn(),
        getContainer: vi.fn(() => {
            const div = document.createElement('div');
            div.id = 'map-container';
            return div;
        }),
        // 增加辅助方法模拟
        getZoom: vi.fn(() => 10),
        getCenter: vi.fn(() => ({ lat: 0, lng: 0 })),
    })),
    geoJSON: vi.fn(() => ({
        addTo: vi.fn(),
        clearLayers: vi.fn(),
        addData: vi.fn(),
        setStyle: vi.fn(),
        eachLayer: vi.fn(),
    })),
    // 增加绘图相关的命名空间模拟，防止 AnnotationModule 报错
    Draw: {
        Polygon: vi.fn(() => ({
            enable: vi.fn(),
            disable: vi.fn(),
            enabled: vi.fn(() => true),
            deleteLastVertex: vi.fn(),
        })),
        Rectangle: vi.fn(() => ({
            enable: vi.fn(),
            disable: vi.fn(),
            enabled: vi.fn(() => true),
        }))
    },
    DomEvent: {
        stopPropagation: vi.fn(),
        preventDefault: vi.fn(),
        on: vi.fn(),
    }
};

// 模拟全局 Store 和业务桥接对象
global.__app_id = 'test-app-id';
global.RS = {
    toggleEditMode: vi.fn(),
    cancelDraw: vi.fn(),
    exitEditMode: vi.fn(),
};

// 模拟 Fetch API (增加基本的回调支持)
global.fetch = vi.fn(() =>
    Promise.resolve({
        ok: true,
        json: () => Promise.resolve({}),
    })
);