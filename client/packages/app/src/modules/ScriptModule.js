import { Store } from '../store/index.js';
import { RasterAPI } from '../api/raster.js';
import { ModalComponent } from '../../../ui/src/components/Modal.js';
import { applyTranslations, t } from '../i18n/index.js';

export class ScriptModule {
    constructor(app) {
        this.app = app;
        this.currentScript = '';
        this.selectedRasterIds = [];
        this.outputName = '';
        this.isExecuting = false;
        this.scriptHistory = this.loadScriptHistory();
        this._templatePromise = null;
        this._templateCache = null;
        this._validationFrame = null;
    }

    /**
     * Open script editor modal
     */
    openScriptEditor() {
        const modal = document.getElementById('script-modal');
        if (!modal) {
            console.error('[ScriptModule] Script editor modal not found');
            return;
        }

        // Render content
        const content = document.getElementById('script-content');
        content.innerHTML = ModalComponent.renderScriptEditor(
            Store.getRasters(),
            this.selectedRasterIds,
            this.currentScript
        );
        applyTranslations(content);

        // Show modal
        modal.classList.remove('hidden');

        // Bind editor events
        this.bindEditorEvents();

        // Load template selector
        this.loadTemplates();

        // Initialize code highlighting（if available）
        this.initializeCodeHighlight();
    }

    /**
     * Close script editor
     */
    closeScriptEditor() {
        const modal = document.getElementById('script-modal');
        modal?.classList.add('hidden');

        // Save current script to draft
        this.saveDraft();
    }

    /**
     * Bind editor events
     */
    bindEditorEvents() {
        // Script content changed
        const editor = document.getElementById('script-editor-textarea');
        if (editor) {
            editor.addEventListener('input', (e) => {
                this.currentScript = e.target.value;
                this.scheduleScriptValidation();
            });

            // Tabkey support
            editor.addEventListener('keydown', (e) => {
                if (e.key === 'Tab') {
                    e.preventDefault();
                    const start = editor.selectionStart;
                    const end = editor.selectionEnd;
                    editor.value = editor.value.substring(0, start) + '    ' + editor.value.substring(end);
                    editor.selectionStart = editor.selectionEnd = start + 4;
                    this.currentScript = editor.value;
                    this.scheduleScriptValidation();
                }
            });
        }

        // Raster selection changed
        const rasterCheckboxes = document.querySelectorAll('.script-raster-checkbox');
        rasterCheckboxes.forEach(checkbox => {
            checkbox.addEventListener('change', (e) => {
                const id = parseInt(e.target.value);
                if (e.target.checked) {
                    if (!this.selectedRasterIds.includes(id)) {
                        this.selectedRasterIds.push(id);
                    }
                } else {
                    this.selectedRasterIds = this.selectedRasterIds.filter(rid => rid !== id);
                }
                this.updateSelectedCount();
            });
        });

        // Output File Name
        const outputInput = document.getElementById('script-output-name');
        if (outputInput) {
            outputInput.addEventListener('input', (e) => {
                this.outputName = e.target.value;
            });
        }
    }

    /**
     * Base64 encode with Unicode support
     */
    encodeBase64(str) {
        return btoa(encodeURIComponent(str).replace(/%([0-9A-F]{2})/g, (match, p1) => {
            return String.fromCharCode(parseInt(p1, 16));}));}

    /**
     * Base64 decode with Unicode support
     */
    decodeBase64(str) {
        return decodeURIComponent(atob(str).split('').map(c => {
            return '%' + ('00' + c.charCodeAt(0).toString(16)).slice(-2);
        }).join(''));
    }

    /**
     * Load script templates
     */
    async loadTemplates() {
        try {
            const templates = await this._getTemplates();
            const selector = document.getElementById('script-template-selector');

            if (selector && templates) {
                selector.innerHTML = '<option value="">-- Select Template --</option>' +
                    templates.map(t => {
                        // Use Unicode-safe Base64 encoding
                        const encodedCode = this.encodeBase64(t.code);
                        return `<option value="${encodedCode}">${t.name} - ${t.description}</option>`;
                    }).join('');
                applyTranslations(selector);

                selector.addEventListener('change', (e) => {
                    if (e.target.value) {
                        const code = this.decodeBase64(e.target.value);
                        document.getElementById('script-editor-textarea').value = code;
                        this.currentScript = code;
                        this.scheduleScriptValidation();
                    }
                });
            }
        } catch (error) {
            console.error('[ScriptModule] Template load failed:', error);
        }
    }

