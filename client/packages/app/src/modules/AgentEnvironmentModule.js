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
        this._status('Loading configuration…');
        this._busy(true);
        try {
            this._populate(await AIAPI.getEnvironment());
            this._status('');
        } catch (error) {
            this._status(error.message, true);
        } finally {
            this._busy(false);
        }
    }

    _createDialog() {
        document.getElementById('ai-environment-dialog')?.remove();
        document.body.insertAdjacentHTML('beforeend', agentEnvironment);
        this.dialog = document.getElementById('ai-environment-dialog');
        this.dialog.addEventListener('close', () => {
            this._input('key').value = '';
            this.returnFocus?.focus();
        });
        this.dialog.querySelector('[data-environment-close]').addEventListener('click', () => this.dialog.close());
        this.dialog.addEventListener('submit', event => {
            event.preventDefault();
            void this.save();
        });
        this._input('reset').addEventListener('click', () => { void this.reset(); });
        this._input('provider').addEventListener('change', () => this._providerChanged());
        this._input('base').addEventListener('input', () => this._keyHint());
        applyTranslations(this.dialog);
    }

    _input(name) {
        return this.dialog.querySelector(`#ai-environment-${name}`);
    }

    _populate(data) {
        this.saved = data.settings;
        this.providers = data.providers;
        const select = this._input('provider');
        select.replaceChildren(...this.providers.map(provider => new Option(provider.name, provider.id)));
        select.value = this.providers.some(item => item.id === this.saved.provider) ? this.saved.provider : 'compatible';
        const preset = this.providers.find(item => item.id === select.value);
        this._input('model').value = (this.saved.model || '').replace(new RegExp(`^${select.value}/`), '');
        this._input('model').placeholder = t(preset?.model_hint || 'Model ID');
        this._input('base').value = this.saved.base_url || preset?.base_url || '';
        this._input('key').value = '';
        this._input('timeout').value = (this.saved.timeout_ms || 90000) / 1000;
        this._input('tokens').value = this.saved.max_tokens || 4096;
        this._input('reasoning').value = this.saved.tool_reasoning_effort || '';
        this._input('source').textContent = t(this.saved.source === 'ui' ? 'Using saved configuration' : 'Using .env / server environment');
        this._keyHint();
    }

    _providerChanged() {
        const preset = this.providers.find(item => item.id === this._input('provider').value);
        this._input('base').value = preset?.base_url || '';
        this._input('model').value = '';
        this._input('model').placeholder = t(preset?.model_hint || 'Model ID');
        this._input('key').value = '';
        this._input('reasoning').value = '';
        this._keyHint();
    }

    _keyHint() {
        const same = this.saved?.source === 'ui' && this.saved.has_api_key
            && this.saved.provider === this._input('provider').value
            && this.saved.base_url === this._input('base').value.replace(/\/+$/, '');
        const optional = this._input('provider').value === 'ollama';
        this._input('key').required = !same && !optional;
        this._input('key-hint').textContent = t(same
            ? 'Key saved. Leave blank to keep it for this provider and address.'
            : optional ? 'A local Ollama server does not require a key.'
                : 'Enter the key for this provider. Keys from .env are never shown or copied.');
    }

    _busy(value) {
        this.busy = value;
        this._input('fields').disabled = value || !this.saved;
        this._input('save').disabled = value || !this.saved;
        this._input('reset').disabled = value;
    }

    _status(message, error = false) {
        this._input('status').textContent = t(message);
        this._input('status').dataset.error = String(error);
    }

    async save() {
        if (this.busy || !this.dialog.querySelector('form').reportValidity()) return;
        const payload = {
            provider: this._input('provider').value,
            model: this._input('model').value.trim(),
            base_url: this._input('base').value.trim(),
            api_key: this._input('key').value || null,
            timeout_ms: Math.round(Number(this._input('timeout').value) * 1000),
            max_tokens: Number(this._input('tokens').value),
            tool_reasoning_effort: this._input('reasoning').value || null,
        };
        this._busy(true);
        this._status('Saving configuration…');
        try {
            this._populate(await AIAPI.saveEnvironment(payload));
            this._status('Saved. The next AI request will use this configuration.');
        } catch (error) {
            this._status(error.message, true);
        } finally {
            this._input('key').value = '';
            payload.api_key = null;
            this._busy(false);
        }
    }

    async reset() {
        if (this.busy) return;
        this._busy(true);
        try {
            this._populate(await AIAPI.resetEnvironment());
            this._status('Restored .env / server environment defaults.');
        } catch (error) {
            this._status(error.message, true);
        } finally {
            this._busy(false);
        }
    }
}
