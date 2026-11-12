import { AIAPI } from '../api/ai.js';
import { Store } from '../store/index.js';
import { ModalComponent } from '../../../ui/src/components/Modal.js';
import { SidebarComponent } from '../../../ui/src/components/Sidebar.js';
import { getLanguage, t } from '../i18n/index.js';
import { renderAgentMarkdown } from '../utils/agentMarkdown.js';
import { AgentEnvironmentModule } from './AgentEnvironmentModule.js';

const AGENT_ATTACHMENT_LIMIT = 6;
const AGENT_TEXT_EXCERPT_CHARS = 12000;
const AGENT_TEXT_FILE_BYTES = 512 * 1024;
const AGENT_IMAGE_FILE_BYTES = 3 * 1024 * 1024;
const AGENT_IMAGE_MIME_TYPES = new Set([
    'image/png',
    'image/jpeg',
    'image/webp',
    'image/gif',
]);

export class AIModule {
    constructor(app) {
        this.app = app;
        this.environment = new AgentEnvironmentModule();

        // English AI English
        // English"English vs English"English
        this._pendingPayload = null;
        this._pendingResult  = null;
        this._sessionId = this._createSessionId();
        this._agentConversation = [];
        this._functionCatalog = [];
        this._selectedFunction = null;
        this._selectedFunctionCategory = '';
        this._functionsLoading = false;
        this._functionCatalogError = '';
        this._conversationArchives = [];
        this._archivePanelOpen = true;
        this._activeArchiveId = null;
        this._saveTail = Promise.resolve();
        this._conversationSwitching = false;
        this._historyError = '';
        this._sendMode = this._readPreference('send-mode', 'enter');
        this._archivesLoading = false;
        this._agentAttachments = [];
        this._agentQueueTail = Promise.resolve();
        this._agentQueueDepth = 0;
        this._loadingDepth = 0;
    }

    openModal() {
        const modal = document.getElementById('ai-modal');
        if (!modal) return;
        if (modal.classList.contains('hidden')) this._returnFocus = document.activeElement;

        // English Store English/VectorEnglish
        const rasters = Store.getRasters();
        const Layers = Store.getVectorLayers();
        document.getElementById('ai-target-select').innerHTML =
            ModalComponent.renderAITargetOptions(rasters, Layers);
        const modeSelect = document.getElementById('ai-mode-select');
        if (modeSelect) modeSelect.value = 'agent';
        const languageSelect = document.getElementById('ai-language-select');
        if (languageSelect) languageSelect.value = getLanguage();

        this._bindModalEvents();
        this._syncDataTypeWithTarget();
        this._syncModeUI();
        this._renderFunctionCatalog();
        void this.loadFunctionCatalog();
        void this.loadConversationArchives();

        modal.classList.remove('hidden');
        document.getElementById('ai-prompt-input')?.focus();
    }

    closeModal() {
        document.getElementById('ai-modal')?.classList.add('hidden');
        this._resetState();
        this._returnFocus?.focus?.();
    }

    async execute() {
        if (this._loadingDepth || this._conversationSwitching) return;
        const targetId  = document.getElementById('ai-target-select')?.value;
        const dataType  = document.getElementById('ai-datatype-select')?.value;   // 'raster' | 'vector'
        const mode      = document.getElementById('ai-mode-select')?.value;       // 'analyze' | 'modify' | 'agent'
        const language  = document.getElementById('ai-language-select')?.value;   // 'zh' | 'en' | 'ja' | 'es'
        let prompt      = document.getElementById('ai-prompt-input')?.value?.trim();

        if (mode === 'agent' && !prompt && this._agentAttachments.length) {
            prompt = 'Please analyze the attached file(s).';
        }

        if (!prompt || (mode !== 'agent' && !targetId)) {
            this._showError(t('ai.error.missingTargetPrompt'));
            return;
        }

        const payload = this._buildRequestPayload({
            targetId,
            dataType,
            language,
            prompt,
            mode,
        });

        this._setLoading(true);
        if (mode === 'agent') {
            this._clearTransientMessages();
        } else {
            this._clearResult();
        }

        try {
            if (mode === 'analyze') {
                await this._runAnalyze(payload);
            } else if (mode === 'modify') {
                await this._runModify(payload);
            } else {
                await this._runAgent(payload);
            }
        } catch (err) {
            this._showError(err.message);
        } finally {
            this._setLoading(false);
        }
    }

    async _runAnalyze(payload) {
        const result = await AIAPI.analyze(payload);

        // English
        const reportEl = document.getElementById('ai-result-content');
        if (reportEl) {
            reportEl.innerHTML = this._renderMarkdown(result.report);
            reportEl.classList.add('ai-result-markdown');
        }

        // English
        const downloadBtn = document.getElementById('ai-download-btn');
        if (downloadBtn && result.file_url) {
            downloadBtn.href = AIAPI.resolveURL(result.file_url);
            downloadBtn.download = result.artifact?.name || 'ai-analysis.md';
            const label = downloadBtn.querySelector('span');
            if (label) label.textContent = `Download ${result.artifact?.name || 'Analysis Report'}`;
            downloadBtn.classList.remove('hidden');
        }

        document.getElementById('ai-result-section')?.classList.remove('hidden');
    }

    async _runModify(payload) {
        const result = await AIAPI.modify(payload);

        // English payload English，English
        this._pendingPayload = payload;
        this._pendingResult  = result;

        // English：English AI returnsEnglish
        const previewEl = document.getElementById('ai-result-content');
        if (previewEl) {
            previewEl.textContent = JSON.stringify(result.modified_data, null, 2);
        }

        // English"English"English"English"English
        document.getElementById('ai-confirm-section')?.classList.remove('hidden');
        document.getElementById('ai-result-section')?.classList.remove('hidden');
    }

    async _runAgent(payload, retryMessage = null) {
        payload = { ...payload, request_id: payload.request_id || this._createMessageId() };
        const promptInput = document.getElementById('ai-prompt-input');
        const userMessage = {
            id: this._createMessageId(),
            role: 'user',
            content: payload.user_prompt,
            attachments: this._displayAttachments(payload.attachments ?? []),
        };
        const assistantMessage = retryMessage || {
            id: this._createMessageId(),
            role: 'assistant',
            content: '',
            visibleContent: '',
            pending: true,
            pendingLabel: this._agentQueueDepth > 0 ? 'Queued' : 'Waiting for AI response',
            steps: [],
            streaming: false,
        };
        Object.assign(assistantMessage, { pending: true, error: false, content: '', visibleContent: '', retryPayload: payload });
        if (!retryMessage) this._agentConversation.push(userMessage, assistantMessage);
        this._renderAgentConversation();
        if (promptInput && !retryMessage) promptInput.value = '';
        this._resizeComposer();
        if (!retryMessage) this._clearAgentAttachments();
        void this._saveConversation();

        this._agentQueueDepth += 1;
        const runRequest = async () => {
            assistantMessage.pendingLabel = 'Waiting for AI response';
            assistantMessage.progress = null;
            assistantMessage.elapsedSeconds = 0;
            this._renderAgentConversation();
            const stopProgress = this._startAgentProgress(payload, assistantMessage);

            try {
                let result;
                try {
                    result = await AIAPI.agent(payload);
                } catch (err) {
                    assistantMessage.pending = false;
                    assistantMessage.error = true;
                    assistantMessage.content = err.message || 'Agent request failed.';
                    this._renderAgentConversation();
                    throw err;
                }

                if (result.session_id) this._sessionId = result.session_id;
                assistantMessage.pending = false;
                assistantMessage.error = result.status === 'interrupted';
                if (!assistantMessage.error) delete assistantMessage.retryPayload;
                assistantMessage.steps = result.steps ?? [];
                assistantMessage.workflow = result.workflow ?? null;
                assistantMessage.artifacts = this._displayArtifacts(result.artifacts ?? []);
                const answer = `${result.answer ?? ''}${assistantMessage.error && result.error ? `\n\n${result.error}` : ''}`;
                await this._revealAgentResponse(assistantMessage, answer);
                if ((result.used_tools ?? []).some(name => name !== 'clip_vector_by_raster')) {
                    await this._refreshSidebar('raster');
                }
                await this._applyWorkspaceImports(result.workspace_imports || []);
            } finally {
                stopProgress();
                await this._saveConversation();
                this._agentQueueDepth = Math.max(0, this._agentQueueDepth - 1);
            }
        };

        const task = this._agentQueueTail.catch(() => {}).then(runRequest);
        this._agentQueueTail = task.catch(() => {});
        return task;
    }

    _startAgentProgress(payload, message) {
        const controller = new AbortController();
        const startedAt = Date.now();
        let stopped = false;
        let pollTimer;
        const elapsedTimer = setInterval(() => {
            if (stopped || !message.pending) return;
            message.elapsedSeconds = Math.floor((Date.now() - startedAt) / 1000);
            this._refreshAgentProgress(message);
        }, 1000);
        const poll = async () => {
            if (stopped || !message.pending || this._sessionId !== payload.session_id) return;
            try {
                const progress = await AIAPI.agentProgress(payload.session_id, payload.request_id, controller.signal);
                if (progress && !stopped && message.pending && progress.request_id === payload.request_id) {
                    message.progress = progress;
                    this._refreshAgentProgress(message);
                }
            } catch (_) {
                // Progress is best-effort. Keep waiting for the actual request result.
            }
            if (!stopped && message.pending) pollTimer = setTimeout(poll, 2000);
        };
        pollTimer = setTimeout(poll, 700);
        return () => {
            stopped = true;
            clearTimeout(pollTimer);
            clearInterval(elapsedTimer);
            controller.abort();
        };
    }

    async retryAgentMessage(messageId) {
        if (this._loadingDepth || this._agentQueueDepth || this._conversationSwitching) return;
        const message = this._agentConversation.at(-1);
        if (message?.id !== messageId || !message.retryPayload || message.retryPayload.session_id !== this._sessionId) return;
        this._setLoading(true);
        try {
            this._clearTransientMessages();
            await this._runAgent(message.retryPayload, message);
        } catch (err) {
            this._showError(err.message);
        } finally {
            this._setLoading(false);
        }
    }

    async _revealAgentResponse(message, answer) {
        // The API returns a complete answer. Artificial typing delayed interaction
        // and reparsed the entire conversation for every sentence.
        message.content = answer;
        message.visibleContent = answer;
        message.streaming = false;
        this._renderAgentConversation();
    }

    async startNewAgentChat() {
        if (this._agentQueueDepth || this._conversationSwitching) return;
        this._conversationSwitching = true;
        const saved = await this._saveConversation();
        this._conversationSwitching = false;
        if (!saved) return;
        this._sessionId = this._createSessionId();
        this._activeArchiveId = null;
        this._agentConversation = [];
        this._pendingPayload = null;
        this._pendingResult = null;
        this._clearAgentAttachments();
        this._clearTransientMessages();
        const permissionSelect = document.getElementById('ai-permission-select');
        if (permissionSelect) permissionSelect.value = 'standard';
        this._syncPermissionUI();
        this._renderAgentConversation();
        this._renderArchivePanel();
        const input = document.getElementById('ai-prompt-input');
        if (input) input.value = '';
        this._resizeComposer();
        document.getElementById('ai-prompt-input')?.focus();
    }

    async archiveAgentConversation() {
        return this._saveConversation();
    }

