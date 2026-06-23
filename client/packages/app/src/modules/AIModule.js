import { AIAPI } from '../api/ai.js';
import { Store } from '../store/index.js';
import { ModalComponent } from '../../../ui/src/components/Modal.js';
import { SidebarComponent } from '../../../ui/src/components/Sidebar.js';
import { getLanguage, t } from '../i18n/index.js';

const AGENT_ATTACHMENT_LIMIT = 6;
const AGENT_TEXT_EXCERPT_CHARS = 12000;
const AGENT_TEXT_FILE_BYTES = 512 * 1024;
const AGENT_IMAGE_FILE_BYTES = 3 * 1024 * 1024;
const AGENT_RESPONSE_REVEAL_DELAY_MS = 90;

export class AIModule {
    constructor(app) {
        this.app = app;

        // English AI English
        // English"English vs English"English
        this._pendingPayload = null;
        this._pendingResult  = null;
        this._sessionId = this._createSessionId();
        this._agentConversation = [];
        this._functionCatalog = [];
        this._selectedFunction = null;
        this._functionsLoading = false;
        this._functionCatalogError = '';
        this._conversationArchives = [];
        this._archivePanelOpen = false;
        this._archivesLoading = false;
        this._agentAttachments = [];
        this._agentQueueTail = Promise.resolve();
        this._agentQueueDepth = 0;
        this._loadingDepth = 0;
    }

    openModal() {
        const modal = document.getElementById('ai-modal');
        if (!modal) return;

        // English Store English/VectorEnglish
        const rasters = Store.getRasters();
        const Layers = Store.getVectorLayers();
        document.getElementById('ai-target-select').innerHTML =
            ModalComponent.renderAITargetOptions(rasters, Layers);
        const languageSelect = document.getElementById('ai-language-select');
        if (languageSelect) languageSelect.value = getLanguage();

        this._bindModalEvents();
        this._syncDataTypeWithTarget();
        this._syncModeUI();
        this._renderFunctionCatalog();
        void this.loadFunctionCatalog();
        void this.loadConversationArchives();

        modal.classList.remove('hidden');
    }

    closeModal() {
        document.getElementById('ai-modal')?.classList.add('hidden');
        this._resetState();
    }

    async execute() {
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
        if (reportEl) reportEl.textContent = result.report;

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

    async _runAgent(payload) {
        const promptInput = document.getElementById('ai-prompt-input');
        const userMessage = {
            id: this._createMessageId(),
            role: 'user',
            content: payload.user_prompt,
            attachments: this._displayAttachments(payload.attachments ?? []),
        };
        const assistantMessage = {
            id: this._createMessageId(),
            role: 'assistant',
            content: '',
            visibleContent: '',
            pending: true,
            pendingLabel: this._agentQueueDepth > 0 ? 'Queued' : 'Waiting for AI response',
            steps: [],
            streaming: false,
        };

        this._agentConversation.push(userMessage, assistantMessage);
        this._renderAgentConversation();
        if (promptInput) promptInput.value = '';
        this._clearAgentAttachments();

        this._agentQueueDepth += 1;
        const runRequest = async () => {
            assistantMessage.pendingLabel = 'Waiting for AI response';
            this._renderAgentConversation();

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
                assistantMessage.steps = result.steps ?? [];
                assistantMessage.artifacts = this._displayArtifacts(result.artifacts ?? []);
                await this._revealAgentResponse(assistantMessage, result.answer ?? '');
                if ((result.used_tools ?? []).some(name => name !== 'clip_vector_by_raster')) {
                    await this._refreshSidebar('raster');
                }
            } finally {
                this._agentQueueDepth = Math.max(0, this._agentQueueDepth - 1);
            }
        };

        const task = this._agentQueueTail.catch(() => {}).then(runRequest);
        this._agentQueueTail = task.catch(() => {});
        return task;
    }

