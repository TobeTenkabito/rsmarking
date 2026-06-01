import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { AIAPI } from '@app/api/ai.js';
import { VectorAPI } from '@app/api/vector.js';
import { MapEngine } from '@core/map.js';


function jsonResponse(payload) {
    return {
        ok: true,
        status: 200,
        json: vi.fn(async () => payload),
    };
}


describe('service port routing', () => {
    beforeEach(() => {
        global.fetch.mockReset();
        global.fetch.mockResolvedValue(jsonResponse([]));
    });

    afterEach(() => {
        vi.restoreAllMocks();
    });

    it('sends vector project requests to the annotation port', async () => {
        await VectorAPI.fetchProjects();

        expect(global.fetch.mock.calls[0][0]).toBe('http://localhost:8001/projects');
    });

    it('builds vector tile templates for the vector tile port', () => {
        vi.spyOn(Date, 'now').mockReturnValue(1732);

        expect(VectorAPI.getMvtUrlTemplate('layer-a')).toBe(
            'http://localhost:8003/tiles/layer-a/{z}/{x}/{y}.pbf?t=1732'
        );
    });

    it('lists AI functions through the AI gateway port', async () => {
        await AIAPI.listFunctions('catalog');

        expect(global.fetch).toHaveBeenCalledWith(
            'http://localhost:8006/ai/functions?format=catalog'
        );
    });

    it('runs AI agent requests through the AI gateway port', async () => {
        await AIAPI.agent({ user_prompt: 'Create NDVI', language: 'en' });

        expect(global.fetch.mock.calls[0][0]).toBe('http://localhost:8006/ai/agent');
    });

    it('archives AI conversations through the AI gateway port', async () => {
        await AIAPI.archiveConversation({
            session_id: 'session-a',
            messages: [{ role: 'user', content: 'hello' }],
        });

        expect(global.fetch.mock.calls[0][0]).toBe('http://localhost:8006/ai/conversations');
    });

    it('clears archived AI conversations through the AI gateway port', async () => {
        await AIAPI.clearConversations();

        expect(global.fetch).toHaveBeenCalledWith(
            'http://localhost:8006/ai/conversations',
            { method: 'DELETE' }
        );
    });

    it('keeps raster tile requests on the tile service port', () => {
        const map = {
            setView: vi.fn(function setView() {
                return this;
            }),
        };
        const mapControl = { addTo: vi.fn() };
        const baseLayer = { addTo: vi.fn() };
        global.L.map.mockReturnValue(map);
        global.L.control = { zoom: vi.fn(() => mapControl) };
        global.L.tileLayer = vi.fn(() => baseLayer);
        vi.spyOn(console, 'group').mockImplementation(() => {});
        vi.spyOn(console, 'groupEnd').mockImplementation(() => {});
        vi.spyOn(console, 'log').mockImplementation(() => {});

        const engine = new MapEngine('map');

        expect(engine.tileServiceBase).toBe('http://localhost:8005');
    });
});