    _saveConversation() {
        const messages = this._archiveableAgentMessages().slice(-500);
        if (!messages.length) return Promise.resolve(true);
        const sessionId = this._sessionId;
        // Stable client-generated identity makes retrying a failed save idempotent.
        if (!this._activeArchiveId) {
            const bytes = new Uint8Array(16);
            globalThis.crypto.getRandomValues(bytes);
            this._activeArchiveId = Array.from(bytes, b => b.toString(16).padStart(2, '0')).join('');
        }
        const archiveId = this._activeArchiveId;
        const title = messages.find(message => message.role === 'user')?.content.slice(0, 80) || 'Agent conversation';
        const payload = { archive_id: archiveId, session_id: sessionId, title, messages, metadata: { source: 'agent-ui', autosaved: true } };
        this._setSaveStatus('Saving…');
        const save = async () => {
            try {
                const result = await AIAPI.archiveConversation(payload);
                const summary = result.conversation;
                this._conversationArchives = [summary, ...this._conversationArchives.filter(item => item.archive_id !== archiveId)];
                this._setSaveStatus('Saved');
                this._renderArchivePanel();
                return true;
            } catch (_error) {
                this._setSaveStatus('Not saved · click to retry');
                return false;
            }
        };
        this._saveTail = this._saveTail.catch(() => {}).then(save);
        return this._saveTail;
    }

    _setSaveStatus(label) {
        const status = document.getElementById('ai-save-status');
        if (status) status.textContent = t(label);
    }

    async loadConversationArchives({ force = false } = {}) {
        if (this._archivesLoading) return;
        if (this._conversationArchives.length && !force) {
            this._renderArchivePanel();
            return;
        }

        this._archivesLoading = true;
        this._renderArchivePanel();
        try {
            const result = await AIAPI.listConversations();
            this._conversationArchives = result.conversations ?? [];
            this._historyError = '';
        } catch (err) {
            this._historyError = t('History unavailable. Click refresh to retry.');
        } finally {
            this._archivesLoading = false;
            this._renderArchivePanel();
        }
    }

    async toggleArchivePanel() {
        await this.loadConversationArchives({ force: true });
    }

    async loadConversationArchive(archiveId) {
        if (!archiveId || this._agentQueueDepth || this._conversationSwitching) return;
        if (archiveId === this._activeArchiveId) return;
        this._conversationSwitching = true;
        try {
            if (!await this._saveConversation()) return;
            const result = await AIAPI.getConversation(archiveId);
            const archive = result.conversation;
            await this._activateArchivedConversation(archive);
        } catch (err) {
            this._showError(err.message);
        } finally {
            this._conversationSwitching = false;
        }
    }

    async _activateArchivedConversation(archive) {
        const sessionId = archive.session_id || archive.archive_id || this._createSessionId();
        await AIAPI.restoreConversation(archive.archive_id, sessionId);
        this._sessionId = sessionId;
        this._activeArchiveId = archive.archive_id;
        this._historyMenuId = null;
        this._agentConversation = (archive.messages ?? [])
            .filter(message => ['user', 'assistant'].includes(message.role))
            .map(message => ({
                id: this._createMessageId(),
                role: message.role,
                content: message.content,
                steps: Array.isArray(message.steps) ? message.steps : [],
                workflow: message.workflow ?? null,
                attachments: Array.isArray(message.attachments)
                    ? this._displayAttachments(message.attachments)
                    : [],
                artifacts: Array.isArray(message.artifacts)
                    ? this._displayArtifacts(message.artifacts)
                    : [],
            }));
        this._clearAgentAttachments();
        const input = document.getElementById('ai-prompt-input');
        if (input) input.value = '';
        this._resizeComposer();
        this.setMode('agent');
        this._renderArchivePanel();
        this._renderAgentConversation();
        this._setSaveStatus('Saved');
    }

    async toggleConversationPin(archiveId) {
        if (this._historyBusy) return;
        const archive = this._conversationArchives.find(item => item.archive_id === archiveId);
        if (!archive) return;
        this._historyBusy = true;
        this._renderArchivePanel();
        const save = async () => {
            try {
                const { conversation } = await AIAPI.pinConversation(archiveId, !archive.pinned);
                this._conversationArchives = this._conversationArchives.map(item => item.archive_id === archiveId ? conversation : item);
                this._historyMenuId = null;
                return true;
            } catch (_error) {
                this._showError(t('Could not change pin status. Please retry.'));
                return false;
            } finally {
                this._historyBusy = false;
                this._renderArchivePanel();
            }
        };
        this._saveTail = this._saveTail.catch(() => {}).then(save);
        return this._saveTail;
    }