    async _revealAgentResponse(message, answer) {
        const chunks = this._splitResponseIntoRevealChunks(answer);
        message.content = answer;
        message.visibleContent = '';
        message.streaming = true;

        if (!chunks.length) {
            message.visibleContent = '';
            message.streaming = false;
            this._renderAgentConversation();
            return;
        }

        for (const chunk of chunks) {
            message.visibleContent += chunk;
            this._renderAgentConversation();
            await this._delayAgentReveal();
        }

        message.visibleContent = answer;
        message.streaming = false;
        this._renderAgentConversation();
    }

    _splitResponseIntoRevealChunks(text = '') {
        const value = String(text);
        if (!value) return [];

        const chunks = [];
        const sentenceEndings = new Set(['.', '!', '?', '\u3002', '\uff01', '\uff1f']);
        const closingMarks = new Set([
            '"', "'", ')', ']', '}', '*', '_', '~', '`',
            '\u201d', '\u2019', '\uff09', '\u3011', '\u300b', '\u300d', '\u300f',
        ]);
        let start = 0;

        const pushChunk = (end) => {
            if (end > start) chunks.push(value.slice(start, end));
            start = end;
        };

        for (let i = 0; i < value.length; i += 1) {
            if (value[i] === '\n' && value[i + 1] === '\n') {
                let end = i + 2;
                while (value[end] === '\n') end += 1;
                pushChunk(end);
                i = end - 1;
                continue;
            }

            if (!sentenceEndings.has(value[i])) continue;

            let end = i + 1;
            while (sentenceEndings.has(value[end])) end += 1;
            while (closingMarks.has(value[end])) end += 1;

            if (end < value.length && !/\s/.test(value[end])) continue;
            while (end < value.length && /\s/.test(value[end])) end += 1;

            pushChunk(end);
        }

        pushChunk(value.length);
        return chunks.length ? chunks : [value];
    }

    _delayAgentReveal() {
        return new Promise(resolve => setTimeout(resolve, AGENT_RESPONSE_REVEAL_DELAY_MS));
    }

    startNewAgentChat() {
        this._sessionId = this._createSessionId();
        this._agentConversation = [];
        this._pendingPayload = null;
        this._pendingResult = null;
        this._clearAgentAttachments();
        this._clearTransientMessages();
        this._renderAgentConversation();
        document.getElementById('ai-prompt-input')?.focus();
    }