    /**
     * Run Script
     */
    async executeScript() {
        if (this.isExecuting) return;

        // Validate input
        if (!this.currentScript.trim()) {
            alert(t('script.validation.empty'));
            return;
        }

        if (this.selectedRasterIds.length === 0) {
            alert(t('script.alert.selectRaster'));
            return;
        }

        if (!this.outputName.trim()) {
            this.outputName = `script_output_${Date.now()}.tif`;
            document.getElementById('script-output-name').value = this.outputName;
        }

        this.isExecuting = true;
        this.updateExecutionUI(true);

        try {
            // Show progress
            this.app.ui.showGlobalLoading(t('script.validation.running'));

            // Call API
            const result = await RasterAPI.executeScript(
                this.currentScript,
                this.selectedRasterIds,
                this.outputName
            );

            if (result?.status === 'success') {
                this.app.ui.showToast(t('script.toast.success'), 'success');

                // Show execution logs（if available）
                // Save to history
                this.saveToHistory();

                // Refresh data
                await this.app.raster.refreshData();

                // Close modal
                this.closeScriptEditor();
            } else {
                throw new Error(result?.error || result?.message || 'Script execution failed');
            }
        } catch (error) {
            console.error('[ScriptModule] Execution failed:', error);
            this.app.ui.showToast(t('script.toast.failed', { message: error.message }), 'error');
        } finally {
            this.isExecuting = false;
            this.updateExecutionUI(false);
            this.app.ui.hideGlobalLoading();
        }
    }

    /**
     * Update execution UI state
     */
    updateExecutionUI(isExecuting) {
        const executeBtn = document.getElementById('script-execute-btn');
        const cancelBtn = document.getElementById('script-cancel-btn');

        if (executeBtn) {
            executeBtn.disabled = isExecuting;
            executeBtn.textContent = isExecuting ? t('script.execute.running') : t('script.execute.idle');
        }

        if (cancelBtn) {
            cancelBtn.disabled = isExecuting;
        }
    }

    scheduleScriptValidation() {
        if (this._validationFrame) return;
        this._validationFrame = requestAnimationFrame(() => {
            this._validationFrame = null;
            this.updateScriptValidation();
        });
    }

    /**
     * Validate script syntax
     */
    updateScriptValidation() {
        const validationDiv = document.getElementById('script-validation');
        if (!validationDiv) return;

        const script = this.currentScript.trim();

        if (!script) {
            validationDiv.innerHTML = `<span class="text-gray-400">${t('script.validation.empty')}</span>`;
            return;
        }

        // Basic syntax check
        const issues = [];

        // Check dangerous keywords
        const dangerous = ['__import__', 'exec', 'eval', 'compile', '__builtins__'];
        dangerous.forEach(keyword => {
            if (script.includes(keyword)) {
                issues.push(`Contains blocked keyword: ${keyword}`);
            }
        });

        // Check required imports
        if (!script.includes('import rasterio') && !script.includes('from rasterio')) {
            issues.push('Consider importing rasterio for raster processing');
        }

        // Show validation result
        if (issues.length > 0) {
            validationDiv.innerHTML = `
                <div class="text-amber-600 text-xs">
                    <div class="font-bold mb-1">⚠️ Warning:</div>
                    ${issues.map(i => `<div>• ${i}</div>`).join('')}
                </div>
            `;
        } else {
            validationDiv.innerHTML = `<span class="text-green-600 text-xs">${t('script.validation.ok')}</span>`;
        }
    }

    /**
     * Update selected-count display
     */
    updateSelectedCount() {
        const countDiv = document.getElementById('script-selected-count');
        if (countDiv) {
            countDiv.textContent = `Selected ${this.selectedRasterIds.length} imagery items`;
        }
    }