    async exportConversationFile(archiveId) {
        if (this._historyBusy) return;
        this._historyBusy = true;
        this._renderArchivePanel();
        try {
            if (archiveId === this._activeArchiveId && !await this._saveConversation()) return;
            await this._saveTail;
            const bundle = await AIAPI.exportConversation(archiveId);
            const filename = (bundle.conversation.title || 'conversation').replace(/[<>:"/\\|?*\x00-\x1f]/g, '_').slice(0, 80);
            const url = URL.createObjectURL(new Blob([JSON.stringify(bundle, null, 2)], { type: 'application/json;charset=utf-8' }));
            const link = document.createElement('a');
            link.href = url;
            link.download = `${filename}.json`;
            document.body.append(link);
            link.click();
            link.remove();
            setTimeout(() => URL.revokeObjectURL(url), 1000);
            this._historyMenuId = null;
        } catch (_error) {
            this._showError(t('Export failed. Check that the chat is saved and under 20 MB.'));
        } finally {
            this._historyBusy = false;
            this._renderArchivePanel();
        }
    }

    async importConversationFile(file) {
        if (!file) return;
        if (file.size > 20 * 1024 * 1024) {
            this._showError(t('Chat files must be smaller than 20 MB.'));
            return;
        }
        let bundle;
        try {
            bundle = JSON.parse((await file.text()).replace(/^\uFEFF/, ''));
            if (bundle?.format !== 'rsmarking.conversation' || bundle.version !== 1 || !Array.isArray(bundle.conversation?.messages)) throw new Error('format');
        } catch (_error) {
            this._showError(t('Choose a valid chat JSON exported by this application.'));
            return;
        }
        return this._createChatFromArchive(() => AIAPI.importConversation(bundle), 'Import failed. Check the chat file format and try again.');
    }

    async branchConversation(archiveId, messageId = null) {
        const payload = {};
        const archive = this._conversationArchives.find(item => item.archive_id === archiveId);
        if (archive) payload.title = `${archive.title.slice(0, 100)} · ${t('Branch')}`;
        if (messageId) {
            // Match the server's saved, visible message indices, including the 500-message cap.
            const messages = this._agentConversation.filter(item => !item.pending && item.content && ['user', 'assistant'].includes(item.role)).slice(-500);
            payload.message_index = messages.findIndex(item => item.id === messageId);
            if (payload.message_index < 0) {
                this._showError(t('This message is outside the saved history.'));
                return;
            }
        }
        return this._createChatFromArchive(() => AIAPI.branchConversation(archiveId, payload), 'Could not create a branch. Please retry.');
    }

    async _createChatFromArchive(create, errorLabel) {
        if (this._historyBusy || this._conversationSwitching || this._agentQueueDepth || this._loadingDepth) {
            this._showError(t('Wait for the current operation to finish.'));
            return false;
        }
        this._historyBusy = true;
        this._conversationSwitching = true;
        this._renderArchivePanel();
        let created = false;
        try {
            if (!await this._saveConversation()) return false;
            await this._saveTail;
            const { conversation } = await create();
            created = true;
            this._conversationArchives = [conversation, ...this._conversationArchives];
            const search = document.getElementById('ai-history-search');
            if (search) search.value = '';
            const result = await AIAPI.getConversation(conversation.archive_id);
            await this._activateArchivedConversation(result.conversation);
            document.getElementById('ai-prompt-input')?.focus();
            return true;
        } catch (_error) {
            this._showError(t(created ? 'The new chat was saved. Open it from history to continue.' : errorLabel));
            return false;
        } finally {
            this._historyBusy = false;
            this._conversationSwitching = false;
            this._renderArchivePanel();
        }
    }

    async deleteConversationArchive(archiveId) {
        if (!archiveId || this._agentQueueDepth || this._conversationSwitching) return;
        if (!window.confirm(t('Delete this conversation?'))) return;
        this._conversationSwitching = true;
        try {
            await this._saveTail;
            await AIAPI.deleteConversation(archiveId);
            if (this._activeArchiveId === archiveId) {
                this._activeArchiveId = null;
                this._sessionId = this._createSessionId();
                this._agentConversation = [];
                this._renderAgentConversation();
            }
            this._conversationArchives = this._conversationArchives
                .filter(item => item.archive_id !== archiveId);
            if (this._archiveEdit?.id === archiveId) this._archiveEdit = null;
            this._renderArchivePanel();
            this._showSuccess('Conversation archive deleted.');
        } catch (err) {
            this._showError(err.message);
        } finally {
            this._conversationSwitching = false;
        }
    }

    editConversationDetails(archiveId) {
        if (this._archiveEdit?.saving) return;
        const archive = this._conversationArchives.find(item => item.archive_id === archiveId);
        if (!archive) return;
        this._archiveEdit = { id: archiveId, title: archive.title || '', note: archive.note || '', saving: false, error: '' };
        this._renderArchivePanel();
        document.getElementById('ai-history-edit-title')?.focus();
    }

    async saveConversationDetails() {
        const draft = this._archiveEdit;
        if (!draft || draft.saving) return;
        if (!draft.title.trim()) {
            draft.error = t('Please enter a conversation title.');
            this._renderArchivePanel();
            document.getElementById('ai-history-edit-title')?.focus();
            return;
        }
        draft.saving = true;
        draft.error = '';
        this._renderArchivePanel();
        const save = async () => {
            try {
                const { conversation } = await AIAPI.updateConversation(draft.id, { title: draft.title.trim(), note: draft.note.trim() });
                this._conversationArchives = this._conversationArchives.map(item => item.archive_id === draft.id ? conversation : item);
                this._archiveEdit = null;
                this._renderArchivePanel();
                this._focusHistoryEditButton(draft.id);
                return true;
            } catch (_error) {
                draft.saving = false;
                draft.error = t('Could not save. Your edits are kept; please retry.');
                this._renderArchivePanel();
                document.getElementById('ai-history-edit-title')?.focus();
                return false;
            }
        };
        // Use the same queue as message autosaves to avoid stale sidebar updates.
        this._saveTail = this._saveTail.catch(() => {}).then(save);
        return this._saveTail;
    }

    cancelConversationDetails() {
        if (this._archiveEdit?.saving) return;
        const id = this._archiveEdit?.id;
        this._archiveEdit = null;
        this._renderArchivePanel();
        this._focusHistoryEditButton(id);
    }

    _focusHistoryEditButton(id) {
        Array.from(document.querySelectorAll('[data-ai-edit-chat]')).find(button => button.dataset.aiEditChat === id)?.focus();
    }

    async clearConversationArchives() {
        if (this._agentQueueDepth || this._conversationSwitching) return;
        if (!this._conversationArchives.length) {
            this._showSuccess('No saved conversations to clear.');
            return;
        }
        if (!window.confirm('Clear all saved AI conversation archives?')) return;
        this._conversationSwitching = true;
        try {
            await this._saveTail;
            const result = await AIAPI.clearConversations();
            this._conversationArchives = [];
            this._activeArchiveId = null;
            this._sessionId = this._createSessionId();
            this._agentConversation = [];
            this._renderAgentConversation();
            this._renderArchivePanel();
            this._showSuccess(`Cleared ${result.deleted ?? 0} archived conversation(s).`);
        } catch (err) {
            this._showError(err.message);
        } finally {
            this._conversationSwitching = false;
        }
    }

    async confirmCreate() {
        if (!this._pendingPayload || !this._pendingResult) return;

        this._setLoading(true);
        try {
            // ✅ EnglishRefreshSidebar
            await this._refreshSidebar(this._pendingPayload.data_type);

            const newId = this._pendingResult?.new_index_id
                ?? this._pendingResult?.new_layer_id
                ?? this._pendingResult?.index_id
                ?? this._pendingResult?.target_id
                ?? 'Unknown';

            this._showSuccess(t('ai.success.created', { id: newId }));
            this._resetState();
            setTimeout(() => this.closeModal(), 1200);

        } catch (err) {
            this._showError(err.message);
        } finally {
            this._setLoading(false);
        }
    }

    async confirmOverwrite() {
        if (!this._pendingPayload) return;

        const confirmed = window.confirm(t('ai.confirm.overwrite'));
        if (!confirmed) return;

        this._setLoading(true);
        try {
            await AIAPI.confirmOverwrite(this._pendingPayload);

            // ✅ EnglishRefreshSidebar
            await this._refreshSidebar(this._pendingPayload.data_type);

            this._showSuccess(t('ai.success.overwritten'));
            this._resetState();
            setTimeout(() => this.closeModal(), 1200);

        } catch (err) {
            this._showError(err.message);
        } finally {
            this._setLoading(false);
        }
    }

    async loadFunctionCatalog({ force = false } = {}) {
        if (this._functionsLoading) return;
        if (this._functionCatalog.length && !force) {
            this._renderFunctionCatalog();
            return;
        }

        this._functionsLoading = true;
        this._functionCatalogError = '';
        this._renderFunctionCatalog();
        let loaded = false;

        try {
            const response = await AIAPI.listFunctions('catalog');
            this._functionCatalog = response.functions ?? [];
            this._selectedFunction = this._selectedFunction
                ? this._functionCatalog.find(fn => fn.name === this._selectedFunction.name) ?? this._functionCatalog[0] ?? null
                : this._functionCatalog[0] ?? null;
            this._selectedFunctionCategory = this._selectedFunction?.category || this._firstFunctionCategory();
            loaded = true;
        } catch (err) {
            this._functionCatalogError = err.message || 'Failed to load backend functions';
        } finally {
            this._functionsLoading = false;
            this._renderFunctionCatalog();
            if (loaded) this.resetFunctionArgs();
        }
    }

    async reloadFunctions() {
        await this.loadFunctionCatalog({ force: true });
    }

    setMode(mode) {
        const normalizedMode = ['agent', 'analyze', 'modify'].includes(mode) ? mode : 'agent';
        const modeSelect = document.getElementById('ai-mode-select');
        if (!modeSelect) return;

        modeSelect.value = normalizedMode;
        this._syncModeUI();
    }

    selectFunction(name) {
        const fn = this._functionCatalog.find(item => item.name === name);
        if (!fn) return;

        this._selectedFunction = fn;
        this._selectedFunctionCategory = fn.category || 'other';
        this._renderFunctionCatalog();
        this.resetFunctionArgs();
    }

    selectFunctionCategory(category) {
        const normalizedCategory = category || 'other';
        const items = this._functionCatalog
            .filter(item => (item.category || 'other') === normalizedCategory);
        if (!items.length) return;

        this._selectedFunctionCategory = normalizedCategory;
        if ((this._selectedFunction?.category || 'other') !== normalizedCategory) {
            this._selectedFunction = items[0];
        }
        this._renderFunctionCatalog();
        this.resetFunctionArgs();
    }

    resetFunctionArgs() {
        if (!this._selectedFunction) return;

        const argsInput = document.getElementById('ai-function-args-input');
        if (!argsInput) return;

        const skeleton = this._buildFunctionArgumentSkeleton(this._selectedFunction);
        argsInput.value = JSON.stringify(skeleton, null, 2);
    }

    async runSelectedFunction() {
        if (!this._selectedFunction) {
            this._showError('Please select a backend function first.');
            return;
        }

        const argsInput = document.getElementById('ai-function-args-input');
        let args = {};

        try {
            args = JSON.parse(argsInput?.value?.trim() || '{}');
        } catch (err) {
            this._showError(`Arguments must be valid JSON: ${err.message}`);
            return;
        }

        this._setFunctionLoading(true);
        this._clearResult();

        try {
            const result = await AIAPI.invokeFunction(this._selectedFunction.name, args);
            this._showFunctionResult(result);
            await this._refreshAfterFunctionRun();
            if (result.result?.workspace_import) await this._applyWorkspaceImports([result.result.workspace_import]);
            this._showSuccess(`Function completed: ${this._selectedFunction.name}`);
        } catch (err) {
            this._showError(err.message);
        } finally {
            this._setFunctionLoading(false);
        }
    }

    _buildRequestPayload({ targetId, dataType, language, prompt, mode = 'analyze' }) {
        const mapContext = this._collectMapContext(targetId, dataType);

        const request = {
            language,
            user_prompt: prompt,
            session_id: this._sessionId,
            map_context: mapContext,
        };

        if (mode === 'agent') {
            request.execution_mode = document.getElementById('ai-execution-select')?.value || 'collaborative';
            request.permission_level =
                document.getElementById('ai-permission-select')?.value || 'standard';
            request.allow_task_steps = document.getElementById('ai-task-autonomy')?.checked ?? false;
            request.include_workspace_context = document.getElementById('ai-workspace-context')?.checked ?? true;
            request.include_archive_memory = document.getElementById('ai-archive-memory')?.checked ?? false;
            if (document.getElementById('ai-use-tools')?.checked === false) request.tool_names = [];
        }

        if (targetId) {
            request.target_id = targetId;
            request.data_type = dataType;
        }

        if (mode === 'agent' && this._agentAttachments.length) {
            request.attachments = this._requestAttachments(this._agentAttachments);
        }

        return request;
    }

    _bindModalEvents() {
        const targetSelect = document.getElementById('ai-target-select');
        if (targetSelect && targetSelect.dataset.aiBound !== 'true') {
            targetSelect.dataset.aiBound = 'true';
            targetSelect.addEventListener('change', () => {
                this._syncDataTypeWithTarget();
                this.resetFunctionArgs();
            });
        }

        const modeSelect = document.getElementById('ai-mode-select');
        if (modeSelect && modeSelect.dataset.aiBound !== 'true') {
            modeSelect.dataset.aiBound = 'true';
            modeSelect.addEventListener('change', () => this._syncModeUI());
        }

        const permissionSelect = document.getElementById('ai-permission-select');
        if (permissionSelect && permissionSelect.dataset.aiBound !== 'true') {
            permissionSelect.dataset.aiBound = 'true';
            permissionSelect.addEventListener('change', () => this._syncPermissionUI());
        }

        this._bindAgentAttachmentEvents();
        this._bindChatEvents();
    }

    _readPreference(name, fallback) {
        try { return localStorage.getItem(`rsmarking.ai.${name}`) || fallback; }
        catch (_error) { return fallback; }
    }

    _bindChatEvents() {
        const modal = document.getElementById('ai-modal');
        const input = document.getElementById('ai-prompt-input');
        const select = document.getElementById('ai-send-mode');
        if (select) select.value = this._sendMode === 'ctrl-enter' ? 'ctrl-enter' : 'enter';
        this._syncKeyboardHint();
        if (!modal || modal.dataset.chatBound === 'true') return;
        modal.dataset.chatBound = 'true';
        modal.addEventListener('keydown', event => {
            if (event.isComposing) return;
            if (event.key === 'Escape') {
                event.preventDefault();
                const openSettings = modal.querySelector('details[open]');
                if (openSettings) openSettings.open = false;
                else this.closeModal();
            }
            if (event.key === 'Tab') {
                const focusable = [...modal.querySelectorAll('button:not(:disabled), input, textarea, select, summary, a[href]')]
                    .filter(element => element.getClientRects().length && !element.closest('.hidden'));
                const first = focusable[0], last = focusable.at(-1);
                if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last?.focus(); }
                if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first?.focus(); }
            }
        });
        input?.addEventListener('keydown', event => this._handleComposerKeydown(event));
        input?.addEventListener('input', () => this._resizeComposer());
        select?.addEventListener('change', () => {
            this._sendMode = select.value;
            try { localStorage.setItem('rsmarking.ai.send-mode', this._sendMode); } catch (_error) { /* optional preference */ }
            this._syncKeyboardHint();
        });
        document.getElementById('ai-history-search')?.addEventListener('input', () => this._renderArchivePanel());
        document.getElementById('ai-history-import-file')?.addEventListener('change', async event => {
            const file = event.target.files?.[0];
            event.target.value = '';
            await this.importConversationFile(file);
        });
        const history = document.getElementById('ai-agent-archive-list');
        history?.addEventListener('input', event => {
            if (this._archiveEdit && event.target.dataset.aiEditField) {
                this._archiveEdit[event.target.dataset.aiEditField] = event.target.value;
            }
        });
        history?.addEventListener('submit', event => {
            if (!event.target.matches('[data-ai-edit-form]')) return;
            event.preventDefault();
            void this.saveConversationDetails();
        });
        history?.addEventListener('keydown', event => {
            if (event.key === 'Escape' && this._archiveEdit) {
                event.preventDefault();
                event.stopPropagation();
                this.cancelConversationDetails();
            } else if (event.key === 'Escape' && this._historyMenuId) {
                event.preventDefault();
                event.stopPropagation();
                const id = this._historyMenuId;
                this._historyMenuId = null;
                this._renderArchivePanel();
                Array.from(history.querySelectorAll('[data-ai-history-menu]')).find(button => button.dataset.aiHistoryMenu === id)?.focus();
            }
        });
        const collapseNote = event => {
            const row = event.target.closest('.ai-history-item');
            if (!row || row.contains(event.relatedTarget)) return;
            row.querySelector('[data-ai-note]')?.setAttribute('aria-expanded', 'false');
        };
        history?.addEventListener('pointerout', collapseNote);
        history?.addEventListener('focusout', collapseNote);
        modal.addEventListener('click', async event => {
            const button = event.target.closest('button');
            if (!button) return;
            if (button.hasAttribute('data-ai-environment')) await this.environment.open();
            if (button.hasAttribute('data-ai-new-chat')) await this.startNewAgentChat();
            if (button.hasAttribute('data-ai-refresh-history')) await this.loadConversationArchives({ force: true });
            if (button.hasAttribute('data-ai-save-chat')) await this._saveConversation();
            if (button.hasAttribute('data-ai-import-chat')) document.getElementById('ai-history-import-file')?.click();
            if (button.dataset.aiHistoryMenu) {
                this._historyMenuId = this._historyMenuId === button.dataset.aiHistoryMenu ? null : button.dataset.aiHistoryMenu;
                this._renderArchivePanel();
                const row = Array.from(history.querySelectorAll('[data-ai-history-menu]')).find(item => item.dataset.aiHistoryMenu === button.dataset.aiHistoryMenu)?.closest('.ai-history-item');
                (row?.querySelector('.ai-history-menu button') || row?.querySelector('[data-ai-history-menu]'))?.focus();
            }
            if (button.dataset.aiPinChat) await this.toggleConversationPin(button.dataset.aiPinChat);
            if (button.dataset.aiExportChat) await this.exportConversationFile(button.dataset.aiExportChat);
            if (button.dataset.aiBranchChat) await this.branchConversation(button.dataset.aiBranchChat);
            if (button.dataset.aiBranchMessage) await this.branchConversation(this._activeArchiveId, button.dataset.aiBranchMessage);
            if (button.dataset.aiRetryMessage) await this.retryAgentMessage(button.dataset.aiRetryMessage);
            if (button.dataset.aiOpenChat) await this.loadConversationArchive(button.dataset.aiOpenChat);
            if (button.dataset.aiDeleteChat) await this.deleteConversationArchive(button.dataset.aiDeleteChat);
            if (button.dataset.aiEditChat) this.editConversationDetails(button.dataset.aiEditChat);
            if (button.hasAttribute('data-ai-cancel-edit')) this.cancelConversationDetails();
            if (button.hasAttribute('data-ai-note')) button.setAttribute('aria-expanded', String(button.getAttribute('aria-expanded') !== 'true'));
            if (button.dataset.aiSuggestion && input) {
                input.value = t(button.dataset.aiSuggestion);
                input.focus();
                this._resizeComposer();
            }
            if (button.dataset.aiCopyMessage) {
                const message = this._agentConversation.find(item => item.id === button.dataset.aiCopyMessage);
                try {
                    await navigator.clipboard.writeText(message?.content || '');
                    button.textContent = t('Copied');
                } catch (_error) { this._showError(t('Copy failed. Select the text to copy.')); }
            }
        });
    }