    async archiveAgentConversation() {
        if (!this._agentConversation.length) {
            this._showError('No agent conversation to archive yet.');
            return;
        }

        try {
            const title = this._agentConversation.find(message => message.role === 'user')?.content?.slice(0, 80)
                || `Agent chat ${new Date().toLocaleString()}`;
            await AIAPI.archiveConversation({
                session_id: this._sessionId,
                title,
                messages: this._archiveableAgentMessages(),
                metadata: { source: 'agent-ui' },
            });
            this._showSuccess('Conversation archived.');
            await this.loadConversationArchives({ force: true });
            this._archivePanelOpen = true;
            this._renderArchivePanel();
        } catch (err) {
            this._showError(err.message);
        }
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
        } catch (err) {
            console.warn('[AIModule] failed to load conversation archives:', err);
        } finally {
            this._archivesLoading = false;
            this._renderArchivePanel();
        }
    }

    async toggleArchivePanel() {
        this._archivePanelOpen = !this._archivePanelOpen;
        this._renderArchivePanel();
        if (this._archivePanelOpen) {
            await this.loadConversationArchives({ force: true });
        }
    }

    async loadConversationArchive(archiveId) {
        if (!archiveId) return;
        try {
            const result = await AIAPI.getConversation(archiveId);
            const archive = result.conversation;
            const sessionId = archive.session_id || archive.archive_id || this._createSessionId();
            await AIAPI.restoreConversation(archiveId, sessionId);
            this._sessionId = sessionId;
            this._agentConversation = (archive.messages ?? [])
                .filter(message => ['user', 'assistant'].includes(message.role))
                .map(message => ({
                    role: message.role,
                    content: message.content,
                    steps: Array.isArray(message.steps) ? message.steps : [],
                    attachments: Array.isArray(message.attachments)
                        ? this._displayAttachments(message.attachments)
                        : [],
                    artifacts: Array.isArray(message.artifacts)
                        ? this._displayArtifacts(message.artifacts)
                        : [],
                }));
            this._archivePanelOpen = false;
            this._renderArchivePanel();
            this._renderAgentConversation();
            this._showSuccess('Conversation restored.');
        } catch (err) {
            this._showError(err.message);
        }
    }

    async deleteConversationArchive(archiveId) {
        if (!archiveId) return;
        try {
            await AIAPI.deleteConversation(archiveId);
            this._conversationArchives = this._conversationArchives
                .filter(item => item.archive_id !== archiveId);
            this._renderArchivePanel();
            this._showSuccess('Conversation archive deleted.');
        } catch (err) {
            this._showError(err.message);
        }
    }

    async clearConversationArchives() {
        if (!this._conversationArchives.length) {
            this._showSuccess('No saved conversations to clear.');
            return;
        }
        if (!window.confirm('Clear all saved AI conversation archives?')) return;

        try {
            const result = await AIAPI.clearConversations();
            this._conversationArchives = [];
            this._renderArchivePanel();
            this._showSuccess(`Cleared ${result.deleted ?? 0} archived conversation(s).`);
        } catch (err) {
            this._showError(err.message);
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

    selectFunction(name) {
        const fn = this._functionCatalog.find(item => item.name === name);
        if (!fn) return;

        this._selectedFunction = fn;
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

        this._bindAgentAttachmentEvents();
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
        const mode = document.getElementById('ai-mode-select')?.value ?? 'analyze';
        const isAgent = mode === 'agent';
        const promptInput = document.getElementById('ai-prompt-input');
        const promptBlock = promptInput?.closest('.space-y-1\\.5');
        const agentPanel = document.getElementById('ai-agent-panel');
        const attachmentControls = document.getElementById('ai-agent-attachment-controls');
        const executeLabel = document.getElementById('ai-execute-label')
            ?? document.querySelector('#ai-execute-btn span:last-child');

        agentPanel?.classList.toggle('hidden', !isAgent);
        attachmentControls?.classList.toggle('hidden', !isAgent);
        document.getElementById('ai-function-panel')?.classList.toggle('hidden', isAgent);

        if (isAgent) {
            if (agentPanel && promptBlock?.parentElement && agentPanel.nextElementSibling !== promptBlock) {
                promptBlock.parentElement.insertBefore(agentPanel, promptBlock);
            }
            document.getElementById('ai-result-section')?.classList.add('hidden');
            document.getElementById('ai-confirm-section')?.classList.add('hidden');
            if (promptInput) promptInput.rows = 2;
            if (executeLabel) executeLabel.textContent = 'Send Message';
            this._renderAgentConversation();
            this._renderArchivePanel();
            this._renderAgentAttachments();
        } else {
            document.getElementById('ai-agent-panel')?.classList.add('hidden');
            document.getElementById('ai-agent-attachment-controls')?.classList.add('hidden');
            if (promptInput) promptInput.rows = 3;
            if (executeLabel) executeLabel.textContent = 'Run AI Task';
        }
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
        const kind = file.type?.startsWith('image/') ? 'image' : this._isTextAttachment(file) ? 'text' : 'file';
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

        messagesEl.innerHTML = this._agentConversation.length
            ? this._agentConversation.map(message => this._renderAgentMessage(message)).join('')
            : '<div class="h-full"></div>';

        this._scrollAgentChatToBottom();
    }

    _renderAgentAttachments() {
        const list = document.getElementById('ai-agent-attachment-list');
        if (!list) return;

        list.innerHTML = this._agentAttachments.length
            ? this._agentAttachments.map(attachment => this._renderAttachmentChip(attachment, { removable: true })).join('')
            : '';
    }

    _renderArchivePanel() {
        const panel = document.getElementById('ai-agent-archive-panel');
        const list = document.getElementById('ai-agent-archive-list');
        if (!panel || !list) return;

        panel.classList.toggle('hidden', !this._archivePanelOpen);
        if (!this._archivePanelOpen) return;

        if (this._archivesLoading) {
            list.innerHTML = '<div class="py-3 text-center text-[10px] font-bold uppercase tracking-widest text-slate-400">Loading archives...</div>';
            return;
        }

        if (!this._conversationArchives.length) {
            list.innerHTML = '<div class="py-3 text-center text-[10px] font-bold uppercase tracking-widest text-slate-400">No archived chats</div>';
            return;
        }

        list.innerHTML = this._conversationArchives.map((archive) => {
            const title = this._escapeHTML(archive.title || 'Agent conversation');
            const date = archive.updated_at ? new Date(archive.updated_at).toLocaleString() : '';
            const id = this._escapeHTML(archive.archive_id);
            return `
                <div class="flex items-center gap-2 rounded-xl border border-slate-200 bg-slate-50 px-3 py-2">
                    <button type="button" onclick="RS.aiLoadConversationArchive('${id}')"
                        class="min-w-0 flex-1 text-left">
                        <div class="truncate text-[11px] font-bold text-slate-700">${title}</div>
                        <div class="mt-0.5 truncate text-[9px] font-mono text-slate-400">${this._escapeHTML(date)} · ${archive.message_count ?? 0} messages</div>
                    </button>
                    <button type="button" onclick="RS.aiDeleteConversationArchive('${id}')"
                        title="Delete archive"
                        class="flex h-7 w-7 shrink-0 items-center justify-center rounded-lg text-slate-400 hover:bg-red-50 hover:text-red-500">
                        <svg class="h-3.5 w-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862A2 2 0 015.867 19.142L5 7m5 4v6m4-6v6M4 7h16m-6-3h-4"/>
                        </svg>
                    </button>
                </div>`;
        }).join('');
    }

    _renderAgentMessage(message) {
        const isUser = message.role === 'user';
        const wrapperClass = isUser ? 'justify-end' : 'justify-start';
        const bubbleClass = isUser
            ? 'bg-slate-900 text-white'
            : message.error
                ? 'border border-red-100 bg-red-50 text-red-700 shadow-sm'
                : 'border border-slate-200 bg-white text-slate-700 shadow-sm';
        const avatar = isUser
            ? ''
            : `<div class="mt-1 flex h-7 w-7 shrink-0 items-center justify-center rounded-lg bg-violet-100 text-[9px] font-black text-violet-700">AI</div>`;
        const trace = this._renderAgentToolTrace(message.steps ?? []);
        const attachments = this._renderMessageAttachments(message.attachments ?? [], isUser);
        const artifacts = this._renderGeneratedArtifacts(message.artifacts ?? []);
        const content = message.pending
            ? this._renderPendingAgentMessage(message)
            : isUser
                ? `<div class="break-words">${this._renderMarkdown(message.content)}</div>`
                : this._renderAgentMarkdownOutput(message);

        return `
            <div class="flex ${wrapperClass} gap-2">
                ${avatar}
                <div class="max-w-[82%] rounded-2xl px-4 py-3 text-xs leading-relaxed ${bubbleClass}">
                    ${content}
                    ${attachments}
                    ${artifacts}
                    ${trace}
                </div>
            </div>`;
    }

    _renderPendingAgentMessage(message = {}) {
        const label = this._escapeHTML(message.pendingLabel ?? 'Waiting for AI response');
        return `
            <div class="flex items-center gap-2 text-slate-500">
                <span class="font-bold">${label}</span>
                <span class="flex gap-1">
                    <span class="h-1.5 w-1.5 animate-pulse rounded-full bg-violet-400"></span>
                    <span class="h-1.5 w-1.5 animate-pulse rounded-full bg-violet-400" style="animation-delay:120ms"></span>
                    <span class="h-1.5 w-1.5 animate-pulse rounded-full bg-violet-400" style="animation-delay:240ms"></span>
                </span>
            </div>`;
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
        const lines = String(markdown).replace(/\r\n/g, '\n').split('\n');
        const blocks = [];
        let paragraph = [];
        let i = 0;

        const flushParagraph = () => {
            if (!paragraph.length) return;
            blocks.push(`<p class="mb-2 last:mb-0">${this._renderInlineMarkdown(paragraph.join(' '))}</p>`);
            paragraph = [];
        };

        while (i < lines.length) {
            const rawLine = lines[i];
            const line = rawLine.trim();

            if (!line) {
                flushParagraph();
                i += 1;
                continue;
            }

            if (line.startsWith('```')) {
                flushParagraph();
                const language = line.slice(3).trim();
                const code = [];
                i += 1;
                while (i < lines.length && !lines[i].trim().startsWith('```')) {
                    code.push(lines[i]);
                    i += 1;
                }
                if (i < lines.length) i += 1;
                blocks.push(this._renderCodeBlock(code.join('\n'), language));
                continue;
            }

            const heading = line.match(/^(#{1,4})\s+(.+)$/);
            if (heading) {
                flushParagraph();
                const level = heading[1].length;
                const size = level === 1 ? 'text-sm' : 'text-xs';
                blocks.push(`<h${level} class="mb-2 mt-3 first:mt-0 font-black ${size} text-slate-800">${this._renderInlineMarkdown(heading[2])}</h${level}>`);
                i += 1;
                continue;
            }

            if (this._isMarkdownTableStart(lines, i)) {
                flushParagraph();
                const tableLines = [lines[i], lines[i + 1]];
                i += 2;
                while (i < lines.length && lines[i].includes('|') && lines[i].trim()) {
                    tableLines.push(lines[i]);
                    i += 1;
                }
                blocks.push(this._renderMarkdownTable(tableLines));
                continue;
            }

            if (/^[-*+]\s+/.test(line)) {
                flushParagraph();
                const items = [];
                while (i < lines.length && /^[-*+]\s+/.test(lines[i].trim())) {
                    items.push(lines[i].trim().replace(/^[-*+]\s+/, ''));
                    i += 1;
                }
                blocks.push(`<ul class="mb-2 ml-4 list-disc space-y-1">${items.map(item => `<li>${this._renderInlineMarkdown(item)}</li>`).join('')}</ul>`);
                continue;
            }

            if (/^\d+\.\s+/.test(line)) {
                flushParagraph();
                const items = [];
                while (i < lines.length && /^\d+\.\s+/.test(lines[i].trim())) {
                    items.push(lines[i].trim().replace(/^\d+\.\s+/, ''));
                    i += 1;
                }
                blocks.push(`<ol class="mb-2 ml-4 list-decimal space-y-1">${items.map(item => `<li>${this._renderInlineMarkdown(item)}</li>`).join('')}</ol>`);
                continue;
            }

            if (line.startsWith('>')) {
                flushParagraph();
                const quote = [];
                while (i < lines.length && lines[i].trim().startsWith('>')) {
                    quote.push(lines[i].trim().replace(/^>\s?/, ''));
                    i += 1;
                }
                blocks.push(`<blockquote class="mb-2 border-l-2 border-violet-200 pl-3 text-slate-500">${this._renderInlineMarkdown(quote.join(' '))}</blockquote>`);
                continue;
            }

            paragraph.push(line);
            i += 1;
        }

        flushParagraph();
        return `<div class="ai-markdown space-y-1">${blocks.join('') || '<p class="mb-0"></p>'}</div>`;
    }

    _renderInlineMarkdown(text = '') {
        const codeTokens = [];
        let rendered = this._escapeHTML(text).replace(/`([^`]+)`/g, (_match, code) => {
            const token = `@@CODE_${codeTokens.length}@@`;
            codeTokens.push(`<code class="rounded bg-slate-100 px-1 py-0.5 font-mono text-[11px] text-slate-700">${code}</code>`);
            return token;
        });

        rendered = rendered.replace(/\[([^\]]+)\]\(([^)]+)\)/g, (_match, label, url) => {
            const href = url.replace(/&amp;/g, '&').trim();
            if (!this._isSafeMarkdownUrl(href)) return label;
            return `<a href="${this._escapeHTML(href)}" target="_blank" rel="noopener noreferrer" class="font-bold text-violet-600 underline decoration-violet-200 underline-offset-2">${label}</a>`;
        });

        rendered = rendered
            .replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>')
            .replace(/__([^_]+)__/g, '<strong>$1</strong>')
            .replace(/(^|[\s(])\*([^*\n]+)\*/g, '$1<em>$2</em>')
            .replace(/(^|[\s(])_([^_\n]+)_/g, '$1<em>$2</em>');

        codeTokens.forEach((html, index) => {
            rendered = rendered.replace(`@@CODE_${index}@@`, html);
        });
        return rendered;
    }

    _renderCodeBlock(code = '', language = '') {
        const lang = language ? `<div class="border-b border-slate-800 px-3 py-1 text-[9px] font-black uppercase tracking-widest text-slate-400">${this._escapeHTML(language)}</div>` : '';
        return `
            <div class="my-3 overflow-hidden rounded-xl bg-slate-950 text-slate-100">
                ${lang}
                <pre class="overflow-x-auto p-3 text-[11px] leading-relaxed"><code>${this._escapeHTML(code)}</code></pre>
            </div>`;
    }

    _isMarkdownTableStart(lines, index) {
        const current = lines[index]?.trim() ?? '';
        const next = lines[index + 1]?.trim() ?? '';
        return current.includes('|') && /^\|?\s*:?-{3,}:?\s*(\|\s*:?-{3,}:?\s*)+\|?$/.test(next);
    }

    _renderMarkdownTable(tableLines) {
        const header = this._splitMarkdownTableRow(tableLines[0]);
        const rows = tableLines.slice(2).map(line => this._splitMarkdownTableRow(line));
        return `
            <div class="my-3 overflow-x-auto rounded-xl border border-slate-200">
                <table class="min-w-full border-collapse text-left text-[11px]">
                    <thead class="bg-slate-100 text-slate-600">
                        <tr>${header.map(cell => `<th class="border-b border-slate-200 px-3 py-2 font-black">${this._renderInlineMarkdown(cell)}</th>`).join('')}</tr>
                    </thead>
                    <tbody>
                        ${rows.map(row => `<tr class="odd:bg-white even:bg-slate-50">${row.map(cell => `<td class="border-t border-slate-100 px-3 py-2 align-top">${this._renderInlineMarkdown(cell)}</td>`).join('')}</tr>`).join('')}
                    </tbody>
                </table>
            </div>`;
    }

    _splitMarkdownTableRow(row = '') {
        return row.trim().replace(/^\|/, '').replace(/\|$/, '').split('|').map(cell => cell.trim());
    }

    _isSafeMarkdownUrl(url = '') {
        if (url.startsWith('#') || url.startsWith('/')) return true;
        try {
            const parsed = new URL(url);
            return ['http:', 'https:', 'mailto:'].includes(parsed.protocol);
        } catch (_err) {
            return false;
        }
    }

    _renderAgentToolTrace(steps) {
        if (!steps.length) return '';

        const items = steps.map((step) => {
            const isSuccess = step.status === 'success';
            const statusClass = isSuccess
                ? 'bg-emerald-50 text-emerald-700 border-emerald-100'
                : 'bg-red-50 text-red-700 border-red-100';
            const statusText = isSuccess ? 'ok' : 'error';
            const error = step.error
                ? `<div class="mt-1 text-[10px] leading-relaxed text-red-600">${this._escapeHTML(step.error)}</div>`
                : '';

            return `
                <div class="rounded-xl border border-slate-100 bg-slate-50 px-3 py-2">
                    <div class="flex items-center justify-between gap-3">
                        <span class="truncate font-mono text-[10px] font-bold text-slate-500">${this._escapeHTML(step.name)}</span>
                        <span class="shrink-0 rounded-full border px-2 py-0.5 text-[9px] font-black uppercase tracking-widest ${statusClass}">${statusText}</span>
                    </div>
                    ${error}
                </div>`;
        }).join('');

        return `<div class="mt-3 space-y-1.5 border-t border-slate-100 pt-2">${items}</div>`;
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
        if (resultEl) resultEl.textContent = '';
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
        if (el) { el.textContent = msg; el.classList.remove('hidden'); }
    }

    _showSuccess(msg) {
        const el = document.getElementById('ai-success-msg');
        if (el) { el.textContent = msg; el.classList.remove('hidden'); }
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
