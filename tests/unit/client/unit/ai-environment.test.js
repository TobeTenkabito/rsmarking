import { beforeEach, afterEach, describe, expect, it, vi } from 'vitest';
import { AIAPI } from '@app/api/ai.js';
import { AIModule } from '@app/modules/AIModule.js';
import { AgentEnvironmentModule } from '@app/modules/AgentEnvironmentModule.js';
import { Store } from '@app/store/index.js';

const provider = { id: 'openai', name: 'OpenAI', base_url: 'https://api.openai.com/v1' };
const configured = {
    settings: {
        source: 'ui',
        provider: 'openai',
        model: 'test-model',
        base_url: provider.base_url,
        has_api_key: true,
    },
    providers: [provider, { id: 'compatible', name: 'Custom', base_url: '' }],
};

beforeEach(() => {
    document.body.innerHTML = '';
    localStorage.clear();
    HTMLDialogElement.prototype.showModal = vi.fn(function () {
        this.open = true;
    });
    HTMLDialogElement.prototype.close = vi.fn(function () {
        this.open = false;
        this.dispatchEvent(new Event('close'));
    });
});
afterEach(() => {
    vi.restoreAllMocks();
    delete HTMLDialogElement.prototype.showModal;
    delete HTMLDialogElement.prototype.close;
});

describe('Agent environment', () => {
    it('keeps secrets out of storage and clears the password on save and close', async () => {
        vi.spyOn(AIAPI, 'getEnvironment').mockResolvedValue(configured);
        let submitted;
        vi.spyOn(AIAPI, 'saveEnvironment').mockImplementation(async payload => {
            submitted = structuredClone(payload);
            return configured;
        });
        const environment = new AgentEnvironmentModule();
        await environment.open();
        const key = document.getElementById('ai-environment-key');
        expect(key.value).toBe('');
        expect(key.required).toBe(false);
        key.value = 'fake-key-for-ui-test';
        await environment.save();
        expect(submitted.api_key).toBe('fake-key-for-ui-test');
        expect(key.value).toBe('');
        expect(localStorage.length).toBe(0);
        key.value = 'discard-this-key';
        environment.dialog.close();
        expect(key.value).toBe('');
    });

    it('requires a new key when the provider or address changes', async () => {
        vi.spyOn(AIAPI, 'getEnvironment').mockResolvedValue(configured);
        const environment = new AgentEnvironmentModule();
        await environment.open();
        const key = document.getElementById('ai-environment-key');
        const base = document.getElementById('ai-environment-base');
        base.value = 'https://another.example/v1';
        base.dispatchEvent(new Event('input'));
        expect(key.required).toBe(true);
        key.value = 'do-not-carry-over';
        const select = document.getElementById('ai-environment-provider');
        select.value = 'compatible';
        select.dispatchEvent(new Event('change'));
        expect(key.value).toBe('');
        expect(base.value).toBe('');
    });

    it('reports save failures, clears the submitted key, and restores controls', async () => {
        vi.spyOn(AIAPI, 'getEnvironment').mockResolvedValue(configured);
        vi.spyOn(AIAPI, 'saveEnvironment').mockRejectedValue(new Error('Save failed'));
        const environment = new AgentEnvironmentModule();
        await environment.open();
        document.getElementById('ai-environment-key').value = 'discard-on-failure';
        await environment.save();
        expect(document.getElementById('ai-environment-status').textContent).toBe('Save failed');
        expect(document.getElementById('ai-environment-key').value).toBe('');
        expect(document.getElementById('ai-environment-save').disabled).toBe(false);
    });
});

describe('Workspace imports on the map', () => {
    it('refreshes projects, selects the new project and enables its imported layer once', async () => {
        Store.state.visibleVectorLayerIds = new Set();
        const app = {
            project: {
                refreshProjects: vi.fn(),
                handleSelectProject: vi.fn(),
            },
            mapController: {
                toggleVectorLayer: vi.fn(id => Store.state.visibleVectorLayerIds.add(id)),
                updateUI: vi.fn(),
            },
        };
        const ai = new AIModule(app);
        const result = [{ data_type: 'vector', project_id: 'project', layer_id: 'layer' }];
        await ai._applyWorkspaceImports(result);
        await ai._applyWorkspaceImports(result);
        expect(app.project.handleSelectProject).toHaveBeenCalledWith('project');
        expect(app.mapController.toggleVectorLayer).toHaveBeenCalledTimes(1);
        expect(Store.state.activeVectorLayerId).toBe('layer');
    });
});