    _handleComposerKeydown(event) {
        if (event.key !== 'Enter' || event.isComposing || event.keyCode === 229) return;
        if (event.shiftKey || event.altKey) return;
        const modifier = event.ctrlKey || event.metaKey;
        const send = this._sendMode === 'ctrl-enter' ? modifier : !modifier;
        if (send) {
            event.preventDefault();
            event.stopPropagation();
            if (!event.repeat && !this._loadingDepth && !this._conversationSwitching) void this.execute();
        } else if (modifier) {
            // Browsers do not insert a line break for Ctrl+Enter by default.
            event.preventDefault();
            event.stopPropagation();
            event.target.setRangeText('\n', event.target.selectionStart, event.target.selectionEnd, 'end');
            this._resizeComposer();
        }
    }

    _syncKeyboardHint() {
        const hint = document.getElementById('ai-keyboard-hint');
        if (hint) hint.textContent = t(this._sendMode === 'ctrl-enter' ? 'Enter for a new line' : 'Ctrl + Enter for a new line');
    }

    _resizeComposer() {
        const input = document.getElementById('ai-prompt-input');
        if (input) {
            input.style.height = 'auto';
            input.style.height = `${Math.min(180, Math.max(48, input.scrollHeight))}px`;
        }
    }

    _syncDataTypeWithTarget() {
        const targetSelect = document.getElementById('ai-target-select');
        const dataTypeSelect = document.getElementById('ai-datatype-select');
        const selectedOption = targetSelect?.selectedOptions?.[0];
        const selectedType = selectedOption?.dataset?.type;

        if (dataTypeSelect && selectedType) {
            dataTypeSelect.value = selectedType;
        }
    }

    _syncModeUI() {
        const mode = document.getElementById('ai-mode-select')?.value ?? 'agent';
        const isAgent = mode === 'agent';
        const promptInput = document.getElementById('ai-prompt-input');
        const agentPanel = document.getElementById('ai-agent-panel');
        const attachmentControls = document.getElementById('ai-agent-attachment-controls');
        const contextPanel = document.getElementById('ai-context-panel');
        const contextSummary = document.getElementById('ai-context-summary');
        const modeCaption = document.getElementById('ai-mode-caption');
        const promptLabel = document.getElementById('ai-prompt-label');
        const functionPanel = document.getElementById('ai-function-panel');
        const permissionControl = document.getElementById('ai-permission-control');
        const executeLabel = document.getElementById('ai-execute-label')
            ?? document.querySelector('#ai-execute-btn span:last-child');

        agentPanel?.classList.toggle('hidden', !isAgent);
        attachmentControls?.classList.toggle('hidden', !isAgent);
        permissionControl?.classList.toggle('hidden', !isAgent);
        document.getElementById('ai-execution-control')?.classList.toggle('hidden', !isAgent);
        functionPanel?.classList.toggle('hidden', isAgent);
        if (functionPanel) functionPanel.open = false;
        if (contextPanel) contextPanel.open = false;

        this._syncModeButtons(mode);

        if (isAgent) {
            if (contextSummary) contextSummary.textContent = 'Optional in agent mode';
            if (modeCaption) modeCaption.textContent = t('Agent mode');
            if (promptLabel) promptLabel.textContent = 'Message';
            document.getElementById('ai-result-section')?.classList.add('hidden');
            document.getElementById('ai-confirm-section')?.classList.add('hidden');
            if (promptInput) promptInput.rows = 2;
            if (executeLabel) executeLabel.textContent = t('Send');
            this._renderAgentConversation();
            this._renderArchivePanel();
            this._renderAgentAttachments();
            this._syncPermissionUI();
        } else {
            if (contextSummary) contextSummary.textContent = 'Required for analysis and modify modes';
            if (modeCaption) modeCaption.textContent = t(mode === 'modify' ? 'Modify mode' : 'Analysis mode');
            if (promptLabel) promptLabel.textContent = 'Prompt';
            document.getElementById('ai-agent-panel')?.classList.add('hidden');
            document.getElementById('ai-agent-attachment-controls')?.classList.add('hidden');
            if (promptInput) promptInput.rows = 3;
            if (executeLabel) executeLabel.textContent = t('Run');
        }
    }

    _syncPermissionUI() {
        const permission = document.getElementById('ai-permission-select')?.value || 'standard';
        const banner = document.getElementById('ai-permission-banner');
        const select = document.getElementById('ai-permission-select');
        const profiles = {
            read_only: {
                text: 'Read-only permission: the Agent can inspect and explain, but cannot create, run, update, or delete.',
                title: 'Read only: no side effects',
                classes: 'shrink-0 border-b border-sky-100 bg-sky-50 px-5 py-2 text-[10px] font-semibold text-sky-700',
            },
            safe: {
                text: 'Safe actions: the Agent may run isolated processing and create new outputs, but cannot change or delete existing data.',
                title: 'Safe actions: create new outputs, no updates or deletion',
                classes: 'shrink-0 border-b border-emerald-100 bg-emerald-50 px-5 py-2 text-[10px] font-semibold text-emerald-700',
            },
            standard: {
                text: 'Standard permission: sandbox available; changes follow user or validated task instructions.',
                title: 'Standard: sandbox and validated task assignments',
                classes: 'shrink-0 border-b border-slate-100 bg-slate-50 px-5 py-2 text-[10px] font-semibold text-slate-500',
            },
            full_control: {
                text: 'Full control: the Agent may autonomously change or delete project data for this task. Source code and host files remain protected.',
                title: 'Full control: autonomous project-data changes; source code remains protected',
                classes: 'shrink-0 border-b border-amber-200 bg-amber-50 px-5 py-2 text-[10px] font-semibold text-amber-800',
            },
        };
        const profile = profiles[permission] || profiles.standard;
        if (banner) {
            banner.textContent = t(profile.text);
            banner.className = 'ai-setting-note';
        }
        if (select) select.title = t(profile.title);
    }

    _syncModeButtons(mode) {
        document.querySelectorAll('[data-ai-mode-option]').forEach((button) => {
            const isActive = button.dataset.aiModeOption === mode;
            button.setAttribute('aria-pressed', String(isActive));
            button.classList.toggle('bg-white', isActive);
            button.classList.toggle('text-slate-900', isActive);
            button.classList.toggle('shadow-sm', isActive);
            button.classList.toggle('text-slate-500', !isActive);
            button.classList.toggle('hover:text-slate-800', !isActive);
        });
    }

    _bindAgentAttachmentEvents() {
        const input = document.getElementById('ai-agent-file-input');
        if (input && input.dataset.aiBound !== 'true') {
            input.dataset.aiBound = 'true';
            input.addEventListener('change', async () => {
                await this._handleAgentAttachmentFiles(input.files);
                input.value = '';
            });
        }

        const picker = document.getElementById('ai-agent-attachment-picker');
        if (picker && picker.dataset.aiBound !== 'true') {
            picker.dataset.aiBound = 'true';
            picker.addEventListener('click', () => input?.click());
        }

        const list = document.getElementById('ai-agent-attachment-list');
        if (list && list.dataset.aiBound !== 'true') {
            list.dataset.aiBound = 'true';
            list.addEventListener('click', (event) => {
                const button = event.target?.closest?.('[data-ai-attachment-remove]');
                if (!button) return;
                this._removeAgentAttachment(button.dataset.aiAttachmentRemove);
            });
        }
    }

    async _handleAgentAttachmentFiles(fileList) {
        const files = Array.from(fileList ?? []);
        if (!files.length) return;

        const remainingSlots = Math.max(0, AGENT_ATTACHMENT_LIMIT - this._agentAttachments.length);
        if (remainingSlots === 0) {
            this._showError(`You can attach up to ${AGENT_ATTACHMENT_LIMIT} files per message.`);
            return;
        }

        const acceptedFiles = files.slice(0, remainingSlots);
        if (files.length > remainingSlots) {
            this._showError(`Only ${remainingSlots} more attachment(s) can be added.`);
        }

        for (const file of acceptedFiles) {
            try {
                this._agentAttachments.push(await this._readAgentAttachment(file));
            } catch (err) {
                this._showError(err.message || `Failed to attach ${file.name}`);
            }
        }
        this._renderAgentAttachments();
    }

    async _readAgentAttachment(file) {
        const kind = AGENT_IMAGE_MIME_TYPES.has((file.type || '').toLowerCase())
            ? 'image'
            : this._isTextAttachment(file)
                ? 'text'
                : 'file';
        const attachment = {
            id: this._createMessageId(),
            name: file.name || 'attachment',
            kind,
            mime_type: file.type || '',
            size: file.size ?? 0,
            truncated: false,
        };

        if (kind === 'image') {
            if (file.size <= AGENT_IMAGE_FILE_BYTES) {
                attachment.image_data_url = await this._readFileAsDataURL(file);
                const dimensions = await this._readImageDimensions(attachment.image_data_url);
                if (dimensions) {
                    attachment.width = dimensions.width;
                    attachment.height = dimensions.height;
                }
            } else {
                attachment.truncated = true;
            }
            return attachment;
        }

        if (kind === 'text') {
            if (file.size > AGENT_TEXT_FILE_BYTES) {
                attachment.truncated = true;
            }
            const readableFile = file.size > AGENT_TEXT_FILE_BYTES
                ? file.slice(0, AGENT_TEXT_FILE_BYTES)
                : file;
            const text = await this._readFileAsText(readableFile);
            attachment.text_excerpt = text.slice(0, AGENT_TEXT_EXCERPT_CHARS);
            attachment.truncated = attachment.truncated || text.length > AGENT_TEXT_EXCERPT_CHARS;
        }

        return attachment;
    }

    _isTextAttachment(file) {
        const name = (file.name || '').toLowerCase();
        const type = file.type || '';
        return type.startsWith('text/')
            || type.includes('json')
            || [
                '.md',
                '.markdown',
                '.txt',
                '.json',
                '.geojson',
                '.csv',
                '.xml',
                '.log',
                '.py',
                '.js',
                '.ts',
                '.html',
                '.css',
                '.yml',
                '.yaml',
            ].some(ext => name.endsWith(ext));
    }

    _readFileAsText(file) {
        if (typeof file.text === 'function') {
            return file.text();
        }
        return new Promise((resolve, reject) => {
            const reader = new FileReader();
            reader.onload = () => resolve(String(reader.result || ''));
            reader.onerror = () => reject(new Error(`Could not read ${file.name}`));
            reader.readAsText(file);
        });
    }

    _readFileAsDataURL(file) {
        return new Promise((resolve, reject) => {
            const reader = new FileReader();
            reader.onload = () => resolve(String(reader.result || ''));
            reader.onerror = () => reject(new Error(`Could not read ${file.name}`));
            reader.readAsDataURL(file);
        });
    }

