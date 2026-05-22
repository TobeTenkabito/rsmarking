import { vi } from 'vitest';

function createDrawHandler({ canDeleteVertex = false } = {}) {
    return {
        enable: vi.fn(),
        disable: vi.fn(),
        enabled: vi.fn(() => true),
        ...(canDeleteVertex ? { deleteLastVertex: vi.fn() } : {}),
    };
}

// Mock the Leaflet surface used by frontend unit tests.
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
    Draw: {
        Polygon: vi.fn(function Polygon() {
            return createDrawHandler({ canDeleteVertex: true });
        }),
        Rectangle: vi.fn(function Rectangle() {
            return createDrawHandler();
        }),
    },
    DomEvent: {
        stopPropagation: vi.fn(),
        preventDefault: vi.fn(),
        on: vi.fn(),
    },
};

global.__app_id = 'test-app-id';
global.RS = {
    toggleEditMode: vi.fn(),
    cancelDraw: vi.fn(),
    exitEditMode: vi.fn(),
};

global.fetch = vi.fn(() =>
    Promise.resolve({
        ok: true,
        json: () => Promise.resolve({}),
    })
);