    /**
     * Save draft
     */
    saveDraft() {
        if (this.currentScript.trim()) {
            localStorage.setItem('rsmarking_script_draft', JSON.stringify({
                script: this.currentScript,
                rasterIds: this.selectedRasterIds,
                outputName: this.outputName,
                timestamp: Date.now()
            }));
        }
    }

    /**
     * Load draft
     */
    loadDraft() {
        try {
            const draft = localStorage.getItem('rsmarking_script_draft');
            if (draft) {
                const data = JSON.parse(draft);
                // Only load drafts from the last 24 hours
                if (Date.now() - data.timestamp < 24 * 60 * 60 * 1000) {
                    this.currentScript = data.script || '';
                    this.selectedRasterIds = data.rasterIds || [];
                    this.outputName = data.outputName || '';
                    return true;
                }
            }
        } catch (e) {
            console.error('[ScriptModule] Draft load failed:', e);
        }
        return false;
    }

    /**
     * EnglishHistory
     */
    saveToHistory() {
        const history = {
            script: this.currentScript,
            rasterIds: this.selectedRasterIds,
            outputName: this.outputName,
            timestamp: Date.now(),
            id: Date.now().toString()
        };

        this.scriptHistory.unshift(history);
        // Keep only the latest 20 entries
        this.scriptHistory = this.scriptHistory.slice(0, 20);

        localStorage.setItem('rsmarking_script_history', JSON.stringify(this.scriptHistory));
    }

    /**
     * EnglishHistory
     */
    loadScriptHistory() {
        try {
            const history = localStorage.getItem('rsmarking_script_history');
            return history ? JSON.parse(history) : [];
        } catch (e) {
            return [];
        }
    }

    /**
     * EnglishHistory
     */
    async _getTemplates() {
        if (this._templateCache) return this._templateCache;
        if (!this._templatePromise) {
            this._templatePromise = RasterAPI.getScriptTemplates()
                .then((templates) => {
                    this._templateCache = templates ?? [];
                    return this._templateCache;
                })
                .finally(() => {
                    this._templatePromise = null;
                });
        }
        return this._templatePromise;
    }

    showHistory() {
        const historyDiv = document.getElementById('script-history');
        if (!historyDiv) return;

        if (this.scriptHistory.length === 0) {
            historyDiv.innerHTML = `<div class="text-gray-400 text-xs text-center py-4">${t('script.history.empty')}</div>`;
            return;
        }

        historyDiv.innerHTML = this.scriptHistory.map(h => `
            <div class="border rounded p-2 mb-2 hover:bg-gray-50 cursor-pointer" onclick="RS.loadScriptFromHistory('${h.id}')">
                <div class="text-xs font-bold">${h.outputName}</div>
                <div class="text-xs text-gray-500">${new Date(h.timestamp).toLocaleString()}</div>
            </div>
        `).join('');
    }

    /**
     * Load script from history
     */
    loadFromHistory(historyId) {
        const history = this.scriptHistory.find(h => h.id === historyId);
        if (history) {
            this.currentScript = history.script;
            this.selectedRasterIds = history.rasterIds;
            this.outputName = history.outputName;

            // Update UI
            const editor = document.getElementById('script-editor-textarea');
            if (editor) editor.value = this.currentScript;

            const outputInput = document.getElementById('script-output-name');
            if (outputInput) outputInput.value = this.outputName;

            this.updateScriptValidation();
            this.updateSelectedCount();
        }
    }

    /**
     * Initialize code highlighting
     */
    initializeCodeHighlight() {
        // If a code highlighting library is included（such asPrism.jsEnglishhighlight.js），initialize it here
        if (window.Prism) {
            Prism.highlightAll();
        }
    }

    /**
     * Clear Editor
     */
    clearEditor() {
        this.currentScript = '';
        this.selectedRasterIds = [];
        this.outputName = '';

        const editor = document.getElementById('script-editor-textarea');
        if (editor) editor.value = '';

        const outputInput = document.getElementById('script-output-name');
        if (outputInput) outputInput.value = '';

        const checkboxes = document.querySelectorAll('.script-raster-checkbox');
        checkboxes.forEach(cb => cb.checked = false);

        this.updateScriptValidation();
        this.updateSelectedCount();
    }
}