    _readImageDimensions(dataUrl) {
        if (!dataUrl || typeof Image === 'undefined') return Promise.resolve(null);
        return new Promise((resolve) => {
            const image = new Image();
            image.onload = () => resolve({ width: image.naturalWidth, height: image.naturalHeight });
            image.onerror = () => resolve(null);
            image.src = dataUrl;
        });
    }

    _requestAttachments(attachments = []) {
        return attachments.map((attachment) => ({
            name: attachment.name,
            kind: attachment.kind,
            mime_type: attachment.mime_type || null,
            size: attachment.size ?? null,
            text_excerpt: attachment.text_excerpt || null,
            image_data_url: attachment.image_data_url || null,
            width: attachment.width ?? null,
            height: attachment.height ?? null,
            truncated: Boolean(attachment.truncated),
        }));
    }

    _displayAttachments(attachments = []) {
        return attachments.map((attachment) => ({
            id: attachment.id || this._createMessageId(),
            name: attachment.name,
            kind: attachment.kind || 'file',
            mime_type: attachment.mime_type || '',
            size: attachment.size ?? 0,
            text_excerpt: attachment.text_excerpt || '',
            image_data_url: attachment.image_data_url || '',
            width: attachment.width ?? null,
            height: attachment.height ?? null,
            truncated: Boolean(attachment.truncated),
        }));
    }

    _clearAgentAttachments() {
        this._agentAttachments = [];
        this._renderAgentAttachments();
    }

    _removeAgentAttachment(id) {
        this._agentAttachments = this._agentAttachments.filter(item => item.id !== id);
        this._renderAgentAttachments();
    }

    _archiveableAgentMessages() {
        return this._agentConversation
            .filter(message => !message.pending)
            .map(message => ({
                role: message.role,
                content: message.content || '',
                steps: Array.isArray(message.steps) ? message.steps : [],
                workflow: message.workflow ?? null,
                attachments: this._archiveableAttachments(message.attachments ?? []),
                artifacts: this._archiveableArtifacts(message.artifacts ?? []),
            }));
    }

    _archiveableAttachments(attachments = []) {
        return attachments.map((attachment) => ({
            name: attachment.name,
            kind: attachment.kind,
            mime_type: attachment.mime_type || '',
            size: attachment.size ?? 0,
            width: attachment.width ?? null,
            height: attachment.height ?? null,
            truncated: Boolean(attachment.truncated),
            text_excerpt: attachment.text_excerpt || '',
            image_data_url: attachment.image_data_url || '',
        }));
    }

    _archiveableArtifacts(artifacts = []) {
        return artifacts.map((artifact) => ({
            artifact_id: artifact.artifact_id,
            name: artifact.name,
            kind: artifact.kind || 'file',
            mime_type: artifact.mime_type || '',
            size: artifact.size ?? 0,
            row_count: artifact.row_count ?? null,
            column_count: artifact.column_count ?? null,
            preview_url: artifact.source_preview_url || artifact.preview_url || '',
            download_url: artifact.source_download_url || artifact.download_url || '',
        }));
    }

    _displayArtifacts(artifacts = []) {
        return artifacts.map((artifact) => ({
            artifact_id: artifact.artifact_id || '',
            name: artifact.name || 'AI artifact',
            kind: artifact.kind || 'file',
            mime_type: artifact.mime_type || '',
            size: artifact.size ?? 0,
            row_count: artifact.row_count ?? null,
            column_count: artifact.column_count ?? null,
            source_preview_url: artifact.preview_url || '',
            source_download_url: artifact.download_url || '',
            preview_url: AIAPI.resolveURL(artifact.preview_url),
            download_url: AIAPI.resolveURL(artifact.download_url),
        })).filter(artifact => artifact.download_url);
    }

    _renderFunctionCatalog() {
        const statusEl = document.getElementById('ai-function-status');
        const buttonsEl = document.getElementById('ai-function-buttons');
        this._syncSelectedFunctionCategory();

        if (statusEl) {
            const statusText = this._functionsLoading
                ? 'Loading backend functions...'
                : this._functionCatalogError
                    ? this._functionCatalogError
                    : `${this._functionCatalog.length} backend functions available`;

            statusEl.textContent = statusText;
            statusEl.classList.toggle('text-red-500', Boolean(this._functionCatalogError));
            statusEl.classList.toggle('text-slate-400', !this._functionCatalogError);
        }

        if (buttonsEl) {
            buttonsEl.innerHTML = ModalComponent.renderAIFunctionButtons(
                this._functionCatalog,
                this._selectedFunction?.name,
                this._selectedFunctionCategory,
            );
        }

        this._renderFunctionDetails();
    }

    _renderFunctionDetails() {
        const detailEl = document.getElementById('ai-function-detail');
        const summaryEl = document.getElementById('ai-function-summary');

        if (!detailEl || !summaryEl) return;

        detailEl.classList.toggle('hidden', !this._selectedFunction);
        if (this._selectedFunction) {
            summaryEl.innerHTML = ModalComponent.renderAIFunctionSummary(this._selectedFunction);
        }
    }

    _buildFunctionArgumentSkeleton(fn) {
        const schemaDefaults = {};
        const properties = fn.parameters?.properties ?? {};

        for (const [name, schema] of Object.entries(properties)) {
            schemaDefaults[name] = this._buildDefaultArgument(name, schema, fn);
        }

        return {
            ...schemaDefaults,
            ...this._getFunctionSpecificDefaults(fn.name),
        };
    }

    _buildDefaultArgument(name, schema = {}, fn = {}) {
        if (Object.prototype.hasOwnProperty.call(schema, 'default')) {
            return schema.default;
        }
        if (Array.isArray(schema.enum) && schema.enum.length) {
            return schema.enum[0];
        }

        const type = this._getSchemaType(schema);
        const primaryRasterId = this._getPrimaryRasterId();

        if (name === 'new_name') {
            return this._defaultNewName(fn.name);
        }
        if (name === 'band_ids') {
            return this._getRasterIds().slice(0, 2);
        }
        if (name === 'raster_ids') {
            return this._getRasterIds().slice(0, 2);
        }
        if (name === 'output_name') {
            return this._defaultNewName(fn.name);
        }
        if (name === 'script') {
            return this._defaultSandboxScript();
        }
        if (name === 'band_indices') {
            return [1];
        }
        if (name === 'target_resolution_x' || name === 'target_resolution_y') {
            return 1;
        }
        if (name === 'resolution_unit') {
            return 'source';
        }
        if (name === 'resampling_method') {
            return 'bilinear';
        }
        if (name === 'geometries') {
            const geometry = this._viewportGeometry();
            return geometry ? [geometry] : [];
        }
        if (name === 'clip_geometry') {
            return this._viewportGeometry() ?? {};
        }
        if (name === 'features') {
            return this._collectSelectedFeatureObjects();
        }
        if (name === 'var_mapping') {
            const rasterIds = this._getRasterIds();
            return {
                A: rasterIds[0] ?? primaryRasterId,
                B: rasterIds[1] ?? primaryRasterId,
            };
        }
        if (name === 'expression') {
            return '(A - B) / (A + B)';
        }
        if (name === 'src_vector_crs') {
            return 'EPSG:4326';
        }
        if (name === 'threshold_mode') {
            return 'abs';
        }
        if (name === 'index_type') {
            return 'ndvi';
        }
        if (name === 'mode') {
            return fn.name === 'clip_vector_by_raster' ? 'intersects' : '';
        }
        if (name === 'raster_id' || name.endsWith('_id') || name.includes('index_id')) {
            return primaryRasterId;
        }

        if (type === 'array') return [];
        if (type === 'object') return {};
        if (type === 'boolean') return false;
        if (type === 'integer' || type === 'number') return 0;
        if (type === 'null') return null;
        return '';
    }

    _getSchemaType(schema = {}) {
        if (schema.type) return schema.type;
        const unionTypes = schema.anyOf ?? schema.oneOf;
        const concreteType = unionTypes?.find(item => item.type && item.type !== 'null');
        return concreteType?.type ?? 'string';
    }

    _getFunctionSpecificDefaults(name) {
        const rasterIds = this._getRasterIds();
        const primary = this._getPrimaryRasterId();
        const secondary = this._getSecondaryRasterId();
        const third = rasterIds[2] ?? primary;
        const fourth = rasterIds[3] ?? secondary;
        const viewportGeometry = this._viewportGeometry();

        const indexDefaults = {
            calculate_ndvi: { red_id: primary, nir_id: secondary, new_name: this._defaultNewName('NDVI') },
            calculate_ndwi: { green_id: primary, nir_id: secondary, new_name: this._defaultNewName('NDWI') },
            calculate_ndbi: { swir_id: primary, nir_id: secondary, new_name: this._defaultNewName('NDBI') },
            calculate_mndwi: { green_id: primary, swir_id: secondary, new_name: this._defaultNewName('MNDWI') },
        };

        if (indexDefaults[name]) return indexDefaults[name];

        if (name === 'run_raster_calculator') {
            return {
                expression: '(A - B) / (A + B)',
                new_name: this._defaultNewName('raster_calculator'),
                var_mapping: {
                    A: primary,
                    B: secondary,
                },
            };
        }

        if (name === 'synthesize_raster_bands') {
            return {
                raster_ids: rasterIds.slice(0, 2),
                new_name: this._defaultNewName('band_stack'),
            };
        }

        if (name === 'extract_raster_bands') {
            return {
                raster_id: primary,
                band_indices: [1],
                new_name: this._defaultNewName('band_extract'),
            };
        }

        if (name === 'resample_raster') {
            const raster = Store.getRasters().find(item => Number(item.index_id ?? item.id) === Number(primary));
            const xResolution = Number(raster?.resolution_x);
            const yResolution = Number(raster?.resolution_y);
            return {
                raster_id: primary,
                target_resolution_x: Number.isFinite(xResolution) && xResolution > 0 ? xResolution : 1,
                target_resolution_y: Number.isFinite(yResolution) && yResolution > 0 ? yResolution : null,
                resolution_unit: 'source',
                resampling_method: 'bilinear',
                new_name: this._defaultNewName('resample'),
            };
        }

        if (name === 'radiometric_calibration') {
            return {
                raster_id: primary,
                new_name: this._defaultNewName('radiometric'),
                calibration_type: 'auto',
                scale_factor: null,
                offset: null,
                radiance_mult: null,
                radiance_add: null,
                reflectance_mult: null,
                reflectance_add: null,
                sun_elevation: null,
                earth_sun_distance: 1,
                solar_irradiance: null,
                sun_elevation_correction: true,
                clamp: false,
            };
        }

        if (name === 'geometric_correction') {
            return {
                raster_id: primary,
                new_name: this._defaultNewName('geometric'),
                dst_crs: null,
                resampling_method: 'bilinear',
                target_resolution_x: null,
                target_resolution_y: null,
                shift_x: 0,
                shift_y: 0,
                scale_x: 1,
                scale_y: 1,
                rotation_degrees: 0,
                gcps: null,
            };
        }

        if (name === 'supervised_classification') {
            return {
                raster_id: primary,
                samples: [
                    { row: 0, col: 0, class_id: 1 },
                    { row: 1, col: 1, class_id: 2 },
                ],
                classifier: 'nearest_centroid',
                band_indices: null,
                n_estimators: 100,
                random_seed: 13,
                smoothing: 0,
                new_name: this._defaultNewName('supervised_classification'),
            };
        }

        if (name === 'unsupervised_classification') {
            return {
                raster_id: primary,
                n_classes: 5,
                method: 'kmeans',
                band_indices: null,
                max_samples: 50000,
                random_seed: 13,
                smoothing: 0,
                new_name: this._defaultNewName('unsupervised_classification'),
            };
        }

        if (name === 'deep_learning_segmentation') {
            return {
                raster_id: primary,
                new_name: this._defaultNewName('deep_segmentation'),
                model_path: null,
                backend: 'auto',
                n_classes: 2,
                band_indices: null,
                threshold: 0.5,
                random_seed: 13,
                max_samples: 50000,
                compactness: 0.15,
                smoothing: 1,
            };
        }

        if (name === 'run_script_sandbox') {
            return {
                raster_ids: rasterIds.slice(0, 1),
                output_name: this._defaultNewName('sandbox_script'),
                script: this._defaultSandboxScript(),
            };
        }

        const extractionDefaults = {
            extract_vegetation: { threshold: 0.3, mode: 'ndvi' },
            extract_water: { threshold: 0.0, mode: 'mndwi' },
            extract_buildings: { threshold: 0.1, mode: 'ndbi' },
            extract_clouds: { threshold: 0.5, mode: 'cloud' },
        };

        if (extractionDefaults[name]) {
            return {
                band_ids: rasterIds.slice(0, 2),
                new_name: this._defaultNewName(name),
                ...extractionDefaults[name],
            };
        }

        if (name === 'clip_raster_by_vector') {
            return {
                raster_id: primary,
                new_name: this._defaultNewName('clip_raster'),
                geometries: viewportGeometry ? [viewportGeometry] : [],
                src_vector_crs: 'EPSG:4326',
                crop: true,
                nodata: null,
                all_touched: false,
            };
        }

        if (name === 'clip_vector_by_raster') {
            return {
                clip_geometry: viewportGeometry ?? {},
                features: this._collectSelectedFeatureObjects(),
                src_vector_crs: 'EPSG:4326',
                mode: 'intersects',
            };
        }

        if (name === 'detect_band_diff') {
            return {
                index_id_t1: primary,
                index_id_t2: secondary,
                band_idx: 1,
                threshold: 0.1,
                threshold_mode: 'abs',
                output_mask: true,
            };
        }

        if (name === 'detect_band_ratio') {
            return {
                index_id_t1: primary,
                index_id_t2: secondary,
                band_idx: 1,
                threshold: 0.2,
                output_mask: true,
            };
        }

        if (name === 'detect_index_diff') {
            return {
                index_id_t1_b1: primary,
                index_id_t1_b2: secondary,
                index_id_t2_b1: third,
                index_id_t2_b2: fourth,
                index_type: 'ndvi',
                threshold: 0.15,
                threshold_mode: 'abs',
                output_mask: true,
            };
        }

        return {};
    }

