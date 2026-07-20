import { afterEach, describe, expect, it, vi } from 'vitest';

import { MapEngine } from '@core/map.js';

function bareEngine() {
    const engine = Object.create(MapEngine.prototype);
    Object.assign(engine, {
        isReady: true,
        map: {
            removeLayer: vi.fn(),
            invalidateSize: vi.fn(),
            setView: vi.fn(),
        },
        vectorLayers: new Map(),
        _vectorGeoJSONSources: new Map(),
        _vectorLayerOrder: [],
        _cesiumVectorDataSources: new Map(),
        _cesiumVectorSyncTokens: new Map(),
        _cesiumVectorFingerprints: new Map(),
        _cesiumVectorPendingFingerprints: new Map(),
        _cesiumViewer: null,
        _is3D: false,
        _viewChangeListeners: new Set(),
        _modeTransitionToken: 0,
        _modeSwitchTimer: null,
        containerId: 'map',
    });
    return engine;
}

describe('MapEngine 2D/3D synchronization', () => {
    afterEach(() => {
        vi.useRealTimers();
        delete global.Cesium;
        document.body.innerHTML = '';
    });

    it('rebuilds Leaflet coordinates and retains the latest source GeoJSON', () => {
        const engine = bareEngine();
        const existingLayer = {
            options: { pointToLayer: () => null },
            clearLayers: vi.fn(),
            addData: vi.fn(),
            bringToFront: vi.fn(),
        };
        engine.vectorLayers.set('layer-a', existingLayer);
        const source = {
            type: 'FeatureCollection',
            features: [{
                type: 'Feature',
                id: 'line-a',
                properties: {},
                geometry: {
                    type: 'LineString',
                    coordinates: [[170, 10], [-170, 10]],
                },
            }],
        };

        engine.updateVectorLayer('layer-a', source, null);

        expect(existingLayer.clearLayers).toHaveBeenCalledOnce();
        expect(existingLayer.addData).toHaveBeenCalledOnce();
        const rendered = existingLayer.addData.mock.calls[0][0];
        expect(rendered.features[0].geometry.type).toBe('MultiLineString');
        expect(engine._vectorGeoJSONSources.get('layer-a')).toBe(source);
    });

    it('cancels a pending 3D synchronization when immediately switching back to 2D', () => {
        vi.useFakeTimers();
        document.body.innerHTML = [
            '<div id="map"></div>',
            '<div id="cesium-container"></div>',
            '<button id="globe-toggle-btn"></button>',
            '<span id="globe-btn-label"></span>',
        ].join('');

        global.Cesium = {
            Cartesian3: { fromDegrees: vi.fn(() => ({})) },
            Math: { toDegrees: vi.fn(value => value) },
        };

        const engine = bareEngine();
        engine.map.getCenter = vi.fn(() => ({ lng: 100, lat: 30 }));
        engine.map.getZoom = vi.fn(() => 4);
        engine._initCesium = vi.fn(() => true);
        engine._syncRastersToCesium = vi.fn();
        engine._syncVectorsToCesium = vi.fn();
        engine._cesiumViewer = {
            resize: vi.fn(),
            camera: {
                flyTo: vi.fn(),
                cancelFlight: vi.fn(),
                positionCartographic: {
                    longitude: 100,
                    latitude: 30,
                    height: 2500000,
                },
            },
        };

        engine.switchTo3D();
        engine.switchTo2D();
        vi.runAllTimers();

        expect(engine._is3D).toBe(false);
        expect(engine._cesiumViewer.camera.flyTo).not.toHaveBeenCalled();
        expect(engine._syncVectorsToCesium).not.toHaveBeenCalled();
        expect(document.getElementById('map').style.visibility).toBe('visible');
    });

    it('keeps the old Cesium data source visible until its replacement is ready', async () => {
        let resolveLoad;
        const loadPromise = new Promise(resolve => {
            resolveLoad = resolve;
        });
        const oldDataSource = { name: 'layer-a', marker: 'old' };
        const newDataSource = {
            name: '',
            marker: 'new',
            entities: { values: [] },
        };
        const collection = [oldDataSource];
        const dataSources = {
            add: vi.fn(async dataSource => {
                collection.push(dataSource);
                return dataSource;
            }),
            remove: vi.fn(dataSource => {
                const index = collection.indexOf(dataSource);
                if (index >= 0) collection.splice(index, 1);
                return index >= 0;
            }),
            getByName: vi.fn(name =>
                collection.filter(dataSource => dataSource.name === name)
            ),
            raiseToTop: vi.fn(),
        };
        global.Cesium = {
            GeoJsonDataSource: {
                load: vi.fn(() => loadPromise),
            },
        };

        const engine = bareEngine();
        engine._is3D = true;
        engine._cesiumViewer = { dataSources };
        engine._vectorLayerOrder = ['layer-a'];
        engine.vectorLayers.set('layer-a', {});
        engine._vectorGeoJSONSources.set('layer-a', {
            type: 'FeatureCollection',
            features: [{
                type: 'Feature',
                id: 'line-a',
                properties: {},
                geometry: {
                    type: 'LineString',
                    coordinates: [[0, 0], [10, 0]],
                },
            }],
        });
        engine._cesiumVectorDataSources.set('layer-a', oldDataSource);

        const synchronization = engine._syncSingleVectorToCesium('layer-a');
        await Promise.resolve();
        const duplicateSynchronization =
            engine._syncSingleVectorToCesium('layer-a');

        expect(dataSources.remove).not.toHaveBeenCalled();
        expect(collection).toContain(oldDataSource);
        await duplicateSynchronization;
        expect(global.Cesium.GeoJsonDataSource.load).toHaveBeenCalledOnce();

        resolveLoad(newDataSource);
        await synchronization;

        expect(collection).toEqual([newDataSource]);
        expect(dataSources.add.mock.invocationCallOrder[0]).toBeLessThan(
            dataSources.remove.mock.invocationCallOrder[0]
        );

        await engine._syncSingleVectorToCesium('layer-a');
        expect(global.Cesium.GeoJsonDataSource.load).toHaveBeenCalledOnce();
        expect(dataSources.remove).toHaveBeenCalledOnce();
    });

    it('notifies view listeners without letting one failure block the others', () => {
        const engine = bareEngine();
        const first = vi.fn(() => {
            throw new Error('listener failure');
        });
        const second = vi.fn();
        const unsubscribe = engine.onViewChange(first);
        engine.onViewChange(second);

        engine._emitViewChange();
        unsubscribe();
        engine._emitViewChange();

        expect(first).toHaveBeenCalledOnce();
        expect(second).toHaveBeenCalledTimes(2);
    });
});
