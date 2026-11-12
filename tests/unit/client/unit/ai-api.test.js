import { afterEach, describe, expect, it } from 'vitest';

import { AIAPI } from '@app/api/ai.js';


describe('AIAPI usage limits', () => {
    afterEach(() => {
        global.fetch.mockReset();
    });

    it('does not impose a tool-turn budget on ordinary Agent requests', async () => {
        global.fetch.mockResolvedValueOnce({
            ok: true,
            json: async () => ({ status: 'success' }),
        });

        await AIAPI.agent({ prompt: 'Extract the coastline.' });

        const [, options] = global.fetch.mock.calls[0];
        const payload = JSON.parse(options.body);
        expect(payload.max_steps).toBeNull();
        expect(payload).not.toHaveProperty('max_tool_calls');
        expect(payload).not.toHaveProperty('max_model_calls');
        expect(payload).not.toHaveProperty('agent_token_budget');
    });

    it('preserves limits explicitly supplied by the caller', async () => {
        global.fetch.mockResolvedValueOnce({
            ok: true,
            json: async () => ({ status: 'success' }),
        });
        const request = {
            prompt: 'Inspect the image.',
            max_steps: 2,
            max_tool_calls: 6,
            max_model_calls: 8,
            agent_token_budget: 100000,
        };

        await AIAPI.agent(request);

        const [, options] = global.fetch.mock.calls[0];
        expect(JSON.parse(options.body)).toEqual(request);
    });
});