    _getRasterIds() {
        const ids = [];
        for (const raster of Store.getRasters()) {
            const id = Number(raster.index_id ?? raster.id);
            if (Number.isFinite(id)) ids.push(id);
        }
        return ids;
    }

    _getPrimaryRasterId() {
        const target = this._getSelectedTarget();
        if (target.dataType === 'raster' && target.targetId) {
            const numericTargetId = Number(target.targetId);
            if (Number.isFinite(numericTargetId)) return numericTargetId;
        }

        return this._getRasterIds()[0] ?? null;
    }

    _getSecondaryRasterId() {
        const primary = this._getPrimaryRasterId();
        return this._getRasterIds().find(id => id !== primary) ?? primary;
    }

    _getSelectedTarget() {
        const targetSelect = document.getElementById('ai-target-select');
        const dataTypeSelect = document.getElementById('ai-datatype-select');
        const selectedOption = targetSelect?.selectedOptions?.[0];

        return {
            targetId: targetSelect?.value ?? '',
            dataType: selectedOption?.dataset?.type ?? dataTypeSelect?.value ?? 'raster',
        };
    }

    _defaultNewName(prefix = 'ai_result') {
        const safePrefix = String(prefix)
            .replace(/^calculate_/, '')
            .replace(/^run_/, '')
            .replace(/[^a-z0-9]+/gi, '_')
            .replace(/^_+|_+$/g, '')
            || 'ai_result';

        return `${safePrefix}_${Date.now()}.tif`;
    }

    _defaultSandboxScript() {
        return [
            'import rasterio',
            'import numpy as np',
            '',
            'with rasterio.open(input_0) as src:',
            '    data = src.read()',
            '    profile = src.profile',
            '',
            '# Replace this with the custom raster operation.',
            'result = data',
            '',
            'with rasterio.open(OUTPUT_FILE, "w", **profile) as dst:',
            '    dst.write(result)',
            '',
            'print("Sandbox script completed")',
        ].join('\n');
    }

    _viewportGeometry() {
        const bbox = this._collectViewport()?.bbox;
        if (!bbox || bbox.length !== 4) return null;

        const [west, south, east, north] = bbox;
        return {
            type: 'Polygon',
            coordinates: [[
                [west, south],
                [east, south],
                [east, north],
                [west, north],
                [west, south],
            ]],
        };
    }

    _collectSelectedFeatureObjects() {
        const selectedId = Store.state.selectedFeatureId;
        if (!selectedId) return [];

        const features = Store.state.currentFeatures?.features ?? [];
        const selectedFeature = features.find((feature) => {
            const candidateId = feature?.id
                ?? feature?.properties?.id
                ?? feature?.properties?.feature_id;
            return String(candidateId) === String(selectedId);
        });

        return selectedFeature ? [selectedFeature] : [];
    }

    _showFunctionResult(result) {
        const reportEl = document.getElementById('ai-result-content');
        if (reportEl) reportEl.textContent = JSON.stringify(result, null, 2);
        const artifact = result?.result?.artifact_id ? this._displayArtifacts([result.result])[0] : null;
        const downloadBtn = document.getElementById('ai-download-btn');
        if (downloadBtn && artifact) {
            downloadBtn.href = artifact.download_url;
            downloadBtn.download = artifact.name;
            const label = downloadBtn.querySelector('span');
            if (label) label.textContent = `Download ${artifact.name}`;
            downloadBtn.classList.remove('hidden');
        }
        document.getElementById('ai-result-section')?.classList.remove('hidden');
    }

    _renderAgentConversation() {
        const messagesEl = document.getElementById('ai-agent-messages');
        const sessionEl = document.getElementById('ai-agent-session-label');
        if (sessionEl) sessionEl.textContent = this._sessionId.slice(-8);
        if (!messagesEl) return;

        const nearBottom = messagesEl.scrollHeight - messagesEl.scrollTop - messagesEl.clientHeight < 100;
        const suggestions = [
            'Summarize my workspace',
            'Help me analyze this imagery',
            'What can you do?',
        ];
        messagesEl.innerHTML = this._agentConversation.length
            ? this._agentConversation.map(message => this._renderAgentMessage(message)).join('')
            : `<div class="ai-empty">
                <span class="ai-brand-mark">RS</span>
                <h3>${this._escapeHTML(t('What would you like to explore?'))}</h3>
                <p>${this._escapeHTML(t('Ask about your maps, analyze imagery, or turn an idea into a result.'))}</p>
                <div class="ai-suggestions">
                    ${suggestions.map(label => `
                        <button type="button" data-ai-suggestion="${label}">${this._escapeHTML(t(label))}</button>
                    `).join('')}
                </div>
            </div>`;
        if (nearBottom) this._scrollAgentChatToBottom();
    }

    _renderAgentAttachments() {
        const list = document.getElementById('ai-agent-attachment-list');
        if (!list) return;

        list.innerHTML = this._agentAttachments.length
            ? this._agentAttachments.map(attachment => this._renderAttachmentChip(attachment, { removable: true })).join('')
            : '';
    }

    _renderArchivePanel() {
        const list = document.getElementById('ai-agent-archive-list');
        if (!list) return;
        const query = (document.getElementById('ai-history-search')?.value || '').trim().toLocaleLowerCase();
        const items = this._conversationArchives.filter(archive => {
            return archive.archive_id === this._archiveEdit?.id
                || `${archive.title || ''} ${archive.note || ''}`.toLocaleLowerCase().includes(query);
        }).sort((a, b) => {
            const pinOrder = Number(Boolean(b.pinned)) - Number(Boolean(a.pinned));
            if (pinOrder) return pinOrder;
            const firstDate = String((a.pinned ? a.pinned_at : a.updated_at) || '');
            const secondDate = String((b.pinned ? b.pinned_at : b.updated_at) || '');
            return secondDate.localeCompare(firstDate)
                || String(b.archive_id).localeCompare(String(a.archive_id));
        });
        if (!items.length) {
            let label = query ? 'No matching conversations' : 'Your conversations will appear here';
            if (this._archivesLoading) {
                label = 'Loading conversations…';
            } else if (this._historyError) {
                label = this._historyError;
            }
            list.innerHTML = `<p class="ai-history-note">${this._escapeHTML(t(label))}</p>`;
            return;
        }
        let focused = null;
        if (list.contains(document.activeElement) && document.activeElement.dataset.aiEditField) {
            focused = {
                id: document.activeElement.id,
                start: document.activeElement.selectionStart,
                end: document.activeElement.selectionEnd,
            };
        }
        const label = text => this._escapeHTML(t(text));
        const disabled = this._historyBusy ? 'disabled' : '';
        list.innerHTML = items.map(archive => {
            const id = this._escapeHTML(archive.archive_id);
            const active = archive.archive_id === this._activeArchiveId;
            const title = this._escapeHTML(archive.title || 'Agent conversation');
            const date = archive.updated_at ? new Date(archive.updated_at).toLocaleDateString() : '';
            if (this._archiveEdit?.id === archive.archive_id) {
                const draft = this._archiveEdit;
                return `<div class="ai-history-item ai-history-editing">
                    <form data-ai-edit-form class="ai-history-editor">
                        <label for="ai-history-edit-title">${label('Conversation title')}</label>
                        <input id="ai-history-edit-title" data-ai-edit-field="title"
                            value="${this._escapeHTML(draft.title)}" maxlength="120" required ${draft.saving ? 'disabled' : ''}>
                        <label for="ai-history-edit-note">${label('Conversation note')}</label>
                        <textarea id="ai-history-edit-note" data-ai-edit-field="note" rows="4" maxlength="4000"
                            placeholder="${label('Add a note (optional)')}" ${draft.saving ? 'disabled' : ''}>${this._escapeHTML(draft.note)}</textarea>
                        ${draft.error ? `<p class="ai-history-edit-error" role="alert">${this._escapeHTML(draft.error)}</p>` : ''}
                        <div class="ai-history-edit-actions">
                            <button type="button" data-ai-cancel-edit ${draft.saving ? 'disabled' : ''}>${label('Cancel')}</button>
                            <button type="submit" ${draft.saving ? 'disabled' : ''}>${label(draft.saving ? 'Saving…' : 'Save')}</button>
                        </div>
                    </form>
                </div>`;
            }
            const note = archive.note
                ? `<button type="button" class="ai-history-annotation" data-ai-note aria-expanded="false"
                    title="${label('Click to expand or collapse note')}">${this._escapeHTML(archive.note)}</button>`
                : '';
            const menuOpen = this._historyMenuId === archive.archive_id;
            const menu = menuOpen ? `<div class="ai-history-menu">
                <button type="button" data-ai-pin-chat="${id}" ${disabled}>${label(archive.pinned ? 'Unpin chat' : 'Pin chat')}</button>
                <button type="button" data-ai-export-chat="${id}" ${disabled}>${label('Export chat')}</button>
                <button type="button" data-ai-branch-chat="${id}" ${disabled}>${label('Branch to new chat')}</button>
                <button type="button" data-ai-delete-chat="${id}" ${disabled}>${label('Delete archive')}</button>
            </div>` : '';
            return `<div class="ai-history-item ${active ? 'active' : ''}">
                <button type="button" class="ai-history-open" data-ai-open-chat="${id}" ${active ? 'aria-current="page"' : ''} title="${title}">
                    <strong>${title}</strong>
                </button>
                <div class="ai-history-actions">
                    <button type="button" class="ai-history-edit" data-ai-edit-chat="${id}"
                        aria-label="${label('Edit title and note')}" title="${label('Edit title and note')}">✎</button>
                    <button type="button" class="ai-history-more" data-ai-history-menu="${id}" aria-expanded="${menuOpen}"
                        aria-label="${label('Conversation actions')}" title="${label('Conversation actions')}">⋯</button>
                </div>
                ${note}
                <small class="ai-history-date">${archive.pinned ? `<span class="ai-history-pin">${label('Pinned')} · </span>` : ''}${this._escapeHTML(date)}</small>
                ${menu}
            </div>`;
        }).join('');
        if (focused) {
            const field = document.getElementById(focused.id);
            field?.focus();
            field?.setSelectionRange(focused.start, focused.end);
        }
    }

