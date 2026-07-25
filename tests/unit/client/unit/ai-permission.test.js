import { afterEach, describe, expect, it } from 'vitest';

import { AIModule } from '../../../../client/packages/app/src/modules/AIModule.js';
import { aiModal } from '../../../../client/packages/ui/src/templates/modals/aiModal.js';


describe('AI agent permission tiers', () => {
    afterEach(() => {
        document.body.innerHTML = '';
    });

    it('renders all four permission choices', () => {
        expect(aiModal).toContain('value="read_only"');
        expect(aiModal).toContain('value="safe"');
        expect(aiModal).toContain('value="standard"');
        expect(aiModal).toContain('value="full_control"');
    });

    it('sends the selected permission only for Agent requests', () => {
        document.body.innerHTML = `
            <select id="ai-permission-select">
                <option value="standard">Standard</option>
                <option value="full_control" selected>Full control</option>
            </select>
        `;
        const module = new AIModule({});
        module._collectMapContext = () => ({});

        const agentPayload = module._buildRequestPayload({
            targetId: null,
            dataType: 'raster',
            language: 'en',
            prompt: 'Take over this project.',
            mode: 'agent',
        });
        const analyzePayload = module._buildRequestPayload({
            targetId: 1,
            dataType: 'raster',
            language: 'en',
            prompt: 'Analyze this raster.',
            mode: 'analyze',
        });

        expect(agentPayload.permission_level).toBe('full_control');
        expect(analyzePayload).not.toHaveProperty('permission_level');
    });

    it('shows an explicit warning when full control is selected', () => {
        document.body.innerHTML = `
            <select id="ai-permission-select">
                <option value="full_control" selected>Full control</option>
            </select>
            <div id="ai-permission-banner"></div>
        `;
        const module = new AIModule({});

        module._syncPermissionUI();

        expect(document.getElementById('ai-permission-banner').textContent)
            .toContain('autonomously change or delete project data');
        expect(document.getElementById('ai-permission-banner').textContent)
            .toContain('Source code and host files remain protected');
    });
});
