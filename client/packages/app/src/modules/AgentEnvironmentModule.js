import { AIAPI } from '../api/ai.js';
import { applyTranslations, t } from '../i18n/index.js';
import { agentEnvironment } from '../../../ui/src/templates/modals/agentEnvironment.js';

export class AgentEnvironmentModule {
    constructor() {
        this.dialog = null;
        this.providers = [];
        this.saved = null;
        this.busy = false;
    }

    async open() {
        if (!this.dialog?.isConnected) this._createDialog();
        if (this.dialog.open) return;
        this.returnFocus = document.activeElement;
        this.dialog.showModal();
        this._showStatus('Loading configuration…');
        this._setLoading(true);
        try {
            this._populateSettings(await AIAPI.getEnvironment());
            this._showStatus('');
        } catch (error) {
            this._showStatus(error.message, true);
        } finally {
            this._setLoading(false);
        }
    }

    _createDialog() {
        document.getElementById('ai-environment-dialog')?.remove();
        document.body.insertAdjacentHTML('beforeend', agentEnvironment);
        this.dialog = document.getElementById('ai-environment-dialog');
        this.dialog.addEventListener('close', () => {
            this._getElement('key').value = '';
            this.returnFocus?.focus();
        });
        this.dialog.querySelector('[data-environment-close]').addEventListener('click', () => {
            this.dialog.close();
        });
        this.dialog.addEventListener('submit', event => {
            event.preventDefault();
            void this.save();
        });
        this._getElement('reset').addEventListener('click', () => {
            void this.reset();
        });
        this._getElement('provider').addEventListener('change', () => this._handleProviderChange());
        this._getElement('base').addEventListener('input', () => this._updateKeyHint());
        applyTranslations(this.dialog);
    }

    _getElement(name) {
        return this.dialog.querySelector(`#ai-environment-${name}`);
    }

    _populateSettings(data) {
        this.saved = data.settings;
        this.providers = data.providers;
        const providerSelect = this._getElement('provider');
        const providerOptions = this.providers.map(provider => new Option(provider.name, provider.id));
        providerSelect.replaceChildren(...providerOptions);
        providerSelect.value = this.providers.some(provider => provider.id === this.saved.provider)
            ? this.saved.provider
            : 'compatible';
        const preset = this.providers.find(provider => provider.id === providerSelect.value);
        this._getElement('model').value = (this.saved.model || '').replace(new RegExp(`^${providerSelect.value}/`), '');
        this._getElement('model').placeholder = t(preset?.model_hint || 'Model ID');
        this._getElement('base').value = this.saved.base_url || preset?.base_url || '';
        this._getElement('key').value = '';
        this._getElement('timeout').value = (this.saved.timeout_ms || 90000) / 1000;
        this._getElement('tokens').value = this.saved.max_tokens || 4096;
        this._getElement('reasoning').value = this.saved.tool_reasoning_effort || '';
        this._getElement('source').textContent = t(this.saved.source === 'ui'
            ? 'Using saved configuration'
            : 'Using .env / server environment');
        this._updateKeyHint();
    }

    _handleProviderChange() {
        const preset = this.providers.find(item => item.id === this._getElement('provider').value);
        this._getElement('base').value = preset?.base_url || '';
        this._getElement('model').value = '';
        this._getElement('model').placeholder = t(preset?.model_hint || 'Model ID');
        this._getElement('key').value = '';
        this._getElement('reasoning').value = '';
        this._updateKeyHint();
    }

    _updateKeyHint() {
        const hasSavedKey = this.saved?.source === 'ui' && this.saved.has_api_key
            && this.saved.provider === this._getElement('provider').value
            && this.saved.base_url === this._getElement('base').value.replace(/\/+$/, '');
        const isOllama = this._getElement('provider').value === 'ollama';
        this._getElement('key').required = !hasSavedKey && !isOllama;

        let hint = 'Enter the key for this provider. Keys from .env are never shown or copied.';
        if (hasSavedKey) {
            hint = 'Key saved. Leave blank to keep it for this provider and address.';
        } else if (isOllama) {
            hint = 'A local Ollama server does not require a key.';
        }
        this._getElement('key-hint').textContent = t(hint);
    }

    _setLoading(value) {
        this.busy = value;
        this._getElement('fields').disabled = value || !this.saved;
        this._getElement('save').disabled = value || !this.saved;
        this._getElement('reset').disabled = value;
    }

    _showStatus(message, error = false) {
        this._getElement('status').textContent = t(message);
        this._getElement('status').dataset.error = String(error);
    }

    async save() {
        if (this.busy || !this.dialog.querySelector('form').reportValidity()) return;
        const payload = {
            provider: this._getElement('provider').value,
            model: this._getElement('model').value.trim(),
            base_url: this._getElement('base').value.trim(),
            api_key: this._getElement('key').value || null,
            timeout_ms: Math.round(Number(this._getElement('timeout').value) * 1000),
            max_tokens: Number(this._getElement('tokens').value),
            tool_reasoning_effort: this._getElement('reasoning').value || null,
        };
        this._setLoading(true);
        this._showStatus('Saving configuration…');
        try {
            this._populateSettings(await AIAPI.saveEnvironment(payload));
            this._showStatus('Saved. The next AI request will use this configuration.');
        } catch (error) {
            this._showStatus(error.message, true);
        } finally {
            this._getElement('key').value = '';
            payload.api_key = null;
            this._setLoading(false);
        }
    }

    async reset() {
        if (this.busy) return;
        this._setLoading(true);
        try {
            this._populateSettings(await AIAPI.resetEnvironment());
            this._showStatus('Restored .env / server environment defaults.');
        } catch (error) {
            this._showStatus(error.message, true);
        } finally {
            this._setLoading(false);
        }
    }
}