    _renderAgentMessage(message) {
        const isUser = message.role === 'user';
        const content = message.pending ? this._renderPendingAgentMessage(message) : this._renderAgentMarkdownOutput(message);
        const copy = !message.pending && message.id
            ? `<button type="button" class="ai-message-copy"
                data-ai-copy-message="${this._escapeHTML(message.id)}">${this._escapeHTML(t('Copy'))}</button>`
            : '';
        const branch = !message.pending && message.id && message.content
            ? `<button type="button" class="ai-message-copy"
                data-ai-branch-message="${this._escapeHTML(message.id)}">${this._escapeHTML(t('Branch from here'))}</button>`
            : '';
        const retry = message.error && message.retryPayload && message === this._agentConversation.at(-1)
            ? `<button type="button" class="ai-message-copy"
                data-ai-retry-message="${this._escapeHTML(message.id)}">${this._escapeHTML(t('Retry this request'))}</button>`
            : '';
        return `<article class="ai-message ai-message-${isUser ? 'user' : 'assistant'}" data-ai-message="${this._escapeHTML(message.id || '')}">
            <div class="ai-bubble ${message.error ? 'ai-message-error' : ''}">
                ${isUser ? '' : '<div class="ai-message-label">RS · Assistant</div>'}
                ${content}${this._renderMessageAttachments(message.attachments ?? [], isUser)}
                ${this._renderGeneratedArtifacts(message.artifacts ?? [])}
                ${this._renderAgentWorkflow(message.workflow)}${this._renderAgentToolTrace(message.steps ?? [])}
                <div class="ai-message-actions">${copy}${branch}${retry}</div>
            </div>
        </article>`;
    }

    _refreshAgentProgress(message) {
        const messages = document.getElementById('ai-agent-messages');
        if (!messages) return;
        const article = [...messages.querySelectorAll('[data-ai-message]')]
            .find(element => element.dataset.aiMessage === message.id);
        const pending = article?.querySelector('[data-ai-pending]');
        if (!pending) return;
        const nearBottom = messages.scrollHeight - messages.scrollTop - messages.clientHeight < 100;
        pending.outerHTML = this._renderPendingAgentMessage(message);
        if (nearBottom) this._scrollAgentChatToBottom();
    }

    _renderPendingAgentMessage(message = {}) {
        const progress = message.progress;
        const stages = {
            planning: 'Inspecting inputs and planning tasks', replanning: 'Adjusting the plan after review',
            executing: 'Executing assigned tasks', reviewing: 'Checking the actual outputs',
        };
        const statusLabel = progress?.phase === 'complete' ? 'Preparing the final response' : stages[progress?.stage];
        const label = this._escapeHTML(t(statusLabel || message.pendingLabel || 'Waiting for AI response'));
        const details = [];
        if (progress?.task_title) details.push(progress.task_title);
        if (progress?.phase === 'tool' && progress.tool) details.push(`${t('Using tool')}: ${progress.tool}`);
        else if (progress?.phase === 'model') details.push(t('Model is preparing the next step'));
        if (progress?.total_tasks) details.push(`${progress.completed_tasks}/${progress.total_tasks} ${t('tasks completed')}`);
        if (progress?.round) details.push(`${progress.round} ${t('repair rounds')}`);
        if (message.elapsedSeconds) details.push(`${t('Elapsed')}: ${message.elapsedSeconds}s`);
        return `
            <div data-ai-pending role="status"><div class="flex items-center gap-2 text-slate-500">
                <span class="font-bold">${label}</span>
                <span class="flex gap-1">
                    <span class="h-1.5 w-1.5 animate-pulse rounded-full bg-violet-400"></span>
                    <span class="h-1.5 w-1.5 animate-pulse rounded-full bg-violet-400" style="animation-delay:120ms"></span>
                    <span class="h-1.5 w-1.5 animate-pulse rounded-full bg-violet-400" style="animation-delay:240ms"></span>
                </span>
            </div><div class="ai-progress-detail">${this._escapeHTML(details.join(' · '))}</div></div>`;
    }

    _renderAgentMarkdownOutput(message = {}) {
        const content = message.streaming
            ? message.visibleContent ?? ''
            : message.visibleContent || message.content || '';
        const cursor = message.streaming
            ? '<span class="ml-0.5 inline-block h-3 w-1 animate-pulse rounded-sm bg-violet-500 align-[-1px]"></span>'
            : '';
        return `<div class="break-words">${this._renderMarkdown(content)}${cursor}</div>`;
    }

    _renderMessageAttachments(attachments = [], isUser = false) {
        if (!attachments.length) return '';

        const imageAttachments = attachments.filter(item => item.kind === 'image' && item.image_data_url);
        const fileAttachments = attachments.filter(item => item.kind !== 'image' || !item.image_data_url);
        const chips = fileAttachments.map(attachment => this._renderAttachmentChip(attachment, { compact: true })).join('');
        const images = imageAttachments.map(attachment => `
            <div class="overflow-hidden rounded-xl border ${isUser ? 'border-white/15 bg-white/10' : 'border-slate-200 bg-slate-50'}">
                <img src="${this._escapeHTML(attachment.image_data_url)}" alt="${this._escapeHTML(attachment.name)}"
                    class="max-h-44 w-full object-cover">
                <div class="truncate px-2 py-1 text-[10px] ${isUser ? 'text-slate-200' : 'text-slate-500'}">
                    ${this._escapeHTML(attachment.name)}
                </div>
            </div>
        `).join('');

        return `
            <div class="mt-3 space-y-2">
                ${images ? `<div class="grid grid-cols-2 gap-2">${images}</div>` : ''}
                ${chips ? `<div class="flex flex-wrap gap-2">${chips}</div>` : ''}
            </div>`;
    }

    _syncSelectedFunctionCategory() {
        if (!this._functionCatalog.length) {
            this._selectedFunctionCategory = '';
            return;
        }

        if (this._selectedFunction) {
            const stillAvailable = this._functionCatalog
                .some(fn => fn.name === this._selectedFunction.name);
            if (!stillAvailable) {
                this._selectedFunction = this._functionCatalog[0] ?? null;
            }
        } else {
            this._selectedFunction = this._functionCatalog[0] ?? null;
        }

        const selectedCategory = this._selectedFunction?.category || 'other';
        const categoryAvailable = this._functionCatalog
            .some(fn => (fn.category || 'other') === (this._selectedFunctionCategory || selectedCategory));
        this._selectedFunctionCategory = categoryAvailable
            ? (this._selectedFunctionCategory || selectedCategory)
            : selectedCategory;
    }

    _firstFunctionCategory() {
        return this._functionCatalog[0]?.category || (this._functionCatalog.length ? 'other' : '');
    }

    _renderGeneratedArtifacts(artifacts = []) {
        if (!artifacts.length) return '';

        const cards = artifacts.map((artifact) => {
            const name = this._escapeHTML(artifact.name || 'AI artifact');
            const downloadUrl = this._escapeHTML(artifact.download_url || '');
            const meta = [
                artifact.mime_type || artifact.kind || 'file',
                this._formatBytes(artifact.size),
                artifact.row_count != null ? `${artifact.row_count} rows` : '',
                artifact.column_count != null ? `${artifact.column_count} columns` : '',
            ].filter(Boolean).join(' · ');
            const preview = artifact.kind === 'image' && artifact.preview_url
                ? `<img src="${this._escapeHTML(artifact.preview_url)}" alt="${name}"
                        class="max-h-56 w-full bg-slate-50 object-contain">`
                : '';
            return `
                <div class="overflow-hidden rounded-xl border border-violet-100 bg-violet-50/60">
                    ${preview}
                    <div class="flex items-center gap-3 px-3 py-2.5">
                        <span class="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-white text-violet-600 shadow-sm">
                            ${artifact.kind === 'image' ? this._imageIcon() : artifact.kind === 'table' ? this._textIcon() : this._fileIcon()}
                        </span>
                        <span class="min-w-0 flex-1">
                            <span class="block truncate text-[11px] font-black text-slate-700">${name}</span>
                            <span class="block truncate text-[9px] text-slate-400">${this._escapeHTML(meta)}</span>
                        </span>
                        <a href="${downloadUrl}" download="${name}"
                            class="shrink-0 rounded-lg bg-violet-600 px-2.5 py-1.5 text-[10px] font-black text-white hover:bg-violet-700">
                            Export
                        </a>
                    </div>
                </div>`;
        }).join('');

        return `<div class="mt-3 space-y-2">${cards}</div>`;
    }

    _renderAttachmentChip(attachment, { removable = false, compact = false } = {}) {
        const icon = attachment.kind === 'image' ? this._imageIcon() : attachment.kind === 'text' ? this._textIcon() : this._fileIcon();
        const name = this._escapeHTML(attachment.name || 'attachment');
        const meta = [
            attachment.mime_type || attachment.kind || 'file',
            this._formatBytes(attachment.size),
            attachment.width && attachment.height ? `${attachment.width}x${attachment.height}` : '',
            attachment.truncated ? 'truncated' : '',
        ].filter(Boolean).join(' · ');
        const removeButton = removable
            ? `<button type="button" data-ai-attachment-remove="${this._escapeHTML(attachment.id)}"
                    class="ml-1 flex h-5 w-5 shrink-0 items-center justify-center rounded-md text-slate-400 hover:bg-red-50 hover:text-red-500"
                    title="Remove attachment">
                    <svg class="h-3 w-3 pointer-events-none" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 6l12 12M18 6L6 18"/>
                    </svg>
                </button>`
            : '';

        return `
            <div class="flex min-w-0 max-w-full items-center gap-2 rounded-xl border border-slate-200 bg-white px-2.5 py-2 text-slate-600 shadow-sm ${compact ? 'text-[10px]' : 'text-[11px]'}">
                <span class="flex h-7 w-7 shrink-0 items-center justify-center rounded-lg bg-slate-100 text-slate-500">${icon}</span>
                <span class="min-w-0">
                    <span class="block truncate font-bold">${name}</span>
                    <span class="block truncate text-[9px] text-slate-400">${this._escapeHTML(meta)}</span>
                </span>
                ${removeButton}
            </div>`;
    }

    _imageIcon() {
        return `<svg class="h-3.5 w-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 16l4-4 4 4 4-5 4 5M5 5h14v14H5z"/></svg>`;
    }

    _textIcon() {
        return `<svg class="h-3.5 w-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M7 4h7l5 5v11H7zM13 4v6h6M9 14h6M9 17h6"/></svg>`;
    }

    _fileIcon() {
        return `<svg class="h-3.5 w-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M8 4h8l3 3v13H8zM16 4v4h4"/></svg>`;
    }

    _formatBytes(size = 0) {
        const bytes = Number(size) || 0;
        if (bytes < 1024) return `${bytes} B`;
        if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
        return `${(bytes / 1024 / 1024).toFixed(1)} MB`;
    }

    _renderMarkdown(markdown = '') {
        return renderAgentMarkdown(markdown);
    }

