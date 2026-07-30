import { afterEach, describe, expect, it, vi } from 'vitest';

import { TimeSeriesModule } from '@app/modules/TimeSeriesModule.js';
import { Store } from '@app/store/index.js';


function createModule() {
    return new TimeSeriesModule({
        ui: {
            showGlobalLoader: vi.fn(),
            showToast: vi.fn(),
        },
        raster: {
            refreshData: vi.fn(async () => {}),
        },
    });
}


describe('TimeSeriesModule automatic workflow', () => {
    afterEach(() => {
        document.body.innerHTML = '';
        Store.state.rasters = [];
    });

    it('uses acquisition metadata and never treats upload time as acquisition time', () => {
        const module = createModule();

        expect(module._dateInfo({
            acquired_at: '2024-06-18T03:21:41Z',
            acquired_at_source: 'stac',
            acquired_at_confidence: 1,
            created_at: '2026-07-30T01:00:00Z',
        })).toEqual({
            date: '2024-06-18',
            source: 'stac',
            confidence: 1,
        });
        expect(module._dateInfo({
            file_name: 'renamed-image.tif',
            created_at: '2026-07-30T01:00:00Z',
        })).toBeNull();
    });

    it('automatically selects the largest compatible series candidate', () => {
        const module = createModule();
        const rasters = [
            {
                index_id: 1,
                platform: 'S2A',
                sensor: 'MSI',
                processing_level: 'L2A',
                tile_id: 'T49QGE',
                bands: 4,
            },
            {
                index_id: 2,
                platform: 'S2A',
                sensor: 'MSI',
                processing_level: 'L2A',
                tile_id: 'T49QGE',
                bands: 4,
            },
            {
                index_id: 3,
                platform: 'Landsat-9',
                sensor: 'OLI_TIRS',
                processing_level: 'L2SP',
                tile_id: '122/034',
                bands: 7,
            },
        ];

        expect([...module._automaticSelectionIds(rasters)]).toEqual(['1', '2']);
    });

    it('does not merge partial product metadata from different regions', () => {
        const module = createModule();
        const common = {
            platform: 'S2A',
            sensor: 'MSI',
            processing_level: 'L2A',
            tile_id: null,
            bands: 4,
        };
        const rasters = [
            {
                ...common,
                index_id: 1,
                bounds_wgs84: [115, 30, 115.01, 30.01],
            },
            {
                ...common,
                index_id: 2,
                bounds_wgs84: [115, 30, 115.01, 30.01],
            },
            {
                ...common,
                index_id: 3,
                bounds_wgs84: [116, 30, 116.01, 30.01],
            },
        ];

        expect([...module._automaticSelectionIds(rasters)]).toEqual(['1', '2']);
    });

    it('rejects impossible dates inferred from filenames', () => {
        const module = createModule();

        expect(module._dateInfo({ file_name: 'scene_20240229.tif' })?.date)
            .toBe('2024-02-29');
        expect(module._dateInfo({ file_name: 'scene_20230229.tif' })).toBeNull();
    });

    it('leaves automatic dates authoritative on the server', () => {
        document.body.innerHTML = `
            <select id="time-series-raster-select" multiple>
                <option value="1" selected>one</option>
            </select>
            <textarea id="time-series-dates-input">2024-06-18</textarea>
            <input id="time-series-band-index" value="1" />
            <input id="time-series-moving-window-size" value="3" />
            <input id="time-series-savgol-window-length" value="5" />
            <input id="time-series-savgol-polyorder" value="2" />
            <input id="time-series-phenology-threshold" value="0.2" />
            <input id="time-series-name-input" value="output" />
        `;
        Store.state.rasters = [{
            index_id: 1,
            acquired_at: '2024-06-18T03:21:41Z',
            bands: 1,
        }];
        const module = createModule();
        module.orderedRasters = [...Store.state.rasters];
        module.autoDatesText = '2024-06-18';

        expect(module._readPayload().dates).toBe('');

        document.getElementById('time-series-dates-input').value = '2024-06-19';
        expect(module._readPayload().dates).toBe('2024-06-19');
    });
});