    _renderAgentWorkflow(workflow) {
        if (!workflow || !Array.isArray(workflow.events)) return '';
        const states = {
            success: 'Completed', not_accepted: 'Not accepted', needs_input: 'Needs input',
            budget_exhausted: 'Budget reached', planning: 'Planning', replanning: 'Replanning',
            executing: 'Executing', reviewing: 'Reviewing',
        };
        const events = workflow.events.filter(event => event && typeof event === 'object').map(event => `
            <li><strong>${this._escapeHTML(this._agentRoleLabel(event.agent))}${event.task_id ? ` · ${this._escapeHTML(event.task_id)}` : ''}</strong>
            <span>${this._escapeHTML(t(event.status))}</span><p>${this._escapeHTML(event.summary || '')}</p></li>
        `).join('');
        const status = this._escapeHTML(t(states[workflow.stage] || 'Not accepted'));
        const tasks = (Array.isArray(workflow.tasks) ? workflow.tasks : [])
            .filter(task => task && typeof task === 'object')
            .map(task => `<li>
                <strong>${this._escapeHTML(task.title || '')}</strong>
                <p>${this._escapeHTML(task.instruction || '')}</p>
                <p>${this._escapeHTML(t('Task inputs'))}: ${this._escapeHTML((Array.isArray(task.inputs) ? task.inputs : []).join('; '))}</p>
                <p>${this._escapeHTML(t('Expected output'))}: ${this._escapeHTML(task.expected_output || '')}</p>
                <p>${this._escapeHTML(t('Assigned tools'))}: ${this._escapeHTML((Array.isArray(task.tool_names) ? task.tool_names : []).join(', '))}</p>
            </li>`).join('');
        return `<details class="ai-tool-trace ai-workflow"><summary>${this._escapeHTML(t('Agent workflow'))} · ${status}</summary>
            <p>${Number(workflow.model_calls) || 0} ${this._escapeHTML(t('model calls'))} · ${Number(workflow.round) || 0} ${this._escapeHTML(t('repair rounds'))}</p>
            ${tasks ? `<strong>${this._escapeHTML(t('Task assignments'))}</strong><ol>${tasks}</ol>` : ''}
            <ol>${events}</ol></details>`;
    }

    _agentRoleLabel(role) {
        const labels = { planner: 'Planner', executor: 'Executor', verifier: 'Verifier', coordinator: 'Coordinator' };
        return t(labels[role] || 'Coordinator');
    }

    _renderAgentToolTrace(steps) {
        if (!steps.length) return '';

        const items = steps.map((step) => {
            const isSuccess = step.status === 'success';
            const statusClass = isSuccess
                ? 'bg-emerald-50 text-emerald-700 border-emerald-100'
                : 'bg-red-50 text-red-700 border-red-100';
            const statusText = isSuccess ? 'ok' : 'error';
            const roleLabel = step.agent_role ? `${this._escapeHTML(this._agentRoleLabel(step.agent_role))} · ` : '';
            const error = step.error
                ? `<div class="mt-1 text-[10px] leading-relaxed text-red-600">${this._escapeHTML(step.error)}</div>`
                : '';

            return `
                <div class="rounded-xl border border-slate-100 bg-slate-50 px-3 py-2">
                    <div class="flex items-center justify-between gap-3">
                        <span class="truncate font-mono text-[10px] font-bold text-slate-500">${roleLabel}${this._escapeHTML(step.name)}</span>
                        <span class="shrink-0 rounded-full border px-2 py-0.5 text-[9px] font-black uppercase tracking-widest ${statusClass}">${statusText}</span>
                    </div>
                    ${error}
                </div>`;
        }).join('');

        return `<details class="ai-tool-trace"><summary>${steps.length} ${this._escapeHTML(t('tool steps'))}</summary><div class="mt-2 space-y-1.5">${items}</div></details>`;
    }

    _scrollAgentChatToBottom() {
        const messagesEl = document.getElementById('ai-agent-messages');
        if (messagesEl) messagesEl.scrollTop = messagesEl.scrollHeight;
    }

    async _refreshAfterFunctionRun() {
        if (!this._selectedFunction || this._selectedFunction.name === 'clip_vector_by_raster') {
            return;
        }

        await this._refreshSidebar('raster');
    }

    _collectMapContext(targetId, dataType) {
        const viewport = this._collectViewport();
        const selectedFeatures = this._collectSelectedFeatures();
        const activeLayers = [
            ...Array.from(Store.state.activeLayerIds, (id) => `raster:${id}`),
            ...Array.from(Store.state.visibleVectorLayerIds, (id) => `vector:${id}`),
        ];

        if (!viewport && selectedFeatures.length === 0 && activeLayers.length === 0) {
            return null;
        }

        return {
            viewport,
            selected_features: selectedFeatures,
            active_layers: activeLayers,
            extra: {
                target_id: String(targetId),
                target_data_type: dataType,
                active_project_id: Store.state.activeProject?.id ?? null,
                active_vector_layer_id: Store.state.activeVectorLayerId ?? null,
            },
        };
    }

    _collectViewport() {
        const map = this.app.mapEngine?.map || this.app.mapEngine;
        if (!map?.getCenter || !map?.getBounds || !map?.getZoom) {
            return null;
        }

        const center = map.getCenter();
        const bounds = map.getBounds();

        return {
            zoom: map.getZoom(),
            center_lng: center.lng,
            center_lat: center.lat,
            bbox: [
                bounds.getWest(),
                bounds.getSouth(),
                bounds.getEast(),
                bounds.getNorth(),
            ],
        };
    }

    _collectSelectedFeatures() {
        const selectedId = Store.state.selectedFeatureId;
        if (!selectedId) return [];

        const features = Store.state.currentFeatures?.features ?? [];
        const selectedFeature = features.find((feature) => {
            const candidateId = feature?.id
                ?? feature?.properties?.id
                ?? feature?.properties?.feature_id;
            return String(candidateId) === String(selectedId);
        });

        if (!selectedFeature) return [];

        return [{
            feature_id: String(
                selectedFeature.id
                ?? selectedFeature.properties?.id
                ?? selectedFeature.properties?.feature_id
                ?? selectedId
            ),
            layer_id: Store.state.activeVectorLayerId ?? null,
            geometry_type: selectedFeature.geometry?.type ?? null,
            geometry: selectedFeature.geometry ?? null,
            properties: this._trimFeatureProperties(selectedFeature.properties),
        }];
    }

    _trimFeatureProperties(properties = {}) {
        return Object.fromEntries(Object.entries(properties).slice(0, 10));
    }

    _escapeHTML(value = '') {
        return String(value).replace(/[&<>"']/g, (char) => ({
            '&': '&amp;',
            '<': '&lt;',
            '>': '&gt;',
            '"': '&quot;',
            "'": '&#39;',
        }[char]));
    }

    _createSessionId() {
        if (globalThis.crypto?.randomUUID) {
            return globalThis.crypto.randomUUID();
        }

        return `ai-${Date.now()}-${Math.random().toString(16).slice(2)}`;
    }

    _createMessageId() {
        return `msg-${Date.now()}-${Math.random().toString(16).slice(2)}`;
    }

    _setLoading(isLoading) {
        this._loadingDepth = isLoading
            ? this._loadingDepth + 1
            : Math.max(0, this._loadingDepth - 1);
        const active = this._loadingDepth > 0;
        const btn = document.getElementById('ai-execute-btn');
        const spinner = document.getElementById('ai-spinner');
        if (btn) btn.disabled = active;
        if (spinner) spinner.classList.toggle('hidden', !active);
    }

    _setFunctionLoading(isLoading) {
        const btn = document.getElementById('ai-function-run-btn');
        if (!btn) return;
        btn.disabled = isLoading;
        btn.textContent = isLoading ? 'Running...' : 'Run Function';
    }

    _clearResult() {
        const resultEl = document.getElementById('ai-result-content');
        if (resultEl) { resultEl.textContent = ''; resultEl.classList.remove('ai-result-markdown'); }
        this._clearTransientMessages();
        document.getElementById('ai-result-section')?.classList.add('hidden');
        document.getElementById('ai-confirm-section')?.classList.add('hidden');
        document.getElementById('ai-download-btn')?.classList.add('hidden');
    }

    _clearTransientMessages() {
        document.getElementById('ai-error-msg')?.classList.add('hidden');
        document.getElementById('ai-success-msg')?.classList.add('hidden');
        document.getElementById('ai-confirm-section')?.classList.add('hidden');
        document.getElementById('ai-download-btn')?.classList.add('hidden');
    }

    _showError(msg) {
        const el = document.getElementById('ai-error-msg');
        if (el) { el.textContent = t(msg); el.classList.remove('hidden'); }
    }

    _showSuccess(msg) {
        const el = document.getElementById('ai-success-msg');
        if (el) { el.textContent = t(msg); el.classList.remove('hidden'); }
    }

    _resetState() {
        this._pendingPayload = null;
        this._pendingResult  = null;
        document.getElementById('ai-error-msg')?.classList.add('hidden');
        document.getElementById('ai-success-msg')?.classList.add('hidden');
    }

    /**
     * English → English Store → EnglishRefreshSidebarEnglish
     *
     * Raster：English #raster-list English
     * Vector：English #vector-list-container English
     *
     * @param {'raster'|'vector'} dataType
     */
    async _applyWorkspaceImports(imports) {
        const vectors = imports.filter(item => item.data_type === 'vector' && item.project_id && item.layer_id);
        const rasters = imports.filter(item => item.data_type === 'raster' && item.id != null);
        if (rasters.length) {
            await this._refreshSidebar('raster');
            for (const item of rasters) {
                if (!Store.state.activeLayerIds.has(item.id)) await this.app.mapController?.toggleLayer(item.id);
            }
        }
        if (!vectors.length) return;
        await this.app.project?.refreshProjects();
        const projectId = vectors.at(-1).project_id;
        await this.app.project?.handleSelectProject(projectId);
        for (const item of vectors.filter(value => value.project_id === projectId)) {
            if (!Store.state.visibleVectorLayerIds.has(item.layer_id)) {
                await this.app.mapController?.toggleVectorLayer(item.layer_id);
            }
        }
        const last = vectors.at(-1);
        if (Store.state.activeVectorLayerId !== last.layer_id) {
            Store.setActiveVectorLayer(last.layer_id);
            await this.app.mapController?.fetchViewportFeatures?.();
        }
        if (Array.isArray(last.bbox) && last.bbox.length === 4 && last.bbox.every(Number.isFinite)) {
            this.app.mapEngine?.fitLayer?.(last.layer_id, last.bbox);
        }
        this.app.mapController?.updateUI();
    }

    async _refreshSidebar(dataType) {
        if (dataType === 'raster') {
            await this.app.raster?.refreshData();
            if (this.app.mapController?.updateUI) {
                this.app.mapController.updateUI();
                return;
            }
            const rasterListEl = document.getElementById('raster-list');
            if (rasterListEl) {
                rasterListEl.innerHTML = SidebarComponent.renderRasterSection(
                    Store.state.rasters,
                    Store.state.activeLayerIds,
                    Store.state.loadingIds
                );
            }

        } else {
            await this.app.project?.refreshProjects();
            if (this.app.mapController?.updateUI) {
                this.app.mapController.updateUI();
                return;
            }
            const vectorContainerEl = document.getElementById('vector-list-container');
            if (vectorContainerEl) {
                vectorContainerEl.innerHTML = SidebarComponent.renderVectorSection(
                    Store.state.projects,
                    Store.state.activeProject,
                    Store.state.vectorLayers,
                    Store.state.activeVectorLayerId,
                    Store.state.visibleVectorLayerIds
                );
            }
        }
    }
}
